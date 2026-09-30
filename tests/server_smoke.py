#!/usr/bin/env python3
"""Optional manual checks against a real SSH server; never restart a tunnel.

Not part of make test or unittest discovery. Run this script explicitly only
when a real-server check is wanted; it is not required for builds or commits.

Uses the built artifact and native SSH for inventory/dry-run/list/show.
No remote writes, locks or restarts. Only status and counts are printed.
"""

import argparse
import json
from pathlib import Path
import runpy
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--ssh-config", required=True)
    parser.add_argument("--sudo", action="store_true")
    parser.add_argument("--directory", default="/etc/amnezia/amneziawg")
    parser.add_argument("--binary", default=str(Path(__file__).resolve().parents[1] / "build/awgctl"))
    args = parser.parse_args()
    binary = str(Path(args.binary).resolve())
    # Load exactly the built backend for connectivity and read-only checks.
    built = runpy.run_path(binary)
    built["set_batch"](True)
    remote = built["SshBackend"](args.ssh, ssh_config=args.ssh_config, use_sudo=args.sudo)
    connection = ["--ssh", args.ssh, "--ssh-config", args.ssh_config, "--batch"]
    if args.sudo:
        connection.append("--sudo")

    def cli(*arguments):
        result = subprocess.run([sys.executable, binary, *connection, *arguments],
                                capture_output=True, text=True, timeout=60)
        # Do not emit stdout on failure: get/add/rekey output contains secrets.
        if result.returncode:
            raise RuntimeError(f"CLI command failed ({result.returncode}): {arguments[1:2] or arguments[:1]}")
        return result.stdout

    try:
        identity = remote.run(["id", "-un"]).stdout.strip()
        print(f"SSH connected as {identity}", flush=True)
        remote.run(["test", "-d", args.directory], sudo=args.sudo)
        inventory = json.loads(cli("configs", args.directory, "--json"))
        print(f"configs: {len(inventory)} found", flush=True)
        for row in inventory:
            require(row["status"] != "error", "Cannot read a server config")
            path = row["path"]
            before = remote.run(["sha256sum", "--", path], sudo=args.sudo).stdout
            report = json.loads(cli(path, "init", "--dry", "--json"))
            if row["status"] == "managed":
                clients = json.loads(cli(path, "list", "--json"))
                require(len(clients) == row["count"], "Client count mismatch")
            if row["status"] != "client":
                iface = Path(path).stem
                active = remote.run(["ip", "link", "show", iface], sudo=args.sudo, check=False)
                if active.returncode == 0:
                    status = json.loads(cli(path, "show", "--json"))
                    print(f"show: {iface}, {len(status['peers'])} peers", flush=True)
            after = remote.run(["sha256sum", "--", path], sudo=args.sudo).stdout
            require(after == before, "Config changed during read-only checks")
            print(f"read-only checks: {row['name']} ({report['status']}) OK", flush=True)

    finally:
        remote._cleanup()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        # CalledProcessError commands could contain encoded configs: do not print.
        if isinstance(error, OSError):
            print(f"Server check failed: {error.strerror} (errno={error.errno})", file=sys.stderr)
        elif isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print(f"Server check failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
