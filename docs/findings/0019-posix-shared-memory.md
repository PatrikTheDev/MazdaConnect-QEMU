# POSIX shared memory for the original vehicle database

The software service launcher now mounts tmpfs at `/dev/shm` with mode 1777,
`nosuid,nodev`, before starting original services. Lab PID 1 mounts devtmpfs
but did not provide this filesystem. This is an emulated environment correction;
no original firmware binary, semaphore operation or database response is patched.
Mount failure stops service startup rather than silently continuing.

The original `/jci/lib/libjcismdb.so` imports `sem_open`, `sem_wait`,
`sem_post` and `sem_close`. In `/software/live-tqqhg2q2`, semaphore creation
failed with `Function not implemented`. VDM then repeatedly reported missing
SMDB handles and failed writes. The original glibc POSIX named-semaphore
implementation needs a shared-memory filesystem; supplying it resolves the
observed initialization failure.

## Validation

`just probe --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --seconds 90` produced
`/software/test-s6x3oy2p`. Original VDM logged **11 successful SMDB opens**.
Regenerative power and electrical load reads each logged 84 numeric results
(initial zero values in this simulation). The run has zero semaphore creation
failures, missing SMDB handles, `SMDB_WriteIntData failure` messages, or
`SMDB_WriteString` bad-argument errors. This establishes database availability,
not the accuracy of simulated vehicle measurements.

All selected autorun services reached `STARTED`. Opera remained alive, the
original home screen displayed 23:45, and the guest powered down normally at
uptime 115.002 seconds. `just test` passed (13 tests, shellcheck and ARM/QEMU
smoke checks).

## Repeatable audit and remaining issues

```sh
just report /software/live-tqqhg2q2 --limit 10
just report /software/test-s6x3oy2p --limit 10
```

This recipe reports observed service lifecycle states, selected failure markers
and frequent warnings/errors. It does not assert that absent services work or
that a `STARTED` service is fully functional. Firmware log severity alone is
not a pass/fail verdict.

The new boot still has two `Transitions watchdog timer fired` messages.
These are GUI animation fallback timeouts, distinct from Opera's
`OnHeartbeatMissed` watchdog (zero occurrences). Missing application services
such as radio/navigation, the missing `MIC Level` mixer control, and NVRAM
expectations also remain to be investigated. None are hidden by this change.
