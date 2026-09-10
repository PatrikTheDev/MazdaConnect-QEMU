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
