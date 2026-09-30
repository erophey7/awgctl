"""Regression tests for parsing, address allocation, storage and live commands."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src import backend, commands, config, importer, utils
from src.constants import BEGIN, END, DEFAULT_PARAMS


class ParsingTests(unittest.TestCase):
    def test_metadata_roundtrip_and_defaults(self):
        record = {"name": "phone", "ip": "10.0.0.2", "client_priv": "abc==", "psk": "def="}
        restored = config.parse_meta(config.make_meta(record))
        for key, value in record.items():
            self.assertEqual(restored[key], value)
        self.assertIsNone(config.parse_meta("# AWGCTL-HOST = vpn"))
        lines = [BEGIN, "# AWGCTL-HOST = vpn", "# AWGCTL-DEFAULTS |dns=9.9.9.9|keepalive=0|", END]
        defaults = config.get_defaults(lines)
        self.assertEqual(defaults["host"], "vpn")
        self.assertEqual(defaults["dns"], "9.9.9.9")
        self.assertEqual(defaults["keepalive"], "0")
        self.assertEqual(defaults["routes"], DEFAULT_PARAMS["routes"])

    def test_normalize_blanks_preserves_outside_region(self):
        lines = ["", "", BEGIN, "", "", "# comment", "", "", END, "", ""]
        config.normalize_region_blanks(lines)
        self.assertEqual(lines, ["", "", BEGIN, "", "# comment", "", END, "", ""])

    def test_role_uses_interface_listen_port(self):
        self.assertEqual(importer.detect_role(["[Interface]", "ListenPort = 1234"]), "server")
        self.assertEqual(importer.detect_role(["[Interface]", "[Peer]", "ListenPort = 1234"]), "client")

    def test_peer_names_types_and_collision_handling(self):
        peers = importer.parse_peers([
            "# BEGIN My Phone", "[Peer]", "#_PrivateKey = private==", "PublicKey = public==",
            "AllowedIPs = 10.0.0.2/32", "# END My Phone",
            "[Peer]", "#_Name = gateway", "PublicKey = other", "AllowedIPs = 192.168.0.0/16"])
        self.assertEqual(peers[0]["priv"], "private==")
        self.assertNotIn("#_PrivateKey", "\n".join(peers[0]["clean"]))
        self.assertEqual(importer.classify_peer(peers[0]), "client")
        self.assertEqual(importer.classify_peer(peers[1]), "gateway")
        self.assertEqual(importer.classify_peer({"endpoint": "vpn:22"}), "s2s")
        self.assertEqual(importer.classify_peer({}), "no-allowed")
        self.assertEqual(importer.peer_host_ip(peers[0]), "10.0.0.2")
        self.assertEqual(importer.peer_host_ip(peers[1]), "")
        self.assertEqual(importer.suggest_name(peers[0], {"My-Phone"}), "My-Phone2")

    def test_ip_allocation_skips_used_server_and_broadcast(self):
        self.assertEqual(utils.next_free_ip("10.0.0.0/29", "10.0.0.1/29", {"10.0.0.2"}), "10.0.0.3")
        self.assertIsNone(utils.next_free_ip("10.0.0.0/30", "10.0.0.1/30", {"10.0.0.2"}))
        with patch("src.utils.MAX_IP_SCAN", 2):
            self.assertIsNone(utils.next_free_ip("fd00::/64", "fd00::1/64", {"fd00::2"}))

    def test_render_endpoint_precedence_ipv6_and_masking(self):
        entry = {"ip": "10.0.0.2", "client_priv": "private", "server_pub": "public", "host": "2001:db8::1"}
        rendered = commands.render_client_config(entry, host="default", port=51820, prefix=29,
                                                  masking=["Jc = 4"])
        self.assertIn("Endpoint = [2001:db8::1]:51820", rendered)
        self.assertIn("Address = 10.0.0.2/29", rendered)
        self.assertIn("Jc = 4", rendered)
        entry["endpoint"] = "fixed:2222"
        self.assertIn("Endpoint = fixed:2222", commands.render_client_config(entry, host="default", port=51820))


class StorageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "server.conf")
        self.local = backend.LocalBackend()

    def test_atomic_write_backup_permissions_and_lock_release(self):
        self.local.write_lines(self.path, ["original"])
        with self.local.lock(self.path):
            self.local.write_lines(self.path, ["replacement"])
        self.assertEqual(self.local.read_lines(self.path), ["replacement"])
        self.assertEqual(Path(self.path + ".bak").read_text(), "original\n")
        self.assertEqual(Path(self.path).stat().st_mode & 0o777, 0o600)
        self.assertFalse(Path(self.path + ".tmp").exists())
        with self.assertRaises(RuntimeError):
            with self.local.lock(self.path):
                raise RuntimeError("failure")
        # LOCK_NB detects a leaked lock without hanging the test process.
        import fcntl
        with open(self.path + ".lock") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_failed_replace_preserves_original(self):
        self.local.write_lines(self.path, ["original"])
        with patch("src.backend.os.replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                self.local.write_lines(self.path, ["replacement"])
        self.assertEqual(self.local.read_lines(self.path), ["original"])
        self.assertEqual(Path(self.path + ".bak").read_text(), "original\n")

    def test_address_and_masking_selection(self):
        self.local.write_lines(self.path, ["[Interface]", "Address = fd00::1/64, 10.0.0.1/28",
                                          "ListenPort = 4444", "Jc = 4", "[Peer]", "H1 = 123"])
        self.assertEqual(utils.get_server_address(self.path), ("10.0.0.1/28", "10.0.0.0/28", 4444))
        self.assertEqual(utils.client_prefix(self.path), 28)
        self.assertEqual(utils.get_server_maskings(self.path), ["Jc = 4"])

    def test_permission_checks(self):
        for perms, issues in [((0o600, 0, 0), 0), ((0o644, 1000, 1000), 3), (None, 0)]:
            with self.subTest(perms=perms), patch.object(utils.BACKEND, "stat_perms", return_value=perms):
                self.assertEqual(len(utils.config_perm_issues(self.path)), issues)


class SecretTests(unittest.TestCase):
    def test_environment_and_fd_sources_strip_one_newline(self):
        with patch.dict(os.environ, {"AWGCTL_TEST_SECRET": "secret\r\n"}):
            self.assertEqual(backend.read_secret("env:AWGCTL_TEST_SECRET"), "secret")
        with tempfile.TemporaryFile() as secret:
            secret.write(b"secret\n")
            secret.seek(0)
            self.assertEqual(backend.read_secret(f"fd:{secret.fileno()}"), "secret")

    def test_invalid_secret_sources(self):
        with patch.dict(os.environ, {}, clear=True):
            for source in ("env:AWGCTL_MISSING", "fd:bad", "fd:-1", "literal-secret"):
                with self.subTest(source=source), self.assertRaises(RuntimeError):
                    backend.read_secret(source)


class LiveCommandTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.run = stack.enter_context(patch.object(commands.BACKEND, "run"))
        stack.enter_context(patch("src.commands.find_wg_bin", return_value="awg"))
        stack.enter_context(patch("src.commands._wg_or_die", return_value="awg"))

    def test_show_maps_peers_and_never_prints_dump_secrets(self):
        self.run.return_value = subprocess.CompletedProcess([], 0,
            "server-private\tserver-public\t51820\t0\n"
            "known\tpeer-psk\t1.2.3.4:5555\t10.0.0.2/32\t100\t1024\t2048\t25\n"
            "unknown\tother-psk\t(none)\t10.0.0.3/32\t0\t0\t0\toff\n", "")
        with patch("src.commands.read_config", return_value=[BEGIN, "# AWGCTL |name=phone|client_pub=known|", END]):
            commands.cmd_show("/tmp/awg0.conf", json_out=True)
        report = json.loads(self.stdout.getvalue())
        self.assertEqual(report["interface"], "awg0")
        self.assertEqual(report["peers"][0]["name"], "phone")
        self.assertEqual(report["peers"][0]["transfer_rx"], 1024)
        self.assertEqual(report["peers"][1]["name"], "")
        self.assertEqual(report["peers"][1]["endpoint"], "")
        self.assertNotIn("server-private", self.stdout.getvalue())
        self.assertNotIn("peer-psk", self.stdout.getvalue())

    def test_show_failure_returns_error(self):
        self.run.return_value = subprocess.CompletedProcess([], 1, "", "not running")
        with self.assertRaises(SystemExit) as caught:
            commands.cmd_show("/tmp/awg0.conf")
        self.assertEqual(caught.exception.code, 1)

    def test_restart_inactive_does_not_change_interface(self):
        self.run.return_value.returncode = 1
        commands.cmd_restart("/tmp/awg0.conf")
        self.run.assert_called_once_with(["ip", "link", "show", "awg0"], sudo=True, check=False)

    def test_restart_active_orders_down_before_up(self):
        self.run.return_value.returncode = 0
        commands.cmd_restart("/tmp/awg0.conf")
        self.assertEqual([c.args[0] for c in self.run.call_args_list], [
            ["ip", "link", "show", "awg0"], ["awg-quick", "down", "awg0"], ["awg-quick", "up", "awg0"]])

    def test_restart_down_failure_does_not_continue(self):
        self.run.side_effect = [subprocess.CompletedProcess([], 0), subprocess.CalledProcessError(1, "awg-quick")]
        with self.assertRaises(subprocess.CalledProcessError):
            commands.cmd_restart("/tmp/awg0.conf")
        self.assertEqual(self.run.call_count, 2)


class RemoteBackendTests(unittest.TestCase):
    def setUp(self):
        self.remote = backend.SshBackend("admin@test", use_sudo=True)
        self.remote._connected = True

    def test_sudo_quoting_and_cached_passwordless_probe(self):
        with patch.object(self.remote, "_exec", return_value=subprocess.CompletedProcess([], 0)) as execute:
            self.remote.run(["cat", "/tmp/a b;$(touch bad)"], sudo=True)
            self.remote.run(["true"], sudo=True)
        self.assertEqual(execute.call_args_list[1].args[0], "sudo -n -- cat '/tmp/a b;$(touch bad)'")
        self.assertEqual(execute.call_count, 3)

    def test_sudo_password_uses_stdin_not_command(self):
        self.remote._sudo_needs_pw = True
        self.remote._sudo_password = "test-secret"
        with patch.object(self.remote, "_exec") as execute:
            self.remote.run(["true"], sudo=True)
        self.assertNotIn("test-secret", execute.call_args.args[0])
        self.assertEqual(execute.call_args.kwargs["stdin"], "test-secret\n")
        with self.assertRaises(RuntimeError):
            self.remote.run(["cat"], stdin="payload", sudo=True)

    def test_batch_sudo_without_secret_fails_without_prompt(self):
        with patch("src.utils.noninteractive", return_value=True), patch("src.backend.getpass.getpass") as prompt:
            with self.assertRaises(RuntimeError):
                self.remote._get_sudo_password()
            prompt.assert_not_called()

    def test_remote_lock_release_on_error(self):
        with patch.object(self.remote, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            with self.assertRaises(ValueError):
                with self.remote.lock("/tmp/test.conf"):
                    raise ValueError("test")
        self.assertEqual([c.args[0] for c in run.call_args_list], [
            ["mkdir", "/tmp/test.conf.lockd"], ["rmdir", "/tmp/test.conf.lockd"]])

    def test_remote_write_roundtrip_using_local_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "a b';x.conf")
            Path(path).write_text("original\n")
            def local_run(argv, **kwargs):
                return subprocess.run(argv, capture_output=True, text=True)
            with patch.object(self.remote, "run", side_effect=local_run):
                self.remote.write_lines(path, ["private=='$()", "second"])
            self.assertEqual(Path(path).read_text(), "private=='$()\nsecond\n")
            self.assertEqual(Path(path + ".bak").read_text(), "original\n")
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
