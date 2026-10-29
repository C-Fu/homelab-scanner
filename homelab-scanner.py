#!/usr/bin/env python3
"""
homelab-scanner - generate a Markdown inventory of ports, Docker services,
volumes, compose stacks and disk usage for this host, then print it to the
terminal.

Read-only. Requires Python 3.8+. Docker/Compose are optional: the script still
reports ports and host services when Docker is absent or unreachable.

Usage:
    ./homelab-scanner.py                 # write homelab-report-YYYYMMDD-HHMMSS.md and print
    ./homelab-scanner.py --no-file       # print only
    ./homelab-scanner.py -o /tmp/inv.md  # write elsewhere
    ./homelab-scanner.py --fast          # skip deep du measurements

The same code can be compiled into a standalone executable with PyInstaller;
see README.md for the build command.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VERSION = "1.1.0"


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def app_dir():
    """Directory of the script, or of the executable when frozen as a binary."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def app_name():
    """Display name of the script or the compiled executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).name
    return Path(__file__).name


def have(cmd):
    return shutil.which(cmd) is not None


def run(cmd, timeout=60):
    """Run a command, never raise. Returns (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout, errors="replace",
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "%s: not found" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "", "%s: timed out" % cmd[0]
    except Exception as exc:  # noqa: BLE001 - keep the report generator alive
        return 1, "", str(exc)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def human(n):
    if n is None:
        return "—"
    n = float(n)
    if n < 1024:
        return "%d B" % int(n)
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        n /= 1024.0
        if n < 1024:
            if n >= 100:
                return "%.0f %s" % (n, unit)
            if n >= 10:
                return "%.1f %s" % (n, unit)
            return "%.2f %s" % (n, unit)
    return "%.1f EB" % n


def parse_size(text):
    """Parse '43.79GB' / '419.6MB (85%)' to bytes. Returns 0 on failure."""
    if not text:
        return 0
    m = re.match(r"\s*([0-9.]+)\s*([KMGTPE]?)i?B", str(text), re.I)
    if not m:
        return 0
    value = float(m.group(1))
    power = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4, "P": 5, "E": 6}[m.group(2).upper()]
    return int(value * (1024 ** power))


def du_sizes(paths):
    """Return {normalised_path: bytes} for existing paths using one batched du."""
    cleaned = []
    seen = set()
    for p in paths:
        if not p:
            continue
        p = os.path.normpath(os.path.abspath(str(p)))
        if p in seen or not os.path.exists(p):
            continue
        seen.add(p)
        cleaned.append(p)
    result = {}
    if not cleaned or not have("du"):
        return result
    for i in range(0, len(cleaned), 100):
        chunk = cleaned[i:i + 100]
        rc, out, _ = run(["du", "-skx"] + chunk, timeout=300)
        if rc == 124:
            continue
        for line in out.splitlines():
            line = line.rstrip("\n")
            if "\t" in line:
                size, path = line.split("\t", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                size, path = parts
            try:
                result[os.path.normpath(path)] = int(size) * 1024
            except ValueError:
                continue
    return result


def esc(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def md_table(headers, rows, align=None):
    if not rows:
        rows = [["—"] * len(headers)]
    align = align or ["---"] * len(headers)
    out = ["| " + " | ".join(esc(h) for h in headers) + " |"]
    out.append("|" + "|".join(align) + "|")
    for row in rows:
        out.append("| " + " | ".join(esc(c) for c in row) + " |")
    return "\n".join(out)


def short(text, limit=80):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


# --------------------------------------------------------------------------
# host information
# --------------------------------------------------------------------------

def os_name():
    for line in read_text("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def host_ips():
    ips = []
    rc, out, _ = run(["hostname", "-I"], timeout=5)
    if rc == 0:
        ips = out.split()
    if not ips:
        try:
            ips = [socket.gethostbyname(socket.gethostname())]
        except OSError:
            pass
    cleaned = []
    for ip in ips:
        if ip.startswith("127.") or ip == "::1":
            continue
        if ip not in cleaned:
            cleaned.append(ip)
    return cleaned


def root_disk():
    try:
        st = os.statvfs("/")
    except OSError:
        return None
    total = st.f_blocks * st.f_frsize
    free = st.f_bfree * st.f_frsize
    avail = st.f_bavail * st.f_frsize
    used = total - free
    pct = (used / total * 100.0) if total else 0.0
    source = ""
    rc, out, _ = run(["findmnt", "-n", "-o", "SOURCE", "/"], timeout=5)
    if rc == 0 and out.strip():
        source = out.strip().splitlines()[0]
    return {
        "total": total, "used": used, "free": free, "avail": avail,
        "pct": pct, "source": source,
    }


def memory_info():
    data = {}
    for line in read_text("/proc/meminfo").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            try:
                data[parts[0][:-1]] = int(parts[1]) * 1024
            except ValueError:
                pass
    return data


def uptime_text():
    raw = read_text("/proc/uptime").split()
    if not raw:
        return ""
    try:
        seconds = int(float(raw[0]))
    except ValueError:
        return ""
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    return ("%dd %dh" % (days, hours)) if days else ("%dh %dm" % (hours, rem // 60))


def firewall_status():
    if have("ufw"):
        rc, out, _ = run(["ufw", "status"], timeout=10)
        if rc == 0 and "Status: active" in out:
            return "UFW active"
    if have("nft"):
        rc, out, _ = run(["nft", "list", "ruleset"], timeout=10)
        if rc == 0 and "hook input" in out:
            policies = re.findall(r"hook input[^;]*;\s*policy\s+(\w+)", out)
            if "drop" in policies:
                return "nftables input filter active (policy drop)"
            if policies:
                return "no host firewall filter (nftables input policy %s)" % policies[0]
            return "nftables present, input chain default accept"
    if have("iptables"):
        rc, out, _ = run(["iptables", "-S", "INPUT"], timeout=10)
        if rc == 0:
            if "-P INPUT ACCEPT" in out:
                return "no host firewall filter (iptables INPUT policy ACCEPT)"
            return "iptables filter present"
    return "firewall state unknown"


# --------------------------------------------------------------------------
# listening ports
# --------------------------------------------------------------------------

def parse_ss():
    rc, out, _ = run(["ss", "-tulpnH"], timeout=15)
    if rc != 0:
        return None
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 6)
        if len(parts) < 5:
            continue
        proto, state, local = parts[0].lower(), parts[1].upper(), parts[4]
        proc = parts[6] if len(parts) > 6 else ""
        if ":" not in local:
            continue
        addr, port_s = local.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            continue
        names = re.findall(r'\("([^"]+)"', proc)
        pids = [int(x) for x in re.findall(r"pid=(\d+)", proc)]
        rows.append({
            "proto": proto, "state": state, "addr": addr, "port": port,
            "process": ",".join(dict.fromkeys(names)) or "?",
            "pids": pids,
        })
    return rows


def parse_netstat():
    if not have("netstat"):
        return None
    rc, out, _ = run(["netstat", "-tulpn"], timeout=15)
    if rc != 0:
        return None
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        proto = parts[0].lower()
        if proto not in ("tcp", "tcp6", "udp", "udp6"):
            continue
        proto = proto[:3]
        local = parts[3]
        prog = parts[6] if len(parts) > 6 else ""
        addr, port_s = local.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            continue
        pid = 0
        name = prog
        if "/" in prog:
            pid_s, name = prog.split("/", 1)
            try:
                pid = int(pid_s)
            except ValueError:
                pid = 0
        rows.append({
            "proto": proto, "state": "LISTEN" if proto == "tcp" else "UNCONN",
            "addr": addr, "port": port, "process": name or "?",
            "pids": [pid] if pid else [],
        })
    return rows


def parse_proc_net():
    """Last-resort listener detection without process names."""
    rows = []
    for proto, path in (("tcp", "/proc/net/tcp"), ("tcp", "/proc/net/tcp6"),
                        ("udp", "/proc/net/udp"), ("udp", "/proc/net/udp6")):
        for line in read_text(path).splitlines()[1:]:
            parts = line.split()
            if len(parts) < 4:
                continue
            if proto == "tcp" and parts[3] != "0A":
                continue
            local = parts[1]
            if ":" not in local:
                continue
            _, port_hex = local.rsplit(":", 1)
            try:
                port = int(port_hex, 16)
            except ValueError:
                continue
            rows.append({
                "proto": proto, "state": "LISTEN" if proto == "tcp" else "UNCONN",
                "addr": "?", "port": port, "process": "?", "pids": [],
            })
    return rows


def listening_ports():
    rows = parse_ss()
    if rows is None:
        rows = parse_netstat()
    if rows is None:
        rows = parse_proc_net()
    # merge duplicate IPv4/IPv6 rows for same proto/port/process/state
    merged = {}
    for r in rows:
        key = (r["proto"], r["port"], r["process"], r["state"])
        item = merged.setdefault(key, {
            "proto": r["proto"], "port": r["port"], "process": r["process"],
            "pids": [], "state": r["state"], "addrs": [],
        })
        for pid in r["pids"]:
            if pid not in item["pids"]:
                item["pids"].append(pid)
        if r["addr"] not in item["addrs"]:
            item["addrs"].append(r["addr"])
    return sorted(merged.values(), key=lambda x: (x["port"], x["proto"]))


def bind_scope(addrs):
    all_bind = any(a in ("0.0.0.0", "::", "*", "[::]") for a in addrs)
    local_only = bool(addrs) and all(
        a.startswith("127.") or a in ("::1", "[::1]", "localhost") for a in addrs
    )
    if all_bind:
        return "all interfaces"
    if local_only:
        return "localhost"
    return ", ".join(addrs)


# --------------------------------------------------------------------------
# docker
# --------------------------------------------------------------------------

def docker_available():
    if not have("docker"):
        return False
    rc, out, _ = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
    return rc == 0 and bool(out.strip())


def docker_info():
    version = ""
    rc, out, _ = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
    if rc == 0:
        version = out.strip().splitlines()[0] if out.strip() else ""
    return version


def docker_containers():
    rc, out, _ = run(["docker", "ps", "-aq"], timeout=30)
    if rc != 0 or not out.strip():
        return []
    ids = out.split()
    rc, out, _ = run(["docker", "inspect", "--size"] + ids, timeout=180)
    if rc != 0:
        return []
    try:
        raw = json.loads(out)
    except ValueError:
        return []
    containers = []
    for c in raw:
        labels = c.get("Config", {}).get("Labels") or {}
        state = c.get("State", {}) or {}
        ports = c.get("NetworkSettings", {}).get("Ports") or {}
        mounts = c.get("Mounts") or []
        containers.append({
            "id": c.get("Id", ""),
            "name": (c.get("Name") or "").lstrip("/"),
            "image": c.get("Config", {}).get("Image", ""),
            "image_id": c.get("Image", ""),
            "project": labels.get("com.docker.compose.project", ""),
            "service": labels.get("com.docker.compose.service", ""),
            "working_dir": labels.get("com.docker.compose.project.working_dir", ""),
            "status": state.get("Status", "unknown"),
            "running": bool(state.get("Running")),
            "pid": state.get("Pid") or 0,
            "ports": ports,
            "exposed": (c.get("Config", {}).get("ExposedPorts") or {}),
            "mounts": mounts,
            "network_mode": (c.get("HostConfig", {}) or {}).get("NetworkMode", ""),
            "size_rw": c.get("SizeRw") or 0,
            "size_rootfs": c.get("SizeRootFs") or 0,
            "labels": labels,
        })
    return containers


def docker_images():
    rc, out, _ = run(["docker", "images", "-aq", "--no-trunc"], timeout=30)
    if rc != 0 or not out.strip():
        return {}
    ids = sorted(set(out.split()))
    rc, out, _ = run(["docker", "image", "inspect"] + ids, timeout=120)
    if rc != 0:
        return {}
    try:
        raw = json.loads(out)
    except ValueError:
        return {}
    result = {}
    for img in raw:
        result[img.get("Id", "")] = {
            "size": img.get("Size") or 0,
            "tags": img.get("RepoTags") or [],
        }
    return result


def docker_system_df():
    rc, out, _ = run(["docker", "system", "df", "--format", "{{json .}}"], timeout=30)
    rows = []
    if rc == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            rows.append({
                "type": obj.get("Type", "?"),
                "total": obj.get("TotalCount", "?"),
                "active": obj.get("Active", "?"),
                "size": obj.get("Size", "?"),
                "reclaimable": obj.get("Reclaimable", "?"),
            })
    if rows:
        return rows
    rc, out, _ = run(["docker", "system", "df"], timeout=30)
    if rc != 0:
        return []
    for line in out.splitlines()[1:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 5:
            rows.append({
                "type": parts[0], "total": parts[1], "active": parts[2],
                "size": parts[3], "reclaimable": parts[4],
            })
    return rows


def docker_volumes():
    rc, out, _ = run(["docker", "volume", "ls", "--format", "{{json .}}"], timeout=30)
    vols = []
    if rc != 0:
        return vols
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            v = json.loads(line)
        except ValueError:
            continue
        labels = {}
        raw_labels = v.get("Labels") or ""
        for pair in raw_labels.split(","):
            if "=" in pair:
                k, val = pair.split("=", 1)
                labels[k] = val
        vols.append({
            "name": v.get("Name", ""),
            "mountpoint": v.get("Mountpoint", ""),
            "driver": v.get("Driver", ""),
            "labels": labels,
        })
    return vols


def docker_compose_projects():
    """Return {project_name: status} and {project_name: config_files}."""
    status, files = {}, {}
    if not have("docker"):
        return status, files
    rc, out, _ = run(["docker", "compose", "ls", "-a", "--format", "json"], timeout=30)
    if rc != 0:
        return status, files
    try:
        raw = json.loads(out)
    except ValueError:
        return status, files
    for item in raw:
        name = item.get("Name", "")
        if not name:
            continue
        status[name] = item.get("Status", "")
        files[name] = item.get("ConfigFiles", "")
    return status, files


def container_by_cgroup(containers, pid):
    if not pid:
        return None
    cg = read_text("/proc/%d/cgroup" % pid)
    m = re.search(r"docker-([0-9a-f]{12,64})", cg)
    if not m:
        return None
    cid = m.group(1)
    for c in containers:
        if c["id"].startswith(cid) or cid.startswith(c["id"][:12]):
            return c
    return None


def unit_by_cgroup(pid):
    if not pid:
        return ""
    cg = read_text("/proc/%d/cgroup" % pid)
    m = re.search(r"([^/]+\.service)", cg)
    return m.group(1) if m else ""


def published_port_map(containers):
    """(proto, host_port) -> container"""
    result = {}
    for c in containers:
        for key, bindings in (c.get("ports") or {}).items():
            if not bindings:
                continue
            try:
                cport, proto = key.split("/", 1)
            except ValueError:
                continue
            for b in bindings:
                hp = b.get("HostPort")
                if hp and str(hp).isdigit():
                    result[(proto.lower(), int(hp))] = c
    return result


def unit_label_allowed(unit):
    """Reject session/getty/system plumbing units as service labels."""
    if not unit:
        return False
    name = unit.split(".service")[0]
    reject_prefixes = (
        "container-getty", "console-getty", "serial-getty", "getty@",
        "systemd-", "dbus", "user@", "session-", "init.scope",
    )
    return not name.startswith(reject_prefixes)


def listener_label(row, containers, port_map, unit_pid_map):
    for pid in row["pids"]:
        c = container_by_cgroup(containers, pid)
        if c:
            return c["name"], c
    mapped = port_map.get((row["proto"], row["port"]))
    if mapped:
        return mapped["name"], mapped
    for pid in row["pids"]:
        unit = unit_by_cgroup(pid)
        if unit_label_allowed(unit):
            return unit, None
    return row["process"], None


def collect_mount_sizes(containers):
    """Return per-container bind data bytes and the unique path size map."""
    sources = {}
    for c in containers:
        paths = set()
        for m in c.get("mounts") or []:
            if m.get("Type") != "bind":
                continue
            src = os.path.normpath(m.get("Source") or "")
            if not src or not os.path.isdir(src):
                continue
            if src in ("/var/run/docker.sock", "/etc/localtime", "/etc/timezone", "/proc"):
                continue
            if src.startswith("/run/") or src.startswith("/proc/"):
                continue
            paths.add(src)
        sources[c["id"]] = paths
    all_paths = sorted({p for paths in sources.values() for p in paths})
    sizes = du_sizes(all_paths)
    nested = set()
    for a in all_paths:
        for b in all_paths:
            if a != b and b.startswith(a + os.sep):
                nested.add(a)
                break
    attributed = {}
    owner = {}
    for c in containers:
        total = 0
        for src in sources.get(c["id"], set()):
            if src in nested:
                continue
            if src in owner and owner[src] != c["id"]:
                continue
            owner[src] = c["id"]
            total += sizes.get(src, 0)
        attributed[c["id"]] = total
    return attributed, sizes


def group_containers(containers, mount_bytes, image_info):
    groups = {}
    for c in containers:
        key = c["project"] or ("container:" + c["name"])
        g = groups.setdefault(key, {
            "label": c["project"] or c["name"],
            "containers": [], "image_bytes": 0, "data_bytes": 0,
            "ports": [], "statuses": [],
        })
        g["containers"].append(c)
        img = image_info.get(c["image_id"], {})
        g["image_bytes"] += img.get("size", 0) or 0
        g["data_bytes"] += mount_bytes.get(c["id"], 0)
        g["statuses"].append(c["status"])
        for key2, bindings in (c.get("ports") or {}).items():
            if not bindings:
                continue
            cport, proto = (key2.split("/", 1) + [""])[:2]
            for b in bindings:
                hp = b.get("HostPort")
                if hp:
                    g["ports"].append("%s/%s→%s" % (hp, proto or "tcp", cport))
    return groups


def traefik_routes(containers):
    """Try Traefik API first, then container labels."""
    traefik = None
    for c in containers:
        if c["running"] and "traefik" in (c["image"] + " " + c["name"]).lower():
            traefik = c
            break
    if traefik:
        for client in (["wget", "-qO-"], ["curl", "-fsS"]):
            rc, out, _ = run(
                ["docker", "exec", traefik["name"]] + client +
                ["http://127.0.0.1:8080/api/http/routers"], timeout=10)
            if rc != 0 or not out.strip().startswith("["):
                continue
            try:
                routers = json.loads(out)
            except ValueError:
                continue
            rc2, out2, _ = run(
                ["docker", "exec", traefik["name"]] + client +
                ["http://127.0.0.1:8080/api/http/services"], timeout=10)
            services = {}
            if rc2 == 0:
                try:
                    for svc_obj in json.loads(out2):
                        servers = (svc_obj.get("loadBalancer", {}) or {}).get("servers") or []
                        url = servers[0].get("url", "") if servers else ""
                        name = svc_obj.get("name", "")
                        services[name] = url
                        services[name.replace("@docker", "")] = url
                except (ValueError, AttributeError):
                    pass
            rows = []
            seen = set()
            for r in routers:
                if r.get("provider") != "docker":
                    continue
                rule = r.get("rule", "")
                hosts = re.findall(r"Host\(`([^`]+)`\)", rule)
                svc = r.get("service", "")
                target = services.get(svc, "")
                for host in hosts:
                    key = (host, svc, target)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append([host, svc.replace("@docker", ""), target or "—"])
            if rows:
                return rows
    # label fallback
    rows, seen = [], set()
    for c in containers:
        labels = c.get("labels") or {}
        routers = {}
        for k, v in labels.items():
            m = re.match(r"traefik\.http\.routers\.([^.]+)\.((?:rule)|(?:service))$", k)
            if m:
                routers.setdefault(m.group(1), {})[m.group(2)] = v
        for _, r in routers.items():
            hosts = re.findall(r"Host\(`([^`]+)`\)", r.get("rule", ""))
            svc = r.get("service", "")
            port = ""
            if svc:
                port = labels.get(
                    "traefik.http.services.%s.loadbalancer.server.port" % svc, "")
            for host in hosts:
                key = (host, svc or c["name"], port)
                if key in seen:
                    continue
                seen.add(key)
                rows.append([host, svc or c["name"], "container :%s" % port if port else c["name"]])
    return sorted(rows)


# --------------------------------------------------------------------------
# compose stacks / idle data
# --------------------------------------------------------------------------

COMPOSE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
PRUNE_DIRS = {
    ".git", ".cache", ".local", ".npm", ".opencode", ".steam", ".docker",
    "node_modules", "serverfiles", "steamapps", "overlay2", "workspace",
    "backups", "storage", "vendor", "dist", "build", "__pycache__",
    "data", "config", "logs", "log", "cache", "saves", "csgo",
}


def compose_root_skip(path):
    path = path.rstrip("/")
    return any(path == p or path.startswith(p + "/") for p in (
        "/opt/runtipi/app-data", "/opt/runtipi/repos", "/opt/runtipi/apps",
        "/var/lib/docker", "/usr", "/proc", "/sys", "/dev",
    ))


def find_compose_files(roots, max_depth=4):
    results = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        root = os.path.abspath(root)
        for current, dirs, files in os.walk(root):
            rel = os.path.relpath(current, root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            dirs[:] = [
                d for d in dirs
                if d.lower() not in PRUNE_DIRS and not d.startswith(".")
                and not compose_root_skip(os.path.join(current, d))
            ]
            if depth >= max_depth:
                dirs[:] = []
            for name in files:
                if name in COMPOSE_NAMES:
                    results.append(os.path.join(current, name))
    # keep only the shallowest compose file per directory tree
    results.sort(key=lambda p: (p.count(os.sep), p))
    kept = []
    for path in results:
        d = os.path.dirname(path)
        if any(d == kd or d.startswith(kd + os.sep) for kd in kept):
            continue
        kept.append(d)
    return kept


def compose_port_token(token):
    """Parse a short-syntax compose port. Returns 'host/proto' or ''."""
    token = token.strip().strip("\"'")
    if not token or token.startswith("$") is False and ":" not in token:
        return ""
    m = re.match(r"^(?:(.*):)?(\d+)(?:/(tcp|udp))?$", token)
    if not m:
        return ""
    host_part, cont, proto = m.group(1), m.group(2), m.group(3) or "tcp"
    if not host_part:
        return ""
    numbers = re.findall(r"\d+", host_part)
    if not numbers:
        return ""
    return "%s/%s" % (numbers[-1], proto)


def parse_compose_ports(text):
    lines = text.splitlines()
    ports = []

    def add_token(tok):
        parsed = compose_port_token(tok)
        if parsed:
            ports.append(parsed)

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.split("#", 1)[0].strip()
        m = re.match(r"^ports:\s*(.*)$", stripped)
        if not m:
            i += 1
            continue
        ports_indent = len(raw) - len(raw.lstrip())
        inline = m.group(1).strip()
        if inline.startswith("["):
            for tok in inline.strip("[]").split(","):
                add_token(tok)
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.lstrip().startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= ports_indent:
                break
            stripped = line.split("#", 1)[0].strip()
            if not stripped.startswith("-"):
                i += 1
                continue
            dash_indent = indent
            item = stripped[1:].strip()
            keys = {}
            # long syntax: key: value on the dash line and following lines
            km = re.match(r"^([A-Za-z_]+):\s*(.*)$", item)
            if km:
                keys[km.group(1)] = km.group(2).strip().strip("\"'")
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip() or nxt.lstrip().startswith("#"):
                    j += 1
                    continue
                nindent = len(nxt) - len(nxt.lstrip())
                if nindent <= dash_indent:
                    break
                nkm = re.match(r"^([A-Za-z_]+):\s*(.*)$", nxt.split("#", 1)[0].strip())
                if nkm:
                    keys[nkm.group(1)] = nkm.group(2).strip().strip("\"'")
                j += 1
            if keys:
                target = keys.get("target", "")
                published = keys.get("published", "")
                proto = keys.get("protocol", "tcp")
                if target.isdigit():
                    nums = re.findall(r"\d+", published)
                    if nums:
                        ports.append("%s/%s" % (nums[-1], proto))
            elif item:
                add_token(item)
            i = j
    return sorted(dict.fromkeys(ports))


def parse_compose_meta(text):
    image = ""
    container = ""
    m = re.search(r"^\s*image:\s*[\"']?([^\"'\s]+)", text, re.M)
    if m:
        image = m.group(1)
    m = re.search(r"^\s*container_name:\s*[\"']?([^\"'\s]+)", text, re.M)
    if m:
        container = m.group(1)
    return image, container


def scan_compose_stacks(roots, running_projects, containers, skip_sizes=False):
    dirs = find_compose_files(roots)
    stack_paths = []
    for d in dirs:
        path = os.path.join(d, next((n for n in COMPOSE_NAMES if os.path.exists(os.path.join(d, n))), ""))
        text = read_text(path)
        image, container = parse_compose_meta(text)
        stack_paths.append({
            "dir": d, "file": path, "image": image, "container": container,
            "ports": parse_compose_ports(text),
            "project": os.path.basename(d),
        })
    sizes = {} if skip_sizes else du_sizes([s["dir"] for s in stack_paths])
    running_names = {name for name, status in running_projects.items()
                     if "running" in status.lower()}
    for s in stack_paths:
        s["size"] = sizes.get(os.path.normpath(s["dir"]), 0)
        s["running"] = s["project"] in running_names
        if not s["running"]:
            # Also consider a running container whose working dir or mounts
            # point into this stack.
            for c in containers:
                if not c["running"]:
                    continue
                wd = c["working_dir"] or ""
                if wd and (wd == s["dir"] or wd.startswith(s["dir"] + os.sep)):
                    s["running"] = True
                    break
                for m in c.get("mounts") or []:
                    src = os.path.normpath(m.get("Source") or "")
                    if src == s["dir"] or src.startswith(s["dir"] + os.sep):
                        s["running"] = True
                        break
                if s["running"]:
                    break
    return sorted(stack_paths, key=lambda s: s["size"], reverse=True)


def migrated_data():
    """Runtipi migrated/legacy application data."""
    base = "/opt/runtipi/app-data/migrated"
    if not os.path.isdir(base):
        return 0, []
    children = [os.path.join(base, n) for n in os.listdir(base)]
    sizes = du_sizes(children)
    rows = [(os.path.basename(p), sizes.get(os.path.normpath(p), 0))
            for p in children if os.path.isdir(p)]
    rows.sort(key=lambda x: x[1], reverse=True)
    return sum(sizes.values()), rows


# --------------------------------------------------------------------------
# host services (systemd)
# --------------------------------------------------------------------------

def running_units():
    if not have("systemctl"):
        return []
    rc, out, _ = run(
        ["systemctl", "list-units", "--type=service", "--state=running",
         "--no-legend", "--no-pager", "--plain"], timeout=20)
    if rc != 0:
        return []
    units = []
    skip_prefix = ("systemd-", "dbus", "container-getty", "console-getty", "getty@")
    skip_exact = {"docker.service", "containerd.service", "cron.service"}
    for line in out.splitlines():
        parts = line.split()
        if not parts or not parts[0].endswith(".service"):
            continue
        unit = parts[0]
        if unit in skip_exact or unit.startswith(skip_prefix):
            continue
        units.append(unit)
    return units


def unit_details(units):
    details = {}
    for unit in units:
        rc, pid_s, _ = run(["systemctl", "show", "-p", "MainPID", "--value", unit], timeout=5)
        rc2, exec_s, _ = run(["systemctl", "show", "-p", "ExecStart", "--value", unit], timeout=5)
        rc3, dir_s, _ = run(["systemctl", "show", "-p", "StateDirectory", "--value", unit], timeout=5)
        pid = 0
        try:
            pid = int(pid_s.strip() or 0)
        except ValueError:
            pid = 0
        exe = ""
        m = re.search(r"path=([^ ;]+)", exec_s)
        if m:
            exe = m.group(1)
        details[unit] = {"pid": pid, "exec": exe, "statedir": dir_s.strip()}
    return details


def app_size(exec_path, statedir):
    """Approximate package + state size for a host app."""
    paths = []
    if exec_path:
        real = os.path.realpath(exec_path)
        m = re.match(r"^(/usr/lib/[^/]+|/usr/local/[^/]+|/opt/[^/]+)", real)
        if m and os.path.isdir(m.group(1)) and os.path.basename(m.group(1)) not in ("bin", "sbin", "lib"):
            paths.append(m.group(1))
        elif os.path.isfile(real):
            paths.append(real)
    if statedir and statedir != "-":
        for name in statedir.split():
            p = "/var/lib/" + name if not name.startswith("/") else name
            if os.path.exists(p):
                paths.append(p)
    if not paths:
        return 0
    return sum(du_sizes(paths).values())


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def build_report(args):
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    host = socket.gethostname()
    disk = root_disk()
    mem = memory_info()
    ips = host_ips()
    fw = firewall_status()
    docker_ok = docker_available()
    dver = docker_info() if docker_ok else ""

    containers = docker_containers() if docker_ok else []
    images = docker_images() if docker_ok else {}
    df_rows = docker_system_df() if docker_ok else []
    volume_rows = docker_volumes() if docker_ok else []
    running_projects, project_files = docker_compose_projects() if docker_ok else ({}, {})

    mount_bytes, mount_sizes = ({}, {}) if args.fast else collect_mount_sizes(containers)
    if args.fast:
        mount_bytes = {c["id"]: 0 for c in containers}

    running = [c for c in containers if c["running"]]
    stopped = [c for c in containers if not c["running"]]
    port_map = published_port_map(running)
    units = running_units()
    unit_info = unit_details(units)
    unit_pid_map = {info["pid"]: unit for unit, info in unit_info.items() if info["pid"]}
    active_volumes = set()
    for c in containers:
        for m in c.get("mounts") or []:
            if m.get("Type") == "volume" and m.get("Name"):
                active_volumes.add(m["Name"])

    # sizes for volumes
    vol_sizes = {} if args.fast else du_sizes(
        [v["mountpoint"] for v in volume_rows if v.get("mountpoint")])
    for v in volume_rows:
        v["size"] = vol_sizes.get(os.path.normpath(v["mountpoint"]), 0) if not args.fast else 0
        v["active"] = v["name"] in active_volumes

    stacks = [] if args.skip_compose else scan_compose_stacks(
        args.scan_root, running_projects, containers, skip_sizes=args.fast)
    idle_stacks = [s for s in stacks if not s["running"]]
    idle_total = sum(s["size"] for s in idle_stacks)
    migrated_total, migrated_rows = migrated_data() if not args.fast else (0, [])

    lines = []
    add = lines.append
    add("# Service Inventory — %s" % host)
    add("")
    add("Generated **%s** by `%s` v%s (read-only)." % (now, app_name(), VERSION))
    add("")
    add("## System")
    add("")
    add("- **Host:** `%s`" % host)
    add("- **OS:** %s" % os_name())
    if ips:
        add("- **IPs:** %s" % ", ".join("`%s`" % ip for ip in ips))
    add("- **Firewall:** %s" % fw)
    if disk:
        add("- **Disk:** **%s used / %s (%0.0f%%)**, %s free%s" % (
            human(disk["used"]), human(disk["total"]), disk["pct"], human(disk["avail"]),
            (" on `%s`" % disk["source"]) if disk["source"] else ""))
    if mem:
        add("- **RAM:** %s total, %s used" % (
            human(mem.get("MemTotal")), human(mem.get("MemTotal", 0) - mem.get("MemAvailable", 0))))
    add("- **Uptime:** %s" % uptime_text())
    if docker_ok:
        add("- **Docker:** server %s — %d containers (%d running), %d images, %d volumes" % (
            dver or "?", len(containers), len(running), len(images), len(volume_rows)))
    else:
        add("- **Docker:** not available")
    add("")

    # ---- ports ----
    ports = listening_ports()
    add("## Listening ports")
    add("")
    port_rows = []
    for row in ports:
        label, container = listener_label(row, containers, port_map, unit_pid_map)
        if container:
            label = "%s (container)" % container["name"]
        port_rows.append([
            row["port"], row["proto"].upper(), label, bind_scope(row["addrs"]),
        ])
    add(md_table(["Port", "Proto", "Service / Process", "Bind"],
                 port_rows, ["---:", "---", "---", "---"]))
    add("")
    if any(not (a in ("127.0.0.1", "::1", "[::1]") or a.startswith("127."))
           for row in ports for a in row["addrs"]):
        add("Ports bound to `0.0.0.0`/`::` are reachable from the LAN unless a firewall blocks them.")
        add("")

    # ---- container mappings ----
    if containers:
        add("## Container port mappings")
        add("")
        rows = []
        for c in running:
            entries = []
            for key, bindings in (c.get("ports") or {}).items():
                if bindings:
                    for b in bindings:
                        entries.append("%s/%s → %s" % (
                            b.get("HostPort", "?"), key.split("/")[-1], key.split("/")[0]))
                elif c.get("network_mode") == "host":
                    entries.append("%s (host network)" % key)
            if entries:
                rows.append([c["name"], c["project"] or "—",
                             ", ".join(dict.fromkeys(entries)), c["status"]])
        add(md_table(["Container", "Project", "Host → Container", "State"], rows))
        add("")
        internal = []
        for c in running:
            if c.get("network_mode") == "host":
                continue
            for key, bindings in (c.get("ports") or {}).items():
                if not bindings:
                    internal.append([c["name"], key])
            if not c.get("ports"):
                for key in (c.get("exposed") or {}):
                    internal.append([c["name"], key])
        if internal:
            seen = set()
            rows = []
            for name, key in internal:
                if (name, key) in seen:
                    continue
                seen.add((name, key))
                rows.append([name, key])
            add("**Internal-only container ports** (not published on the host):")
            add("")
            add(md_table(["Container", "Port/Proto"], rows))
            add("")

    # ---- traefik ----
    if containers:
        routes = traefik_routes(containers)
        add("## Reverse proxy routes")
        add("")
        if routes:
            add(md_table(["Host", "Router / Service", "Backend"], routes))
        else:
            add("No Traefik/HTTP proxy routes discovered (no API or labels found).")
        add("")

    # ---- running services ----
    groups = group_containers(running, mount_bytes, images)
    add("## Running Docker services")
    add("")
    add("Image sizes are Docker's virtual sizes (shared layers count per image); "
        "data is bind-mount data. Totals are approximate.")
    add("")
    rows = []
    running_total = 0
    for g in sorted(groups.values(), key=lambda x: x["image_bytes"] + x["data_bytes"], reverse=True):
        total = g["image_bytes"] + g["data_bytes"]
        running_total += total
        parts = ", ".join(sorted({c["service"] or c["name"] for c in g["containers"]}))
        rows.append([
            g["label"], parts, len(g["containers"]),
            human(g["image_bytes"]), human(g["data_bytes"]), "**%s**" % human(total),
        ])
    add(md_table(["Service", "Components", "Count", "Image", "Data", "Total"], rows,
                 ["---", "---", "---:", "---:", "---:", "---:"]))
    add("")
    add("**Running Docker total (virtual): %s**" % human(running_total))
    add("")

    # ---- host services ----
    add("## Host services (non-Docker)")
    add("")
    if units:
        rows = []
        for unit in sorted(units):
            info = unit_info.get(unit, {})
            pid = info.get("pid") or 0
            ports_for = sorted({r["port"] for r in ports if pid in r.get("pids", [])})
            exe = info.get("exec") or ""
            size = 0 if args.fast else app_size(exe, info.get("statedir", ""))
            rows.append([
                unit, ", ".join(str(p) for p in ports_for) or "—", pid or "—",
                short(exe, 60) or "—", human(size) if size else "—",
            ])
        add(md_table(["Unit", "Port(s)", "PID", "Executable", "Size"], rows,
                     ["---", "---", "---:", "---", "---:"]))
        add("")
        add("Size covers a detected package directory and systemd `StateDirectory`; "
            "system binaries are not counted.")
    else:
        add("systemd not available or no running services detected.")
    add("")

    # ---- docker storage ----
    add("## Docker storage")
    add("")
    if df_rows:
        add(md_table(
            ["Type", "Count", "Active", "Size", "Reclaimable"],
            [[r["type"], r["total"], r["active"], r["size"], r["reclaimable"]] for r in df_rows],
            ["---", "---:", "---:", "---:", "---:"]))
        add("")
    docker_dir = 0 if args.fast else du_sizes(["/var/lib/docker"]).get("/var/lib/docker", 0)
    if docker_dir:
        add("On-disk Docker usage: **%s** (`/var/lib/docker`)." % human(docker_dir))
        add("")

    # ---- volumes ----
    add("## Volumes")
    add("")
    if volume_rows:
        ordered = sorted(volume_rows, key=lambda v: v.get("size", 0), reverse=True)
        shown = ordered[:args.max_volumes]
        rows = []
        for v in shown:
            labels = v.get("labels") or {}
            owner = labels.get("com.docker.compose.project", "")
            note = "active" if v.get("active") else "unused"
            if labels.get("com.docker.volume.anonymous") == "":
                note += ", anonymous"
            rows.append([short(v["name"], 34), human(v.get("size")) if v.get("size") else "—",
                         owner or "—", note])
        add(md_table(["Volume", "Size", "Owner", "State"], rows))
        rest = ordered[args.max_volumes:]
        if rest:
            add("")
            add("_Plus %d smaller volumes (%s)._" % (len(rest), human(sum(v.get("size", 0) for v in rest))))
        add("")
        add("Volume total (measured): **%s**." % human(sum(v.get("size", 0) for v in volume_rows)))
    else:
        add("No Docker volumes.")
    add("")

    # ---- stopped containers ----
    if stopped:
        add("## Stopped / created Docker containers")
        add("")
        sgroups = group_containers(stopped, mount_bytes, images)
        rows = []
        for g in sorted(sgroups.values(), key=lambda x: x["image_bytes"], reverse=True):
            statuses = ", ".join(sorted(set(g["statuses"])))
            ports_s = ", ".join(g["ports"]) or "—"
            rows.append([
                g["label"], ", ".join(sorted({c["service"] or c["name"] for c in g["containers"]})),
                statuses, ports_s, human(g["image_bytes"] or None),
            ])
        add(md_table(["Stack", "Components", "State", "Port(s)", "Image"], rows))
        add("")
        add("These images remain on disk and are part of the Docker storage totals above.")
        add("")

    # ---- compose stacks ----
    if not args.skip_compose:
        add("## Compose stacks on disk")
        add("")
        if stacks:
            shown = stacks[:args.max_stacks]
            rows = []
            for s in shown:
                rows.append([
                    "`%s`" % s["dir"], s["project"],
                    ", ".join(s["ports"]) or "—",
                    "running" if s["running"] else "**idle**",
                    human(s["size"]) if s["size"] else "—",
                ])
            add(md_table(["Directory", "Project", "Configured ports", "State", "Size"], rows))
            rest = stacks[args.max_stacks:]
            if rest:
                add("")
                add("_Plus %d smaller stacks (%s)._" % (
                    len(rest), human(sum(s["size"] for s in rest))))
            add("")
            add("**Idle compose-stack data: %s across %d stacks.**" % (
                human(idle_total), len(idle_stacks)))
        else:
            add("No compose files found under: %s" % ", ".join(args.scan_root))
        if migrated_rows:
            add("")
            add("### Migrated / legacy Runtipi app data")
            add("")
            rows = [[name, human(size)] for name, size in migrated_rows if size]
            add(md_table(["App", "Size"], rows, ["---", "---:"]))
            add("")
            add("**Legacy/migrated total: %s**" % human(migrated_total))
        add("")

    # ---- directories ----
    add("## Disk usage")
    add("")
    known = ["/root", "/var/lib/docker", "/var/lib/containerd", "/opt", "/usr",
             "/home", "/srv", "/data", "/tmp"]
    if args.fast:
        add("_Deep size measurement skipped (`--fast`)._")
        add("")
    else:
        dsizes = du_sizes(known)
        rows = []
        for p in known:
            if p in dsizes:
                rows.append(["`%s`" % p, human(dsizes[p])])
        if os.path.isdir("/root"):
            children = [os.path.join("/root", n) for n in os.listdir("/root")
                        if os.path.isdir(os.path.join("/root", n))]
            csizes = du_sizes(children)
            big = sorted(((p, s) for p, s in csizes.items() if s >= 1024 ** 3),
                         key=lambda x: x[1], reverse=True)[:10]
            for p, s in big:
                rows.append(["`%s`" % p, human(s)])
        add(md_table(["Path", "Size"], rows, ["---", "---:"]))
        add("")
        if disk:
            add("Root filesystem: **%s / %s** used, **%s** available." % (
                human(disk["used"]), human(disk["total"]), human(disk["avail"])))
        add("")

    # ---- totals ----
    add("## Totals")
    add("")
    if disk:
        rows = [["Root filesystem used", human(disk["used"])]]
        if docker_dir:
            rows.append(["Docker engine (`/var/lib/docker`)", human(docker_dir)])
        if stacks:
            rows.append(["Idle compose-stack data", human(idle_total)])
        if migrated_total:
            rows.append(["Legacy/migrated Runtipi data", human(migrated_total)])
        if running:
            rows.append(["Running Docker images + data (virtual)", human(running_total)])
        add(md_table(["Bucket", "Size"], rows, ["---", "---:"]))
        add("")
    add("### Reclaim candidates")
    add("")
    reclaim = []
    for r in df_rows:
        if r["reclaimable"] and not r["reclaimable"].startswith("0"):
            reclaim.append(["Docker %s" % r["type"].lower(), r["reclaimable"]])
    if idle_total:
        reclaim.append(["Idle compose stacks", human(idle_total)])
    unused_vol = sum(v.get("size", 0) for v in volume_rows if not v.get("active"))
    if unused_vol:
        reclaim.append(["Unused Docker volumes", human(unused_vol)])
    if migrated_total:
        reclaim.append(["Legacy/migrated Runtipi data", human(migrated_total)])
    if reclaim:
        add(md_table(["Candidate", "Reclaimable"], reclaim, ["---", "---:"]))
        add("")
        add("Check each item before deleting. `docker system prune -a --volumes` "
            "is destructive and is not run by this script.")
    else:
        add("No reclaim candidates detected.")
    add("")
    add("---")
    add("")
    add("_Generated read-only; sizes are approximations. Bind data is attributed to "
        "the most specific container mount to avoid double counting._")

    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate and print a Markdown inventory of ports, Docker "
                    "services, volumes, compose stacks and disk usage.")
    parser.add_argument("-o", "--output", default=None,
                        help="Markdown output path (default: homelab-report-YYYYMMDD-HHMMSS.md "
                             "next to this executable/script; use '-' for stdout only)")
    parser.add_argument("--no-file", action="store_true", help="do not write a file")
    parser.add_argument("--fast", action="store_true", help="skip deep du measurements")
    parser.add_argument("--skip-compose", action="store_true", help="skip compose-file scanning")
    parser.add_argument("--scan-root", action="append", default=None,
                        help="root to scan for compose files (repeatable; default /root /home /srv /opt)")
    parser.add_argument("--max-stacks", type=int, default=15,
                        help="number of compose stacks shown (default 15)")
    parser.add_argument("--max-volumes", type=int, default=15,
                        help="number of volumes shown (default 15)")
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    args = parser.parse_args(argv)
    if not args.scan_root:
        args.scan_root = ["/root", "/home", "/srv", "/opt"]
    if not args.output:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = str(app_dir() / ("homelab-report-%s.md" % stamp))
    if not have("docker"):
        print("note: docker not found; Docker sections will be empty", file=sys.stderr)
    report = build_report(args)
    sys.stdout.write(report)
    if not args.no_file and args.output not in ("-", ""):
        try:
            Path(args.output).write_text(report, encoding="utf-8")
            print("wrote %s" % args.output, file=sys.stderr)
        except OSError as exc:
            print("could not write %s: %s" % (args.output, exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
