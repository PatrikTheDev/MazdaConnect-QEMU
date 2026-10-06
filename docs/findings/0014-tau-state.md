# Simulated TAU connection state

The VIP peer now answers the observed 0x1d5 request for message 0x195 after VBS
registration. The response selects only A08A (connection/standby), using payload
`08 <state>`. Other TAU configuration fields remain absent. Original VIM and VBS
continue decoding and publishing the signal through their normal interfaces.

The simulated device state is configurable:

```sh
just probe --probe-vip-service --seconds 20 --debug-services --tau-state connected
just probe --probe-vip-service --seconds 20 --debug-services --tau-state standby
just probe --probe-vip-service --seconds 20 --debug-services --tau-state disconnected
```

Values follow the vendor diagnostic: standby=0, connected=1, disconnected=2.
The probe defaults to connected. This models device presence; it does not provide
a radio tuner, audio routing, or declare the entire infotainment stack ready.
The normal live boot still does not enable the incomplete VIP peer by default.

`software-vip-protocol-test` covers each state and the selective mask. Pending
status replies wait for an outstanding frame's acknowledgment, and take priority
over the next periodic heartbeat. Original-binary validation is required to
confirm the mask interpretation and resulting system transition.

Original-binary probe `/software/test-6noztxo2` confirmed the selective field:
VBS logged connection state 1, the radio module stopped its TAU request timer,
and the system logged `Tau is connected!`. The next explicit dependency is
`Still waiting for audio manager to get running...`. This is not complete UI
startup. `just probe --probe-vip-service --verify-tau --tau-state {{state}} --seconds 20 --debug-services connected [state]` now checks original decoding and rejects
connected notifications for standby/disconnected configurations.

The disconnected integration test passed in `/software/test-_78bl3p6`: original
VBS decoded state 2, VIM/VBS/system startup passed, and no connected notification
was emitted. An earlier run appeared to fail because `debugfs` read an unreplayed
ext4 journal after forced guest poweroff. Replaying the journal on a copy recovered
the original diagnostics, including state 2. The harness now replays only the
disposable output disk's journal after QEMU exits, before extracting artifacts;
the original decoding and startup assertions remain unchanged.
The connected regression also passed in `/software/test-_ecwd91r`, including
the original system's connection notification and VBS's stopped request timer.
The project `just test` checks passed after the extraction fix.
