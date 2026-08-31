"""All awgctl commands: init, list, add, del, get, rekey, set, defaults, show, restart, configs."""

import ipaddress
import json
import os
import re
import subprocess
import sys
import time

from .constants import (
    DEFAULT_PARAMS, CLIENT_PARAMS, DEFAULT_KEYS, BEGIN, END,
    HOST_LINE_PREFIX, DEFAULTS_PREFIX, STD_CONFIG_DIR,
)
from .i18n import _t
from .backend import (
    read_config, write_config, config_lock, find_wg_bin, _wg_or_die,
    BACKEND, read_secret,
)
from .utils import (
    noninteractive, config_perm_issues, fix_config_perms,
    genkey, pubkey, genpsk,
    get_server_address, client_prefix, next_free_ip,
    get_server_private, _ask,
    _human_bytes, _human_ago, get_server_maskings,
)
from .config import (
    find_ctl_region, get_ctl_host, region_contents,
    parse_meta, make_meta, get_defaults,
    _write_ctl_host, make_defaults_line, _build_region,
    _first_peer_index, normalize_region_blanks,
)
from .importer import (
    detect_role, parse_peers, classify_peer,
    peer_host_ip, suggest_name,
)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------
def cmd_init(cfg_path, host=None, assume_yes=False, rekey_imported=False,
             dry_run=False, json_out=False, fix_perms=False):
    if dry_run:
        _init_dry(cfg_path, host, json_out)
        return
    with config_lock(cfg_path):
        _cmd_init_locked(cfg_path, host, assume_yes, rekey_imported, fix_perms)


def _init_dry_report(cfg_path, host):
    """Build config parsing report for init (--dry). No writes."""
    lines = read_config(cfg_path)
    start, end = find_ctl_region(lines)
    rep = {"config": cfg_path, "perm_issues": config_perm_issues(cfg_path)}
    if start is not None:
        clients = region_contents(lines, start, end)
        rep.update(status="managed", clients=len(clients),
                   current_host=get_ctl_host(lines) or "",
                   would_set_host=host or "")
        return rep
    if detect_role(lines) == "client":
        rep.update(status="client")
        return rep
    rep["status"] = "server"
    rep["has_server_priv"] = bool(get_server_private(cfg_path))
    rep["has_wg"] = bool(find_wg_bin())
    peers_out, taken, flagged = [], set(), 0
    for p in parse_peers(lines):
        kind = classify_peer(p)
        name = suggest_name(p, taken)
        taken.add(name)
        warns = []
        if not p["pubkey"]:
            warns.append("no PublicKey — cannot manage/issue config")
        if kind != "client":
            warns.append(f"degenerate type '{kind}' — adopt as-is, "
                         f"rekey/management limited")
        elif not p["priv"]:
            warns.append("no client_priv — get will be incomplete, rekey needed")
        if warns:
            flagged += 1
        peers_out.append({
            "name": name, "name_from_config": bool(p.get("name")), "kind": kind,
            "pubkey": p["pubkey"] or "", "allowed": p["allowed"] or "",
            "endpoint": p["endpoint"] or "", "advsec": p.get("advsec") or "",
            "has_psk": bool(p["psk"]), "has_priv": bool(p["priv"]),
            "warnings": warns,
        })
    rep.update(peers=peers_out, flagged=flagged)
    return rep


def _init_dry(cfg_path, host, json_out=False):
    """Config parsing for init without writing (--dry). Text or JSON output."""
    rep = _init_dry_report(cfg_path, host)
    if json_out:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return

    print(_t("dry_run_notice", path=cfg_path))
    if rep["perm_issues"]:
        print(_t("perm_issues_notice", issues="; ".join(rep["perm_issues"])))
    if rep["status"] == "managed":
        print(_t("info_dry_managed", count=rep["clients"]))
        if rep["would_set_host"]:
            print(f"init would update default host: "
                  f"{rep['current_host'] or '—'} -> {rep['would_set_host']}.")
        else:
            print("init would change nothing (host not provided).")
        return
    if rep["status"] == "client":
        print(_t("info_dry_role_client"))
        print(_t("info_dry_rejected"))
        return

    print(_t("info_dry_role_server"))
    if not rep["has_server_priv"]:
        print("  ⚠ no PrivateKey in [Interface] — server_pub cannot be computed, "
              "init would fail.")
    elif not rep["has_wg"]:
        print("  ⚠ awg/wg not available locally — server_pub will be empty on import "
              "(filled at get/rekey where wg is available).")
    peers = rep["peers"]
    if not peers:
        print("\n" + _t("info_dry_no_peers"))
        return
    print("\n" + _t("info_dry_peers_found", count=len(peers)))
    for idx, p in enumerate(peers, 1):
        src = "from config" if p["name_from_config"] else "auto"
        print(_t("info_dry_peer", idx=idx, name=p["name"], src=src, kind=p["kind"]))
        print(_t("info_dry_peer_pubkey", pubkey=(p["pubkey"] or "— NOT found")))
        print(_t("info_dry_peer_allowed", allowed=(p["allowed"] or "— NOT found")))
        print(_t("info_dry_peer_endpoint", endpoint=(p["endpoint"] or "—")))
        if p["advsec"]:
            print(_t("info_dry_peer_advsec", advsec=p["advsec"]))
        print(_t("info_dry_peer_psk", psk=("yes" if p["has_psk"] else "—")))
        print(_t("info_dry_peer_priv", priv=("yes (#_PrivateKey)" if p["has_priv"] else "— no")))
        for w in p["warnings"]:
            print(f"      ⚠ {w}")
    print("\n" + _t("info_dry_summary", count=len(peers), flagged=rep["flagged"]))


def _init_fix_perms(cfg_path, fix_perms):
    """During init: unsafe config permissions are fixed only with --fix-perms
    (privileged action). Without flag — offer interactively (with TTY)
    or warn (in batch/no TTY).
    """
    issues = config_perm_issues(cfg_path)
    if not issues:
        return
    print(_t("warn_perms_init", path=cfg_path, issues="; ".join(issues)),
          file=sys.stderr)
    print("  Config contains private keys — root:root 0600 is recommended.",
          file=sys.stderr)
    do_fix = fix_perms
    if not do_fix and not noninteractive():
        ans = _ask(_t("prompt_fix_perms"), "N")
        do_fix = ans.strip().lower() in ("y", "yes", "д", "да")
    if do_fix:
        if fix_config_perms(cfg_path):
            print(_t("info_perms_fixed"), file=sys.stderr)
    else:
        print("  Left as-is (fix manually or run init with --fix-perms).",
              file=sys.stderr)


def _cmd_init_locked(cfg_path, host=None, assume_yes=False,
                     rekey_imported=False, fix_perms=False):
    _init_fix_perms(cfg_path, fix_perms)
    lines = read_config(cfg_path)
    start, end = find_ctl_region(lines)
    if start is not None:
        _update_ctl_host(cfg_path, lines, start, end, host)
        return
    if detect_role(lines) == "client":
        print(_t("err_client_config"), file=sys.stderr)
        sys.exit(1)
    peers = parse_peers(lines)
    if not peers:
        _init_markers_only(cfg_path, lines, host)
        return
    _init_import(cfg_path, lines, peers, host, assume_yes, rekey_imported)


def _init_markers_only(cfg_path, lines, host):
    """Server without clients: just add markers at the end."""
    head = list(lines)
    while head and head[-1].strip() == "":
        head.pop()
    new_lines = head + _build_region(host, [])
    normalize_region_blanks(new_lines)
    write_config(cfg_path, new_lines)
    if not host:
        print(_t("warn_no_host"), file=sys.stderr)
    print(_t("info_markup_added", path=cfg_path))


def _regen_into(entry, clean, server_pub):
    """Generate new client pair+PSK and write into entry and clean [Peer]."""
    priv = genkey()
    pub = pubkey(priv)
    psk = genpsk()
    entry.update(client_priv=priv, client_pub=pub, psk=psk)
    if server_pub:
        entry["server_pub"] = server_pub
    psk_done = False
    for k in range(len(clean)):
        if re.match(r"^\s*PublicKey\s*=", clean[k], re.I):
            clean[k] = f"PublicKey = {pub}"
        elif re.match(r"^\s*PresharedKey\s*=", clean[k], re.I):
            clean[k] = f"PresharedKey = {psk}"
            psk_done = True
    if not psk_done:
        for k in range(len(clean)):
            if clean[k].startswith("PublicKey ="):
                clean.insert(k + 1, f"PresharedKey = {psk}")
                break


def _init_import(cfg_path, lines, peers, host, assume_yes, rekey_imported=False):
    """Adopt existing [Peer] into AWGCTL zone (init auto-conversion)."""
    server_priv = get_server_private(cfg_path)
    if not server_priv:
        print(_t("err_import_no_priv"), file=sys.stderr)
        sys.exit(1)
    wgbin = find_wg_bin()
    server_pub = ""
    if wgbin:
        try:
            server_pub = pubkey(server_priv)
        except subprocess.CalledProcessError:
            pass

    print(_t("msg_import_count", count=len(peers)), file=sys.stderr)
    taken, entries, eligible = set(), [], []
    for p in peers:
        kind = classify_peer(p)
        default = suggest_name(p, taken)
        if assume_yes or noninteractive():
            name = default
        else:
            pub = (p["pubkey"] or "-")[:16]
            print(_t("msg_peer_summary", pub=pub, allow=(p["allowed"] or "-"),
                     kind=kind, priv=("yes" if p["priv"] else "no")),
                  file=sys.stderr)
            name = re.sub(r"[^\w.-]", "-", _ask(_t("prompt_name"), default)) or default
            while name in taken:
                name = re.sub(r"[^\w.-]", "-",
                              _ask(_t("prompt_name_taken", name=name), default + "2"))                     or default + "2"
        taken.add(name)
        if kind != "client":
            print(_t("msg_degenerate", name=name, kind=kind), file=sys.stderr)
        elif not p["priv"]:
            print(_t("msg_no_client_priv", name=name), file=sys.stderr)
        entry = {
            "name": name,
            "ip": peer_host_ip(p),
            "allow": p["allowed"] or "",
            "routes": "0.0.0.0/0, ::/0",
            "keepalive": "25",
            "endpoint": "",
            "psk": p["psk"] or "",
            "server_pub": server_pub,
            "client_pub": p["pubkey"] or "",
            "client_priv": p["priv"] or "",
        }
        entries.append((entry, p["clean"]))
        if kind == "client" and not p["priv"]:
            eligible.append((entry, p["clean"]))

    if eligible:
        do_rekey = rekey_imported
        if not do_rekey and not assume_yes and not noninteractive():
            ans = _ask(_t("prompt_rekey", count=len(eligible)), "N")
            do_rekey = ans.strip().lower() in ("y", "yes", "д", "да")
        if do_rekey and not wgbin:
            print(_t("warn_no_wg_import"), file=sys.stderr)
        elif do_rekey:
            for entry, clean in eligible:
                _regen_into(entry, clean, server_pub)
            print(_t("info_rekeyed", count=len(eligible)), file=sys.stderr)

    cut = _first_peer_index(lines)
    head = lines[:cut]
    while head and head[-1].strip() == "":
        head.pop()
    new_lines = head + _build_region(host, entries)
    normalize_region_blanks(new_lines)
    write_config(cfg_path, new_lines)
    if not host:
        print(_t("warn_no_host_init"), file=sys.stderr)
    print(_t("info_imported", count=len(entries), path=cfg_path), file=sys.stderr)


def _update_ctl_host(cfg_path, lines, start, end, host):
    """Markup already exists: update HOST line if host provided, else notify."""
    if host is None:
        print(_t("info_markup_exists"))
        return
    changed = False
    for i in range(start + 1, (end if end is not None else len(lines))):
        if lines[i].strip().startswith(HOST_LINE_PREFIX):
            lines[i] = f"{HOST_LINE_PREFIX} {host}"
            changed = True
            break
    if not changed:
        lines.insert(start + 1, f"{HOST_LINE_PREFIX} {host}")
    write_config(cfg_path, lines)
    print(_t("info_host_updated", host=host))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
def cmd_list(cfg_path, json_out=False):
    lines = read_config(cfg_path)
    clients = region_contents(lines, *find_ctl_region(lines))
    if json_out:
        out = [{
            "name": c.get("name", ""),
            "ip": c.get("ip", ""),
            "allow": c.get("allow", ""),
            "routes": c.get("routes", ""),
            "endpoint": c.get("endpoint", ""),
            "keepalive": c.get("keepalive", "25"),
            "client_pub": c.get("client_pub", ""),
            "has_client_priv": bool(c.get("client_priv")),
            "has_psk": bool(c.get("psk")),
        } for c in clients]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not clients:
        print(_t("msg_no_clients"))
        return
    print(f"{_t('label_name'):<20} {_t('label_ip'):<20} {_t('label_allow'):<20} "
          f"{_t('label_routes'):<28} {_t('label_endpoint'):<12} {_t('label_ka')}")
    for c in clients:
        print(f"{c.get('name',''):<20} {c.get('ip',''):<20} "
              f"{c.get('allow',''):<20} {c.get('routes',''):<28} "
              f"{c.get('endpoint',''):<12} {c.get('keepalive','25')}")
    print("\n" + _t("msg_total_clients", count=len(clients)))


# ---------------------------------------------------------------------------
# configs overview
# ---------------------------------------------------------------------------
def config_status(lines):
    """Classify config by its lines.

    Returns ('client'|'unmanaged'|'managed', n_clients). n_clients is count
    of AWGCTL zone records (for managed), otherwise count of [Peer] in file.
    """
    if detect_role(lines) == "client":
        return "client", 0
    start, end = find_ctl_region(lines)
    if start is not None:
        return "managed", len(region_contents(lines, start, end))
    return "unmanaged", len(parse_peers(lines))


STATUS_RU = {
    "client": _t("status_client"),
    "unmanaged": _t("status_unmanaged"),
    "managed": _t("status_managed"),
}


def cmd_configs(directory=None, json_out=False):
    """Overview of configs in directory: name, role/status, client/peer count.

    Statuses: client (no ListenPort), unmanaged (server without AWGCTL markup),
    managed (server under awgctl management).
    """
    directory = directory or STD_CONFIG_DIR
    names = [n for n in BACKEND.list_dir(directory) if n.endswith(".conf")]
    rows = []
    for name in names:
        path = os.path.join(directory, name)
        row = {"name": name, "path": path}
        try:
            lines = read_config(path)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as e:
            row.update(status="error", status_ru=_t("status_no_access"), count=None,
                       error=str(e).strip())
            rows.append(row)
            continue
        status, count = config_status(lines)
        row.update(status=status, status_ru=STATUS_RU[status], count=count)
        rows.append(row)

    if json_out:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print(_t("msg_no_configs", dir=directory))
        return
    print(f"{_t('label_config'):<24} {_t('label_status'):<20} {_t('label_clients')}")
    for r in rows:
        if r["status"] == "error":
            cnt = "—"
        elif r["status"] == "client":
            cnt = "—"
        else:
            cnt = str(r["count"])
        print(f"{r['name']:<24} {r['status_ru']:<20} {cnt}")
    print("\n" + _t("msg_total_configs", count=len(rows), dir=directory))


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------
def validate_allowed_ips(value, what):
    """Verify string is a comma-separated list of CIDRs. Exits on error."""
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ipaddress.ip_network(part, strict=False)
        except ValueError:
            print(_t("err_bad_cidr", what=what, part=part), file=sys.stderr)
            sys.exit(1)


def cmd_add(cfg_path, name, allow=None, routes=None, keepalive=None,
            endpoint=None, dns=None, json_out=False):
    if not find_wg_bin():
        print(_t("err_no_wg"), file=sys.stderr)
        sys.exit(1)
    if not re.match(r"^[\w.-]+$", name):
        print(_t("err_invalid_name"), file=sys.stderr)
        sys.exit(1)
    if allow is not None:
        validate_allowed_ips(allow, "--client-allow")
    if routes is not None:
        validate_allowed_ips(routes, "--client-routes")

    with config_lock(cfg_path):
        lines = read_config(cfg_path)
        defaults = get_defaults(lines)
        start, end = find_ctl_region(lines)
        if start is None:
            print(_t("err_no_markup"), file=sys.stderr)
            sys.exit(1)

        clients = region_contents(lines, start, end)
        existing = [c["name"] for c in clients]
        if name in existing:
            print(_t("err_exists", name=name), file=sys.stderr)
            sys.exit(1)
        used_ips = {c["ip"] for c in clients}

        addr, subnet, port = get_server_address(cfg_path)
        if subnet is None:
            print(_t("err_no_address"), file=sys.stderr)
            sys.exit(1)

        client_ip_val = next_free_ip(subnet, addr, used_ips)
        if client_ip_val is None:
            print(_t("err_no_free_ip"), file=sys.stderr)
            sys.exit(1)

        if allow is None:
            allow = f"{client_ip_val}/32"
        if routes is None:
            routes = defaults["routes"]
        if keepalive is None:
            keepalive = defaults["keepalive"]
        if dns is None:
            dns = defaults["dns"]
        if endpoint is None:
            endpoint = ""

        server_priv = get_server_private(cfg_path)
        if not server_priv:
            print(_t("err_no_server_priv"), file=sys.stderr)
            sys.exit(1)
        try:
            server_pub = pubkey(server_priv)
        except subprocess.CalledProcessError:
            print(_t("err_server_pub_fail"), file=sys.stderr)
            sys.exit(1)

        priv = genkey()
        pub = pubkey(priv)
        psk = genpsk()

        entry = {
            "name": name,
            "ip": client_ip_val,
            "allow": allow,
            "routes": routes,
            "keepalive": keepalive,
            "endpoint": endpoint,
            "dns": dns,
            "psk": psk,
            "server_pub": server_pub,
            "client_pub": pub,
            "client_priv": priv,
        }

        meta_line = make_meta(entry)
        peer_block = [
            "",
            meta_line,
            "[Peer]",
            f"PublicKey = {pub}",
            f"PresharedKey = {psk}",
            f"AllowedIPs = {allow}",
            "",
        ]
        new_lines = lines[:end] + peer_block + lines[end:]
        normalize_region_blanks(new_lines)
        write_config(cfg_path, new_lines)

        ctl_host = get_ctl_host(lines)

    kw = dict(host=ctl_host or "", port=port, prefix=client_prefix(cfg_path),
              masking=get_server_maskings(cfg_path))
    if json_out:
        print(json.dumps(client_json(entry, **kw), ensure_ascii=False, indent=2))
    else:
        print_client_config(entry, **kw)
    print("\n" + _t("info_added", name=name, path=cfg_path), file=sys.stderr)


# ---------------------------------------------------------------------------
# client config rendering
# ---------------------------------------------------------------------------
def _bracket_host(host):
    """Wrap bare IPv6 literal in brackets for host:port endpoint."""
    if host and ":" in host and not host.startswith("["):
        try:
            ipaddress.IPv6Address(host)
            return f"[{host}]"
        except ValueError:
            pass
    return host


def _resolve_client_fields(e, host="", port=None, prefix=24):
    """Return effective (considering defaults/priorities) client fields."""
    routes = e.get("routes") or DEFAULT_PARAMS["routes"]
    keepalive = e.get("keepalive") or DEFAULT_PARAMS["keepalive"]
    dns = e.get("dns") or DEFAULT_PARAMS["dns"]
    eff_host = e.get("host") or host
    if e.get("endpoint"):
        endpoint = e["endpoint"]
    elif eff_host:
        endpoint = f"{_bracket_host(eff_host)}:{port}" if port else eff_host
    else:
        endpoint = ""
    return {
        "name": e.get("name", ""),
        "address": f"{e['ip']}/{prefix}",
        "dns": dns,
        "routes": routes,
        "keepalive": keepalive,
        "endpoint": endpoint,
        "server_pub": e.get("server_pub", ""),
        "client_pub": e.get("client_pub", ""),
        "client_priv": e.get("client_priv", ""),
        "psk": e.get("psk", ""),
    }


def render_client_config(e, host="", port=None, prefix=24, masking=()):
    """Assemble client config text (string)."""
    f = _resolve_client_fields(e, host, port, prefix)
    out = (
        "[Interface]\n"
        f"PrivateKey = {f['client_priv']}\n"
        f"Address = {f['address']}\n"
    )
    if f["dns"]:
        out += f"DNS = {f['dns']}\n"
    if masking:
        out += "\n" + "\n".join(masking) + "\n"
    out += (
        "\n[Peer]\n"
        f"PublicKey = {f['server_pub']}\n"
    )
    if f["psk"]:
        out += f"PresharedKey = {f['psk']}\n"
    if f["endpoint"]:
        out += f"Endpoint = {f['endpoint']}\n"
    out += (f"AllowedIPs = {f['routes']}\n"
            f"PersistentKeepalive = {f['keepalive']}\n")
    return out


def client_json(e, host="", port=None, prefix=24, masking=()):
    """Structured representation of client + ready config string."""
    f = _resolve_client_fields(e, host, port, prefix)
    f["masking"] = list(masking)
    f["config"] = render_client_config(e, host, port, prefix, masking)
    return f


def print_client_config(e, host="", port=None, prefix=24, masking=()):
    print(render_client_config(e, host, port, prefix, masking), end="")


# ---------------------------------------------------------------------------
# del
# ---------------------------------------------------------------------------
def cmd_del(cfg_path, name):
    with config_lock(cfg_path):
        _cmd_del_locked(cfg_path, name)


def _cmd_del_locked(cfg_path, name):
    lines = read_config(cfg_path)
    start, end = find_ctl_region(lines)
    if start is None or end is None:
        print(_t("err_no_markup"), file=sys.stderr)
        sys.exit(1)
    i = start + 1
    found_start = None
    while i < end:
        if lines[i].startswith("# AWGCTL"):
            meta = parse_meta(lines[i])
            if meta and meta.get("name") == name:
                found_start = i
                break
        i += 1
    if found_start is None:
        print(_t("err_peer_not_found", name=name), file=sys.stderr)
        sys.exit(1)
    j = found_start + 1
    while j < end:
        if lines[j].startswith("# AWGCTL"):
            break
        j += 1
    del lines[found_start:j]
    normalize_region_blanks(lines)
    write_config(cfg_path, lines)
    print(_t("info_deleted", name=name))


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
def cmd_get(cfg_path, name, json_out=False):
    lines = read_config(cfg_path)
    clients = region_contents(lines, *find_ctl_region(lines))
    host = get_ctl_host(lines)
    prefix = client_prefix(cfg_path)
    addr, subnet, port = get_server_address(cfg_path)
    defaults = get_defaults(lines)
    for c in clients:
        if c.get("name") == name:
            for k in ("dns", "routes", "keepalive"):
                if not c.get(k):
                    c[k] = defaults[k]
            if not c.get("server_pub"):
                priv = get_server_private(cfg_path)
                if priv and find_wg_bin():
                    try:
                        c["server_pub"] = pubkey(priv)
                    except subprocess.CalledProcessError:
                        pass
            if not c.get("server_pub"):
                print(_t("warn_server_pub_missing"), file=sys.stderr)
            if not c.get("client_priv"):
                print(_t("warn_client_priv_missing", name=name), file=sys.stderr)
            kw = dict(host=host or "", port=port, prefix=prefix,
                      masking=get_server_maskings(cfg_path))
            if json_out:
                print(json.dumps(client_json(c, **kw), ensure_ascii=False, indent=2))
            else:
                print_client_config(c, **kw)
            return
    print(_t("err_peer_not_found", name=name), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------
def _print_defaults(d):
    for k in DEFAULT_KEYS:
        print(f"  {k:<10}= {d.get(k, '') or '—'}")


def cmd_defaults(cfg_path, changes=None):
    """Show or change default client parameters at config level.

    changes — dict subset of DEFAULT_KEYS (host/dns/routes/keepalive). host
    is stored in # AWGCTL-HOST line, others in # AWGCTL-DEFAULTS line.
    Without changes prints current defaults. Values are used in add when
    corresponding flag is not set.
    """
    changes = changes or {}
    if not changes:
        d = get_defaults(read_config(cfg_path))
        print("Default client parameters (used in add when flag omitted):")
        _print_defaults(d)
        return
    if "routes" in changes:
        validate_allowed_ips(changes["routes"], "--routes")
    if "keepalive" in changes:
        _validate_keepalive(changes["keepalive"])
    with config_lock(cfg_path):
        lines = read_config(cfg_path)
        start, end = find_ctl_region(lines)
        if start is None or end is None:
            print(_t("err_no_markup"), file=sys.stderr)
            sys.exit(1)
        if "host" in changes:
            _write_ctl_host(lines, start, end, changes["host"])
            start, end = find_ctl_region(lines)
        rest = {k: v for k, v in changes.items() if k != "host"}
        if rest:
            d = get_defaults(lines)
            d.update(rest)
            new_line = make_defaults_line(d)
            idx = None
            for i in range(start + 1, end):
                if lines[i].strip().startswith(DEFAULTS_PREFIX):
                    idx = i
                    break
            if idx is not None:
                lines[idx] = new_line
            else:
                ins = start + 1
                for i in range(start + 1, end):
                    if lines[i].strip().startswith(HOST_LINE_PREFIX):
                        ins = i + 1
                        break
                lines.insert(ins, new_line)
        final = get_defaults(lines)
        write_config(cfg_path, lines)
    print("Defaults updated:")
    _print_defaults(final)


def _validate_keepalive(v):
    try:
        int(v)
    except (TypeError, ValueError):
        print(_t("err_keepalive_num", v=v), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------
def cmd_set(cfg_path, names, all_clients=False, changes=None):
    """Change parameters of existing clients (supports bulk).

    names — client names; all_clients — apply to all. changes — dict subset
    of CLIENT_PARAMS (dns/routes/keepalive/endpoint/allow). Modifies meta
    line; for `allow` also changes AllowedIPs in server [Peer]. Does not
    touch keys (pub/priv/psk) — use rekey for rotation.
    """
    changes = changes or {}
    if not changes:
        print(_t("err_no_params"), file=sys.stderr)
        sys.exit(1)
    if not all_clients and not names:
        print(_t("err_no_names"), file=sys.stderr)
        sys.exit(1)
    if "routes" in changes:
        validate_allowed_ips(changes["routes"], "--routes")
    if "allow" in changes:
        validate_allowed_ips(changes["allow"], "--allow")
    if "keepalive" in changes:
        _validate_keepalive(changes["keepalive"])

    with config_lock(cfg_path):
        lines = read_config(cfg_path)
        start, end = find_ctl_region(lines)
        if start is None or end is None:
            print(_t("err_no_markup"), file=sys.stderr)
            sys.exit(1)
        metas = []
        for i in range(start + 1, end):
            if lines[i].startswith("# AWGCTL"):
                meta = parse_meta(lines[i])
                if meta and meta.get("name"):
                    metas.append((i, meta))
        if not metas:
            print(_t("msg_no_clients"), file=sys.stderr)
            sys.exit(1)

        if all_clients:
            selected = metas
        else:
            by_name = {m[1]["name"]: m for m in metas}
            missing = [n for n in names if n not in by_name]
            if missing:
                print(_t("err_missing_clients", names=", ".join(missing)),
                      file=sys.stderr)
                sys.exit(1)
            selected = [by_name[n] for n in names]

        changed = []
        for meta_idx, meta in selected:
            b = meta_idx + 1
            while b < end and not lines[b].startswith("# AWGCTL"):
                b += 1
            meta.update(changes)
            lines[meta_idx] = make_meta(meta)
            if "allow" in changes:
                _apply_allow(lines, meta_idx, b, changes["allow"])
            changed.append(meta["name"])
        normalize_region_blanks(lines)
        write_config(cfg_path, lines)

    fields = ", ".join(f"{k}={v}" for k, v in changes.items())
    print(_t("info_changed", count=len(changed), fields=fields))
    for n in changed:
        print(f"  - {n}")
    print(_t("msg_distribute"), file=sys.stderr)


def _apply_allow(lines, meta_idx, block_end, allow):
    """Update (or insert) AllowedIPs line in client's [Peer] block."""
    for j in range(meta_idx + 1, block_end):
        if re.match(r"^\s*AllowedIPs\s*=", lines[j], re.I):
            lines[j] = f"AllowedIPs = {allow}"
            return
    anchor = None
    for j in range(meta_idx + 1, block_end):
        if re.match(r"^\s*PublicKey\s*=", lines[j], re.I):
            anchor = j
        elif re.match(r"^\s*\[Peer\]", lines[j], re.I) and anchor is None:
            anchor = j
    if anchor is not None:
        lines.insert(anchor + 1, f"AllowedIPs = {allow}")


# ---------------------------------------------------------------------------
# rekey
# ---------------------------------------------------------------------------
def cmd_rekey(cfg_path, name):
    """Rotate client keys: new pair + PSK, update [Peer] and meta.

    Gives full management for imported clients without client_priv. Changes
    keys — old client config stops connecting until new one is distributed.
    """
    if not find_wg_bin():
        print(_t("err_no_wg"), file=sys.stderr)
        sys.exit(1)
    with config_lock(cfg_path):
        lines = read_config(cfg_path)
        start, end = find_ctl_region(lines)
        if start is None or end is None:
            print(_t("err_no_markup"), file=sys.stderr)
            sys.exit(1)
        meta_idx = None
        for i in range(start + 1, end):
            if lines[i].startswith("# AWGCTL"):
                meta = parse_meta(lines[i])
                if meta and meta.get("name") == name:
                    meta_idx = i
                    break
        if meta_idx is None:
            print(_t("err_peer_not_found", name=name), file=sys.stderr)
            sys.exit(1)
        b = meta_idx + 1
        while (b < end and lines[b].strip() != ""
               and not lines[b].startswith("# AWGCTL")):
            b += 1

        entry = parse_meta(lines[meta_idx])
        server_priv = get_server_private(cfg_path)
        server_pub = entry.get("server_pub") or ""
        if not server_pub and server_priv:
            try:
                server_pub = pubkey(server_priv)
            except subprocess.CalledProcessError:
                pass

        priv = genkey()
        pub = pubkey(priv)
        psk = genpsk()
        entry.update(client_priv=priv, client_pub=pub, psk=psk,
                     server_pub=server_pub)
        entry.setdefault("routes", "0.0.0.0/0, ::/0")
        entry.setdefault("keepalive", "25")
        entry.setdefault("endpoint", "")
        entry.setdefault("allow", "")
        entry.setdefault("ip", "")

        lines[meta_idx] = make_meta(entry)
        pub_i = psk_i = None
        for k in range(meta_idx + 1, b):
            if re.match(r"^\s*PublicKey\s*=", lines[k], re.I):
                pub_i = k
            elif re.match(r"^\s*PresharedKey\s*=", lines[k], re.I):
                psk_i = k
        if pub_i is not None:
            lines[pub_i] = f"PublicKey = {pub}"
        if psk_i is not None:
            lines[psk_i] = f"PresharedKey = {psk}"
        elif pub_i is not None:
            lines.insert(pub_i + 1, f"PresharedKey = {psk}")
            b += 1

        write_config(cfg_path, lines)
        host = get_ctl_host(lines)
        _, _, port = get_server_address(cfg_path)

    print_client_config(entry, host=host or "", port=port,
                        prefix=client_prefix(cfg_path),
                        masking=get_server_maskings(cfg_path))
    print("\n" + _t("info_rekeyed_client", name=name), file=sys.stderr)


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------
def cmd_restart(cfg_path):
    iface = os.path.splitext(os.path.basename(cfg_path))[0]
    running = BACKEND.run(["ip", "link", "show", iface],
                          sudo=True, check=False).returncode == 0
    if not running:
        print(_t("info_not_running", iface=iface), file=sys.stderr)
        return
    BACKEND.run(["awg-quick", "down", iface], sudo=True)
    BACKEND.run(["awg-quick", "up", iface], sudo=True)
    print(_t("info_restart", iface=iface))


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
def cmd_show(cfg_path, json_out=False):
    """Live tunnel status: per client — name, handshake, RX/TX, endpoint.

    Data from `awg show <iface> dump` (needs running interface and root/--sudo).
    Public keys are matched to names from AWGCTL zone.
    """
    iface = os.path.splitext(os.path.basename(cfg_path))[0]
    if not find_wg_bin():
        print(_t("err_no_wg"), file=sys.stderr)
        sys.exit(1)
    wg = _wg_or_die()
    r = BACKEND.run([wg, "show", iface, "dump"], sudo=True, check=False)
    if r.returncode != 0:
        msg = (r.stderr or "").strip()
        print(f"Error: failed to get status for '{iface}' "
              f"(interface running?){': ' + msg if msg else ''}",
              file=sys.stderr)
        sys.exit(1)

    lines = read_config(cfg_path)
    clients = region_contents(lines, *find_ctl_region(lines))
    name_by_pub = {c.get("client_pub", ""): c.get("name", "")
                   for c in clients if c.get("client_pub")}

    dump = r.stdout.splitlines()
    peers = []
    for ln in dump[1:]:
        f = ln.split("\t")
        if len(f) < 8:
            continue
        pub, _psk, endpoint, allowed, hs, rx, tx, ka = f[:8]
        peers.append({
            "name": name_by_pub.get(pub, ""),
            "pubkey": pub,
            "endpoint": endpoint if endpoint != "(none)" else "",
            "allowed_ips": allowed,
            "latest_handshake": int(hs) if hs.isdigit() else 0,
            "transfer_rx": int(rx) if rx.isdigit() else 0,
            "transfer_tx": int(tx) if tx.isdigit() else 0,
            "keepalive": ka,
        })

    if json_out:
        print(json.dumps({"interface": iface, "peers": peers},
                         ensure_ascii=False, indent=2))
        return
    if not peers:
        print(_t("msg_peer_none", iface=iface))
        return
    print(f"{_t('label_name'):<20} {_t('label_handshake'):<16} "
          f"{_t('label_rx'):>10} {_t('label_tx'):>10}  ENDPOINT")
    for p in peers:
        print(f"{(p['name'] or _t('label_unknown')):<20} "
              f"{_human_ago(p['latest_handshake']):<16} "
              f"{_human_bytes(p['transfer_rx']):>10} "
              f"{_human_bytes(p['transfer_tx']):>10}  {p['endpoint'] or '—'}")
    print("\n" + _t("msg_peers_count", count=len(peers), iface=iface))
