# Original Opera frame-callback delivery

```sh
just software-callback-report /software/test-y7y19r8y
just software-transition-trace --sample-render --seconds 90
```

The report pairs original `wl_surface.frame` requests with their callback IDs,
excluding display-sync callbacks. It reports request-to-delivery time and
variation in the difference between the receiving Wayland log timestamp and
the compositor-supplied callback timestamp. It subtracts the minimum observed
difference, so the latter metric is **relative lag, not absolute latency**.
The calculation assumes a stable clock offset during the bounded run and
rejects backwards/wrapped timestamps. It includes server flushing, scheduling
and client dispatch, not just time Opera was busy. A final unmatched request is
reported rather than counted as a completed frame.

| Retained run | Matched callbacks | Request wait median ms | Relative lag median ms | Relative lag p95 ms |
| --- | ---: | ---: | ---: | ---: |
| `test-y7y19r8y`, full UI with event trace | 34 | 598.75 | 379.90 | 2115.59 |
| `test-ih03phk3`, full UI with `--noHWAccel` | 36 | 622.66 | 381.03 | 3439.74 |
| `test-l_bx8j6b`, full UI frame profile | 35 | 611.47 | 375.83 | 3389.99 |
| `test-lp9hvojk`, isolated lifecycle page | 36 | 55.83 | 0.52 | 2296.14 |

Each run has one unmatched final request. Full-run distributions include idle
periods: the isolated page deliberately waits between cases, and long delivery
lags there coexist with successful animations. These distributions therefore
do not establish the cause of full-UI watchdog failures. They justify examining
active transition intervals and sampled browser execution rather than assuming
all delay occurs inside compositor drawing. `just test` passed.

## Timestamped browser and worker sampling

The opt-in sampler now records wall and monotonic timestamps while the main
thread is stopped, then reads `/proc/<pid>/task/<tid>/stat` after detaching.
Worker threads are not stopped. The report prints main-thread PCs alongside
per-thread user+system CPU tick increments; it keys counters by TID and start
time, excludes first observations and missing intervals, and reports ticks
without assuming a tick frequency or converting them to CPU percentages.

```sh
just software-thread-report /software/<run>
just software-thread-report /software/<run> --first 30 --last 50
```

Snapshots are not simultaneous and ptrace perturbs scheduling. Raw sampled
stack words are not an unwound call stack: a value inside a mapping can be
data, a stale address or a return address. They must not be used alone to name
the caller responsible for a wait.

The interrupted `/software/test-49e25y6u` retained only samples 0–29, ending at
00:36:23.874. Its first failing transition began at 00:36:41.232, so those
samples do not cover the failure. The report rejects a requested interval with
no retained samples instead of presenting an empty successful analysis.

The fresh `/software/test-vbaq7rpb` retained all 70 samples (0–69). Disclaimer
began at 14:51:38.776 and its watchdog fired at 14:51:41.148. HomeScreen began
at 14:51:44.862 and its watchdog fired at 14:51:46.389. During samples 32–45
(14:51:39.432–14:51:52.658), the `llvmpipe-0` worker accumulated CPU ticks while
the main thread repeatedly stopped at libc's futex syscall (relative PC
0x792c4). After that interval the worker was mostly idle. For the wider selected
range 30–55, the worker accumulated 671 ticks and the main thread 202 ticks.
This supports investigating rendering-worker cost; it does not identify the
expensive shader or prove that a CPU-count change will fix the animations.

The home screen rendered at 14:52 with no JavaScript exception or Opera
heartbeat miss. However, this run **failed supporting-service validation**:
VBS stopped and the retained SM log contains
`Sync::inflateTasuki ... Assertion MONITOR_MAXIMUM >= mid failed`. Several
audio services did not reach STARTED. These failures were absent in previously
verified boots and need separate investigation; this run is not evidence of
healthy complete startup. The two animation watchdogs remain.

## Compositor timeline during the failing transitions

```sh
just software-frame-report /software/test-vbaq7rpb --timeline
```

The optional timeline prints UTC begin/end timestamps, paint/display/save/total
durations, and the delay from a paired `schedule` record to repaint begin.
Unpaired begins are labelled explicitly: display-control requests can call
repaint directly. It uses the existing trace and changes no guest behavior.

For this run, the frame at 14:51:39.332 finished at 14:51:39.657, taking
324.86 ms. The next began at 14:51:41.111 and finished at 14:51:41.426,
taking 314.82 ms. Its scheduling request occurred at 14:51:41.092, only
19.01 ms before begin, rather than at the beginning of the 1.454-second gap.
The Disclaimer watchdog fired during that latter frame, at 14:51:41.148.

Before HomeScreen's transition, a frame finished at 14:51:44.435. The next
began at 14:51:45.870, after a scheduling request at 14:51:45.852, and
completed at 14:51:46.083 (213.50 ms). The transition began at
14:51:44.862; its watchdog fired at 14:51:46.389. The following repaint
began at 14:51:46.390 and took 268.60 ms, with an 18.02 ms timer wait.

These active intervals distinguish substantial gaps without logged repaint
requests from compositor paint work and its roughly 18–19 ms scheduled timer
waits. Together with the busy llvmpipe worker and main-thread futex samples,
they support investigating browser rendering/submission next. They do not
prove the exact wait dependency, which shader is costly, or that compositor
optimizations cannot help. The timestamps are wall-clock observations and
include diagnostic overhead; the report does not measure client dispatch.

## Opt-in raster-worker instruction sampling

```sh
just software-worker-probe
just software-thread-report /software/test-izfv4080 --first 25 --last 55
just software-transition-report /software/test-izfv4080
just software-health-report /software/test-izfv4080
```

The worker probe adds `--sample-workers` to the existing register sampler.
After main-thread detach and a worker's stat read, it briefly attaches to each
thread whose name starts with `llvmpipe-`, records PC/LR/SP and wall/monotonic
time, and captures the mapping containing that PC while stopped. It detaches
before continuing. Default sampling still leaves workers running. The report
prints file offsets for mapped files and mapping-relative offsets for anonymous
memory, which are not interchangeable with ELF virtual addresses. Worker
sampling adds scheduling perturbation; these observations are not a benchmark
or an unwound call stack.

The fresh run `test-izfv4080` retained all 70 main samples and 66 worker samples
with matching PC mappings and no sampling errors. The original home screen
was visually inspected at 15:20. Selected VBS, audio, settings, time, system,
database and UI services reached STARTED; the known monitor assertion was
absent in this run. That does not resolve its intermittent address-space risk.
There were no JavaScript exceptions, heartbeat misses or database semaphore
failures, but both animation watchdogs remained. The generic diagnostic exits
1 to require inspection of pixels and logs; this is not an automatic success
gate for complete UI startup.

Disclaimer's listener was installed at 15:19:37.173 and its watchdog fired at
15:19:39.169. Samples 33–36 (15:19:38.664 through 15:19:41.722) found the
busy raster worker in anonymous executable mappings, while the main thread
often waited in libc's futex syscall. HomeScreen began at 15:19:42.862 and
its watchdog fired at 15:19:44.807. Samples 38 and 40 found the raster worker
at file offset 0x8368 in the mounted runtime's `libm.so.6`; sample 32 was at
0x3bad8. The library's executable PT_LOAD has matching file and virtual
offsets, and its dynamic symbols identify these as `fesetenv+0x6c` and the
entry to `floorf` (also aliased as `floorf32`). Samples 42 and 44 again found
anonymous executable code. Anonymous mappings are consistent with generated
raster code, but no specific shader or call dependency has yet been recovered.

For samples 25–55 the worker accumulated 696 ticks, versus 253 for the main
thread. After sample 45 it was mostly idle, with sampled PC in the futex wait.
These data narrow investigation toward the software raster workload, including
its generated code and floating-point environment operations. Two hits in
`fesetenv` do not establish its total cost or justify bypassing it.
## Startup trace with the corrected userspace boundary

```sh
just software-frame-profile --kernel-profile vmsplit2g --trace-transitions --seconds 90
just software-frame-report /software/test-ea_xg5bw --timeline
just software-transition-report /software/test-ea_xg5bw
just software-health-report /software/test-ea_xg5bw
```

This run uses the validated 2 GiB kernel from finding 0027, without ptrace
worker sampling. Original VBS and the selected audio services reached STARTED;
HomeScreen was visually inspected. Both animation watchdogs remained, with
zero JavaScript exceptions, heartbeat misses and database semaphore failures.
Missing application-service subscriptions remain. The generic UI diagnostic
exit 1 still requires manual pixel/log review.

The compositor retained 82 complete frames. Painting median/p95/max was
121.59/331.35/410.68 ms; saving the diagnostic PPM was
43.87/151.73/175.41 ms; total frame duration was
169.75/505.74/604.26 ms. These mix startup workloads and include tracing and
single-vCPU scheduling effects; they are not pure isolated drawing costs.

Disclaimer's transition listener was installed at 20:14:09.383 UTC. Its
incoming animation started at 20:14:12.189, the watchdog log appeared at
20:14:12.246, and the natural animation end arrived at 20:14:13.315.
HomeScreen's listener was installed at 20:14:15.992; its watchdog fired at
20:14:18.071, before incoming animationstart at 20:14:20.063.

Immediately before HomeScreen, the frame ending at 20:14:14.814 was followed
by the next beginning at 20:14:16.973. That frame's scheduled timer wait was
only 17.43 ms, and painting/display/save took 155.64/20.87/57.76 ms. Thus the
long submission gap remains alongside substantial compositor work. The
corrected pointer boundary does not resolve either startup watchdog. These
measurements support further browser-submission and compositor-cost analysis;
they do not justify changing the original animation deadlines or synthesizing
completion events.
