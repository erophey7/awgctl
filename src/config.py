"""Config parsing and serialization: AWGCTL markup zone and peer blocks."""

import re

from .constants import BEGIN, END, META_FIELDS, HOST_LINE_PREFIX, DEFAULTS_PREFIX


def is_ctl_comments(s):
    s = s.strip()
    return s.startswith("# AWGCTL") or s == BEGIN or s == END


def find_ctl_region(lines):
    start = end = None
    for i, ln in enumerate(lines):
        if ln.strip() == BEGIN and start is None:
            start = i
        if ln.strip() == END:
            end = i
    return start, end


def get_ctl_host(lines):
    """Default endpoint (host) from markup section, or None."""
    start, end = find_ctl_region(lines)
    if start is None:
        return None
    for i in range(start + 1, (end if end is not None else len(lines))):
        ln = lines[i].strip()
        if ln.startswith(HOST_LINE_PREFIX):
            return ln[len(HOST_LINE_PREFIX):].strip()
    return None


def region_contents(lines, start, end):
    """Parse zone between markers. Returns list of clients and peers."""
    if start is None:
        return []
    clients = []
    cur = {}
    i = start + 1
    while i < (end if end is not None else len(lines)):
        ln = lines[i]
        if ln.startswith("# AWGCTL"):
            meta = parse_meta(ln)
            if meta:
                cur = meta
                cur["_peer_lines"] = []
        elif re.match(r"^\s*\[\w+\]", ln):
            cur.setdefault("_peer_lines", []).append(ln)
        elif cur.get("_peer_lines") is not None:
            cur["_peer_lines"].append(ln)
        if ln.strip() == "" and cur.get("name"):
            clients.append(cur)
            cur = {}
        i += 1
    if cur.get("name"):
        clients.append(cur)
    return clients


def parse_meta(line):
    m = re.match(r"^# AWGCTL\s*\|(.*)\|$", line.strip())
    if not m:
        return None
    d = {}
    for part in m.group(1).split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def make_meta(d):
    """Serialize client record into meta-string according to META_FIELDS.

    Missing fields are written empty — does not break if dict is incomplete
    (e.g. imported/old records without dns).
    """
    parts = "|".join(f"{k}={d.get(k, '')}" for k in META_FIELDS)
    return f"# AWGCTL |{parts}|"


def get_defaults(lines):
    """Default client parameters: fallback DEFAULT_PARAMS, overridden by
    `# AWGCTL-DEFAULTS |k=v|...` (dns/routes/keepalive) and `# AWGCTL-HOST`
    (host) in the markup zone."""
    from .constants import DEFAULT_PARAMS
    d = dict(DEFAULT_PARAMS)
    d["host"] = get_ctl_host(lines) or ""
    start, end = find_ctl_region(lines)
    if start is None:
        return d
    for i in range(start + 1, (end if end is not None else len(lines))):
        ln = lines[i].strip()
        m = re.match(r"^# AWGCTL-DEFAULTS\s*\|(.*)\|$", ln)
        if m:
            for part in m.group(1).split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if v.strip():
                        d[k.strip()] = v.strip()
            break
    return d


def _write_ctl_host(lines, start, end, host):
    """Update or insert # AWGCTL-HOST line in markup zone (in-place)."""
    limit = end if end is not None else len(lines)
    for i in range(start + 1, limit):
        if lines[i].strip().startswith(HOST_LINE_PREFIX):
            lines[i] = f"{HOST_LINE_PREFIX} {host}"
            return
    lines.insert(start + 1, f"{HOST_LINE_PREFIX} {host}")


def make_defaults_line(d):
    keys = ("dns", "routes", "keepalive")
    parts = "|".join(f"{k}={d.get(k, '')}" for k in keys)
    return f"{DEFAULTS_PREFIX} |{parts}|"


def _build_region(host, entries):
    """Build AWGCTL zone block: markers + host + (meta + clean [Peer])* ."""
    rb = ["", BEGIN]
    if host:
        rb.append(f"{HOST_LINE_PREFIX} {host}")
    rb.append("# Managed AWGCTL client zone (do not edit manually).")
    rb.append("# Add/remove clients only via awgctl.")
    for entry, clean in entries:
        rb.append("")
        rb.append(make_meta(entry))
        rb.extend(clean)
    rb.append("")
    rb.append(END)
    return rb


def _first_peer_index(lines):
    """Index of first peer line ([Peer] or '# BEGIN <name>'), else len."""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if re.match(r"^\[Peer\]", s, re.I) or re.match(r"^#\s*BEGIN\s+", s):
            return i
    return len(lines)


def normalize_region_blanks(lines):
    """Collapse consecutive empty lines inside AWGCTL zone to single blanks.

    After del/add empty separators accumulate; normalize zone between
    BEGIN and END to canonical form (no more than one consecutive blank).
    Modifies lines in place.
    """
    start, end = find_ctl_region(lines)
    if start is None or end is None:
        return
    cleaned = []
    prev_blank = False
    for ln in lines[start + 1:end]:
        blank = ln.strip() == ""
        if blank and prev_blank:
            continue
        cleaned.append(ln)
        prev_blank = blank
    lines[start + 1:end] = cleaned
