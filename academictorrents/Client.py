
__author__ = 'alexisgallepe'

import time
import logging
import os
import requests
import json
import datetime
from queue import Queue
from . import PeersManager
from . import PeerSeeker
from . import PiecesManager
from . import Torrent
from . import Tracker
from . import HttpPeer
from . import utils


class Client(object):
    @classmethod
    def __init__(self, hash, torrent_dir):
        newpeersQueue = Queue()
        self.hash = hash
        self.torrent_dir = torrent_dir

        self.torrent = Torrent.Torrent(self.hash, self.torrent_dir)
        self.tracker = Tracker.Tracker(self.torrent, newpeersQueue)
        self.piecesManager = PiecesManager.PiecesManager(self.torrent)
        self.peerSeeker = PeerSeeker.PeerSeeker(newpeersQueue, self.torrent)
        self.peersManager = PeersManager.PeersManager(self.torrent, self.piecesManager)

        self.peersManager.start()
        logging.info("Peers-manager Started")

        self.peerSeeker.start()
        logging.info("Peer-seeker Started")

        self.piecesManager.start()
        logging.info("Pieces-manager Started")

        self.piecesManager.check_disk_pieces()

    def start(self):
        starting_size = self.check_percent_finished()
        new_size = starting_size
        old_size = 0
        while not self.piecesManager.are_pieces_completed():
            if len(self.peersManager.unchokedPeers) > 0:
                for piece in self.piecesManager.pieces:
                    if not piece.finished:
                        pieceIndex = piece.pieceIndex

                        peer = self.peersManager.getUnchokedPeer(pieceIndex)
                        if not peer:
                            continue

                        data = self.piecesManager.pieces[pieceIndex].getEmptyBlock()
                        if data:
                            index, offset, length = data
                            self.peersManager.requestNewPiece(peer, index, offset, length)

                        piece.isComplete()
                        self.reset_pending_blocks(piece)
            if len(self.peersManager.httpPeers) > 0:
                for httpPeer in self.peersManager.httpPeers:
                    pieces = httpPeer.get_pieces(self.piecesManager)
                    pieces_by_file = httpPeer.construct_pieces_by_file(pieces)  # set all those blocks to Pending
                    responses = httpPeer.request_ranges(pieces_by_file)
                    httpPeer.publish_responses(responses, pieces_by_file)

            new_size = self.check_percent_finished()
            if new_size == old_size:
                continue

            old_size = new_size
            print("# Peers:", len(self.peersManager.unchokedPeers), " # HTTPSeeds:", len(self.peersManager.httpPeers), " Completed: ", float((float(new_size) / self.torrent.totalLength)*100), "%")

            time.sleep(0.1)
        downloaded = new_size - starting_size
        remaining = self.torrent.totalLength - (starting_size + downloaded)
        self.tracker.stop_message(downloaded, remaining)
        self.peerSeeker.requestStop()
        self.peersManager.requestStop()

        if remaining == 0:
            utils.write_timestamp(self.hash)

        return self.torrent_dir + self.torrent.torrentFile['info']['name']

    def reset_pending_blocks(self, piece):
        for block in piece.blocks:
            if(int(time.time()) - block[3]) > 8 and block[0] == "Pending":
                block[0] = "Free"
                block[3] = 0

    def check_percent_finished(self):
        b = 0
        for i in range(self.piecesManager.numberOfPieces):
            for j in range(self.piecesManager.pieces[i].num_blocks):
                if self.piecesManager.pieces[i].blocks[j][0] == "Full":
                    b += len(self.piecesManager.pieces[i].blocks[j][2])
        return b
