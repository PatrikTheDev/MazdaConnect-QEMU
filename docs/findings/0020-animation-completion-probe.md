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
