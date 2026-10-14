# Factory-menu debugging (EU 74.00.324A)

This firmware has a diagnostics keypad (`diag.Diagnostics`) and a separate native
JCI script menu (`/jci/tools/jci-systemDialog`). The latter is reached through
JCI Test Mode, test ID 11. They are different from Settings' factory reset.

## Access and evidence

```sh
just start --factory-debug
# Wait for the home screen, then in another terminal:
just key f2              # SelectDiagnostics: request native diagnostics activation
just key f3              # ActivateJCITest / DeactivateJCITest toggle
just key f4              # ReadDTC with testId 11; requires JCI Test Mode
just capture
```

The shortcuts are lab JavaScript injected into a separate, hash-verified copy of
`jci/gui/index.html`. They use `framework.sendEventToMmui`; `framework.debugMode`
is not enabled. F2 sends `syssettings.SelectDiagnostics`; the original
`UIA_SYSSETTINGS_SendGlobalActivateDiag` handler injects native activation for
`diag`. F3/F4 require the actual diagnostics context, and F4 requires the
backend-reported `JCITestMode`. Requests are logged as `LAB_FACTORY_EVENT` in
`syslog.log`, alongside original MMUI/service logging. Navigation and test
results remain native firmware behavior. The native script dialog uses pointer
input; use the VNC mouse for its buttons.

The opt-in SM profile adds stock `jciTestDiag`, preserving its dependencies on
`jciVBS` and `system_mazda_my14`. Its lab adaptations are CPU affinity 0, no board
reset on failure, and zero retries. `factory-debug.json` records source hashes
and the generated HTML hash. No vendor binary is patched. The original extracted
firmware and reference initramfs remain unchanged. A normal boot omits this mode.

## How the event path works

`jci/gui/apps/diag/js/diagApp.js` sends `DiagLoaded` when its screen is ready.
Enter sends `ReadDTC` with `{payload: {testId: <number>}}`; Clear sends `ClearDTC`;
Exit sends `Deactivation`, or `EndTest` when the backend changes its label to END.
Long press toggles `ActivateJCITest` / `DeactivateJCITest`. The native
`libjciuiadiag.so` bridges these events to `com.jci.testdiag` methods including
`ActivateTestMode`, `ActivateJCITestMode`, `StartRoutine`, `StopCommanderRoutine`,
and `DeactivateTestMode`. UI feedback comes back as `TestModeStatus`, `TestInfo`,
`TestStatus`, `DataResponse`, and `GUIState` messages.

In JCI mode, `svcjcitestdiag.so` invokes
`/jci/scripts/startSystemScripts.sh <number>`. In this version, that script only
implements 11, launching `jci-systemDialog`. Entries 12–20 are placeholders;
the script prints that only 11 is used. The native dialog invokes
`/jci/scripts/systemHooks.sh <action>`; its exit status selects the result dialog.
Those statuses frequently describe the requested toggle, without verifying that
the underlying hardware operation succeeded.

## Every JCI script-menu option

These are observations from the original scripts, not verified effects in QEMU.
Action IDs belong to `systemHooks.sh`, not the diagnostics keypad.

| Menu option | Action ID | Underlying operation |
| --- | --- | --- |
| HDCP TOGGLE | 1 | `set_hdcp_config.sh`: write `lvds_hdcp_mode=enable/disable` through NVRAM add/key/commit nodes. |
| SPEED TOGGLE | 4 | `set_speed_restriction_config.sh`: persist `bus_bcm_speed_restriction`. |
| DEV MODE TOGGLE | 7 | `developer_mode.sh`: create/remove developer and Ethernet flags in `/data/integration`; copy/remove the developer GUI config. |
| CPUGAUGE TOGGLE | 10 | `jci-cpugauge.sh`: start/kill `jci_cpu_gauge`, alter `cpugauge_off_flag`. **Stock mismatch:** hook tests `cpugauge_on_flag`, which that script does not create. |
| DISPLAY TOGGLE | 13 | `set_display_config.sh`: persist `lvds_display_type` as `jci` or `visteon`. |
| RESET MAP | 16 | `resetmap`: sends a signal to PID 1 (`kill 1`); this is a system reset request, not a script that deletes navigation maps. |
| RESET VIP | 17 | `resetvip`: drive the original `Reset VIP` GPIO high, then low. |
| USB DRIVER | 18 | `usb_drivers.sh`: load USB serial/HID/MTP/storage/audio modules, CMU I²C and USB gadget drivers; bring up `usb0`; create readiness flag. Paths target the original 3.0.35 kernel. |
| TAUSIM TOGGLE | 19 | `jci-tausim.sh`: create/remove `/data/integration/tau_connected_sim_on_flag`. This is distinct from the lab VIP simulator's `--tau-state`. |
| TERMINAL | 22 | `run-terminal.sh`: load USB HID, launch fullscreen `/usr/bin/terminal`, focus and raise its Wayland surface; explicitly uses `/tmp` as the display socket directory. |
| WIFI AP TOGGLE | 25 | `jci-wifiap.sh`: configure `wlan0` as 192.168.53.1/24, generate hostapd/DHCP configs, start/stop hostapd and udhcpd. Requires original wireless hardware/driver. |
| USERTTY TOGGLE | 28 | Inspect `/data/log/syslog-ng.conf`, then call `jci-log.sh usertty enable/disable` to change terminal logging. |
| LVDS SPEED TOGG | 31 | `set_lvds_speed_restriction_config.sh`: persist the independent `lvds_speed_restriction` NVRAM key. |
| *.vcf FILE TOGGLE | 34 | Native `/jci/pb/pbDebugToggle` reads/inverts/writes registry boolean `com/jci/blm/pb/pbKeepImportedVcfFile`: retain imported contact VCFs for debugging. Dialog says a long ACC cycle is required. Consumers' exact file-retention behavior remains untraced. |
| DelBDSFiles TOGGLE | 37 | Native `/jci/msg/msgsDebugToggle` reads/inverts/writes registry boolean `com/jci/cpp/msgs/DeleteBDSFiles`. Dialog says a long ACC cycle is required. Exact downstream BDS-file deletion policy remains untraced. |
| NNG DEBUG TOGGLE | 40 | `set_nng_debug.sh`: repoint `/data/debug_options.ini` to NNG debugging ON/OFF INI. **Stock mismatch:** hook passes uppercase ON/OFF; the script compares lowercase `on`/`off`, so it can print usage while the dialog reports a toggle. |
| HCI LOG TOGGLE | 43 | `set_hci_logging.sh`: toggle `uartsnifferenable` in `/jci/bds/BdsConfiguration.xml`, default log `/tmp/hci_btsnoop.log`, sync. Requires the Bluetooth stack to consume that configuration. |
| NAVIGATE TOGGLE | 46 | `set_navi_gate_config.sh`: toggle `/data/NaviGate.enabled`; enabling stops the firewall and LDS, starts `nmeaSimApp`, and replaces `/dev/ttymxc2` with a PTY link; disabling attempts UART restoration and LDS restart. |

## Every diagnostics entry

The backend has 58 ID/name slots: the first 48 are normal diagnostics, the last
10 are JCI-only. `TESTDIAG_GetTestInfo_svc` also filters entries for its vehicle
variant. The following describes the requested function; a catalogue entry does
not establish that the lab implements its hardware or that the routine succeeds.
Native names and service-interface symbols support these descriptions. Exact
routine request payloads and all subtests still require per-handler disassembly.

| ID | Option / requested operation | Backend area |
| --- | --- | --- |
| 1 | CD mechanical test | VBS CD/DVD routines |
| 2 | Clear diagnostic trouble codes | VBS diagnostic clear requests |
| 3 | Read AVC trouble codes | VBS diagnostics |
| 4 | Read CMU trouble codes | VBS `ReadCMUFaults` |
| 5 | Read TAU trouble codes | VBS radio/diagnostics |
| 6 | Read CD trouble codes | VBS CD/DVD |
| 8 | Software reset AVC | VBS routine/reset requests |
| 9 | CD software version | VBS CD/DVD identification |
| 10 | CD/DVD part number | VBS CD/DVD identification |
| 25 | Antenna continuity status | VBS radio |
| 28 | HD certification, main tuner AM | Radio certification state machine |
| 30 | Copy recorded vehicle data to USB | VDT data-transfer workflow |
| 31 | Clear all recorded vehicle data | VDT clear workflow |
| 32 | Clear heater data | VDT clear workflow |
| 33 | Clear brake data | VDT clear workflow |
| 34 | Clear battery data | VDT clear workflow |
| 53 | CMU software version | CMU identification helpers |
| 57 | VIP software version | VBS identification |
| 58 | Vehicle info | Vehicle-information decoding |
| 59 | CMU serial number | CMU identification helpers |
| 61 | Vehicle signals / unit status | CMU vehicle-signal helpers |
| 65 | Commander and switch check | Native input reader / VBS switch events |
| 68 | TFT display software version | LVDS `GetSoftwareDispVersion` |
| 69 | Touch-panel software version | LVDS `GetSoftwareTPVersion` |
| 70 | Display check | LVDS TFT routine / test surfaces |
| 72 | GPS data | LDS position/satellite requests and timer |
| 73 | Dead-reckoning unit data | LDS DR test-screen requests |
| 74 | NEO-M8L data | LDS u-blox diagnostics |
| 75 | Clear NEO-M8L backup data | LDS backup-data clear |
| 81 | Clear iAP ID data and reset CMU | Native reset workflow; do not treat as read-only identification |
| 82 | Clear XM data | XM data-clear workflow |
| 83 | DAB test | VBS radio DAB responses |
| 84 | TAU maker code | VBS radio identification |
| 85 | TAU part number | VBS radio identification |
| 86 | AM radio test mode | VBS radio test-mode variation requests |
| 87 | HD certification, main tuner | Radio certification state machine |
| 88 | HD certification, sub tuner | Radio certification state machine |
| 89 | XM certification | XM certification state machine |
| 90 | AM reception sensitivity | Radio reception routine |
| 91 | Main radio tuner test mode | VBS radio test-mode variation requests |
| 92 | Sub radio tuner test mode | VBS radio test-mode variation requests |
| 93 | TAU software version | VBS radio identification |
| 94 | Speaker cyclic test | VBS audio routine |
| 95 | TAU vehicle info | VBS TAU vehicle-information request |
| 96 | XM serial number | XM ESN request |
| 97 | AM field strength | Radio frequency/signal measurements |
| 98 | FM field strength | Radio frequency/signal measurements |
| 99 | System update | MMUI transition into the original `sysupdate` app |
| 11 | JCI_TESTID1 | In JCI mode: launch the script menu via `startSystemScripts.sh 11`. |
| 12–20 | JCI_TESTID2 through JCI_TESTID10 | No script action implemented in this version. |

## Reproduce the analysis

```sh
just dev software factory_catalogue
just dev software inspect_abi jci/mmui/uia/libjciuiadiag.so 0x2f90 0x31f8
just dev software inspect_abi jci/testdiag/svcjcitestdiag.so 0x121c4 0x12420
```

The catalogue reader checks the service's SHA-256 before reading `g_testIDs`
(VA `0x7666c`, offset `0x6e66c`, 58 uint32s) and `g_testNames` (VA `0x76754`,
offset `0x6e754`, 58 strings of 50 bytes). `TESTDIAG_GetTestInfo_svc` at `0x121c4`
selects 48/58 entries. Local scripts and binary exports are proprietary inputs;
the public repository contains analysis and patch procedures, not copies.

## Limits

Live validation on 2026-10-14: `just start --factory-debug --seconds 240`, then
F2/F3/F4 after the home screen rendered, opened the original keypad, reported
`JCI Test Mode Active`, and displayed the native script dialog. Screenshots are
private `artifacts/factory-debug-diagnostics.png` and
`artifacts/factory-debug-script-menu.png`; run diagnostics are retained in
`/software/live-*`. No menu action was executed during this access test.
`just test` passed 24 unit tests, shell checks, the publication guard, and the
ARM/QEMU initialization smoke check. This verifies access, not every test action.

The lab does not supply original NVRAM, wireless hardware, the complete LVDS
diagnostic interface, navigation/DR services, or the full radio/CD/Bluetooth
stack. Those menu actions can fail or time out. The factory result dialog is not
proof of success. Original scripts can also reference the original Wayland socket
or kernel modules. No substitute handlers or fabricated success responses are
introduced by this debug mode. Script-level mismatches listed above remain stock
behavior; correcting them would be a separate, documented firmware adaptation.
The original diagnostics service also reports missing `/config-mfg/fgsn.dat` in
this lab; CMU serial-number results are not backed by a real device inventory.
