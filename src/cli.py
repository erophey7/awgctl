"""CLI entry point: argument parsing, command routing, connection bootstrap."""

import argparse
import os
import re
import sys

from .constants import (set_batch, COMMANDS, GLOBAL_COMMANDS, STD_CONFIG_DIR,
                        DEFAULT_KEYS, CLIENT_PARAMS)
from .i18n import _t
from .backend import BACKEND, SshBackend
from .commands import (
    cmd_init, cmd_list, cmd_add, cmd_del, cmd_get,
    cmd_rekey, cmd_set, cmd_defaults, cmd_show,
    cmd_restart, cmd_configs, cmd_rename
)
from .utils import warn_config_perms


def resolve_config(name):
    if BACKEND.exists(name):
        return name
    if os.sep not in name:
        candidates = [name] if name.endswith(".conf") else [name, name + ".conf"]
        for c in candidates:
            p = os.path.join(STD_CONFIG_DIR, c)
            if BACKEND.exists(p):
                return p
    return None


def _inject_config_for_help(argv):
    if "-h" not in argv and "--help" not in argv:
        return argv
    first = next((t for t in argv if not t.startswith("-")), None)
    if first is None:
        return argv
    if first in COMMANDS or len([c for c in COMMANDS if c.startswith(first)]) == 1:
        return ["\x00nocfg"] + argv
    return argv


def expand_command(argv):
    seen_positional = 0
    for i, tok in enumerate(argv):
        if tok in ("-h", "--help"):
            return
        if tok.startswith("-"):
            continue
        seen_positional += 1
        if seen_positional == 1:
            continue
        if tok in COMMANDS:
            return
        matches = sorted(c for c in COMMANDS if c.startswith(tok))
        if len(matches) == 1:
            argv[i] = matches[0]
        elif len(matches) > 1:
            print(f"awgctl: ambiguous command '{tok}': {', '.join(matches)}",
                  file=sys.stderr)
            sys.exit(2)
        return


def _make_conn_parent():
    conn_opt = argparse.ArgumentParser(add_help=False)
    g = conn_opt.add_argument_group(_t("conn_group"))
    g.add_argument("--ssh", metavar="[USER@]HOST[:PORT]", default=None,
                   help=_t("help_ssh"))
    g.add_argument("--ssh-config", metavar="PATH", default=None,
                   help=_t("help_ssh_config"))
    g.add_argument("--sudo", action="store_true", help=_t("help_sudo"))
    g.add_argument("--ask-pass", dest="ask_pass", action="store_true",
                   help=_t("help_ask_pass"))
    g.add_argument("--ssh-pass", dest="ssh_pass", metavar="SRC", default=None,
                   help=_t("help_ssh_pass"))
    g.add_argument("--sudo-pass", dest="sudo_pass", metavar="SRC", default=None,
                   help=_t("help_sudo_pass"))
    g.add_argument("--batch", "--non-interactive", dest="batch",
                   action="store_true", help=_t("help_batch"))
    return conn_opt


def _extract_conn(argv):
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False,
                                  parents=[_make_conn_parent()])
    return pre.parse_known_args(argv)


_RAW = argparse.RawDescriptionHelpFormatter


def build_parser():
    p = argparse.ArgumentParser(
        prog="awgctl",
        formatter_class=_RAW,
        parents=[_make_conn_parent()],
        description=_t("description"),
        epilog=_t("epilog"))
    p.add_argument("config", help=_t("help_config"))

    restart_opt = argparse.ArgumentParser(add_help=False)
    restart_opt.add_argument(
        "-r", "--restart", action="store_true",
        help=_t("help_restart_flag"))

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    sp = sub.add_parser(
        "init", parents=[restart_opt], formatter_class=_RAW,
        help=_t("init_help"), description=_t("init_desc"),
        epilog=_t("init_epilog"))
    sp.add_argument("--host", default=None, help=_t("help_host"))
    sp.add_argument("-y", "--yes", action="store_true", help=_t("help_yes"))
    sp.add_argument("--rekey-imported", action="store_true",
                    help=_t("help_rekey_imported"))
    sp.add_argument("--fix-perms", dest="fix_perms", action="store_true",
                    help=_t("help_fix_perms"))
    sp.add_argument("--dry", "--dry-run", dest="dry_run", action="store_true",
                    help=_t("help_dry"))
    sp.add_argument("--json", action="store_true", help=_t("help_json"))

    sp = sub.add_parser(
        "list", formatter_class=_RAW, help=_t("list_help"),
        description=_t("list_desc"), epilog=_t("list_epilog"))
    sp.add_argument("--json", action="store_true", help=_t("help_json"))

    sp = sub.add_parser(
        "add", parents=[restart_opt], formatter_class=_RAW,
        help=_t("add_help"), description=_t("add_desc"),
        epilog=_t("add_epilog"))
    sp.add_argument("names", nargs="+", metavar="NAME", help=_t("help_name"))
    sp.add_argument("--client-allow", default=None, help=_t("help_client_allow"))
    sp.add_argument("--client-routes", default=None, help=_t("help_client_routes"))
    sp.add_argument("--keepalive", type=int, default=None, help=_t("help_keepalive"))
    sp.add_argument("--dns", default=None, help=_t("help_dns"))
    sp.add_argument("--endpoint", default=None, help=_t("help_endpoint"))
    sp.add_argument("--json", action="store_true", help=_t("help_json"))

    sp = sub.add_parser(
        "del", parents=[restart_opt], formatter_class=_RAW,
        help=_t("del_help"), description=_t("del_desc"),
        epilog=_t("del_epilog"))
    sp.add_argument("names", nargs="*", metavar="NAME", help=_t("help_names"))
    sp.add_argument("--all", dest="all_clients", action="store_true",
                    help=_t("help_all"))

    sp = sub.add_parser(
        "get", formatter_class=_RAW, help=_t("get_help"),
        description=_t("get_desc"), epilog=_t("get_epilog"))
    sp.add_argument("name", help=_t("help_name"))
    sp.add_argument("--json", action="store_true", help=_t("help_json"))

    sp = sub.add_parser(
        "rename", formatter_class=_RAW, help=_t("rename_help"),
        description=_t("rename_desc"), epilog=_t("rename_epilog"))
    sp.add_argument("name", metavar="OLD", help=_t("help_name"))
    sp.add_argument("new_name", metavar="NEW", help=_t("help_new_name"))

    sp = sub.add_parser(
        "rekey", parents=[restart_opt], formatter_class=_RAW,
        help=_t("rekey_help"), description=_t("rekey_desc"),
        epilog=_t("rekey_epilog"))
    sp.add_argument("names", nargs="*", metavar="NAME", help=_t("help_names"))
    sp.add_argument("--all", dest="all_clients", action="store_true",
                    help=_t("help_all"))

    sp = sub.add_parser(
        "set", parents=[restart_opt], formatter_class=_RAW,
        help=_t("set_help"), description=_t("set_desc"),
        epilog=_t("set_epilog"))
    sp.add_argument("names", nargs="*", metavar="NAME", help=_t("help_names"))
    sp.add_argument("--all", dest="all_clients", action="store_true",
                    help=_t("help_all"))
    sp.add_argument("--dns", default=None, help=_t("help_dns"))
    sp.add_argument("--routes", default=None, help=_t("help_client_routes"))
    sp.add_argument("--keepalive", default=None, help=_t("help_keepalive"))
    sp.add_argument("--host", default=None, help=_t("help_set_host"))
    sp.add_argument("--endpoint", default=None, help=_t("help_set_endpoint"))
    sp.add_argument("--allow", default=None, help=_t("help_set_allow"))
    sp.add_argument("--defaults", dest="set_defaults", action="store_true",
                    help=_t("help_set_defaults"))

    sp = sub.add_parser(
        "defaults", formatter_class=_RAW, help=_t("defaults_help"),
        description=_t("defaults_desc"), epilog=_t("defaults_epilog"))
    sp.add_argument("--host", default=None, help=_t("help_host"))
    sp.add_argument("--dns", default=None, help=_t("help_dns"))
    sp.add_argument("--routes", default=None, help=_t("help_client_routes"))
    sp.add_argument("--keepalive", default=None, help=_t("help_keepalive"))

    sp = sub.add_parser(
        "show", formatter_class=_RAW, help=_t("show_help"),
        description=_t("show_desc"), epilog=_t("show_epilog"))
    sp.add_argument("--json", action="store_true", help=_t("help_json"))

    sub.add_parser(
        "restart", formatter_class=_RAW, help=_t("restart_help"),
        description=_t("restart_desc"), epilog=_t("restart_epilog"))
    return p


def build_configs_parser():
    cp = argparse.ArgumentParser(
        prog="awgctl configs",
        formatter_class=_RAW,
        description=_t("configs_desc"),
        epilog=_t("configs_epilog"))
    cp.add_argument("dir", nargs="?", default=None, metavar="DIR",
                    help=_t("help_dir"))
    cp.add_argument("--json", action="store_true", help=_t("help_json"))
    return cp


def _run_configs(argv):
    rest, dropped = [], False
    for t in argv:
        if not dropped and not t.startswith("-"):
            dropped = True
            continue
        rest.append(t)
    args = build_configs_parser().parse_args(rest)
    cmd_configs(directory=args.dir, json_out=args.json)


def main():
    argv = sys.argv[1:]
    conn, argv = _extract_conn(argv)
    if conn.ssh_config and not conn.ssh:
        print(_t("err_ssh_config_without_ssh"), file=sys.stderr)
        sys.exit(2)
    set_batch(conn.batch)
    if conn.ssh:
        backend = SshBackend(conn.ssh, use_sudo=conn.sudo,
                             ask_pass=conn.ask_pass,
                             ssh_pass_src=conn.ssh_pass,
                             sudo_pass_src=conn.sudo_pass,
                             ssh_config=conn.ssh_config)
        BACKEND.__class__ = SshBackend
        BACKEND.__dict__.update(backend.__dict__)

    first = next((t for t in argv if not t.startswith("-")), None)
    if first is not None and len([g for g in GLOBAL_COMMANDS
                                  if g.startswith(first)]) == 1:
        return _run_configs(argv)

    argv = _inject_config_for_help(argv)
    expand_command(argv)
    p = build_parser()
    args = p.parse_args(argv)

    cfg = resolve_config(args.config)
    if cfg is None:
        print(_t("err_not_found", name=args.config, dir=STD_CONFIG_DIR),
              file=sys.stderr)
        sys.exit(1)
    args.config = cfg

    cmd = args.cmd
    if cmd is None:
        p.print_help()
        sys.exit(1)

    if cmd != "init" and not getattr(args, "json", False):
        warn_config_perms(args.config)

    if cmd == "init":
        cmd_init(args.config, host=args.host, assume_yes=args.yes,
                 rekey_imported=args.rekey_imported, dry_run=args.dry_run,
                 json_out=args.json, fix_perms=args.fix_perms)
    elif cmd == "list":
        cmd_list(args.config, json_out=args.json)
    elif cmd == "add":
        cmd_add(args.config, args.names, allow=args.client_allow,
                routes=args.client_routes, keepalive=args.keepalive,
                endpoint=args.endpoint, dns=args.dns, json_out=args.json)
    elif cmd == "del":
        if not args.names and not args.all_clients:
            print(_t("err_no_names"), file=sys.stderr)
            sys.exit(2)
        cmd_del(args.config, args.names, all_clients=args.all_clients)
    elif cmd == "get":
        cmd_get(args.config, args.name, json_out=args.json)
    elif cmd == "rename":
        cmd_rename(args.config, args.name, args.new_name)
    elif cmd == "rekey":
        if not args.names and not args.all_clients:
            print(_t("err_no_names"), file=sys.stderr)
            sys.exit(2)
        cmd_rekey(args.config, args.names, all_clients=args.all_clients)
    elif cmd == "set":
        changes = {k: getattr(args, k) for k in CLIENT_PARAMS
                   if getattr(args, k) is not None}
        if args.set_defaults:
            if args.names or args.all_clients:
                print(_t("err_defaults_conflict"), file=sys.stderr)
                sys.exit(2)
            bad = [k for k in ("endpoint", "allow") if k in changes]
            if bad:
                print(_t("err_bad_defaults", bad=", ".join(bad)), file=sys.stderr)
                sys.exit(2)
            cmd_defaults(args.config,
                         changes={k: v for k, v in changes.items()
                                  if k in DEFAULT_KEYS})
        else:
            cmd_set(args.config, args.names, all_clients=args.all_clients,
                    changes=changes)
    elif cmd == "defaults":
        changes = {k: getattr(args, k) for k in DEFAULT_KEYS
                   if getattr(args, k) is not None}
        cmd_defaults(args.config, changes=changes)
    elif cmd == "show":
        cmd_show(args.config, json_out=args.json)
    elif cmd == "restart":
        cmd_restart(args.config)

    if (cmd != "restart" and getattr(args, "restart", False)
            and not getattr(args, "dry_run", False)):
        cmd_restart(args.config)
