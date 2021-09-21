#!/usr/bin/env python3
import bugzilla
import json
import os
import socket
import subprocess

from nattka.bugzilla import *

# TODO: List of 'bulky' packages, mark as slow box?

# Configuration
type = "kw"
arch = "arm64"
machine = "sam-box1"
bugzilla_url = "https://bugs.gentoo.org/"
bugzilla_api_key = ""

# Prefix to use for your personal tag
# We'll skip the bug if we see it,
# and set it when we start work on a bug.
# e.g. "sam: amd64"
skip_tag_prefix = "sam"

# Irker configuration
irker_listener = ("127.0.0.1", 6659)
irker_spigot = "irc://irc.freenode.net:6667/##test-arch-simpleworker"

# Setup Nattka


def get_bugs():
    nattka_bugzilla = NattkaBugzilla(
        api_url="{0}/rest".format(bugzilla_url), api_key=bugzilla_api_key
    )

    bugs = nattka_bugzilla.find_bugs(unresolved=True, sanity_check=[True])

    return bugs


def oneshot_msg(num, message):
    # Send a one-off message to IRC via Irker
    message = "[{0}]: bug #{1} - {2}".format(machine, num, message)

    # See https://manpages.debian.org/testing/irker/irkerd.8.en.html
    json_msg = json.JSONEncoder().encode({"to": irker_spigot, "privmsg": message})

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(json_msg.encode("utf8"), irker_listener)
    sock.close()


def bug_ready(bug, num):
    # Is our arch involved in this bug?
    # If not, skip it
    # if not "{0}@gentoo.org".format(arch) in bug.cc:
    #    print("[bug #{0}] not in CC; skipping".format(num))
    #    return False

    # Skip if any blocker bugs
    # TODO: this should maybe be more intelligent
    if bug.depends:
        print("[bug #{0}] blocker bugs; skipping".format(num))
        return False

    # Skip if we already have a report file for this bug
    tatt_base = "{0}-{1}-{2}".format(num, arch, machine)
    if os.path.isfile("{0}.report".format(tatt_base)):
        print("[bug #{0}] existing report file; skipping".format(num))
        return False

    return True


def reserve_bug(num):
    # Set a personal tag on the bug to indicate to other instances
    # that we're working on this bug.
    bzapi = bugzilla.Bugzilla(
        "{0}/xmlrpc.cgi".format(bugzilla_url), api_key=bugzilla_api_key
    )
    # bzbug = bzapi.getbug(num)
    bzapi.update_tags([num], "{0}: {1}".format(skip_tag_prefix, arch))


def start_working(bug, num):
    print("[bug #{0}] starting".format(num))
    oneshot_msg(num, "arch '{0}' starting work".format(arch))

    print("[bug #{0}] has atoms:".format(num))
    print(bug.atoms)
    print(bug)

    count = 0
    for atom in bug.atoms.split("\r\n"):
        if count > 4:
            oneshot_msg(num, "... truncated list")
            break

        name = atom.split(" ")[0]
        if name:
            oneshot_msg(num, "atom <{0}>".format(name))

        count += 1

    # Mark that we're working on this bug
    reserve_bug(num)

    # Useful
    tatt_base = "{0}-{1}-{2}".format(num, arch, machine)

    # Run useflags.sh
    oneshot_msg(num, "running useflags.sh")
    subprocess.run("./{0}-useflags.sh".format(tatt_base), stdout=subprocess.DEVNULL)

    # Sometimes run rdeps (they don't always exist)
    rdeps_path = "{0}-rdeps.sh".format(tatt_base)
    if os.path.isfile(rdeps_path):
        oneshot_msg(num, "running rdeps.sh")
        subprocess.run("./{0}".format(rdeps_path), stdout=subprocess.DEVNULL)
    else:
        oneshot_msg(num, "no rdeps.sh")

    parse_report(bug, num, tatt_base)


def parse_report(bug, num, tatt_base):
    report_path = tatt_base + ".report"

    part = ""
    results = {
        "USE": {
            "test_dep_failure": 0,
            "slot_conflict": 0,
            "blocked": 0,
            "failure": 0,
            "lines": 0,
        },
        "revdep": {
            "test_dep_failure": 0,
            "slot_conflict": 0,
            "blocked": 0,
            "failure": 0,
            "lines": 0,
        },
    }

    with open(report_path, "r") as report:
        for line in report.readlines():
            if "USE tests started" in line:
                part = "USE"
                continue

            if "revdep tests started" in line:
                part = "revdep"
                continue

            if part not in ["USE", "revdep"]:
                print("[bug #{0}] report file parsing failed".format(num))
                break

            results[part]["lines"] += 1

            # Assume we're in the "USE tests" part until we get
            # a line telling us we're not.
            if "merging test dependencies" in line:
                print(
                    "[bug #{0}] failed to merge test dependencies"
                    " in {1} phase".format(num, part)
                )
                results[part]["test_dep_failure"] += 1
            elif "slot conflict" in line:
                print(
                    "[bug #{0}] hit a slot conflict in {1}" " phase".format(num, part)
                )
                results[part]["slot_conflict"] += 1
            elif "blocked" in line:
                print("[bug #{0}] hit a blocker in {1}" " phase".format(num, part))
                results[part]["blocked"] += 1
            elif "failed" in line:
                print(
                    "[bug #{0}] failed for unknown reasons in {1}"
                    " phase".format(num, part)
                )
                results[part]["failure"] += 1

    for part in ["USE", "revdep"]:
        test_dep_failure = results[part]["test_dep_failure"]
        slot_conflict = results[part]["slot_conflict"]
        unknown_failure = results[part]["failure"]
        blocked = results[part]["blocked"]
        total_failure = test_dep_failure + slot_conflict + unknown_failure + blocked
        success = results[part]["lines"] - total_failure

        summary = (
            "[{0}] succeeded: {1}, test dep fail: {2},"
            "slot conflict: {3}, blocked: {4}, unknown:"
            " {5}".format(
                part, success, test_dep_failure, slot_conflict, blocked, unknown_failure
            )
        )

        if results[part]["lines"] > 0:
            print("[bug #{0}] {1}".format(num, summary))
            oneshot_msg(num, "{0} test complete:".format(part))
            oneshot_msg(
                num,
                "> succeeded: {0:>3}, failed: " "{1:>3}".format(success, total_failure),
            )
            oneshot_msg(
                num,
                "> slot conflict: {0:>3}, blocker: "
                "{1:>3}".format(slot_conflict, blocked),
            )
            oneshot_msg(
                num,
                "> test dep fail: {0:>3}, unknown: "
                "{1:>3}".format(test_dep_failure, unknown_failure),
            )


def worker_loop():
    for num, bug in get_bugs().items():
        print("[bug #{0}] checking bug".format(num))

        if not bug_ready(bug, num):
            continue

        if type == "stable":
            if bug.category != BugCategory.STABLEREQ:
                continue
        elif type == "kw":
            if bug.category != BugCategory.KEYWORDREQ:
                continue

        # Let's kick off tatt
        # First, tatt must generate the scripts
        subprocess.run(
            "tatt -b {0} -j {0}-{1}" "-{2}".format(num, arch, machine).split(),
            stdout=subprocess.DEVNULL,
        )

        # Let's see if the scripts exist
        tatt_base = "{0}-{1}-{2}".format(num, arch, machine)
        if not os.path.isfile("{0}-useflags.sh".format(tatt_base)):
            print("[bug #{0}] useflags.sh not found; skipping")
            continue

        # By this point, we should be good to proceed
        start_working(bug, num)


if __name__ == "__main__":
    try:
        worker_loop()
    except Exception as e:
        oneshot_msg("0", "croaking due to exception '{0}'".format(e))
        raise e
