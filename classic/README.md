### simpleworker description

Currently, `simpleworker.py` will:

1. Grab any open bugs from Bugzilla for the given architecture, ignoring bugs with a sepcific tag used
to show e.g. another worker is processing this bug.

2. Run `tatt` on it to generate testing scripts.

3. Execute the aforementioned scripts.

4. Send a summary on IRC when a bug is finished, with information on success/failure

#### Example output

~~~
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
~~~

