# homelab-scanner v1.1.0

`homelab-scanner` is a read-only inventory tool for Linux homelabs. It reports
listening ports, Docker workloads, volumes, compose stacks, host services and
disk usage as a Markdown report, then prints the same report to the terminal.

This is the initial packaged release of the prebuilt Linux x86-64 binary.

## Release assets

| Asset | Description |
|---|---|
| `homelab-scanner-v1.1.0-linux-amd64` | Raw standalone binary |
| `homelab-scanner-v1.1.0-linux-amd64.tar.gz` | Binary, source script, READMEs and these release notes |
| `SHA256SUMS` | SHA-256 checksums for both assets |

## Requirements

- Linux x86-64.
- glibc 2.36 or newer for the prebuilt binary. It was built on Debian 12 with
  Python 3.11 and PyInstaller.
- Python is **not** required to run the binary.
- Docker, Docker Compose, systemd, `ss`/`netstat`, `du` and firewall tools are
  optional. Sections that cannot be collected are left empty or approximate.
- Root access is recommended for complete Docker, process and disk data.

For other architectures or older distributions, rebuild the binary on the
target platform as described in `README.md`.

## Install

```bash
tar -xzf homelab-scanner-v1.1.0-linux-amd64.tar.gz
cd homelab-scanner-v1.1.0-linux-amd64
./homelab-scanner --version
```

Or use the raw binary directly:

```bash
chmod +x homelab-scanner-v1.1.0-linux-amd64
./homelab-scanner-v1.1.0-linux-amd64
```

## Usage

Generate a timestamped report and print it to the terminal:

```bash
./homelab-scanner
```

The report is written next to the executable as
`homelab-report-YYYYMMDD-HHMMSS.md`. Generated reports are ignored by Git and
must not be committed because they can contain live host information.

Common options:

```bash
./homelab-scanner --fast          # skip deep du measurements
./homelab-scanner --no-file       # print without writing a report
./homelab-scanner -o -            # print only, to stdout
./homelab-scanner --skip-compose  # skip compose-file scanning
```

See `README.md` for the full option list and report format. A fictional example
is included in `homelab-sample-report-yyyymmdd-hhmmdd.md`.

## Safety

The scanner is read-only. It does not stop containers, delete files, prune
images or change firewall rules. Reclaim suggestions are informational only;
commands such as `docker system prune -a --volumes` are never executed.

## Verify the download

```bash
sha256sum -c SHA256SUMS
```

The local release bundle can be recreated from the repository with:

```bash
./scripts/prepare-release.sh
```

## Changes

- Added the standalone Linux x86-64 binary and documented binary builds.
- Added English and Malay documentation.
- Added a sanitized sample report for documentation and testing.
- Added release packaging with checksums.
