"""Exercise the shipped single-file CLI against disposable configs (no wg/root)."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = """[Interface]
PrivateKey = server-private
Address = 10.0.0.1/24
ListenPort = 51820

# === AWGCTL-CLIENTS-BEGIN ===
# AWGCTL-HOST = vpn.example.com

# AWGCTL |name=old|ip=10.0.0.2|client_priv=private|client_pub=public|server_pub=server-public|psk=secret|future=keep-me|
[Peer]
PublicKey = public
PresharedKey = secret
AllowedIPs = 10.0.0.2/32
AdvancedSecurity = on

# AWGCTL |name=taken|ip=10.0.0.3|client_pub=other-public|
[Peer]
PublicKey = other-public
AllowedIPs = 10.0.0.3/32

# === AWGCTL-CLIENTS-END ===
# unrelated trailing comment
"""


class RenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build_dir.cleanup)
        cls.executables = {}
        for lang in ("en", "ru"):
            path = Path(cls.build_dir.name) / lang
            subprocess.run(
                [sys.executable, "build.py", "--lang", lang, "--output", str(path)],
                cwd=ROOT, check=True, capture_output=True, text=True)
            cls.executables[lang] = path

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Path(temp.name) / "awg0.conf"
        self.config.write_text(CONFIG)
        self.config.chmod(0o600)

    def cli(self, *args, lang="en", with_config=True):
        return subprocess.run(
            [sys.executable, str(self.executables[lang]),
             *([str(self.config)] if with_config else []), *args],
            capture_output=True, text=True)

    def test_rename_preserves_connection_and_other_content(self):
        before = self.cli("get", "old", "--json")
        self.assertEqual(before.returncode, 0, before.stderr)
        result = self.cli("ren", "old", "phone")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), CONFIG.replace("name=old|", "name=phone|"))
        self.assertEqual(Path(str(self.config) + ".bak").read_text(), CONFIG)
        after = self.cli("get", "phone", "--json")
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(json.loads(before.stdout)["config"], json.loads(after.stdout)["config"])
        self.assertNotEqual(self.cli("get", "old").returncode, 0)
        clients = self.cli("list", "--json")
        self.assertEqual(clients.returncode, 0, clients.stderr)
        self.assertEqual([c["name"] for c in json.loads(clients.stdout)], ["phone", "taken"])

    def test_rejected_names_leave_config_and_backup_untouched(self):
        for old, new in [("missing", "new"), ("old", "taken"), ("old", ""),
                         ("old", "bad name"), ("old", "bad|name"),
                         ("old", "bad\n"), ("old", "bad/name")]:
            with self.subTest(old=old, new=new):
                result = self.cli("rename", old, new)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.config.read_text(), CONFIG)
                self.assertFalse(Path(str(self.config) + ".bak").exists())

    def test_same_name_does_not_write(self):
        before = self.config.stat().st_mtime_ns
        result = self.cli("rename", "old", "old")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.stat().st_mtime_ns, before)
        self.assertFalse(Path(str(self.config) + ".bak").exists())

    def test_missing_markup_does_not_write(self):
        content = "[Interface]\nListenPort = 51820\n"
        self.config.write_text(content)
        result = self.cli("rename", "old", "new")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), content)
        self.assertFalse(Path(str(self.config) + ".bak").exists())

    def test_localized_help_and_unicode_name(self):
        for lang, word in [("en", "rename"), ("ru", "переименовать")]:
            with self.subTest(lang=lang):
                result = self.cli("--help", lang=lang, with_config=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(word, result.stdout)
                help_result = self.cli("rename", "-h", lang=lang, with_config=False)
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                self.assertIn("OLD NEW", help_result.stdout)
        result = self.cli("rename", "old", "Телефон-1.test_2", lang="ru")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("переименован", result.stdout)
        self.assertIn("name=Телефон-1.test_2|", self.config.read_text())


if __name__ == "__main__":
    unittest.main()
