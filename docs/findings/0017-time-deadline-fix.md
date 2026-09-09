# Opt-in BLM time deadline correction

The user approved this firmware change separately from the intro race fix.
It is disabled by default. `--time-deadline-fix` enables the original time
services and substitutes a generated copy of `/jci/time/svcjciblmtime.so` only
inside the disposable guest. Reference firmware and extracted sysroot remain
unchanged. No timeout, connection response or readiness check is bypassed.

## Evidence and scope

In the unpatched `/software/test-15d09bjr` probe, original `jciTime` started,
but `jciBLMTIME` failed initialization. BLM entered its semaphore wait at
23:14:44.165 and reported timeout at 23:14:44.169; CPP's response arrived at
23:14:44.269. The guest's PL031 RTC was present and the CPP log had correct
wall-clock time. Monotonic uptime was approximately 18 seconds.

Original `BLM_TIME_SemTimedWait` calls `clock_gettime(CLOCK_MONOTONIC)` at
0xd59c, adds the supplied timeout seconds, and passes the result to
`sem_timedwait` at 0xd61c. The firmware's own glibc 2.11.1 implementation
(`/lib/libpthread-2.11.1.so`, `sem_timedwait` at 0xde50) calls
`__gettimeofday` at 0xdf28 and subtracts wall-clock time from the deadline.
An uptime-based deadline is therefore already expired. This is a mismatch
between the original binaries' clock expectations, exposed in the lab.
It does not establish how often the issue occurs on physical hardware.

The patch changes ARM `mov r0, #1` (`0xe3a00001`) to `mov r0, #0`
(`0xe3a00000`) at virtual address/file offset **0xd594**. This selects
`CLOCK_REALTIME`. The subsequent arithmetic, timeout duration, semaphore
wait and connection handling are unchanged. ELF layout is unchanged.

- Original SHA-256: `f06789afd378aa164aa9f6322be2c0ddff3fd893768e858088f9676c7e9e8a2f`
- Patched SHA-256: `fc98da02eb99f2398c7949920216648c8cf18583cecccabe7d7510487a0ce081`

The builder rejects an unexpected source hash or instruction. Each enabled
run retains `time-deadline-fix.json` with both hashes and the change location.
Optional service profiles copy original `stage_2`, `jciTime` and `jciBLMTIME`
entries, using the lab's existing single-CPU affinity and no-reset/no-retry
policy. Existing default profiles stay unchanged.

## Reproduction and validation

```sh
just software-time-fix-test
just software-time-fix-probe --seconds 90
# Live viewer after the current guest is stopped:
just software-boot --renderer llvmpipe --intro-race-fix --time-deadline-fix
just software-view
# Unpatched comparison:
just software-time-probe --seconds 90
```

`software-time-fix-test` passed against the actual firmware: exactly one byte
changed, output length unchanged, manifest hash correct, reference hash
unchanged, and the original time-service entries present once each.
`just test` also passed (13 unit tests, shellcheck, ARM/QEMU smoke checks).

The full patched boot `/software/test-isqjow64` completed with
`OPERA_ALIVE_RC=0` and normal guest poweroff at uptime 115.632 seconds.
Original `jciTime` reached `SM_SVC_CMD_STARTED` at uptime 20.541 seconds;
`jciBLMTIME` reached it at 26.573 seconds. BLM waited at 23:30:02.982,
received the actual CPP connection callback at 23:30:03.287, then successfully
registered for minute notifications. Its original minute callback ran at
23:31:00 and queued the event. The captured original HomeScreen displays
**23:31**, matching guest wall-clock time, rather than the previous **00:00**.
The retained manifest matches the hashes above. The diagnostic recipe exits 1
by design to require pixel/log inspection; this is not a failed service test.

This verifies connection readiness, a minute notification, and rendered clock
output. It does not verify GPS synchronization, timezone configuration,
persistence across boots, or a visible minute-to-minute transition (the intro
and disclaimer occupied the early frames). Existing stock websocket exceptions
remain a separate investigation; their code was not changed here.
