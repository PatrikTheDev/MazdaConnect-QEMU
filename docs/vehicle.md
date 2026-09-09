# Read-only vehicle inventory

Collect exact firmware versions and hardware identifiers before comparing a
physical CMU with the reference package. Keep that inventory private.

Read `scripts/vehicle/inventory.sh` before use. It prints kernel, mounts, partition
information, processes, device nodes and selected directory listings. Missing paths
are normal across firmware versions. It does not change mounts, watchdogs or files.

Once the existing root SSH method is known, a typical host invocation is:

```sh
ssh root@VEHICLE 'sh -s' < scripts/vehicle/inventory.sh > artifacts/vehicle-inventory.txt
```

Replace VEHICLE with the known address; do not run the command without confirming
the access method. Nothing in the lab connects to the vehicle automatically.
Record the full OS/recovery versions from the vehicle's version screen in
an ignored `config/firmware/vehicle.local.json`, using `vehicle.example.json` as
a template. Review logs before sharing; command lines and boot
arguments can include device-specific information.

Do not guess a `dd` command. First identify block versus MTD storage, mount state,
and the exact required partitions. A mounted-filesystem copy is not necessarily a
consistent or complete restore image. Plan an appropriate read-only acquisition
after reviewing the inventory.
