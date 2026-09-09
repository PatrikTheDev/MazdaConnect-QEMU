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
