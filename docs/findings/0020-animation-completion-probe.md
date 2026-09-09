# Original Opera animation completion probe

The verified full UI still logs transition fallback timeouts. In
`/software/test-s6x3oy2p`, Crossfade from IntroAnimation to Disclaimer starts
at 23:44:21.145 and falls back at 23:44:24.191. Disclaimer to HomeScreen
starts at 23:44:27.917 and falls back at 23:44:30.101. The original
`Transitions.js` waits for `animationend` before completing the transition.
The generated Crossfade applies `Transitions_fadeIn_300_300` to the new
template and registers that element for cleanup.

## Reproduction

```sh
just software-animations-probe
```

This loads an isolated diagnostic page in the original Opera binary using
llvmpipe and the existing software compositor. It loads original transition
CSS and the original transition manager source without editing either.
The result is rendered in `artifacts/software-visible.png`; the generic
Opera diagnostic recipe intentionally exits 1 pending inspection.

The page compares a stock fade-out class, an unprefixed CSS animation,
Opera-prefixed syntax and WebKit-prefixed syntax. It records event names and
computed opacity. Timer labels indicate requested delays, not measured
elapsed time; this is a capability probe, not a performance benchmark.

It also applies the original Crossfade fade-in class to a fifth element and
registers the original manager's `_setCleanupByEventListener`. The actual
`_animationEndEventCallback`, `_cleanupAfterTransition` and
`_checkTransitionComplete` execute. Only the final framework notification is
replaced with a report line; this case does not construct the full UI.

## Evidence

The first run `/software/test-s3m42rfv` established that the stock fade-out
and unprefixed animation both changed opacity and emitted `animationend`.
Prefixed variants did not animate or emit their corresponding events.

The expanded run `/software/test-y11um6xn` additionally reported
`original manager cleanup=COMPLETE` and `manager events: animationend`.
The manager target's opacity changed from 0 to 1. All results were visually
inspected on the actual Opera surface, and `just test` passed.

These results rule out a general absence of unprefixed CSS animation support,
a general animation-event name mismatch, and an unconditional failure of the
manager's basic completion callback in this runtime. They do not resolve the
full-UI timeouts: rendering load, event timing, target lifecycle, or additional
pending global controls remain possible causes. No animation timeout was
extended, completion event synthesized, or original UI behavior changed.

## Full-UI target trace

`just software-transition-trace --seconds 90` enables logging-only
instrumentation in a generated copy of original `Transitions.js`. It records
listener registration and animation callbacks. At the original watchdog entry,
it records target completion flags and computed styles. Styles are read only
after the timeout has already fired. It does not change classes, listeners,
callback decisions or timeout durations. Logging can still perturb scheduling,
so this diagnostic is opt-in and unsuitable as a performance baseline.

The builder requires source SHA-256
`d2ff7c0da76757d3aa211dcf99708976c1b0b34c9365664336a3618f77b6ab08`.
The tested traced hash is
`13cf7531a5dc9c067d8a9f398e685735f54dfb135747a4c24c96fb131866d38e`.
Each traced run retains `transition-trace.json`; reference firmware is unchanged.

In `/software/test-hqd5c8qq`:

- The Disclaimer listener is registered at 23:53:03.203.
- At 23:53:06.081–.084, both background `animationend` callbacks arrive.
  Their completion flags are false for `isIncomplete`, with final opacity 0/1.
- The watchdog sees only the non-global target incomplete. `Dialog3Tmplt1`
  has the expected fade-in name, duration 0.3s and delay 0.3s, `running` state,
  `display:block`, `visibility:visible`, but opacity **0**.
- A Dialog3 template animation event arrives later at 23:53:07.318.
- HomeScreen's listener is registered at 23:53:09.888. Its timeout likewise
  finds the expected fade-in class and a visible, running target at opacity 0.

This localizes the pending work to the new template, rather than the completed
background animations. It supports investigating delayed animation progress
under full-UI rendering load; it does not establish the exact bottleneck.
The late template event's animation name is not recorded, so it is not proof
that the intended fade-in ultimately completed before cleanup altered classes.

The Opera Wayland log has 37 frame callbacks and 35 commits, with median
successive gaps of 630.8ms and 617.7ms respectively. These whole-run gaps include
idle intervals and are **not** a rendering-rate benchmark or proof of compositor
latency. Profiling active transitions is still needed before changing rendering
or timeout behavior. `just test` passed for the trace integration.
