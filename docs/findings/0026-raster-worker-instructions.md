# Software raster-worker instructions during delayed UI transitions

The previous worker probe established CPU activity in anonymous executable
memory and `libm`. It did not identify that code. The opt-in sampler now reads
at most 32 contiguous words around the worker PC while attached and records
CPSR. It stays within the PC's recorded mapping and detaches afterward. No
registers or guest memory are modified. Default worker sampling remains off.

```sh
just software-worker-probe
just software-thread-report /software/test-adgaofn4 --first 31 --last 46
just software-worker-code /software/test-adgaofn4 35 659
just software-worker-code /software/test-adgaofn4 39 659
just software-worker-code /software/test-adgaofn4 42 659
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
