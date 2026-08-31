"""Importer logic: detect config role and parse existing [Peer] blocks."""

import re


def detect_role(lines):
    """Determine config role by presence of ListenPort in [Interface].

    Returns 'server' (has ListenPort — even without clients) or 'client'.
    """
    in_interface = False
    for ln in lines:
        s = ln.strip()
        if re.match(r"^\[", s):
            in_interface = s.lower().startswith("[interface]")
            continue
        if in_interface and re.match(r"^ListenPort\s*=\s*\d+", s, re.I):
            return "server"
    return "client"


def _parse_peer_block(block_raw, name):
    """Parse a single [Peer] block. name — name from '# BEGIN' (or None).

    Returns dict with peer fields and `clean` — block without service
    comments (only [Peer] and functional Key = Value preserved).
    """
    fields = {}
    clean = []
    priv = None
    for ln in block_raw:
        s = ln.strip()
        if not s:
            continue
        m_name = re.match(r"^#_\s*Name\s*=\s*(.+?)\s*$", s)
        if m_name and not name:
            name = m_name.group(1)
        m_priv = re.match(r"^#_\s*PrivateKey\s*=\s*(\S+)", s)
        if m_priv:
            priv = m_priv.group(1)
        if s.startswith("#"):
            continue
        if re.match(r"^\[Peer\]", s, re.I):
            clean.append("[Peer]")
            continue
        m_kv = re.match(r"^(\w+)\s*=\s*(.+?)\s*$", s)
        if m_kv:
            k, v = m_kv.group(1), m_kv.group(2).strip()
            fields[k.lower()] = v
            clean.append(f"{k} = {v}")
    return {
        "name": name,
        "pubkey": fields.get("publickey"),
        "allowed": fields.get("allowedips"),
        "psk": fields.get("presharedkey"),
        "endpoint": fields.get("endpoint"),
        "advsec": fields.get("advancedsecurity"),
        "priv": priv,
        "clean": clean,
    }


def parse_peers(lines):
    """Extract all [Peer] from config (regardless of naming format).

    Supports three naming schemes: '# BEGIN <name>'/'# END', '#_Name = <name>'
    and no name. Blocks extend until next section/marker/EOF.
    """
    peers = []
    i, n = 0, len(lines)
    pending_name = None
    while i < n:
        s = lines[i].strip()
        m_begin = re.match(r"^#\s*BEGIN\s+(.+?)\s*$", s)
        if m_begin:
            pending_name = m_begin.group(1)
            i += 1
            continue
        if re.match(r"^\[Peer\]\s*$", s, re.I):
            block_raw = [lines[i]]
            j = i + 1
            while j < n:
                s2 = lines[j].strip()
                if re.match(r"^\[\w+\]", s2):
                    break
                if re.match(r"^#\s*BEGIN\s+", s2):
                    break
                if re.match(r"^#\s*END\b", s2):
                    j += 1
                    break
                block_raw.append(lines[j])
                j += 1
            peers.append(_parse_peer_block(block_raw, pending_name))
            pending_name = None
            i = j
            continue
        i += 1
    return peers


def classify_peer(p):
    """Peer type: client (/32), gateway (wider /32), s2s (has Endpoint),
    no-allowed (no AllowedIPs). Everything except 'client' is degenerate."""
    if p.get("endpoint"):
        return "s2s"
    allowed = p.get("allowed")
    if not allowed:
        return "no-allowed"
    nets = [a.strip() for a in allowed.split(",") if a.strip()]
    if len(nets) == 1 and nets[0].endswith("/32"):
        return "client"
    return "gateway"


def peer_host_ip(p):
    """Client IP for meta.ip field: host from single /32, else ''."""
    allowed = p.get("allowed") or ""
    nets = [a.strip() for a in allowed.split(",") if a.strip()]
    if len(nets) == 1 and nets[0].endswith("/32"):
        return nets[0].split("/")[0]
    return ""


def suggest_name(p, taken):
    """Propose name: from source, else from IP (peer-<octet>/gw-<net>),
    else peerN. Guarantees uniqueness against taken set."""
    base = p.get("name")
    if not base:
        ip = peer_host_ip(p)
        if ip:
            base = "peer-" + ip.split(".")[-1]
        else:
            allowed = (p.get("allowed") or "").split(",")[0].strip()
            if allowed:
                base = "gw-" + allowed.replace("/", "_")
            else:
                base = "peer"
    base = re.sub(r"[^\w.-]", "-", base)
    name = base
    k = 1
    while name in taken:
        k += 1
        name = f"{base}{k}"
    return name
