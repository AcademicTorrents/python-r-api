

import academictorrents as at
import pickle
import gzip
import sys
import os
import time

print("Libraries imported, about to start a download")

filename = at.get("323a0048d87ca79b68f12a6350a57776b6a3b7fb")

print("About to open the file")

mnist = gzip.open(filename, 'rb')
train_set, validation_set, test_set = pickle.load(mnist)
mnist.close()
