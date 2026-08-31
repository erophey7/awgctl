"""Backend abstraction: local or remote (SSH) access to config and commands."""

import atexit
import base64
import contextlib
import fcntl
import getpass
import os
import pty
import re
import shlex
import shutil
import subprocess
import sys
import time

from .i18n import _t


class LocalBackend:
    """Config and commands on the local machine (default behavior)."""

    def exists(self, path):
        return os.path.exists(path)

    def read_lines(self, path):
        with open(path) as f:
            return f.read().splitlines()

    def write_lines(self, path, lines):
        if os.path.exists(path):
            try:
                shutil.copy2(path, path + ".bak")
            except OSError as e:
                print(_t("info_backup_fail", e=e), file=sys.stderr)
        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    @contextlib.contextmanager
    def lock(self, path):
        lock_path = path + ".lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def run(self, argv, stdin=None, check=True, sudo=False):
        return subprocess.run(argv, input=stdin, check=check,
                              capture_output=True, text=True)

    def which_wg(self):
        for name in ("awg", "wg"):
            p = shutil.which(name)
            if p:
                return p
        return None

    def list_dir(self, path):
        try:
            return sorted(os.listdir(path))
        except OSError:
            return []

    def stat_perms(self, path):
        try:
            st = os.stat(path)
            return (st.st_mode & 0o777, st.st_uid, st.st_gid)
        except OSError:
            return None


def _pty_send_password(argv, password, prompt_re=rb"[Pp]assword:|passphrase"):
    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.execvp(argv[0], argv)
        finally:
            os._exit(127)
    sent = False
    buf = b""
    try:
        while True:
            try:
                data = os.read(fd, 1024)
            except OSError:
                break
            if not data:
                break
            buf += data
            if not sent and re.search(prompt_re, buf):
                os.write(fd, password.encode() + b"\n")
                sent = True
                buf = b""
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


class SshBackend:
    def __init__(self, target, use_sudo=False, ask_pass=False,
                 ssh_pass_src=None, sudo_pass_src=None):
        user, host = "root", target
        if "@" in target:
            user, host = target.split("@", 1)
        port = None
        if ":" in host and not host.startswith("["):
            host, p = host.rsplit(":", 1)
            if p.isdigit():
                port = p
        self.user, self.host, self.port = user, host, port
        self.use_sudo = use_sudo
        self.ask_pass = ask_pass
        self.ssh_pass_src = ssh_pass_src
        self.sudo_pass_src = sudo_pass_src
        self._connected = False
        self._master = None
        self._ssh_password = None
        self._sudo_password = None
        self._sudo_needs_pw = None
        self._tmpdir = None

    def _target(self):
        return f"{self.user}@{self.host}"

    def _ssh_invocation(self):
        return ["ssh", "-o", "ControlPath=" + self._master, self._target()]

    def _exec(self, remote, stdin=None, check=True):
        full = self._ssh_invocation() + [remote]
        return subprocess.run(full, input=stdin, capture_output=True,
                              text=True, check=check)

    def _connect(self):
        if self._connected:
            return
        self._tmpdir = os.path.join(
            os.environ.get("XDG_RUNTIME_DIR", "/tmp"), f"awgctl-{os.getpid()}")
        os.makedirs(self._tmpdir, mode=0o700, exist_ok=True)
        self._master = os.path.join(self._tmpdir, "cm.sock")
        common = (["-fN", "-M", "-S", self._master,
                   "-o", "ControlPersist=60", "-o", "ConnectTimeout=10",
                   "-o", "StrictHostKeyChecking=accept-new"]
                  + (["-p", self.port] if self.port else []))
        r = subprocess.run(
            ["ssh"] + common + ["-o", "BatchMode=yes", self._target()],
            capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(self._master):
            self._connected = True
            atexit.register(self._cleanup)
            return
        from .utils import noninteractive
        if self.ssh_pass_src:
            self._ssh_password = read_secret(self.ssh_pass_src)
        elif noninteractive():
            raise RuntimeError(
                _t("err_ssh_batch", target=self._target(), err=r.stderr.strip()))
        elif not (self.ask_pass or sys.stdin.isatty()):
            raise RuntimeError(
                _t("err_ssh_no_tty", target=self._target(), err=r.stderr.strip()))
        else:
            self._ssh_password = getpass.getpass(
                f"SSH password for {self._target()}: ")
        argv = (["ssh"] + common
                + ["-o", "NumberOfPasswordPrompts=1", self._target()])
        rc = _pty_send_password(argv, self._ssh_password)
        if rc != 0 or not os.path.exists(self._master):
            raise RuntimeError(_t("err_ssh_auth", target=self._target(), rc=rc))
        self._connected = True
        atexit.register(self._cleanup)

    def _cleanup(self):
        if self._master and os.path.exists(self._master):
            subprocess.run(["ssh", "-o", "ControlPath=" + self._master,
                            "-O", "exit", self._target()],
                           capture_output=True, text=True)
        if self._tmpdir and os.path.isdir(self._tmpdir):
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _sudo_needs_password(self):
        if self._sudo_needs_pw is None:
            r = self._exec("sudo -n true 2>/dev/null", check=False)
            self._sudo_needs_pw = (r.returncode != 0)
        return self._sudo_needs_pw

    def _get_sudo_password(self):
        if self._sudo_password is not None:
            return self._sudo_password
        if self.sudo_pass_src:
            self._sudo_password = read_secret(self.sudo_pass_src)
        elif self._ssh_password is not None:
            self._sudo_password = self._ssh_password
        else:
            from .utils import noninteractive
            if noninteractive():
                raise RuntimeError(
                    _t("err_sudo_batch", target=self._target()))
            elif not sys.stdin.isatty():
                raise RuntimeError(
                    _t("err_sudo_no_tty", target=self._target()))
            else:
                self._sudo_password = getpass.getpass(
                    f"sudo password for {self._target()}: ")
        return self._sudo_password

    def run(self, argv, stdin=None, check=True, sudo=False):
        self._connect()
        remote = " ".join(shlex.quote(a) for a in argv)
        if sudo and self.use_sudo:
            if self._sudo_needs_password():
                if stdin:
                    raise RuntimeError(_t("err_sudo_stdin"))
                stdin = self._get_sudo_password() + "\n"
                remote = "sudo -S -p '' -- " + remote
            else:
                remote = "sudo -n -- " + remote
        return self._exec(remote, stdin=stdin, check=check)

    def exists(self, path):
        r = self.run(["test", "-e", path], sudo=self.use_sudo, check=False)
        return r.returncode == 0

    def read_lines(self, path):
        return self.run(["cat", path], sudo=self.use_sudo).stdout.splitlines()

    def write_lines(self, path, lines):
        content = "\n".join(lines) + "\n"
        b64 = base64.b64encode(content.encode()).decode()
        tmp = path + ".tmp"
        script = ("set -e; umask 077; "
                  f"if [ -f {shlex.quote(path)} ]; then "
                  f"cp -f {shlex.quote(path)} {shlex.quote(path + '.bak')}; fi; "
                  f"printf %s {shlex.quote(b64)} | base64 -d > {shlex.quote(tmp)}; "
                  f"mv {shlex.quote(tmp)} {shlex.quote(path)}")
        r = self.run(["sh", "-c", script], sudo=self.use_sudo, check=False)
        if r.returncode != 0:
            raise RuntimeError(_t("err_remote_write", msg=r.stderr.strip()))

    @contextlib.contextmanager
    def lock(self, path):
        lockd = path + ".lockd"
        acquired = False
        for _ in range(120):
            r = self.run(["mkdir", lockd], sudo=self.use_sudo, check=False)
            if r.returncode == 0:
                acquired = True
                break
            time.sleep(0.5)
        if not acquired:
            raise RuntimeError(_t("err_lock_busy", lockd=lockd))
        try:
            yield
        finally:
            self.run(["rmdir", lockd], sudo=self.use_sudo, check=False)

    def which_wg(self):
        r = self.run(["sh", "-c", "command -v awg || command -v wg"],
                     check=False)
        out = r.stdout.strip()
        return out or None

    def list_dir(self, path):
        r = self.run(["sh", "-c", f"ls -1 {shlex.quote(path)} 2>/dev/null"],
                     sudo=self.use_sudo, check=False)
        return [x for x in r.stdout.splitlines() if x]

    def stat_perms(self, path):
        r = self.run(["stat", "-c", "%a %u %g", path],
                     sudo=self.use_sudo, check=False)
        parts = r.stdout.split()
        if r.returncode != 0 or len(parts) != 3:
            return None
        try:
            return (int(parts[0], 8), int(parts[1]), int(parts[2]))
        except ValueError:
            return None


BACKEND = LocalBackend()


def read_config(path):
    return BACKEND.read_lines(path)


def write_config(path, lines):
    BACKEND.write_lines(path, lines)


def config_lock(path):
    return BACKEND.lock(path)


def find_wg_bin():
    return BACKEND.which_wg()


def _wg_or_die():
    wg = find_wg_bin()
    if not wg:
        raise RuntimeError(_t("err_no_wg"))
    return wg


def read_secret(spec):
    if spec.startswith("env:"):
        var = spec[4:]
        if var not in os.environ:
            raise RuntimeError(_t("err_no_secret_src", var=var))
        val = os.environ[var]
    elif spec.startswith("fd:"):
        try:
            fd = int(spec[3:])
        except ValueError:
            raise RuntimeError(_t("err_bad_fd", spec=spec))
        try:
            chunks = []
            while True:
                b = os.read(fd, 4096)
                if not b:
                    break
                chunks.append(b)
        except OSError as e:
            raise RuntimeError(_t("err_read_fd", fd=fd, e=e))
        val = b"".join(chunks).decode()
    else:
        raise RuntimeError(_t("err_unknown_secret", spec=spec))
    if val.endswith("\n"):
        val = val[:-1]
    if val.endswith("\r"):
        val = val[:-1]
    return val
