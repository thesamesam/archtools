## archtools

A tool to help automate the Gentoo arch testing process.

### Tools

1. The `rq`-based queue system (the rq directory);

2. The 'classic' simpleworker script

### `rq` description

You will need:

- NATTkA
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

You can read more [here](classic/README.md).
