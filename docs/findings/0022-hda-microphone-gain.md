# HDA microphone gain under the original Mazda control name

The user approved exposing HDA capture gain as `MIC Level`, with a documented
lab mapping rather than claiming the vehicle codec's original gain curve.

Original `Set_CPP_aal_mixer` at 0x933b8 in `svcjciblmsettings.so` calls
`AAL_SetMixerElementVolumePercent` with direction 1 and all channels. In
`libjciaal.so` at 0x7038, direction 1 selects capture-volume APIs. The stock
`mic`, `mic_hw` and shared capture routes ultimately use card 0's capture
device. The missing mixer name caused settings writes to fail.

`mazda_hda_mic.ko` renames card 0's existing `Capture Volume` control to
`MIC Level Capture Volume`. ALSA exposes it as simple element `MIC Level`,
with capture-volume capabilities. The module requires card ID `CMU`, uses
`snd_ctl_rename_id`, and fails if the expected card/control is absent. Unload
restores the name. It does not replace control callbacks, PCM routes, samples,
range, channel count or gain behavior. `Capture` remains the capture switch.

The software audio loader installs this mapping after HDA initialization.
`configure-audio` enables capture and initializes `MIC Level` at 100%; original
settings can then apply its own requested gain. Card 1 Bluetooth is unchanged.
No Mazda binary or reference artifact is modified.

## Actual gain behavior and limitation

The pinned lab reports HDA raw range 0–74. At 100%, ALSA reports raw 74 and
0 dB; at 50%, it reports raw 37 and **−37 dB**. However, actual PCM attenuation
through the QEMU/PulseAudio backend is approximately **0.124 amplitude**
(about −18.2 dB), so the reported HDA dB figure is not an accurate calibration
of this backend's resulting audio.

Upstream QEMU 7.2's [HDA gain conversion](https://github.com/qemu/qemu/blob/v7.2.0/hw/audio/hda-codec.c)
scales raw gain into 0–255; 37/74 becomes 127. Its
[PulseAudio backend](https://github.com/qemu/qemu/blob/v7.2.0/audio/paaudio.c)
scales this into `pa_volume_t`, whose amplitude conversion is nonlinear. The
verifier calls the installed `pa_sw_volume_to_linear` to calculate the expected
amplitude for that value. The mapping preserves this existing backend behavior;
it does not correct QEMU's reported dB scale or reproduce vehicle calibration.

## Verification

```sh
just probe --audio-devices --microphone-tone 700 --probe-audio --probe-vip-service --verify-audio --verify-mic-gain --seconds 10 --debug-services
just dev software check_mic_gain /software/test-n70cobb9
```

The diagnostic uses a private 700 Hz microphone source. It records full gain,
sets `MIC Level` to 50%, records again, and restores full gain. It checks mixer
operation statuses, format, sufficient samples and middle-window RMS on both
channels, excluding opening/closing transients.

In `/software/test-n70cobb9`, both channels measured full RMS 5651.8 and
half-control RMS 697.9, ratio **0.123**, versus predicted **0.124**. Original
speaker left/right tones, microphone tone and Bluetooth mono tone also passed.
The initial diagnostic expected linear percentage-to-amplitude behavior and
correctly failed that assumption. Re-analysis against the documented backend
conversion passes; the acceptance band is ±10% of the source-derived value,
not a fitted range around the observation. `just test` passed.

A fresh complete `just probe --audio-devices --microphone-tone 700 --probe-audio --probe-vip-service --verify-audio --verify-mic-gain --seconds 10 --debug-services` passed in
`/software/test-03ki971y`: full RMS 5649.2 and half-control RMS 697.9 on both
channels, ratio 0.124. Playback, microphone and Bluetooth tone checks also
passed, and the guest shut down cleanly.

Full original-settings startup was verified in `/software/test-ke51c_kg` with
`just probe --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --seconds 90`. The original settings service
logged four successful `Set_CPP_aal_mixer` calls (`Attenuation Value Set`), with
zero missing `MIC Level` controls or mixer-call failures. Selected settings,
audio, system, VBS, database, time and UI services reached STARTED. The captured
original home screen displayed Communication and the clock at 00:12.

This boot had no JavaScript exceptions, heartbeat misses or database semaphore
failures. The two existing startup animation watchdog fallbacks remain, as do
subscriptions to application services not yet included in the lab configuration.
