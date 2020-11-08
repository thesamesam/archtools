import socket
import json
import subprocess
import os
import signal
from rq import get_current_job


def kill():
	print("Killing tatt (in third)")
	process = get_current_job().meta['bug_handler'].process
	if process and hasattr(process, 'terminate'):
		process.terminate()
		process.kill()


# test_bug() is the entry point from rq
def test_bug(bug, num, queue, atoms):
	signal.signal(signal.SIGRTMIN, kill)
	signal.signal(signal.SIGINT, kill)
	signal.signal(signal.SIGTERM, kill)

	# Tag this job with our IP
	# TODO: Include hostname?
	job = get_current_job()
	job.meta['handled_by'] = socket.gethostname()
	job.meta['bug_handler'] = BugHandler(bug, num, queue, atoms)
	job.save_meta()

	# Just some tiny debugging output
	print("Testing {0}".format(bug))

	# Actually do some work now
	try:
		job.meta['bug_handler'].start_working()
	except Exception as e:
		process = job.meta['bug_handler'].process
		if process and hasattr(process, 'terminate'):
			process.terminate()
			process.kill()
		raise e


class BugHandler:
	def __init__(self, bug, num, queue, atoms):
		self.bug = bug
		self.num = num
		self.queue = queue
		self.atoms = atoms
		self.process = None

	def oneshot_msg(self, num, message):
		# Send a one-off message to IRC via Irker
		# Irker configuration
		irker_listener = ("127.0.0.1", 6659)
		irker_spigot   = "irc://irc.freenode.net:6667/##test-arch-simpleworker"
		message = "\x0314[{0}]: \x0305bug #{1}\x0F - {2}".format(self.queue, num, message)

		# See https://manpages.debian.org/testing/irker/irkerd.8.en.html
		json_msg = json.JSONEncoder().encode(
			{"to": irker_spigot,
			 "privmsg": message}
		)

		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.sendto(json_msg.encode("utf8"), irker_listener)
		sock.close()

	def start_working(self):
		num = self.num
		print("[bug #{0}] starting".format(num))
		print("[bug #{0}] has atoms:".format(num))
		print(self.atoms)

		self.oneshot_msg(num, "\x16arch '{0}' starting work\x0F".format(self.queue))

		count = 0
		for atom in self.atoms.split("\r\n"):
			if count > 4:
				self.oneshot_msg(num, "... truncated list")
				break

			name = atom.split(" ")[0].lstrip('=~<>')
			if name:
				self.oneshot_msg(num, "atom <\x02{0}\x02>".format(name))
				count += 1

			# Useful
			tatt_base = "{0}-{1}".format(num, self.queue)

		try:
			# Let's kick off tatt
			# First, tatt must generate the scripts
			print("[bug #{0}] running tatt to generate scripts".format(num))
			self.process = subprocess.run(
					"/usr/bin/tatt -b {0} -j {1}".format(num, tatt_base).split(" "),
							  stdout=subprocess.DEVNULL, preexec_fn=os.setpgrp)

			# Let's see if the scripts exist
			if not os.path.isfile("{0}-useflags.sh".format(tatt_base)):
				print("[bug #{0}] useflags.sh not found; skipping".format(num))
				return

			# Run useflags.sh
			print("[bug #{0}] running useflags.sh".format(num))
			self.oneshot_msg(num, "\x0314running useflags.sh\x0F")
			self.process = subprocess.run("./{0}-useflags.sh".format(tatt_base),
										  stdout=subprocess.DEVNULL, preexec_fn=os.setpgrp)

			fails_use = self.parse_report(num, tatt_base)

			# Sometimes run rdeps (they don't always exist)
			rdeps_path = "{0}-rdeps.sh".format(tatt_base)
			if os.path.isfile(rdeps_path):
				print("[bug #{0}] running rdeps.sh".format(num))
				self.oneshot_msg(num, "\x0314running rdeps.sh\x0F")
				self.process = subprocess.run("./{0}".format(rdeps_path),
											  stdout=subprocess.DEVNULL, preexec_fn=os.setpgrp)
				fails_rdep = self.parse_report(num, tatt_base)
			else:
				print("[bug #{0}] no rdeps.sh:".format(num))
				self.oneshot_msg(num, "\x0302no rdeps.sh\x0F")

			if fails_use > 0 or (fails_rdep and fails_rdep > 0):
				self.oneshot_msg(num, "\x0303\x16FINISHED - Good\x0F")
			else:
				self.oneshot_msg(num, "\x0304\x16FINISHED - Bad\x0F")

		except Exception as e:
			if self.process and hasattr(self.process, 'terminate'):
				self.process.terminate()
				raise

	def parse_report(self, num, tatt_base):
		report_path = tatt_base + ".report"

		part = ""
		res = {
				"lines": 0,
				"use_dep": 0,
				"test_dep": 0,
				"slot_conflict": 0,
				"blocked": 0,
				"use_comb": 0,
				"feat_test": 0,
				"other": 0,
		}

		with open(report_path, "r") as report:
			for line in report:
				line = lstrip(line)
				if "USE tests started" in line:
					part = "USE"
					continue

				if "revdep tests started" in line:
					part = "revdep"
					continue

				if part not in ["USE", "revdep"]:
					print("[bug #{0}] report file parsing failed".format(num))
					break

				if "succeeded" in line:
					res["lines"] += 1
				elif "USE dependencies not satisfied" in line:
					print("[bug #{0]}] USE deps not satisfied in {1}"
						  " phase".format(num, part))
					res["use_dep"] += 1
				elif "merging test dependencies" in line:
					print("[bug #{0}] failed to merge test dependencies"
						  " in {1} phase".format(num, part))
					res["test_dep"] += 1
				elif "slot conflict" in line:
					print("[bug #{0}] hit a slot conflict in {1}"
						  " phase".format(num, part))
					res["slot_conflict"] += 1
				elif "blocked" in line:
					print("[bug #{0}] hit a blocker in {1}"
						  " phase".format(num, part))
					res["blocked"] += 1
				elif "failed" in line:
					if line.startswith("USE"):
						reason = "USE combination"
						res["use_comb"] += 1
					elif line.startswith("FEATURES"):
						reason = "tests"
						res["feat_test"] += 1
					else:
						reason = "other reasons"
						res["other"] += 1
					print("[bug #{0}] failed for {2} in {1}"
						  " phase".format(num, part))

			if res["lines"] > 0:
				total_failure = (res["test_dep"] + res["slot_conflict"] +
								 res["other"] + res["blocked"])
				# success = res["lines"] - total_failure

				summary = ("[{0}] succeeded: {1}, test dep fail: {2}, "
						   "slot conflict: {3}, blocked: {4}, other:"
						   " {5}".format(part, res["lines"], res["test_dep"],
										 res["slot_conflict"],
										 res["blocked"], res["other"])
				)

				print("[bug #{0}] {1}".format(num, summary))
				self.oneshot_msg(num, "{0} test complete:".format(part))
				if total_failure > 0:
					self.oneshot_msg(num, "> succeeded: {0:>3},\x0304 failed: "
								"{1:>3}\x03".format(res["lines"], total_failure))
				else:
					self.oneshot_msg(num, ">\x0303 succeeded: {0:>3}\x03, failed: "
								"{1:>3}".format(res["lines"], total_failure))
				self.oneshot_msg(num, "> slot conflict: {0:>3}, blocker: "
								 "{1:>3}".format(res["slot_conflict"],
												 res["blocked"]))
				self.oneshot_msg(num, "> test dep fail: {0:>3}, other:  "
								 "{1:>3}".format(res["test_dep"],
												 res["other"]))

		os.rename(report_path, report_path + "." + part)

		return total_failure
