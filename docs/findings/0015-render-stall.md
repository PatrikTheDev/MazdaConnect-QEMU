# Extended browser rendering stall

The home screen can render after the original audio services reach STARTED and
the system enters NormalState, but extended live startup terminates Opera via
its own `OnHeartbeatMissed` watchdog. The watchdog has not been bypassed.

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
