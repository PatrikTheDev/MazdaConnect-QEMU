# Configurable simulated temperature sensor

The approved sensor is part of `mazda_gpio.ko` and registers a real Linux thermal
zone, `thermal_zone0`, named `mazda-lab`. The original system service reads its
`temp` and `trip_point_0_temp` attributes without patches. Module initialization
fails explicitly if another sensor already owns zone 0.

All values use millidegrees Celsius. The default temperature is 25000 (25°C), and
the default trip threshold is 95000 (95°C). These are documented lab settings,
not recovered vehicle calibrations. Both accept values from -40000 to 150000.
The threshold is a passive thermal trip: the original firmware remains responsible
for its overheating state transition, rather than the kernel powering off the
QEMU guest at a critical trip.

Start the live viewer with chosen values:

```sh
just software-boot --temperature 35000 --trip-temperature 90000
just software-view
```

`software-run` accepts the same options after rebuilding the guest once. The
threshold is set at module load and remains read-only until reload/reboot because
the firmware caches it during startup. Temperature can change while running. In
the guest shell:

```sh
echo 105000 > /sys/module/mazda_gpio/parameters/temperature
cat /sys/devices/virtual/thermal/thermal_zone0/temp
echo 25000 > /sys/module/mazda_gpio/parameters/temperature
```

`just software-thermal-test` checks live reads, bounds, the threshold, and module
unload/reload. It starts the original services at 25°C, requires no overheating
event before a logged injection, then sets 105°C and requires the original
`SYSTEM_SMM_OVER_TEMPERATURE_EVENT`. It restores 25°C before shutdown. This verifies
thermal behavior; it does not claim that the original UI or audio stack is ready.

Verification on 2026-09-09: `just software-thermal-test` passed with two successful
sysfs/lifecycle checks, no overheating before injection, and the original firmware
over-temperature event afterward. `just test` also passed. TAU/audio readiness is
still outstanding; normal original-UI startup is not complete.
