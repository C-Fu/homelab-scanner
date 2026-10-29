# homelab-scanner

`homelab-scanner` is a small, read-only inventory tool for Linux homelabs. It
collects live information about listening ports, Docker workloads, volumes,
compose stacks, host services and disk usage, then writes a Markdown report and
prints the same report to the terminal.

The goal is to replace a hand-maintained `service-inventory.md` with a report
that can be regenerated at any time from the current state of the machine.

## Features

- **System summary** — hostname, OS, IP addresses, firewall state, root
  filesystem usage, RAM and uptime.
- **Listening ports** — detects TCP and UDP listeners with `ss`, `netstat` or
  `/proc/net`, then labels each port with its Docker container, systemd unit or
  process name.
- **Docker inventory** — containers, images, published and internal-only ports,
  stopped containers, Docker storage usage and named volumes.
- **Reverse proxy routes** — discovers Traefik HTTP routes from the Traefik API,
  with a container-label fallback.
- **Service sizes** — per-stack image size, bind-mount data size and totals.
- **Host services** — running systemd services with ports and a best-effort size
  estimate.
- **Compose stacks** — scans local compose files, reports configured ports,
  running/idle state and on-disk size.
- **Disk and reclaim overview** — large directories, disk totals, idle stack
  data, unused volumes and other non-destructive reclaim candidates.

## Requirements

- Linux. The prebuilt `homelab-scanner` binary is for **x86-64** and does not
  require Python to be installed.
- To run the source script, use Python **3.8 or newer**.
- No third-party Python packages are needed at runtime; everything uses the
  standard library.
- Optional tools are used when present:
  - `docker` and the Docker Compose plugin
  - `systemctl`
  - `ss` or `netstat` (there is a `/proc/net` fallback)
  - `du`
  - `nft`, `ufw` or `iptables`
  - `findmnt` and `hostname`

Run as root (or with access to the Docker socket and protected directories) to
get complete results. Without that access, the script still runs and simply
leaves unavailable sections empty or approximate.

## Project layout

```text
homelab-scanner/
├── homelab-scanner          # prebuilt Linux x86-64 executable
├── homelab-scanner.py       # portable source script
├── homelab-report-YYYYMMDD-HHMMSS.md
├── README.md
└── README.ms-MY.md
```

The report filename contains the local date and time, for example
`homelab-report-20261029-105726.md`. Each run creates a new report instead of
overwriting an older one. Both the binary and the source script use the same
filename pattern and write the report next to themselves by default.

## Installation

Place the project directory anywhere on the host. For example:

```bash
cd ~
# copy or clone the homelab-scanner directory here
cd ~/homelab-scanner
chmod +x homelab-scanner homelab-scanner.py
```

No installer, virtual environment or `pip install` step is required to run the
prebuilt binary or the source script.

## Usage

### Prebuilt binary

Generate a timestamped report and print it to the terminal:

```bash
cd ~/homelab-scanner
./homelab-scanner
```

The binary is a PyInstaller build for Linux x86-64. It includes its own Python
runtime, so Python does not need to be installed. It does, however, depend on
the host's glibc and Linux kernel, so use it on a system with a compatible or
newer glibc than the build host (Debian 12 / glibc 2.36). To use it on another
architecture or an older distribution, rebuild it on that target.

### Python script

Run the portable source version with:

```bash
cd ~/homelab-scanner
./homelab-scanner.py
```

Equivalent invocation with an explicit interpreter:

```bash
python3 ~/homelab-scanner/homelab-scanner.py
```

By default the report is written next to the executable or script as
`homelab-report-YYYYMMDD-HHMMSS.md`, and the same content is printed to stdout.
A short confirmation such as `wrote /root/homelab-scanner/...md` is printed to
stderr.

### Common commands

The binary and the Python script accept the same options. The examples below
use the binary; replace `./homelab-scanner` with `./homelab-scanner.py` to use
the source version.

```bash
# Print only, without creating a file
./homelab-scanner --no-file

# Print only, explicitly to stdout
./homelab-scanner -o -

# Write to a specific path
./homelab-scanner -o /tmp/homelab.md

# Faster run: skip deep du measurements
./homelab-scanner --fast

# Skip compose-file scanning
./homelab-scanner --skip-compose

# Scan additional or different roots for compose files
./homelab-scanner --scan-root /opt --scan-root /srv
```

### Rebuilding the binary

The binary must be built on the platform and architecture where it will run.
With Python and pip available:

```bash
cd ~/homelab-scanner
python3 -m venv .venv-build
. .venv-build/bin/activate
python -m pip install --upgrade pyinstaller
pyinstaller --onefile --clean --noconfirm \
  --name homelab-scanner \
  --distpath . --workpath build --specpath build \
  homelab-scanner.py
```

The resulting executable is `~/homelab-scanner/homelab-scanner`. The `build/`
directory and `.venv-build/` are temporary build artifacts and can be removed
afterwards.

### Options

| Option | Description |
|---|---|
| `-o`, `--output PATH` | Write the report to `PATH`. Use `-` for stdout only. The default is a timestamped `homelab-report-YYYYMMDD-HHMMSS.md` next to the executable or script. |
| `--no-file` | Print the report but do not write a file. |
| `--fast` | Skip deep `du` measurements. Structure and port data are still collected, but sizes may be missing or zero. |
| `--skip-compose` | Skip scanning for compose files and idle compose-stack sizes. |
| `--scan-root PATH` | Add a root directory to scan for compose files. Can be repeated. Defaults: `/root`, `/home`, `/srv`, `/opt`. |
| `--max-stacks N` | Number of compose stacks shown in the report (default: 15). |
| `--max-volumes N` | Number of Docker volumes shown in the report (default: 15). |
| `--version` | Print the script version. |
| `-h`, `--help` | Show all command-line options. |

## Report contents

The generated Markdown report contains these sections, depending on what is
available on the host:

1. **System** — host, OS, IPs, firewall, disk, RAM, uptime and Docker version.
2. **Listening ports** — port, protocol, service/container label and bind scope.
3. **Container port mappings** — published and internal-only container ports.
4. **Reverse proxy routes** — Traefik host rules and backend targets.
5. **Running Docker services** — image size, bind data size and total per stack.
6. **Host services** — running systemd units, ports, PIDs and estimated size.
7. **Docker storage** — image, container, volume and build-cache usage.
8. **Volumes** — measured size, owner labels and active/unused state.
9. **Stopped containers** — stopped or created stacks and their image sizes.
10. **Compose stacks on disk** — configured ports, running/idle state and size.
11. **Migrated/legacy app data** — optional Runtipi migrated application data.
12. **Disk usage** — large directories and filesystem totals.
13. **Totals and reclaim candidates** — summarized buckets and cleanup hints.

## How sizes are calculated

Sizes are intentionally labelled as approximations.

- **Docker image size** is the image's virtual size. Shared layers are counted
  for each image, so a sum of running image sizes is not the same as physical
  disk consumption.
- **Docker data size** is measured from bind mounts with `du`. If bind mounts
  are nested, the most specific mount is used to reduce double counting.
- **Named volumes** are measured from their Docker mountpoints.
- **Compose stack size** is the `du` size of the stack directory. Only the
  shallowest compose project in a directory tree is counted.
- **Host service size** covers a detected package directory from the executable
  path plus the systemd `StateDirectory`. It does not include all shared system
  libraries or runtime data.
- **Filesystem and Docker storage** figures come from the host and Docker, and
  may use different accounting methods.

A full run can take several minutes on a busy host because it walks large
directories such as `/root`, `/var/lib/docker` and `/opt`. Use `--fast` when you
only need the structure and do not need deep size measurements.

## Safety

The scanner is **read-only**:

- It does not stop containers, delete files, prune images or modify firewall
  rules.
- Reclaim candidates are informational only.
- Commands such as `docker system prune -a --volumes` are **never executed** by
  this script.

Review anything before deleting it. Docker's reclaimable totals are estimates
and may include data used by stopped containers or shared layers.

## Limitations

- The script targets Linux. It relies on `/proc`, systemd and Linux filesystem
  behaviour for some sections.
- A firewall summary is only a best-effort description of the host's rules; it
  is not a complete security audit.
- Port-to-service labels depend on process visibility. Run with suitable
  permissions for the most accurate results.
- Container names are resolved from cgroups where possible, with published-port
  mappings as a fallback.
- Timeouts or missing optional tools can leave individual sizes or sections
  empty without failing the whole report.

## Troubleshooting

**Docker sections are empty**

Check that the Docker daemon is running and that the current user can access
the Docker socket:

```bash
docker version
docker ps
```

**Ports show `?` or only a process name**

Run the scanner as root, or with permission to inspect the relevant processes.
Some listeners cannot be attributed without elevated access.

**Sizes are missing or the run is slow**

This is usually caused by `du` traversing large or remote filesystems. Try:

```bash
./homelab-scanner.py --fast
```

**Compose files are not found**

Add the directory that contains them:

```bash
./homelab-scanner.py --scan-root /path/to/stacks
```

**A report already exists**

That is expected. Reports are timestamped; old reports are left in place. Move
or delete old reports yourself if you do not need them.
