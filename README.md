## archtools

A tool to help automate the Gentoo arch testing process.

### Tools

1. The `rq`-based queue system (the rq directory);

2. The 'classic' simpleworker script

### `rq` description

You will need:

- python-bugzilla
- dev-python/rq
- A Redis server running for the manager
- An instance of net-irc/irker for each worker (optional)

The `rq` system has two parts:

1. A manager (`manager.py`) which fetches jobs from Bugzilla
   and inserts them into various queues in Redis.
   
2. Workers who fetch jobs from the queues in Redis and
   execute them. They report success via IRC (optionally)
   and also dump successful bugs into a timestamped (daily)
   text file.

#### HOWTO:

1. Set up Redis on the manager and start it up. No other
   configuration needed.
   
   (If you are going to run Redis on a different host to
   the workers, you'll need to password protect Redis
   or use TLS certificate authentication. I recommend
   using one of these plus a firewall for safety.)

2. Edit `manager.py` and modify:
   * the `arches` variable as appropriate (to generate queues)
   
   * the `bad_packages` list depending on the capabilities
	 of the worker machines
 
3. Run `python manager.py`! The manager side needs the following
   files available:
   * `manager.py`
   * `simpleworker.py` (for now, this is temporary)
   * `deploy.py` (for serialisation)

4. On the client(s) side, make sure the following are available:
   * `deploy.py`
   * `worker.py`
   
5. Modify `worker.py` to be aware of your Redis setup.

6. Modify `deploy.py` for your IRC channel of choosing,
   if you're interested. Not required.

7. Run `python deploy.py $queue`. Replace `$queue` with
   e.g. `amd64-stable`.
   
   (You may wish to start Irker if you want IRC notifications.)
   
8. Wait for bugs to be tested. Check for files like:
   `good-bugs-2021-03-08` which contains a list of bugs
   which were successfully tested, along with the arch name.
   
   You can commit these using the `at-commit` script.

### simpleworker description

Currently, `simpleworker.py` will:

1. Grab any open bugs from Bugzilla for the given architecture, ignoring bugs with a sepcific tag used
to show e.g. another worker is processing this bug.

2. Run `tatt` on it to generate testing scripts.

3. Execute the aforementioned scripts.

4. Send a summary on IRC when a bug is finished, with information on success/failure

#### Example output

~~~~
[15:00:14]  <irker899> [sam-box1]: bug #730892 - arch 'arm64' starting work
[15:00:14]  <irker899> [sam-box1]: bug #730892 - atom <app-arch/innoextract>
[15:00:16]  <irker899> [sam-box1]: bug #730892 - running useflags.sh
[... here, the script is being run in the background to test USE flag combinations on the package(s) in the bug ...]
[15:18:14]  <irker899> [sam-box1]: bug #730892 - no rdeps.sh

[... if the package has any stable reverse dependencies, a sample of them will be tested here ... ]
[15:18:15]  <irker899> [sam-box1]: bug #730892 - USE test complete:
[15:18:16]  <irker899> [sam-box1]: bug #730892 - > succeeded:   7, failed:   0
[15:18:17]  <irker899> [sam-box1]: bug #730892 - > slot conflict:   0, blocker:   0
[15:18:18]  <irker899> [sam-box1]: bug #730892 - > test dep fail:   0, unknown:   0
~~~~
