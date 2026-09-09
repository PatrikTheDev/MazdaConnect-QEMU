# Original audio startup prerequisites

`just software-audio-probe` runs the original EU audio configuration script,
then traces `/usr/bin/aopen -a` for at most eight seconds in the disposable guest.
It retains `audio.log` in the diagnostic disk. The recipe deliberately remains a
diagnostic and exits nonzero rather than claiming that the original UI is ready.

The 2026-09-09 probe selected `cmu150_EU`, created the stock ALSA configuration
link, and reached ALSA PCM initialization. It then failed to open sound control
devices, including `/dev/snd/controlC0`; the generic guest currently has no sound
card. ALSA reports invalid cards and PCM-open errors. These are missing emulated
audio-device prerequisites, not host Docker permissions.

The stock service-manager configuration orders audio startup as follows:

1. `audio_config` runs `/jci/am/audioconfigupdate.sh`.
2. `audio_start` runs `/jci/am/start_audio.sh`, invoking `aopen -a` and D-Bus trackers.
3. `xsesvc2dbus_service` and `xsesvc2dbus_tau` require the original `jciVBS` service.
4. Lua audio-control, amplifier and management services consume these bridges.

The TAU bridge uses the service bus, name/interface `com.jci.vbs.radio`, path
`/com/jci/vbs/radio`. Audio management control logic is shipped as Lua 5.1 bytecode.
In the system service, `VbsRadioProxy::init` is at `0xbbb30`,
`getTauStatusAsync` at `0xbbc30`, and the status callbacks at `0xbc058` and `0xbc160`.
`AudioProxy` separately invokes `AUDIO_AMSERVICE_enableStatus`, `enable` and
`Notify_enable`. TAU readiness must therefore be investigated separately from
ALSA device availability; reporting audio success alone would not establish it.

No fake audio/TAU success replies, ALSA null-device substitution, or firmware
control-flow patches have been added. The thermal sensor was subsequently approved and implemented; see
[simulated temperature](0010-simulated-temperature.md). Normal original-UI startup
remains unverified.

After the VIP/TAU work, the original system accepts the simulated TAU connection
and explicitly waits for the audio manager. The stock ALSA configuration needs
hardware cards 0 and 1 plus Loopback0, Loopback1, and Loopback2. The pinned ARMMP
kernel enables snd-aloop and HDA codec modules but disables SND_HDA_INTEL, so
adding QEMU's Intel HDA device alone would not create a usable card. QEMU exposes
HDA and USB audio devices. No substitute sound card has yet been installed.

The stock ALSA file implements the named entertainment, information, telephony,
VR, alert, and driver-side volume controls with `softvol` on card 0. These are not
all custom hardware mixer controls: opening the original PCM definitions can
create them on a suitable card. `aopen` traverses the ALSA configuration in
`doCompound` (0x8d60), then opens/closes selected PCM definitions via `doOpen`
(0x8cec). `doOpen` returns zero even when opening fails, so its exit status alone
must not be used as an audio-readiness assertion. Validation should inspect PCM
errors, actual controls and sample transfer. The pinned kernel also provides
`CONFIG_SND_USB_AUDIO=m`; device capture/rate capabilities still need checking
before choosing it for the stock playback/capture configuration.

## HDA diagnostic path

`just software-audio-build` builds unmodified upstream `hda_intel.c` from Debian's
pinned `linux-source-6.1=6.1.176-1` against the matching installed headers. Existing
packaged HDA codec/core modules are reused. `just software-audio-device-probe`
attaches two QEMU HDA controllers with duplex codecs and loads three ALSA
loopbacks at indices 2–4, named Loopback0/1/2. Original card indices 0 and 1 are
preserved. This remains an opt-in diagnostic; normal live boot is unchanged.

Probe `/software/test-nuid2uoi` enumerated both playback/capture cards and all
three loopbacks. `aopen` no longer failed on missing sound cards. It still tried
opening two capture-only softvol definitions for playback, which ALSA rejected.
Thus `aopen` output/exit status is not a complete readiness criterion.

Probe `/software/test-obwnxlsl` set and read the original
`informationMuxGenericIn` mixer control, then played through `informationGeneric`.
`just software-audio-analyze /software/test-obwnxlsl` measured the expected 1 kHz
left and 2 kHz right tones in QEMU's recorded output. Capture exposed two limits:
the WAV backend cannot create an input voice, and unadapted Bluetooth mono
capture fails HDA's channel constraint. Neither capture path passed.

The user approved retaining HDA with an explicit lab adapter. The adapter appends
four ALSA overrides to a tmpfs copy of the selected stock configuration, retaining
the Bluetooth PCM names/rates while converting mono clients to stereo hardware.
Original firmware files remain intact. Configurable microphone data requires an
input-capable QEMU backend and is not implemented yet. Original audio management
services have not yet been enabled or verified.

The first sample-transfer probe also revealed that `aplay` reads interactive
stdin, consuming queued guest commands. The harness now gives the audio check
`/dev/null` stdin; `/software/test-rfth8c6s` completed guest shutdown and retained
Opera output with that correction. The two capture limitations remained explicit.

With the approved adapter, `/software/test-xzny634w` accepted Bluetooth's 8 kHz
mono PCM format: the channel-count error disappeared. Both microphone and
Bluetooth capture then timed out because the WAV backend provides no input
samples. Speaker tone verification still passed (energy fraction 0.411 in each
expected channel), and the guest shut down normally. This establishes format
adaptation and playback, not functioning capture or audio-service readiness.
`just test` and `git diff --check` passed for these changes.

## Input-capable backend checkpoint

The opt-in audio profile now starts a private PulseAudio server in Docker, with
two recorded speaker monitors and a pipe-fed microphone. `--microphone-tone`
accepts 0 (silence) through 3000 Hz; the diagnostic recipe injects 700 Hz. No host
sound devices are used. Server, feeder and recorders are stopped after QEMU,
and output recordings are retained alongside guest-captured WAV files.

Initial run `/software/test-hurxj4zp` completed the original microphone and
Bluetooth capture commands. Sample verification did **not** pass: speaker
recordings were silent, and microphone active samples were too short. Bluetooth
also reported overruns. Mixer state and capture timing remain under investigation;
successful client exit codes are not treated as successful audio emulation.

`software-audio-services-probe` prepares a separate service-manager profile from
the original seven audio service definitions/dependencies, changing only CPU
affinity and disabling lab board resets. It applies the approved ALSA adapter
before starting that profile. This service probe is not yet verified; normal
live boot still uses the existing profile. The checkpoint remains suitable for
continuing device work, not a claim of complete UI or audio startup.

`just software-audio-test` passed in `/software/test-fld5g_xv` after initializing
HDA's initially muted Master/Capture controls and increasing the lab Bluetooth
buffer to 2048 frames with a 512-frame period. The adapter's added buffering is
256 ms at 8 kHz and 128 ms at 16 kHz; this is a lab latency tradeoff for emulation.
Original software mixer controls still apply per-source policy. The verifier
requires original client success, no reported overruns/underruns, clean shutdown,
and measured 1/2 kHz speaker tones plus 700 Hz microphone/Bluetooth capture.
This validates PCM transport, not the original audio manager's startup.

The original audio-service probe subsequently passed its startup milestones in
`/software/test-urh8h9yg`: all seven audio services reached STARTED, followed by
the original system's `system_smm_StateEnter ... SYSTEM_NormalState` message.
The captured compositor frame showed the original five-icon home screen.

Live boot now enables the same VIP/audio path, with optional `--record-audio`
and `--microphone-tone`. Speaker recordings are off by default for long-running
viewers. `just software-key right` (also left/up/down/ret/esc) sends real emulated
keyboard events through QMP. Live output disks now receive journal replay before
log extraction, matching the diagnostic harness.

The first extended live run `/software/live-j6dymcm1` displayed the intro over
VNC but then went black. The display service did not request blanking. Original
Opera logged `OnHeartbeatMissed` at `opengles_main.cpp:1356`, reporting a frozen
main loop and terminating itself; its Wayland surface was then unregistered.
The browser's last trace contained a surface commit without a subsequent frame
callback. This does not yet prove a compositor defect: browser/render-thread
state must be inspected. No watchdog bypass has been applied. Long-running UI
stability and keyboard interaction remain unverified despite the home-screen
render and successful original system/audio startup.
