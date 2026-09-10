# Original Opera template-attachment lifecycle

The full UI delivers incoming fade-in start events after its watchdog has
already fired. The earlier isolated animation capability probe used an
already-attached target and immediately read computed styles. This diagnostic
tests whether transparent initialization and attachment alone reproduce the
failure without that early style read.

```sh
just software-animation-lifecycle-probe
```

The page runs four sequential cases in original Opera with llvmpipe. It loads
original `TransitionsGen.css` and `Transitions.js`, applies the original delayed
fade-in class, and uses the original manager's listener and completion checks.
Only the final framework notification is replaced with a local completion flag.
It observes that flag at the original 600ms animation + 500ms watchdog margin;
it does not force completion. No computed style is read until the three-second
observation window has ended. Event timestamps use `Date.now()` and measure
delivery, not internal browser animation timing. Results are written to the
page only after all four cases, avoiding diagnostic DOM writes during animation.

In `/software/test-lp9hvojk`, the original Opera surface reported:

| Case | Start event ms | End event ms | Deadline callback ms | Complete at deadline |
| --- | ---: | ---: | ---: | --- |
| Already attached | 341 | 1094 | 1118 | true |
| Attached + transparent init | 346 | 716 | 1115 | true |
| Detached parent + transparent init + reparent | 348 | 704 | 1110 | true |
| Detached parent + reparent, no init | 327 | 674 | 1108 | true |

All targets ended at opacity 1 and original-manager completion. The screenshot
was visually inspected; `done=true` confirms every case finished. `just test`
passed. The generic Opera diagnostic exits 1 pending this pixel inspection.

This rules out an unconditional failure caused only by these attachment and
class operations in this runtime. It does not reproduce the full template's
contents, ancestors, overlapping transitions or rendering load. Cases execute
in a fixed order, so their timing differences are not a controlled performance
comparison. Full-UI scheduling and painting remain under investigation; no
firmware timeout or animation behavior has been changed.

## Full-UI painter comparison

`just software-transition-trace --no-hw-accel --seconds 90` retains the same
llvmpipe configuration and approved startup fixes while passing Opera's
`--noHWAccel` option. The guest command line in `/software/test-ih03phk3`
confirms the option was passed. The home screen rendered with 00:28; selected
services reached STARTED, with no JavaScript exceptions, heartbeat misses or
database semaphore errors. Both animation watchdogs remained. Incoming
Disclaimer and HomeScreen start notifications again arrived after cleanup.
This option alone does not resolve the problem. It is not a measured proof
that every internal painting operation switched backend.

Read-only ABI inspection additionally confirmed that `wlxs_output_post_frames`
at 0x14924 calls through the original surface traversal to
`wlxs_surface_post_frame` at 0x19f68, which calls `wlxs_timestamp` before posting
the callback event. The plugin passes only the output pointer, as expected;
there is no missing timestamp argument in that recovered declaration.
`wlxs_timestamp` at 0x1ce58 reads `CLOCK_MONOTONIC` (clock ID 1) before converting
the result to the protocol timestamp. This verifies the timestamp source, not
the delay between generation and delivery to Opera.
