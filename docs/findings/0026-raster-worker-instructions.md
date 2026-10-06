# Software raster-worker instructions during delayed UI transitions

The previous worker probe established CPU activity in anonymous executable
memory and `libm`. It did not identify that code. The opt-in sampler now reads
at most 32 contiguous words around the worker PC while attached and records
CPSR. It stays within the PC's recorded mapping and detaches afterward. No
registers or guest memory are modified. Default worker sampling remains off.

```sh
just probe --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --trace-transitions --sample-render --sample-workers --seconds 90
just dev software thread_report /software/test-adgaofn4 --first 31 --last 46
just dev software worker_code /software/test-adgaofn4 35 659
just dev software worker_code /software/test-adgaofn4 39 659
just dev software worker_code /software/test-adgaofn4 42 659
```

The disassembly recipe requires a captured instruction window and rejects
noncontiguous or oversized data and a PC outside that window. It writes a
temporary binary, invokes ARM objdump, then removes the temporary file. CPSR
selects ARM or Thumb decoding; Thumb decoding starts at the sampled PC to
avoid guessing the boundary of a preceding Thumb-2 instruction. A window can
contain literal data or partial functions: objdump's interpretation of every
word as an instruction does not establish executable control flow.

## Observations

Run `test-adgaofn4` retained all 70 main samples, 65 worker samples and 2,080
instruction words (32 per worker sample), with no sampling errors. Selected
VBS/audio, system, settings, time, database and UI services reached STARTED.
The original home screen was visually inspected at 15:28. No JavaScript
exceptions, heartbeat misses, database semaphore failures or known monitor
assertion appeared. Two transition watchdogs remained. This does not resolve
the intermittent VBS address-space mismatch or prove every required service.
`just test` passed. The generic UI diagnostic still exits 1 to require pixel
and log inspection.

Disclaimer began at 15:27:20.166 and its watchdog fired at 15:27:22.546.
HomeScreen began at 15:27:26.329 and its watchdog fired at 15:27:28.345.
The sampler perturbs scheduling; compare these observations by workload and
instruction identity, not as a timing benchmark against earlier boots.

* Sample 35, PC 0xb6e9b84c: a NEON `vst1.32 {d16-d17}` followed by pointer
  increments and a bounded four-iteration loop. Nearby instructions include
  `vld1.64`, `vdup.32` and VFP scalar operations.
* Samples 39 and 44, PC 0xb6bb6278: another NEON store and bounded loop,
  with a subsequent vector load and mask test. Literal constants occur just
  before the sampled instruction; those preceding words are not evidence of
  executed arithmetic despite objdump printing instruction mnemonics.
* Sample 42, PC 0xb6bb7b68: `ldr pc, [pc, #-4]`, followed by target literal
  0xb6b38184. The recorded runtime libm executable mapping starts at
  0xb6afb000 with file offset zero. The resulting offset 0x3d184 is the
  entry to `nearbyintf`, also exported as `nearbyintf32`. Its executable ELF
  segment has equal file and virtual offsets. The observed branch target is
  stronger evidence than treating the sampled LR as an unwound caller.

This proves that these captured anonymous code paths use NEON instructions
and at least one calls out to floating-point rounding in libm. It rules out
a blanket assumption that the generated worker code uses only scalar software
floating-point helpers. It connects earlier `fesetenv` samples to a plausible
rounding workload, but does not prove which operation dominates total cost,
identify the complete shader, or justify bypassing floating-point semantics.
Sampled PCs, especially under emulation, are not instruction-level cycle
measurements. Further investigation should preserve the original rounding
behavior and distinguish actual shader cost from sampling/emulation effects.

## Exact runtime rounding path and compatibility check

```sh
just dev software inspect_abi /software/runtime-tree/libm.so.6 0x3d184 0x3d2c0
just dev software inspect_abi /software/runtime-tree/libm.so.6 0x4c800 0x4c890
just dev software inspect_abi /software/runtime-tree/libm.so.6 0x82b4 0x8370
just dev software check_rounding
```

For small nonintegral inputs, the installed `nearbyintf` calls `feholdexcept`
at 0x3d1d8 or 0x3d260, performs arithmetic via helpers at 0x4c844 and
0x4c840, then calls `fesetenv` at 0x3d20c or 0x3d294. Those helpers operate on
floating-point bit patterns with integer instructions. Meanwhile,
`feholdexcept` reads and writes FPSCR through VFP instructions, and
`fesetenv` restores it. The samples at 0x82e4 and 0x8368 therefore match
specific environment-management instructions in this call path; they are
not evidence that the entire rasterizer lacks NEON.

The new check compiles an ARMEL executable with builtin replacement disabled,
calls `nearbyintf` through a volatile function pointer, and runs it under
QEMU user-mode Cortex-A15 using the same flat runtime loader and libm as the
guest. It checks mode-selection success and `fegetround` before evaluating
0.5, 1.5 and -1.5 in each of four modes. Results must match the selected
rounding direction and must not raise FE_INEXACT. The original rounding mode
is restored before exit. This is a contract diagnostic, not a performance
benchmark or a full-system execution test.

The tested libm SHA256 is
`8fb6ed088476bc096a524553e97cc5a6dc288d1db0cfe8114526833b214ff868`.
Both executions produced the same **7/12 passing checks** and a failing exit
status. All round-to-nearest cases passed. Despite successful selection of
other modes, downward 1.5 produced 2 rather than 1; upward 0.5 and -1.5
produced 0 and -2 rather than 1 and -1; toward-zero 1.5 and -1.5 produced
2 and -2 rather than 1 and -1. No tested call raised FE_INEXACT.

This exposes a rounding-mode compatibility limitation in the current
ARMEL/QEMU runtime combination. This initial user-mode check did not measure
the active raster rounding mode or full-system behavior; subsequent evidence
is recorded below. It does not establish visual corruption, the cause of animation
watchdogs, or whether the issue also occurs outside emulation. The diagnostic
must retain its failing result rather than accepting the observed values.
No math replacement, environment bypass or runtime-build adaptation has been
introduced. `just test` passes independently; it does not cover this newly
observed contract failure. Any adaptation needs a decision under the project
instructions, and further investigation must preserve rounding semantics.

## Full-system check and the observed raster rounding mode

```sh
just probe --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --trace-transitions --sample-render --sample-workers --seconds 90 --probe-rounding
just dev software check_rounding /software/test-2rhdkvns
just dev software thread_report /software/test-2rhdkvns --first 31 --last 45
```

The full-system probe adds an independent `rounding-check` process after the
existing service-startup script has mounted the modern runtime, and before
Opera launch. It uses that runtime's loader/libm and retains `rounding.log`
with `ROUNDING_RC`. The report preserves that exit status instead of masking
a failing contract check. Normal boots do not execute this diagnostic.

Worker sampling additionally reads `PTRACE_GETVFPREGS` while the worker is
already stopped. The ARM UAPI contains 32 eight-byte VFP registers followed
by four-byte FPSCR. The report decodes rounding bits 22–23 and flush-to-zero
bit 24; the installed ARM libc header maps modes to 0, 0x400000, 0x800000
and 0xc00000. This reads state without changing the floating-point environment.
Default boots and samplers without worker opt-in are unaffected.

The initial run `test-1qfn3p7a` placed the independent check before the normal
runtime mount. It correctly retained `loader not found` and status 127, so
it is not rounding-contract evidence. The ordering error was fixed rather
than adding a second mount path. Its 66 worker FPSCR samples remain usable.

The corrected run `test-2rhdkvns` executed the check successfully and reproduced
the same five failures, with `ROUNDING_RC=1` and **7/12 passing checks**. Thus
the limitation is present in the full guest, not only the user-mode diagnostic.
The run retained 70 main samples and 65 worker FPSCR samples. Across both
runs, all 131 FPSCR observations showed **round-to-nearest and flush-to-zero
disabled**, including PCs in `feholdexcept`, `fesetenv`, the software arithmetic
helpers and anonymous generated code. There were no sampler errors.

This weakens the hypothesis that the non-nearest contract failure causes the
observed startup watchdogs: the sampled workload uses the mode whose tested
values pass. One-second samples cannot rule out transient mode changes or
establish correctness for every possible rounding input. The cost of the
observed calls remains a separate question; no rounding bypass is justified.

The corrected run's original home screen was visually inspected at 15:46.
Selected VBS/audio, system, settings, database, time and UI services reached
STARTED, with no known monitor assertion, JavaScript exception, heartbeat miss
or database semaphore failure. Both animation watchdogs remained, as did
missing application-service subscriptions. This does not resolve the VBS
address-space risk or prove the full project objective. `just test` passed
independently of the intentionally failing rounding-contract report.
