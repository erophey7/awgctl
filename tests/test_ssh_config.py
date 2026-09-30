"""SSH configuration resolution without connecting to a server."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.backend import SshBackend
from src.cli import _extract_conn


class SshConfigTests(unittest.TestCase):
    def test_target_parsing(self):
        for target, expected, port in [
            ("vpn", "vpn", None), ("admin@vpn:2222", "admin@vpn", "2222"),
            ("2001:db8::1", "2001:db8::1", None),
            ("[2001:db8::1]:2222", "2001:db8::1", "2222"),
            ("admin@[2001:db8::1]", "admin@2001:db8::1", None),
        ]:
            with self.subTest(target=target):
                backend = SshBackend(target)
                with patch.object(backend, "_has_ssh_profile", return_value=True):
                    self.assertEqual(backend._target(), expected)
                self.assertEqual(backend.port, port)

    def test_global_options_anywhere(self):
        for argv in [
            ["--ssh-config", "custom config", "--ssh", "vpn", "configs"],
            ["awg0", "list", "--ssh", "vpn", "--ssh-config", "custom config"],
        ]:
            conn, rest = _extract_conn(argv)
            self.assertEqual(conn.ssh_config, "custom config")
            self.assertEqual(conn.ssh, "vpn")
            self.assertNotIn("custom config", rest)

    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH is unavailable")
    def test_openssh_resolves_include_alias_and_explicit_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "ssh config"
            included = Path(temp) / "hosts"
            included.write_text(
                "Host vpn\n  HostName 192.0.2.10\n  User vpnadmin\n"
                "  Port 2222\n  IdentityFile /tmp/awgctl-test-key\n"
                "  ProxyJump bastion\n")
            config.write_text(f'Include "{included}"\n')
            for target, user, port in [("vpn", "vpnadmin", "2222"),
                                       ("root@vpn:2200", "root", "2200")]:
                backend = SshBackend(target, ssh_config=str(config))
                backend._master = str(Path(temp) / "cm.sock")
                invocation = backend._ssh_invocation()
                result = subprocess.run(
                    [invocation[0], "-G", *invocation[1:]],
                    capture_output=True, text=True, check=True)
                resolved = dict(line.split(" ", 1) for line in result.stdout.splitlines())
                self.assertEqual(resolved["hostname"], "192.0.2.10")
                self.assertEqual(resolved["user"], user)
                self.assertEqual(resolved["port"], port)
                self.assertEqual(resolved["identityfile"], "/tmp/awgctl-test-key")
                self.assertEqual(resolved["proxyjump"], "bastion")

    def test_default_uses_normal_ssh_config(self):
        backend = SshBackend("vpn")
        backend._master = "/tmp/test.sock"
        with patch.object(backend, "_has_ssh_profile", return_value=True):
            invocation = backend._ssh_invocation()
        self.assertNotIn("-F", invocation)
        self.assertEqual(invocation[-1], "vpn")

    def test_config_and_port_used_throughout_connection(self):
        backend = SshBackend("vpn:2222", ssh_config="/tmp/custom config")
        with patch("src.backend.subprocess.run") as run, \
                patch.object(backend, "_has_ssh_profile", return_value=True), \
                patch("src.backend.os.makedirs"), \
                patch("src.backend.os.path.exists", return_value=True), \
                patch("src.backend.os.path.isdir", return_value=False), \
                patch("src.backend.atexit.register"), \
                patch("src.backend.read_secret", return_value="password"), \
                patch("src.backend._pty_send_password", return_value=0) as password:
            # Force password fallback to exercise both master invocations.
            run.return_value.returncode = 1
            backend.ssh_pass_src = "env:TEST_PASSWORD"
            backend._connect()
            backend._exec("true")
            backend._cleanup()
            invocations = [call.args[0] for call in run.call_args_list]
            invocations.append(password.call_args.args[0])
            self.assertEqual(len(invocations), 4)
            for invocation in invocations:
                self.assertEqual(invocation[invocation.index("-F") + 1], "/tmp/custom config")
                self.assertEqual(invocation[invocation.index("-p") + 1], "2222")
                self.assertIn("vpn", invocation)

    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH is unavailable")
    def test_profile_or_root_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"
            config.write_text(
                "Host vpn\n  HostName 192.0.2.10\n"
                "Host prod-* !prod-excluded\n  User deploy\n"
                "Host *\n  ServerAliveInterval 30\n")
            for host, expected in [("vpn", "vpn"), ("unknown", "root@unknown"),
                                   ("prod-app", "prod-app"),
                                   ("prod-excluded", "root@prod-excluded"),
                                   ("admin@unknown", "admin@unknown")]:
                with self.subTest(host=host):
                    backend = SshBackend(host, ssh_config=str(config))
                    self.assertEqual(backend._target(), expected)

    def test_resolution_is_cached_and_explicit_user_skips_probe(self):
        backend = SshBackend("unknown")
        with patch.object(backend, "_has_ssh_profile", return_value=False) as probe:
            self.assertEqual(backend._target(), "root@unknown")
            self.assertEqual(backend._target(), "root@unknown")
            probe.assert_called_once()
        backend = SshBackend("admin@unknown")
        with patch.object(backend, "_has_ssh_profile") as probe:
            self.assertEqual(backend._target(), "admin@unknown")
            probe.assert_not_called()

    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH is unavailable")
    def test_config_errors_do_not_silently_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            backend = SshBackend("vpn", ssh_config=str(Path(temp) / "missing"))
            with self.assertRaises(RuntimeError):
                backend._target()


if __name__ == "__main__":
    unittest.main()
