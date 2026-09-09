# Opt-in firmware change: intro completion race

The user approved implementing and documenting this fix. It **changes original
MMUI firmware behavior** in the software lab. It is disabled by default, and
does not modify the reference firmware archive or extracted sysroot.

The observed failure and original instruction addresses are documented in
[the startup investigation](0015-render-stall.md). When Normal/ShowDisclaimer
arrives before GUI startup launches the intro, playback finishes but MMUI stays
in IntroAnimation. The original completion handler's HMI-ready event does not
cause another Normal transition, so there is no new ShowDisclaimer event.

## Changed behavior

The patch records the latest state delivered to the original MMUI system-state
notification callback. It then preserves the callback's original behavior.
After the original intro-completion handler calls `UIA_SYSTEM_SetAppContext`,
the patch queues the original `ShowDisclaimer` event **only** when both hold:

* MMUI's current context is still 1023 (`IntroAnimation`).
* The latest received system state is 2 (`Normal`).

The existing handler still validates its arguments, marks video playback
finished, reports HMI ready, and updates its context. Unknown/non-Normal states
and an already displayed disclaimer do not trigger the added event. Playback
is not skipped; no device readiness response or watchdog is changed. The
websocket defects remain unpatched.

## Reproduction

* `just software-intro-fix-test`: execute the actual patch assembly under ARM
  emulation, checking five-argument forwarding, return-value preservation,
  original context-call execution, and positive/negative state conditions.
* `just software-intro-fix-probe`: boot original UI and services with llvmpipe,
  the patch and startup diagnostics.
* `just software-boot --renderer llvmpipe --intro-race-fix`: opt in for the live
  VNC viewer; connect with `just software-view`.
* Omit `--intro-race-fix` to retain stock MMUI behavior in a fresh guest.

## Binary handling

`build_intro_fix.py` requires SHA-256
`32431c6b74c8ba531fcc10c50748075416e0f7dc1a3f903f182d816a0f3f5fc2`
for EU 74.00.324A `libjciuiasystem.so`, plus exact original hook instructions.
It assembles `intro-race-fix.S` and changes branch sites `0x2a4d0` (system-state
callback) and `0x1982c` (completion context call).

The ELF already has a 32 KiB virtual gap between its executable and writable
segments. The builder inserts corresponding file space for the added code,
extends the executable segment, shifts file offsets, and reserves four
zero-initialized bytes after the existing BSS in the writable segment. Existing
virtual addresses, symbol values, relocations and section indices stay fixed.
The stack remains non-executable; no writable/executable segment is added.

Only `LAB_INTRO_RACE_FIX=1` selects the generated library in the disposable
guest before services start. Its generated `intro-race-fix.json` records source
and output hashes and code/state addresses, and is retained with the run logs.
Patched firmware bytes are not committed to this repository.

## Validation

`/software/test-jzcg_sai` ran the original services and GUI for 90 seconds with
llvmpipe and the patch. Playback completion at 23:06:17 was followed by the
original ShowDisclaimer event, GUI Disclaimer context at 23:06:18,
DisposeIntroVideo at 23:06:20, and HomeScreen at 23:06:24. The final framebuffer
shows the home menu with Communication selected and the status clock; Opera
remained alive. This is distinct from the intro's final still image.

The ARM ABI/state tests and `just test` pass. Original websocket exceptions
still occur, and menu interaction needs separate verification; this result
does not establish that all supporting services or UI functions are complete.

The subsequent live run `/software/live-m0zcw1xt` used
`just software-boot --renderer llvmpipe --intro-race-fix --seconds 180`.
The VNC framebuffer showed the original HomeScreen. `just software-key right`
moved its selection from Communication to Navigation; a second right followed
by `just software-key ret` opened the original Settings/Display screen. The
Settings screenshot is retained locally as `artifacts/software-settings-verified.png`.
The bounded shutdown occurred before a return-to-home capture, so that action
is not verified. The status clock still reads 00:00 and websocket exceptions
remain unresolved; further service and interaction checks are needed.

The retained live manifest identifies patched SHA-256
`bc8e213013e9090e17acb287f1727b72d7873f0b357712fb335b2fb72e48b91c`,
code at `0x6f79c` and state storage at `0x8ee54`.
