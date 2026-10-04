# Compositor translation fast path

The lab CPU output previously invoked Winston's inverse projective transform
for each of 384,000 output pixels in each view, including identity views.
The original transform at `winston` 0x1b5dc calls `wlxs_view_update_transform`
at 0x1b604 and the matrix helper at 0x1a618. That helper performs double
precision products and division for every coordinate pair.

The recovered view fields at offsets 52 and 32 identify a custom transform
and local clipping respectively. When the custom-transform flag is zero,
`wlxs_view_update_transform` at 0x1ad9c–0x1ae44 installs an identity matrix
with integer translation. The software plugin now calls the original routine
once to update the view and recover its origin, then increments integer
coordinates. Clipped/custom views and extreme integer ranges retain the
original per-pixel path. Blending, surface offsets, view ordering, scheduling
and callback rules are unchanged; no vendor binary or animation deadline is
patched.

```sh
just software-draw-test --kernel-profile vmsplit2g
just software-draw-probe --seconds 90
just software-frame-profile --kernel-profile vmsplit2g --trace-transitions --seconds 90
# Compare with the retained original per-pixel implementation:
just software-frame-profile --kernel-profile vmsplit2g --trace-transitions --reference-draw --seconds 90
```

`--verify-draw` compares local coordinates and inclusion against original
Winston at every output pixel for each eligible draw. A mismatch logs its
coordinates and aborts; verification also requires a live compositor before
shutdown. This diagnostic incurs the original transform cost, so it must not
be used as a fast-path timing benchmark. `--reference-draw` disables the fast
path for comparisons and is mutually exclusive with verification.

## Evidence

The initial exact color-bar run `/software/test-_uuyx3kd` matched all 384,000
coordinates and required exact output pixels, the real Wayland frame callback
and clean shutdown. Full original UI run `/software/test-_ij5v6oy` matched
103 draws (39,552,000 coordinates), with no mismatch. All those views were
unclipped and at origin zero, so this does not verify moved or custom views.
The full comparison preceded the additional explicit compositor-liveness
gate; its HomeScreen screenshot was visually inspected.

The uninstrumented fast-path startup `/software/test-drz7sjxy` retained 96
complete frames. Paint median/p95/max was 31.01/83.99/97.52 ms, compared with
121.59/331.35/410.68 ms in the preceding per-pixel run `test-ea_xg5bw`.
Total frame median changed from 169.75 to 101.42 ms. These are separate boots
with mixed frame content and scheduling effects, not a controlled speedup
ratio. Diagnostic PPM saving remained substantial (median 52.95 ms).

The final exact color-bar replay `/software/test-bdqzkso2` passed with the
explicit liveness gate and the conservative fallback for clipped views.

Original VBS and selected audio services reached STARTED, with no JavaScript
exceptions, heartbeat misses or database semaphore failures. Both animation
watchdogs remained. HomeScreen's listener was installed at 20:23:27.531 UTC;
the watchdog fired at 20:23:29.518 and incoming animationstart appeared at
20:23:31.476. Reducing compositor transform work alone did not resolve the
browser's late incoming animation.

## Nonzero positioning coverage

`just software-draw-position-test --verify-draw` uses the original browser's static test page
and stock `ivi-shell -p` to request positive (40,25) and negative (-30,-20)
pixel translations. It retains each PPM and checks every pixel against a
shifted baseline, including black outside the viewport. This is distinct from
matching the previous output plugin: it checks the requested visible behavior.
Run `/software/test-e6gxl6kt` failed the requested-position pixel gate while
passing five every-coordinate comparisons and explicit compositor liveness.
Both original IVI commands returned zero. Its baseline contained the visible
browser test page, but both positioned images were completely black. A move
of (40,25) gave inverse origin (-10240,-6400); (-30,-20) gave (7680,5120).
These are translations multiplied by 256. Original bounding-rectangle code at
0x1af64 shifts input pixel coordinates left eight bits and at 0x171dc/0x171f4
converts the result back. The output plugin passes unscaled pixel coordinates
to the fixed-point transform and uses its result directly as a pixel index.

This is an existing output-adapter coordinate-unit defect, independently of
the startup animation delays. Matching the previous implementation does not
prove positioned views are rendered correctly. The requested-position check
retains its failing result; no output expectation has been relaxed. Correcting
the adapter's input/output coordinate conversion is a separate next change,
pending the user's decision under the project instruction to report code
issues and let the user decide how to proceed. It requires rechecking custom
transforms, clipping and fractional positions as well as ordinary startup.
`just test` passed independently; it does not cover this failing integration
contract.

The explicit original-path replay
`just software-draw-position-test --reference-draw` also failed in retained run
`/software/test-4kpco4lr`. This confirms the positioning failure is present
without the fast path.
