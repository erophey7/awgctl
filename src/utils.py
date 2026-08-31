"""Utility functions for awgctl: permissions, key generation, IP math, formatting."""

import ipaddress
import os
import re
import subprocess
import sys
import time

from .constants import noninteractive, MASKING_KEYS, MAX_IP_SCAN
from .i18n import _t
from .backend import BACKEND, find_wg_bin, _wg_or_die


def config_perm_issues(cfg_path):
    """List of permission problems (empty = ok or could not check).

    Target model: owner root:root, mode 0600 (config contains private keys,
    interface is raised by root anyway).
    """
    st = BACKEND.stat_perms(cfg_path)
    if st is None:
        return []
    mode, uid, gid = st
    issues = []
    if mode & 0o077:
        issues.append(f"mode {mode:03o} (group/other access; expected 600)")
    if uid != 0:
        issues.append(f"owner uid={uid} (expected root=0)")
    if gid != 0:
        issues.append(f"group gid={gid} (expected root=0)")
    return issues


def warn_config_perms(cfg_path):
    """Print warning about unsafe config permissions (non-fatal)."""
    issues = config_perm_issues(cfg_path)
    if issues:
        print(_t("warn_perms", path=cfg_path, issues="; ".join(issues)),
              file=sys.stderr)


def fix_config_perms(cfg_path):
    """Try to set config to root:root 0600. Returns True on success."""
    r1 = BACKEND.run(["chown", "root:root", cfg_path], sudo=True, check=False)
    r2 = BACKEND.run(["chmod", "600", cfg_path], sudo=True, check=False)
    ok = not config_perm_issues(cfg_path)
    if not ok:
        err = (r1.stderr or r2.stderr or "").strip()
        print(_t("warn_perms_fix_fail", path=cfg_path,
                 err=(": " + err) if err else ""), file=sys.stderr)
    return ok


def genkey():
    return BACKEND.run([_wg_or_die(), "genkey"]).stdout.strip()


def pubkey(priv):
    return BACKEND.run([_wg_or_die(), "pubkey"], stdin=priv + "\n").stdout.strip()


def genpsk():
    return BACKEND.run([_wg_or_die(), "genpsk"]).stdout.strip()


def _addr_version(a):
    try:
        return ipaddress.ip_interface(a).version
    except ValueError:
        return None


def _server_addresses(cfg_path):
    """All Address entries from [Interface] (list of 'ip/plen' in file order)."""
    from .backend import read_config
    addrs = []
    for ln in read_config(cfg_path):
        m = re.match(r"^Address\s*=\s*(.+)$", ln, re.I)
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                if part:
                    addrs.append(part)
    return addrs


def _choose_ipv4(addrs):
    """Pick IPv4 address for client IP allocation (IPv6 space is not scanned).
    Returns first IPv4 'ip/plen', else first address, else None."""
    v4 = [a for a in addrs if "/" in a and _addr_version(a) == 4]
    if v4:
        return v4[0]
    return addrs[0] if addrs else None


def get_server_address(cfg_path):
    """Return (ip_offset, subnet_cidr, listen_port) from [Interface].

    For client IP allocation prefer IPv4: iterating hosts in IPv6 /64 = 2^64
    is meaningless and dangerous (hang).
    """
    from .backend import read_config
    port = None
    for ln in read_config(cfg_path):
        m2 = re.match(r"^ListenPort\s*=\s*(\d+)", ln, re.I)
        if m2:
            port = int(m2.group(1))
    addr = _choose_ipv4(_server_addresses(cfg_path))
    subnet = None
    if addr and "/" in addr:
        ip, plen = addr.split("/")
        net = ipaddress.ip_network(f"{ip}/{plen}", strict=False)
        subnet = str(net)
    return addr, subnet, port


def client_prefix(cfg_path):
    """Prefix (mask) of selected IPv4 server address, default 24."""
    addr = _choose_ipv4(_server_addresses(cfg_path))
    if addr and "/" in addr:
        try:
            return int(addr.split("/")[1])
        except ValueError:
            pass
    return 24


def next_free_ip(subnet, server_ip, used_ips):
    net = ipaddress.ip_network(subnet, strict=False)
    server = ipaddress.ip_address(server_ip.split("/")[0])
    scanned = 0
    for ip in net.hosts():
        scanned += 1
        if scanned > MAX_IP_SCAN:
            return None
        if ip == server:
            continue
        if str(ip) not in used_ips:
            return str(ip)
    return None


def get_server_private(cfg_path):
    from .backend import read_config
    for ln in read_config(cfg_path):
        m = re.match(r"^PrivateKey\s*=\s*(\S+)", ln, re.I)
        if m:
            return m.group(1).strip()
    return None


def _ask(prompt, default, assume_yes=False):
    """Ask user; in --yes/--batch/no TTY returns default."""
    if assume_yes or noninteractive():
        return default
    try:
        ans = input(f"{prompt} [{default}]: ").strip()
    except EOFError:
        return default
    return ans or default


def _human_bytes(n):
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _human_ago(ts):
    if not ts:
        return _t("label_never")
    delta = int(time.time()) - int(ts)
    if delta < 0:
        return _t("label_just_now")
    if delta < 60:
        return _t("label_sec_ago", n=delta)
    if delta < 3600:
        return _t("label_min_ago", n=delta // 60)
    if delta < 86400:
        return _t("label_hour_ago", n=delta // 3600)
    return _t("label_day_ago", n=delta // 86400)


def get_server_maskings(cfg_path):
    """Extract masking parameters from [Interface] of server config."""
    from .backend import read_config
    out = []
    in_interface = False
    for ln in read_config(cfg_path):
        if re.match(r"^\s*\[", ln):
            in_interface = ln.strip().lower().startswith("[interface]")
            continue
        if in_interface:
            m = re.match(r"^\s*(\w+)\s*=\s*(\S.*)$", ln)
            if m:
                nk = re.sub(r"[_\-\s]", "", m.group(1).lower())
                if nk in MASKING_KEYS:
                    out.append(f"{m.group(1)} = {m.group(2).strip()}")
    return out
