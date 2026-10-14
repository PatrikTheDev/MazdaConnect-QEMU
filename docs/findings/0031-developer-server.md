# Vehicle developer server and independent live instances

The supported EU 74.00.324A firmware's `developer_mode.sh on` creates
`/data/integration/developer_mode_on_flag`, enables its Ethernet flag, and copies
the developer GUI configuration into `/data/integration`. Its `start_network.sh`
starts the original BusyBox HTTP server on port 80 with `/jci/gui` as the document
root when the developer flag exists. `GuiConfig.js` derives its WebSocket host
from the HTTP document URL and uses ports 2700 (MMUI), 2766 (DBAPI), and 2800
(AppSDK).

Observed source SHA-256 values:

| Original input | SHA-256 |
| --- | --- |
| `jci/scripts/developer_mode.sh` | `ebe9e9a66fb49126aabad04d285e2b1cb35909d8cc8d38fec6e2fc5fde42c757` |
| `jci/scripts/start_network.sh` | `ec5139bd1cfda9e138d309847f3f81508c2308b5126a5a1f9af2fb67ecb8dc70` |
| `jci/gui/common/js/GuiConfig.js` | `dadf225a4d42637985be69136f0ae59b37636de19dbe3b28133a0ec013eb1833` |
| `jci/gui/common/transitions/js/Transitions.js` | `d2ff7c0da76757d3aa211dcf99708976c1b0b34c9365664336a3618f77b6ab08` |
| `jci/gui/framework/js/Websockets.js` | `40e21c3e7e661174f06b65c234788b3f0a78445685e0d784677f3dabc460cbd2` |

## Lab network adaptation

`--developer-mode` runs the original developer helper and adds a virtio Ethernet
adapter. The generated overlay contains the selected kernel's `virtio_net`
module and its dependencies, checked for matching vermagic and loaded only in
developer mode. The guest uses `eth0`, `10.0.2.15/24`, and gateway `10.0.2.2`.
The gateway route is required even for incoming forwarded requests: SLIRP
preserves non-loopback clients' source addresses, so their replies need a route
outside the guest subnet.

QEMU uses `restrict=on,ipv6=off` and explicitly forwards container TCP port
8080 to guest port 80, with unchanged WebSocket ports. Docker publishes these
only on host loopback and only when a developer option is supplied. The restricted
network permits explicit forwards while blocking guest outbound access, as
described in the [QEMU invocation documentation](https://www.qemu.org/docs/master/system/invocation.html).

`start-dev-server` checks the same developer flag before starting the original
HTTP executable and document root. It replaces the vehicle's i.MX/USB driver,
DHCP, firewall and SSH orchestration with the lab's virtual adapter configuration;
it does not execute the original full network startup script. HTTP runs in the
foreground as a background shell job so its diagnostics are retained.

## Browser compatibility

The original transition constructor calls `window.opera.version()` unconditionally
and later rejects non-Opera browsers through its fatal logger. The approved
developer-only adaptation checks that the version API exists before calling it
and logs a warning for other browsers. The legacy Opera version branch remains.
`build_browser_compat.py` verifies the complete original hash and each expected
patch site before generating a separate file. The original firmware inputs and
software sysroot remain unchanged. Generated patch hashes are retained in
`browser-compat.json`.

The original MMUI frame decoder constructs a `Uint8Array`, takes its `.buffer`,
then reads `.length` and indexed bytes from that `ArrayBuffer`. These properties
are undefined in Chromium, so the JSON length and trailing sequence byte are
lost for screen-context messages. The approved correction removes only the
`.buffer` access and retains the typed view. JSON contents, sequence bytes and
the native WebSocket wire format remain unchanged.

The builder generates both decoder-only and queue-plus-decoder variants, checking
the original source hash and the existing queue correction's output hash before
applying the exact decoder edit. Developer startup selects the variant according
to `LAB_WEBSOCKETS_QUEUE_FIX`; it does not silently enable or remove that separate
correction. Both variants' input/output hashes are retained in the browser patch
report. Normal boots retain the existing queue behavior and original decoder.

`--remote-gui` enables the same developer flag and network but leaves guest Opera
stopped, allowing the desktop browser to be the sole GUI client. The compositor,
original services and intro-video player still start in the guest.

## Independent live runs

Live runs keep an instance-name lock, with separate QMP metadata, logs and
captures. The coordinator holds the shared build lock only while building and
copying the selected kernel, initramfs and software runtime disks into the new
run directory. It releases that lock before launching QEMU. Reference-volume
resource disks remain read-only shared inputs. A failed snapshot removes its
partial directory; completed snapshots stay with private diagnostics.

Builds and probes still serialize shared outputs. Each live instance requires a
distinct name and VNC port. Fixed WebSocket ports permit one developer instance
on the same host address; changing `MAZDA_HTTP_PORT` alone cannot change that.
Instances launched by old code still hold the lifetime build lock until they exit.

## Reproduction

```sh
MAZDA_INSTANCE=dev-server MAZDA_VNC_PORT=5902 just start --remote-gui --seconds 240 --start-delay 0
# In another terminal, after LAB_DEV_SERVER_STARTED:
MAZDA_INSTANCE=dev-server just dev software check_dev_server
# Open http://127.0.0.1:8080/ in the desktop browser.

MAZDA_INSTANCE=parallel MAZDA_VNC_PORT=5903 just restart --seconds 120 --start-delay 0
MAZDA_INSTANCE=parallel just status
just dev software task build-ui --kernel-profile vmsplit2g
```

Validation on 2026-10-14 used Apple Silicon macOS and the existing Linux ARM64
Docker tooling. Host HTTP returned the original index; all three WebSocket
upgrades passed accept-key and native-subprotocol checks. Two named live guests
ran concurrently, instance-specific controls selected separate QMP sockets, and
the UI overlay rebuilt successfully while a live guest used its snapshot.
Firmware-free unit/shell/publication and ARM/QEMU smoke checks passed with a
user-approved read-only Git metadata mount for the managed worktree.

With the typed-array correction, Chromium received the real Disclaimer and
HomeScreen contexts with matching numeric sequence counters and all three
WebSockets open. Enter accepted the disclaimer. A browser attached after guest
Opera started also received HomeScreen; the earlier blank second-client view
was the decoder defect, not evidence of a firmware single-client restriction.
The documented `m` rotary key changed the desktop home selection to Settings.
Selecting Settings with Enter then lost the browser page, even with sequential
automation commands and guest Opera running. Complete desktop Settings
navigation is not verified; no additional animation or MMUI adaptation was
applied to bypass this result.

An earlier rapid arrow-key experiment lost its browser page, and MMUI later
stopped after missing GUI health responses. A subsequent automation wait also
failed with a busy-daemon error after overlapping inspection requests. Those
runs do not establish reliable desktop arrow-key navigation or long-session
stability. HTTP delivery and WebSocket upgrades alone do not prove full vehicle
behavior; the validated screen contexts and remaining limits are recorded here.
