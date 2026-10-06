# Opt-in original GUI transition queue correction

The user separately approved fixing the original `Websockets.js` queue.
`--websockets-queue-fix` installs a generated copy in the disposable guest,
leaving reference firmware and extracted sysroot unchanged. It is disabled by
default. The wire format, sequence byte, acknowledgment code, connection logic
and startup readiness rules are unchanged.

## Evidence and changes

The original GUI repeatedly throws `this._isStack is not a function` during
startup and transitions. Its two queue helpers are global functions, but callers
look for instance methods. Additionally, the helpers compare a serialized JSON
message against a type string such as `transition`, so they never find the
intended entry even when called with the correct receiver.

The generated patch makes these specific changes:

- Define both helpers on `Websockets.prototype` and compare parsed `msgType`
  plus sequence. Preserve the original last-match lookup and removal of all
  matching entries; reverse iteration avoids skipping adjacent matches.
- Store context messages as `[serialized message, sequence]`, matching the
  other queue producers.
- Unwrap the serialized message when the original 50-message forced flush
  passes queue entries to the JSON router.
- Delete a queued transition after delivering it on the focus-arrival path,
  preventing a later forced flush from delivering it again.

No replacement framework or fake MMUI responses are used. The old Opera
ArrayBuffer numeric access and `.length` behavior is retained: it was verified
in that runtime and differs from modern-browser assumptions.

The builder checks the complete original SHA-256 and exact patch-site counts.
The run retains `websockets-queue-fix.json` identifying the generated artifact.

- Original SHA-256: `40e21c3e7e661174f06b65c234788b3f0a78445685e0d784677f3dabc460cbd2`
- Patched SHA-256: `a30aaf297ad784212f4d7d71b825fd73738047e83be0df120f5d4b593cf18aee`

## Reproduction

```sh
just probe --renderer llvmpipe --probe-websockets --websockets-queue-fix --inspect-surface --seconds 20
just probe --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --seconds 90
just dev software task boot --renderer llvmpipe --intro-race-fix --time-deadline-fix --websockets-queue-fix
just view
```

The runtime test loads the generated firmware JavaScript in original Opera.
Only the diagnostic page substitutes the socket transport and downstream
receiver; it feeds the actual `_openMmui` message callback. It does not make
network connections. `artifacts/software-visible.png` contains the test report.
The diagnostic recipe exits 1 intentionally, requiring inspection of its report;
that exit code alone does not mean the assertions failed.

## Verification

`/software/test-_cbgwoif` reports all nine cases PASS: ordered delivery,
waiting for focus, single delivery of a queued transition, context releasing
queued focus/transition, sequence isolation, deletion isolation, context tuple
shape, forced-flush JSON routing and sequence wrap from 255 to 0. The final
`queue_tests=PASS` and `done=true` were visually verified in the actual Opera
surface. `just test` passed as well.

The full original-UI run `/software/live-tqqhg2q2` enabled all three approved
fixes and llvmpipe. It rendered HomeScreen, opened Settings using Right, Right,
Enter, then returned to HomeScreen using Backspace. The framebuffer clock
advanced from 23:39 to 23:40. Both HomeScreen callbacks appear in the log
(23:39:47.914 and 23:40:36.180). The guest was deliberately stopped after the
test and powered down normally at uptime 150.706 seconds.

Every autorun service selected in this profile reached `STARTED`, including
original MMUI, VBS, settings, AppSDK, DBAPI, both time services and the seven
audio services. The retained syslog contains zero `Uncaught exception`,
`this._isStack`, `Unable to parse incoming MMUI`, or `OnHeartbeatMissed`
occurrences. The run manifest matches the tested patch hash above.
These observations establish startup and this interaction sequence, not every
possible queue interleaving or every application in the vehicle firmware.

## Keyboard investigation

The comparison run `/software/live-ka1baueo` opened Settings and displayed a
clock advancing from 23:35 to 23:36. Escape did not navigate back. Inspection
of original `common/js/Multicontroller.js` explains why: Back is **Backspace**
(keycode 8), while M/N are clockwise/counterclockwise rotary events.
`just key` now accepts `backspace`, `m` and `n` in addition to the
previous keys. No firmware keyboard mapping is changed.
