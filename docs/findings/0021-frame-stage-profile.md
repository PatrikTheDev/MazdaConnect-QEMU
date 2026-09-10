# Software frame-stage profiling

`just software-frame-profile --seconds 90` runs the original UI with the three
approved fixes and logs compositor stages without attaching ptrace to Opera.
`just software-frame-report /software/<run>` reports complete-frame wall-clock
durations and excludes idle gaps between frames. Scheduling delays within a
frame remain included; these are not isolated CPU instruction benchmarks.

The baseline `/software/test-57tokbjd` contains 78 complete frames:

| Stage | Median ms | p95 ms |
| --- | ---: | ---: |
| Update | 0.22 | 0.33 |
| Draw | 122.75 | 369.37 |
| Framebuffer display | 14.58 | 56.77 |
| PPM save | 114.32 | 350.29 |
| Callback dispatch | 0.18 | 0.84 |
| Total | 239.79 | 775.55 |

## Change

The PPM writer now converts a whole frame into a 1,152,000-byte temporary RGB
buffer and calls `fwrite` once for the payload, instead of 480 row calls. PPM
format, pixel conversion, final-frame availability and atomic rename remain
unchanged. Allocation/write/close failure leaves the previous completed frame
in place. No original firmware, view transformation, animation, timer or
readiness behavior changes.

An exact-identity transform fast path was also evaluated, but drawing time did
not improve in that run. It was removed rather than retaining an unproven ABI
optimization. The final renderer retains the original per-pixel transform.

The intermediate comparison `/software/test-fqdflzyh` reduced median save time
to 63.91ms and total frame time to 213.68ms, but retained two animation timeouts.
Its 00:00 screenshot was real guest midnight: original BLM logged
`Time:2026-09-10 00:00:00`, not a clock initialization regression.

`just software-test` verified exact color-bar pixels and frame callbacks after
the writer change. `just test` passed. The final PPM-only run `/software/test-l_bx8j6b` contains 82 complete frames:

| Stage | Median ms | p95 ms |
| --- | ---: | ---: |
| Update | 0.22 | 0.34 |
| Draw | 130.16 | 352.64 |
| Framebuffer display | 13.43 | 57.01 |
| PPM save | 61.89 | 199.11 |
| Callback dispatch | 0.20 | 0.33 |
| Total | 200.17 | 619.16 |

In these bounded runs, median save time fell about 46% and total frame time
about 17%. The frames are not identical paired workloads, so these figures
are observations rather than a guaranteed speedup for every screen.

The final screenshot shows the original HomeScreen with 00:03. All selected
autorun services reached STARTED. There were zero JavaScript exceptions,
MMUI JSON parse errors, Opera heartbeat failures, semaphore creation failures,
or missing SMDB handles. Two transition-animation watchdog fallbacks persist.
This optimization reduces diagnostic overhead but does not resolve those
fallbacks or establish complete application-service integration.
