# Extended browser rendering stall

The original audio services reach STARTED and the system enters NormalState,
but extended live startup with softpipe terminates Opera via its own
`OnHeartbeatMissed` watchdog. The watchdog has not been bypassed. The earlier
five-icon image does not establish that the interactive home screen rendered:
the intro contains that image, and the global texture capture includes video.

Two opt-in recipes collect evidence:

* `just software-render-probe`: original browser syscall waits plus timestamps
  around software compositor scheduling, painting, display writes and callbacks.
* `just software-render-sample`: briefly samples the browser main thread's ARM
  registers/stack and records mappings, without rewriting registers. It cannot
  run together with syscall tracing because both use ptrace.

In `/software/test-5tqj4tdi`, the compositor continued completing its frame stages.
Opera's main thread had a roughly ten-second interval without traced waits before
the watchdog killed the process. A missing final browser frame callback alone
therefore did not establish a compositor deadlock.

In `/software/test-zl3i3qpf`, samples repeatedly located the main thread inside
`swrast_dri.so` and libgcc software floating-point arithmetic. The rasterizer's
executable mapping was `b2808000-b39a8000`, with repeated sampled addresses near
`b2f02c18` and `b2f04838`. Other samples landed in `__aeabi_fadd`/`__aeabi_fsub`
in libgcc. This points to expensive CPU rasterization on the ARMEL runtime as
the immediate stall, rather than a thread sleeping on a traced kernel wait.

`just software-ui-probe --no-hw-accel` tests the original browser's CPU-painting
option through 90 seconds of startup, retaining five-second frame samples.
Its result must be checked for actual rendering and watchdog/liveness behavior
before changing the normal live path. No alternative UI implementation or
application-readiness reply has been substituted.

## Renderer comparison

The no-hardware-acceleration probe (`/software/test-eexqvvti`) still ended with
the browser watchdog and a black framebuffer. With
`just software-ui-probe --renderer llvmpipe` (`/software/test-6h0l0gd9`), Opera
remained alive through 90 seconds without a missed heartbeat, but the framebuffer
was still black. The renderer option uses the installed Mesa driver with one
worker thread; softpipe remains the default.

`just software-ui-probe --renderer llvmpipe --inspect-buffer --inspect-surface --seconds 45`
(`/software/test-igi1tjqs`) also remained black when the diagnostic explicitly
set browser surface alpha to 255. Its uploaded-buffer image contains the five
icons, but cannot be attributed to Opera rather than the intro player.

The original GUI logs report `TypeError: 'this._isStack' is not a function` in
`jci/gui/framework/js/Websockets.js`. MMUI remains in `system.IntroAnimation`
even after `UIA_SYSTEM_OnFinishIntroAnimation` receives video completion and
reports HMI ready. These are unresolved leads; neither the stock JavaScript nor
the readiness transitions have been patched. Interactive UI rendering remains
unverified.

## Stock startup sequencing

The extracted `Websockets.js` is byte-identical to the reference rootfs archive
(SHA-256 `40e21c3e7e661174f06b65c234788b3f0a78445685e0d784677f3dabc460cbd2`).
Its message handler calls `this._isStack` and `this._delStack`, but both helpers
are declared as global functions rather than `Websockets.prototype` methods.
The exception is therefore consistent with the stock source. It does not by
itself prove the cause of the stuck intro: the GUI still processes the
`IntroAnimation` context and answers subsequent health checks.

In `/software/test-6h0l0gd9`, the original system enters NormalState at 22:41:38,
MMUI receives `ShowDisclaimer` at 22:41:40, and GUI startup settings trigger
`StartIntroAnimation` at 22:41:45. Video completion arrives at 22:42:07.
`UIA_SYSTEM_OnFinishIntroAnimation` at `libjciuiasystem.so:0x19780` sets the
video-finished flag and reports HMI ready, but its context-table action keeps
the current context. The log confirms next context 1023 (`IntroAnimation`).
The system's normal-state notification callback at `0x2a4d0` emits event
`0x5d3` when entering state 2 from another state; repeating a notification with
old and new state both 2 does not emit that event.

The stock system preparation function at `svcjciblmsystem.so:0x10b310` waits
for display, TAU and audio conditions; the observed transition does not wait
for GUI completion. The GUI sends `DisposeIntroVideo` when the disclaimer has
actually displayed, not when the intro context is displayed. This makes the
early disclaimer/late intro ordering a separate lead from the JavaScript
exception. No synthetic disclaimer event or altered state transition has been
introduced.

`just software-ui-probe --renderer llvmpipe --browser-delay 0 --seconds 60`
tests startup without the harness's fixed five-second browser delay. The
default remains five seconds until the ordering investigation is resolved.
The zero-delay run (`/software/test-muw55kg_`) kept Opera alive for 60 seconds
but still ended with a black framebuffer and MMUI in `IntroAnimation`.
NormalState preceded the intro again, and the same JavaScript exception was
present. Removing the fixed delay alone is therefore insufficient.

Use `just software-startup-report /software/test-muw55kg_` to reproduce the
milestone ordering with exact firmware log lines and source line numbers. It
also works on retained live-run directories and does not infer UI readiness.
Both this probe and `/software/test-6h0l0gd9` show the same sequence: SM reports
boot finished, the system enters Normal, MMUI handles ShowDisclaimer, GUI
startup launches the intro, and playback completion reports HMI ready without
a subsequent disclaimer context.

The zero-delay run confirms that ShowDisclaimer was handled successfully:
`UIAHLP_RequestFocusAndExecuteActionFunctions` calls the Disclaimer enter action
at 22:55:29, before startup settings launch the video at 22:55:32. Thus it was
not merely a dropped D-Bus signal. In the original system binary,
`SYSTEM_SMM_GuiAvailable` posts event 5 (`0x11d894`); the NormalState dispatch
entry for event 5 at `0x111944` branches to its no-action path. These observations
explain why completion cannot recover this ordering by itself.

Proposed next experiment, pending architecture approval: opt-in, hash-checked
firmware fixes for the websocket method binding and an intro-completion path
that resumes the original disclaimer flow if the system is already Normal.
The reference firmware remains unchanged. Delaying device success replies or
injecting an unconditional disclaimer event would conceal the race and is not
the proposed fix.
