"""Black-box tests of both shipped languages using a fake wg executable.

Only key generation is simulated; parsing, CLI routing, files, locks, backups,
and command output use the real implementation. No network or root needed.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVER = """[Interface]
PrivateKey = server-private
Address = fd00::1/64, 10.20.0.1/29
ListenPort = 51820
Jc = 4
H1 = 12345
"""
PEERS = """
# BEGIN phone
[Peer]
#_PrivateKey = imported-private
PublicKey = imported-public
PresharedKey = imported-psk
AllowedIPs = 10.20.0.2/32
# END phone

[Peer]
#_Name = gateway
PublicKey = gateway-public
AllowedIPs = 192.168.0.0/16
Endpoint = gateway.example:5555
AdvancedSecurity = on

[Peer]
PublicKey = laptop-public
AllowedIPs = 10.20.0.3/32
"""
FAKE_WG = """#!/usr/bin/env python3
import base64, hashlib, os, sys
if sys.argv[1] in ('genkey', 'genpsk'):
    print(base64.b64encode(os.urandom(32)).decode())
elif sys.argv[1] == 'pubkey':
    print(base64.b64encode(hashlib.sha256(sys.stdin.read().strip().encode()).digest()).decode())
else:
    sys.exit(3)
"""


class CommandTests(unittest.TestCase):
    lang = "en"

    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.executable = Path(temp.name) / "awgctl"
        subprocess.run([sys.executable, "build.py", "--lang", cls.lang,
                        "--output", str(cls.executable)], cwd=ROOT,
                       check=True, capture_output=True)
        fake = Path(temp.name) / "awg"
        fake.write_text(FAKE_WG)
        fake.chmod(0o700)
        cls.env = dict(os.environ, PATH=temp.name + os.pathsep + os.environ["PATH"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.config = self.directory / "awg0.conf"
        self.config.write_text(SERVER)
        self.config.chmod(0o600)

    def cli(self, *args, ok=True, global_command=False):
        result = subprocess.run(
            [sys.executable, str(self.executable), "--batch",
             *([] if global_command else [str(self.config)]), *args],
            env=self.env, capture_output=True, text=True, timeout=10)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("Traceback", result.stderr)
        return result

    def init(self):
        self.cli("init", "--host", "vpn.example", "-y")

    def clients(self):
        return json.loads(self.cli("list", "--json").stdout)

    def test_init_preview_import_and_repeat(self):
        original = SERVER + PEERS
        self.config.write_text(original)
        report = json.loads(self.cli("init", "--dry", "--json").stdout)
        self.assertEqual(report["status"], "server")
        self.assertEqual([p["kind"] for p in report["peers"]], ["client", "s2s", "client"])
        self.assertNotIn("imported-private", json.dumps(report))
        self.assertNotIn("imported-psk", json.dumps(report))
        self.assertEqual(self.config.read_text(), original)
        self.assertFalse(Path(str(self.config) + ".lock").exists())
        self.init()
        imported = self.config.read_text()
        self.assertIn("Endpoint = gateway.example:5555", imported)
        self.assertIn("AdvancedSecurity = on", imported)
        self.assertNotIn("#_PrivateKey", imported)
        self.assertEqual([c["name"] for c in self.clients()], ["phone", "gateway", "peer-3"])
        self.assertTrue(self.clients()[0]["has_client_priv"])
        self.assertFalse(self.clients()[2]["has_client_priv"])
        self.cli("init", "-y")
        self.assertEqual(self.config.read_text(), imported)
        self.cli("init", "--host", "other.example", "-y")
        self.assertEqual(self.config.read_text(), imported.replace("vpn.example", "other.example"))

    def test_import_rekey_only_eligible_peers(self):
        self.config.write_text(SERVER + PEERS)
        self.cli("init", "-y", "--rekey-imported")
        entries = self.clients()
        self.assertEqual(entries[0]["client_pub"], "imported-public")
        self.assertEqual(entries[1]["client_pub"], "gateway-public")
        self.assertNotEqual(entries[2]["client_pub"], "laptop-public")
        self.assertTrue(entries[2]["has_client_priv"])

    def test_client_config_init_rejected(self):
        client = "[Interface]\nPrivateKey = private\n[Peer]\nPublicKey = public\n"
        self.config.write_text(client)
        self.cli("init", "-y", ok=False)
        self.assertEqual(self.config.read_text(), client)
        self.assertFalse(Path(str(self.config) + ".bak").exists())

    def test_add_get_defaults_and_secret_free_list(self):
        self.init()
        self.cli("defaults", "--dns", "9.9.9.9", "--routes", "10.0.0.0/8", "--keepalive", "0")
        self.assertIn("9.9.9.9", self.cli("defaults").stdout)
        added = json.loads(self.cli("add", "phone", "laptop", "--json").stdout)
        self.assertEqual([e["address"] for e in added], ["10.20.0.2/29", "10.20.0.3/29"])
        for e in added:
            config = self.cli("get", e["name"]).stdout
            self.assertEqual(config.strip(), e["config"].strip())
            for expected in ("Jc = 4", "H1 = 12345", "DNS = 9.9.9.9", "PersistentKeepalive = 0",
                             "Endpoint = vpn.example:51820", "AllowedIPs = 10.0.0.0/8"):
                self.assertIn(expected, config)
        listing = self.cli("list", "--json").stdout
        for e in added:
            self.assertNotIn(e["client_priv"], listing)
            self.assertNotIn(e["psk"], listing)
        self.assertEqual(len(json.loads(listing)), 2)
        self.assertIn("phone", self.cli("list").stdout)

    def test_set_parameters_bulk_preserves_keys_and_endpoint_priority(self):
        self.init()
        added = json.loads(self.cli("add", "phone", "laptop", "--json").stdout)
        self.cli("set", "--all", "--dns", "8.8.8.8", "--allow", "192.0.2.0/24",
                 "--routes", "192.0.2.0/24", "--host", "2001:db8::1")
        for original in added:
            current = json.loads(self.cli("get", original["name"], "--json").stdout)
            for key in ("client_priv", "client_pub", "psk"):
                self.assertEqual(current[key], original[key])
            self.assertEqual(current["endpoint"], "[2001:db8::1]:51820")
            self.assertEqual(current["dns"], "8.8.8.8")
        self.assertEqual(self.config.read_text().count("AllowedIPs = 192.0.2.0/24"), 2)
        self.cli("set", "phone", "--endpoint", "fixed.example:4444")
        self.cli("defaults", "--host", "new.example")
        current = json.loads(self.cli("get", "phone", "--json").stdout)
        self.assertEqual(current["endpoint"], "fixed.example:4444")
        self.cli("set", "--defaults", "--dns", "1.0.0.1")
        self.assertIn("1.0.0.1", self.cli("defaults").stdout)

    def test_rekey_and_delete_bulk(self):
        self.init()
        before = json.loads(self.cli("add", "phone", "laptop", "--json").stdout)
        self.cli("rekey", "--all")
        for original in before:
            after = json.loads(self.cli("get", original["name"], "--json").stdout)
            for key in ("client_priv", "client_pub", "psk"):
                self.assertNotEqual(after[key], original[key])
            self.assertEqual(after["address"], original["address"])
            self.assertIn("PublicKey = " + after["client_pub"], self.config.read_text())
        self.cli("del", "phone")
        self.assertEqual([e["name"] for e in self.clients()], ["laptop"])
        self.cli("del", "--all")
        self.assertEqual(self.clients(), [])
        self.assertNotIn("[Peer]", self.config.read_text())

    def test_mutation_errors_leave_config_unchanged(self):
        self.init()
        self.cli("add", "phone")
        for args in [("add", "new", "phone"), ("add", "same", "same"),
                     ("add", "bad name"), ("add", "new", "--client-allow", "garbage"),
                     ("set", "phone", "missing", "--dns", "9.9.9.9"),
                     ("set", "phone", "--routes", "garbage"),
                     ("set", "phone", "--keepalive", "nope"),
                     ("defaults", "--keepalive", "nope"),
                     ("set", "phone", "--defaults", "--dns", "9.9.9.9"),
                     ("set", "--defaults", "--allow", "0.0.0.0/0"),
                     ("rekey", "phone", "missing"), ("del", "phone", "missing"),
                     ("del",), ("get", "missing")]:
            with self.subTest(args=args):
                before = self.config.read_bytes()
                backup = Path(str(self.config) + ".bak").read_bytes()
                self.cli(*args, ok=False)
                self.assertEqual(self.config.read_bytes(), before)
                self.assertEqual(Path(str(self.config) + ".bak").read_bytes(), backup)

    def test_subnet_exhaustion_does_not_partially_add(self):
        self.config.write_text(SERVER.replace("10.20.0.1/29", "10.20.0.1/30"))
        self.init()
        before = self.config.read_bytes()
        self.cli("add", "one", "two", ok=False)
        self.assertEqual(self.config.read_bytes(), before)

    def test_configs_overview(self):
        self.init()
        (self.directory / "server.conf").write_text(SERVER + PEERS)
        (self.directory / "client.conf").write_text("[Interface]\nAddress = 10.0.0.2/24\n")
        (self.directory / "ignored.txt").write_text(SERVER)
        rows = json.loads(self.cli("configs", str(self.directory), "--json", global_command=True).stdout)
        self.assertEqual({r["name"]: (r["status"], r["count"]) for r in rows}, {
            "awg0.conf": ("managed", 0), "server.conf": ("unmanaged", 3),
            "client.conf": ("client", 0)})

    def test_help_prefixes_and_global_option_errors(self):
        for command in ("init", "add", "get", "list", "del", "rekey", "set", "defaults", "show", "restart", "configs"):
            with self.subTest(command=command):
                self.assertIn("usage:", self.cli(command, "-h", global_command=True).stdout)
        self.init()
        self.cli("a", "phone")
        self.assertEqual(len(json.loads(self.cli("l", "--json").stdout)), 1)
        self.cli("r", ok=False)
        self.cli("configs", "--ssh-config", "/missing", global_command=True, ok=False)


class RussianCommandTests(CommandTests):
    lang = "ru"


if __name__ == "__main__":
    unittest.main()
