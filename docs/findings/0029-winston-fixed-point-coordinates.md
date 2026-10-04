# Correct software-output coordinate units

The user approved this correction on 2026-10-04 after the failing stock IVI
positioning tests in finding 0028. This fixes the lab output adapter's use of
the original Winston ABI. It does not change a vendor binary, browser shader,
animation deadline, service response or the separate Vivante work.

Winston's inverse transform and source clipping operate in signed 24.8
fixed-point coordinates. Output origins, surface/subview offsets and the
software pixel array use whole pixels. The adapter now multiplies global
pixel coordinates by 256 before calling Winston, then arithmetically shifts
the result right eight bits before subtracting the pixel-valued subview
offsets. Its point sampler floors negative coordinates before bounds checks.
Blending is unchanged. This retains the existing point-sampling policy;
it does not claim bilinear-filter parity with the vehicle GPU.

The translation fast path now increments by 256 per output pixel. Its
optional every-coordinate comparison uses the same corrected input units.
Clipped/custom views retain original per-pixel transforms. The output range
is checked before multiplication, and buffer-offset subtraction uses 64-bit
arithmetic to avoid signed overflow. Views whose fast-path fixed-point range
would overflow fall back to the original routine.

```sh
just software-draw-test --kernel-profile vmsplit2g
just software-draw-position-test --verify-draw
just software-draw-position-test --reference-draw
just software-draw-probe --seconds 90
```

The geometry test uses the original Opera test-page buffer and stock IVI
commands. It checks every output pixel against the independently specified
source/destination geometry, including black outside the destination and
viewport. Cases cover positive/negative positioning, an animated endpoint,
source clipping, half-size scaling and combined clipping/scaling. Scaling
uses the adapter's documented point sampler, rather than changing expected
pixels to accept a failure. Crop/scale cases also record whether Winston's
custom-transform and clipping flags were active.

## Initial verification

`/software/test-2rgdzdmt` passed positive/negative translations, five draws of
every-coordinate equivalence, exact browser CSS samples/text, compositor and
Opera liveness, and clean shutdown. Before correction both moved outputs
were entirely black, including with the pre-optimization drawing path.

Expanded run `/software/test-i9b477bf` passed all six geometry cases, exact
browser CSS samples/text and clean shutdown. Its logs include 36 draws with
both custom-transform and clipping flags set. Only the initial unmodified
view exercised the fast path in that first expanded run; a subsequent probe
orders animated movement before applying explicit crop/destination commands
to check fractional translation through the fast path as well.

That subsequent run `/software/test-ai5cttxp` passed every geometry case and
verified 31 fast-path draws (11,904,000 output coordinates). Of these,
24 used fractional pixel translations: fixed-point origins included
(7474,4982), (6479,4312) and (5672,3762), not multiples of 256. Six additional
draws used original custom-transform/clipping paths. The fast path therefore
matches original Winston for the observed fractional movement, not only
whole-pixel or zero origins.

`just test` passed: 13 unit tests, shell checks and ARM userspace/full-system
QEMU initialization. Arbitrary perspective distortion,
rotation and filtering parity are not proved by these axis-aligned cases.

## Original UI startup and live interaction

Bounded startup `/software/test-l8rwtwk6` verified 107 fast-path draws
(41,088,000 output coordinates). HomeScreen was visually inspected, and the
retained kernel-layout report passed with 3,429 ordinary mappings across
28 processes below the 0x80000000 boundary. Original VBS, system, settings,
time, database, MMUI and selected audio services reached STARTED. The checked
logs had zero JavaScript exceptions, heartbeat misses and database semaphore
failures. Two startup animation watchdogs remain.

```sh
just software-boot --kernel-profile vmsplit2g --renderer llvmpipe --intro-race-fix --time-deadline-fix --websockets-queue-fix --seconds 240 --start-delay 0
just software-capture
just software-key right
just software-key right
just software-key ret
just software-capture
just software-key backspace
just software-capture
just software-stop
```

Allow each visible transition to settle before the next capture/key. In live
run `/software/live-_a_z4sxi`, real QEMU input opened the original Settings
Display tab and Backspace returned to HomeScreen. VNC scanout captures were
visually inspected and retained locally as `software-coordinate-home.png`,
`software-coordinate-settings.png` and `software-coordinate-back.png` under
ignored `artifacts/`. The displayed guest clock advanced across minute changes.
Original transition logs corroborate HomeScreen -> DisplayTab -> HomeScreen.
The guest shut down cleanly at uptime 177.98 seconds.

All selected services reached STARTED. There were no JavaScript exceptions,
MMUI parse errors, heartbeat misses, database semaphore failures or known VBS
monitor assertions. Four animation watchdogs occurred across startup and this
interaction sequence, so rendering deadlines remain unresolved. Missing
application-service subscriptions also remain. This proves the approved
coordinate correction and this interaction path, not every application,
transform or the complete project objective.
