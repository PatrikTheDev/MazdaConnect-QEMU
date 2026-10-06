# Software display power control

The approved software service owns `com.jci.lvds` at `/com/jci/lvds` on
`JCI_HMI_BUS`. It implements the power-control subset used by the original system
service. It starts after D-Bus and before the original service manager, using the
private ARMEL runtime. The original LVDS binary and firmware libraries are retained.

Supported methods are `GetDisplayStatus(u)`, and `SetNormalMode`, `SetSleepMode`,
`SetACCOff`, `SetDispOn`, `SetDispOff` with `(uuyy)` arguments. Mode calls return
strings; ACC/display on/off calls return int16. Completion signals carry int16 1.
Unsupported hardware methods return `org.freedesktop.DBus.Error.NotSupported`;
the service does not invent panel firmware versions, HDCP state or diagnostic
results. Introspection and brightness/contrast control are not implemented yet.

## Evidence from the original binaries

The generated `libjcilvds_server.so` embeds the method and signal signatures.
`VideoProxy::init` connects with bus enum 1; `JCIDBUS_conn_connect` maps this to
`JCI_HMI_BUS`. In `svcjciblmsystem.so`:

- `display_normal_confirmed_cb`, address `0xc1b58`, tests acknowledgement against 1.
- `display_sleep_confirmed_cb`, address `0xc1ec8`, also tests against 1.
- `display_status_confirmed_cb`, address `0xc24fc`, requires an array longer than
  six bytes and reads mode at byte 6. Mode 2 is normal, 1 sleep, 3 extended;
  diagnostic mode 0 is also treated as normal by this client.

The `DisplayStatus` signal has signature `(ay)`, a struct containing a byte array.
The vendor default-status helper at `0x39fa0` emits a 17-byte packet. The software
service uses this framing, updates the mode and checksum, and leaves unspecified
hardware fields zero. This is a software-display status, not a serial-device emulator.

## Applied state and verification

The compositor listens on `/tmp/mazda-display.sock` using local sequenced packets.
A two-byte `S,blank` request repaints the actual output before replying; `G,0`
queries applied blanking. Blanking affects both the PPM capture and the VirtIO
framebuffer used by VNC. Normal mode repaints the retained scene. A separate timer
services control requests even when Opera is idle. The service returns a D-Bus
error if the compositor cannot confirm the operation within two seconds.

`just probe --test-page --inspect-surface --verify-display --seconds 20` boots with a real VirtIO framebuffer and a controlled
Opera page. It checks normal/sleep/normal completions, black/visible pixels in both
outputs, the status signal, malformed-request errors and unsupported-method errors.
The full contract/pixel test passed on 2026-09-09, as did `just test`.
The existing exact browser color/text checks still apply. Logs remain in the
retained test disk, including `display.log`; use `just dev software task boot` for live viewing.

## Remaining original-UI blocker

The first full startup with the service confirmed display status and accepted
`SetACCOff`, eliminating the display timeout. GPIO values, edge notifications and
module unload/reload passed. Original GUI/MMUI health-check responses were observed.

However, failed temperature-sensor reads trigger `SYSTEM_SMM_OVER_TEMPERATURE_EVENT`
about five seconds into system-service startup. The firmware then targets standby
and explicitly requests display-off. The resulting black screen is faithful to
that request. Thermal emulation is a separate next step; checks have not been
bypassed. Before the thermal event, the state machine also waits for TAU connection;
afterward it reports waiting for audio-off. Fixing the sensor alone will therefore
not prove that normal startup is complete. Reverse GPIO level
0 is interpreted as reverse-on; the default is now 1 (disengaged). Full CAN/VIP/audio support remains
unimplemented, and interactive original-UI readiness is not asserted.

The missing thermal interface is specifically
`/sys/devices/virtual/thermal/thermal_zone0/{temp,trip_point_0_temp}`.
`system_hsrm_StartPollingTemperature` at `0xfc600` reads the trip point before
creating its timed action. The retained log shows temperature reads every 5000 ms.
The pinned generic kernel has `CONFIG_THERMAL=y` and `CONFIG_THERMAL_HWMON=y`, so
it can expose a real thermal-zone device through the kernel framework. A proposed
sensor should expose configurable temperature and a documented trip threshold,
then verify both normal startup and the original over-temperature transition.
It must not suppress that transition or replace the sensor with ordinary files
under `/sys`. The sensor was subsequently approved and implemented; see
[simulated temperature](0010-simulated-temperature.md).
