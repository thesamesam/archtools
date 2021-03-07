#!/usr/bin/env python3
import itertools
import time

from rq import Queue
from redis import Redis

from simpleworker import *
from deploy import *

# List of arches we have workers for
#arches = ["arm", "arm64", "amd64", "x86"]
arches = ["amd64", "arm", "arm64"]

# Skip bugs with these in there for now
bad_packages = ["mysql", "mariadb", "gcc", "binutils", \
		"firefox", "spidermonkey", "clang", "llvm", \
		"kernel", "chromium", "qemu", "psutil", \
		"sys-libs/db", "gevent", "glibc", "thunderbird"]

# Create a queue for each type of job possible here
# Combine arches with work type
keys = itertools.product(arches, ['stable', 'keywording'])
keys = ['-'.join(map(str, key)) for key in keys]

redis_connection = Redis(host='127.0.0.1', password='')
queues = dict.fromkeys(keys)
for key in queues.keys():
	print(key)
	queues[key] = Queue(key, connection=redis_connection)

wrangled_bugs = []

while True:
	# Indefinitely loop for bugs
	bugs = get_bugs().items()

	for num, bug in get_bugs().items():
		print("[bug #{0}] checking bug".format(num))

		if num in wrangled_bugs:
			continue

		# Checks for blocker bugs
		if not bug_ready(bug, num):
			continue

		for arch in arches:
			if arch in bug.cc:
				# Queue it up for this arch!
				queue_name = arch

				# Our queue names look like:
				# e.g. arm64-stable
				if bug.category == BugCategory.STABLEREQ:
					queue_name += "-stable"
				else:
					queue_name += "-keywording"

				queue = queues[queue_name]

				skip_job = False

				for bad_package in bad_packages:
					if bad_package in bug.atoms.split("\r\n"):
						print("Skipping atom matching {0}.format(bad_package))
						skip_job = True

				if skip_job:
					continue

				# Avoid duplicates
				if str(num) in queue.job_ids or num in queue.job_ids:
					print("[bug #{0}] already running on queue: {1}".format(num, queue_name))
					continue

				print("[bug #{0}] fed to queue: {1}".format(num, queue_name))
				queue.enqueue(test_bug, at_front=bug.security, job_timeout="4d", args=(bug, num, queue_name, bug.atoms))

		# Don't touch this bug in future
		wrangled_bugs.append(num)

	print("Sleeping for 2 hours...")
	time.sleep(60*2)
