# Service Inventory — lab-node-01

Generated **2025-06-14 09:30 UTC** by `homelab-scanner.py` v1.1.0 (read-only).

## System

- **Host:** `lab-node-01`
- **OS:** Debian GNU/Linux 12 (bookworm)
- **IPs:** `192.0.2.20`, `2001:db8:10::20`, `172.30.0.1`, `172.31.0.1`
- **Firewall:** nftables input filter active (policy drop)
- **Disk:** **53.7 GB used / 512 GB (10%)**, 458 GB free on `/dev/mapper/vg0-root`
- **RAM:** 31.3 GB total, 8.42 GB used
- **Uptime:** 42d 7h
- **Docker:** server 27.5.1 — 18 containers (14 running), 24 images, 10 volumes

## Listening ports

| Port | Proto | Service / Process | Bind |
|---:|---|---|---|
| 22 | TCP | ssh.service | all interfaces |
| 53 | TCP | unbound.service | all interfaces |
| 53 | UDP | unbound.service | all interfaces |
| 80 | TCP | traefik (container) | all interfaces |
| 443 | TCP | traefik (container) | all interfaces |
| 2222 | TCP | forgejo (container) | all interfaces |
| 3000 | TCP | grafana (container) | localhost |
| 3001 | TCP | forgejo (container) | localhost |
| 8000 | TCP | paperless (container) | localhost |
| 8096 | TCP | jellyfin (container) | all interfaces |
| 8123 | TCP | homeassistant (container) | all interfaces |
| 8384 | TCP | syncthing (container) | localhost |
| 9000 | TCP | portainer (container) | localhost |
| 9090 | TCP | prometheus (container) | localhost |
| 9100 | TCP | node-exporter (container) | localhost |
| 21027 | UDP | syncthing (container) | all interfaces |
| 22000 | TCP | syncthing (container) | all interfaces |
| 51820 | UDP | wg-quick@wg0.service | all interfaces |

Ports bound to `0.0.0.0`/`::` are reachable from the LAN unless a firewall blocks them.

## Container port mappings

| Container | Project | Host → Container | State |
|---|---|---|---|
| traefik | traefik | 443/tcp → 443, 80/tcp → 80 | running |
| forgejo | forgejo | 2222/tcp → 22, 3001/tcp → 3000 | running |
| grafana | monitoring | 3000/tcp → 3000 | running |
| paperless | paperless | 8000/tcp → 8000 | running |
| jellyfin | jellyfin | 8096/tcp → 8096 | running |
| homeassistant | homeassistant | 8123/tcp → 8123 | running |
| syncthing | syncthing | 8384/tcp → 8384, 21027/udp → 21027, 22000/tcp → 22000 | running |
| portainer | portainer | 9000/tcp → 9000 | running |
| prometheus | monitoring | 9090/tcp → 9090 | running |
| node-exporter | monitoring | 9100/tcp → 9100 | running |

**Internal-only container ports** (not published on the host):

| Container | Port/Proto |
|---|---|
| traefik | 8080/tcp |
| forgejo-db | 5432/tcp |
| paperless-db | 5432/tcp |
| paperless-redis | 6379/tcp |
| paperless-gotenberg | 3000/tcp |
| vaultwarden | 80/tcp |

## Reverse proxy routes

| Host | Router / Service | Backend |
|---|---|---|
| paperless.lab.example | paperless | http://172.30.0.5:8000 |
| jellyfin.lab.example | jellyfin | http://172.30.0.6:8096 |
| home.lab.example | homeassistant | http://172.30.0.7:8123 |
| git.lab.example | forgejo | http://172.30.0.8:3000 |
| vault.lab.example | vaultwarden | http://172.30.0.9:80 |
| grafana.lab.example | grafana | http://172.30.0.10:3000 |
| portainer.lab.example | portainer | http://172.30.0.11:9000 |
| prometheus.lab.example | prometheus | http://172.30.0.12:9090 |

## Running Docker services

Image sizes are Docker's virtual sizes (shared layers count per image); data is bind-mount data. Totals are approximate.

| Service | Components | Count | Image | Data | Total |
|---|---|---:|---:|---:|---:|
| paperless | paperless, paperless-db, paperless-redis | 3 | 1.24 GB | 1.80 GB | **3.04 GB** |
| jellyfin | jellyfin | 1 | 812 MB | 2.20 GB | **3.01 GB** |
| forgejo | forgejo, forgejo-db | 2 | 410 MB | 2.40 GB | **2.81 GB** |
| homeassistant | homeassistant | 1 | 1.05 GB | 480 MB | **1.53 GB** |
| prometheus | prometheus | 1 | 245 MB | 1.10 GB | **1.35 GB** |
| syncthing | syncthing | 1 | 142 MB | 620 MB | **762 MB** |
| grafana | grafana | 1 | 312 MB | 28.0 MB | **340 MB** |
| portainer | portainer | 1 | 168 MB | 4.00 MB | **172 MB** |
| traefik | traefik | 1 | 147 MB | 6.40 MB | **153 MB** |
| vaultwarden | vaultwarden | 1 | 98.0 MB | 12.0 MB | **110 MB** |
| node-exporter | node-exporter | 1 | 22.0 MB | 0 B | **22.0 MB** |

**Running Docker total (virtual): 13.0 GB**

## Host services (non-Docker)

| Unit | Port(s) | PID | Executable | Size |
|---|---|---:|---|---:|
| qemu-guest-agent.service | — | 410 | /usr/sbin/qemu-ga | 410 KB |
| smartd.service | — | 620 | /usr/sbin/smartd | 780 KB |
| ssh.service | 22 | 701 | /usr/sbin/sshd | 1.10 MB |
| unbound.service | 53 | 842 | /usr/sbin/unbound | 18.4 MB |
| wg-quick@wg0.service | 51820 | 912 | /usr/bin/wg-quick | 42.0 KB |
| zfs-zed.service | — | 638 | /usr/sbin/zed | 2.30 MB |

Size covers a detected package directory and systemd `StateDirectory`; system binaries are not counted.

## Docker storage

| Type | Count | Active | Size | Reclaimable |
|---|---:|---:|---:|---:|
| Images | 24 | 15 | 18.42GB | 6.8GB (37%) |
| Containers | 18 | 14 | 412.0MB | 180.0MB (44%) |
| Local Volumes | 10 | 9 | 9.49GB | 118MB (1%) |
| Build Cache | 12 | 0 | 1.25GB | 1.25GB |

On-disk Docker usage: **22.4 GB** (`/var/lib/docker`).

## Volumes

| Volume | Size | Owner | State |
|---|---|---|---|
| paperless_media | 4.12 GB | paperless | active |
| jellyfin_media | 1.84 GB | jellyfin | active |
| forgejo_data | 1.21 GB | forgejo | active |
| prometheus_data | 1.05 GB | monitoring | active |
| syncthing_data | 620 MB | syncthing | active |
| homeassistant_config | 480 MB | homeassistant | active |
| legacy_wiki_data | 118 MB | wiki | unused |
| grafana_data | 28.0 MB | monitoring | active |
| traefik_data | 6.00 MB | traefik | active |
| portainer_data | 4.00 MB | portainer | active |

Volume total (measured): **9.48 GB**.

## Stopped / created Docker containers

| Stack | Components | State | Port(s) | Image |
|---|---|---|---|---|
| wiki | wiki, wiki-db | exited | — | 1.42 GB |
| mealie | mealie | created | — | 780 MB |
| it-tools | it-tools | exited | — | 64.0 MB |

These images remain on disk and are part of the Docker storage totals above.

## Compose stacks on disk

| Directory | Project | Configured ports | State | Size |
|---|---|---|---|---|
| `/srv/stacks/paperless` | paperless | 8000/tcp | running | 5.82 GB |
| `/srv/stacks/forgejo` | forgejo | 2222/tcp, 3001/tcp | running | 3.64 GB |
| `/srv/stacks/photoprism` | photoprism | 2342/tcp | **idle** | 2.41 GB |
| `/srv/stacks/jellyfin` | jellyfin | 8096/tcp | running | 2.18 GB |
| `/srv/stacks/wiki` | wiki | 8088/tcp | **idle** | 1.34 GB |
| `/srv/stacks/homeassistant` | homeassistant | 8123/tcp | running | 1.12 GB |
| `/srv/stacks/mealie` | mealie | 9925/tcp | **idle** | 827 MB |
| `/srv/stacks/monitoring` | monitoring | 3000/tcp, 9090/tcp, 9100/tcp | running | 421 MB |
| `/srv/stacks/vaultwarden` | vaultwarden | — | running | 116 MB |
| `/srv/stacks/syncthing` | syncthing | 8384/tcp, 21027/udp, 22000/tcp | running | 88.0 MB |
| `/srv/stacks/portainer` | portainer | 9000/tcp | running | 8.20 MB |
| `/srv/stacks/traefik` | traefik | 443/tcp, 80/tcp | running | 6.40 MB |

_Plus 7 smaller stacks (34.0 MB)._

**Idle compose-stack data: 4.58 GB across 3 stacks.**

## Disk usage

| Path | Size |
|---|---:|
| `/root` | 48.0 MB |
| `/var/lib/docker` | 22.4 GB |
| `/var/lib/containerd` | 1.20 MB |
| `/opt` | 3.10 GB |
| `/usr` | 2.40 GB |
| `/home` | 620 MB |
| `/srv` | 17.2 GB |
| `/tmp` | 12.0 MB |
| `/srv/media` | 8.90 GB |

Root filesystem: **53.7 GB / 512 GB** used, **458 GB** available.

## Totals

| Bucket | Size |
|---|---:|
| Root filesystem used | 53.7 GB |
| Docker engine (`/var/lib/docker`) | 22.4 GB |
| Idle compose-stack data | 4.58 GB |
| Running Docker images + data (virtual) | 13.0 GB |

### Reclaim candidates

| Candidate | Reclaimable |
|---|---:|
| Docker images | 6.8GB (37%) |
| Docker containers | 180.0MB (44%) |
| Docker local volumes | 118MB (1%) |
| Docker build cache | 1.25GB |
| Idle compose stacks | 4.58 GB |
| Unused Docker volumes | 118 MB |

Check each item before deleting. `docker system prune -a --volumes` is destructive and is not run by this script.

---

_Generated read-only; sizes are approximations. Bind data is attributed to the most specific container mount to avoid double counting._
