# awgctl

AmneziaWG client management utility. Developed as modules (`src/`) with localization (`lang/`), but shipped as a **single self-contained file** (stdlib only), built from sources.

## Build and Installation

Build requirements: `python3` and `make`. No external dependencies.

```bash
make                     # build build/awgctl (default language — en)
make AWGCTL_LANG=ru      # build Russian version
```

The variable is named **`AWGCTL_LANG`**, not `LANG`, so it doesn't override the standard shell `LANG` environment variable.

The result is an executable `build/awgctl`. Run:

```bash
python3 build/awgctl awg0 list      # or ./build/awgctl awg0 list
```

System installation (`PREFIX` defaults to `/usr/local`):

```bash
sudo make install                       # -> /usr/local/bin/awgctl
sudo make install PREFIX=/usr           # -> /usr/bin/awgctl
sudo make uninstall
make clean                              # remove build/
```

The target machine only needs `python3` (standard library is sufficient) and `amneziawg-tools` (`awg`/`wg`) — for key generation and `show`.

### Build Structure

- `src/*.py` — modules (`constants`, `i18n`, `backend`, `utils`, `config`, `importer`, `commands`, `cli`); the concatenation order is defined in `build.py` (`SRC_ORDER`).
- `lang/<code>.py` — message dictionary `MESSAGES`; the selected language is embedded into the built file at build time.
- `build.py` strips internal (relative) imports and concatenates modules into a single namespace, adding shebang, stdlib imports, and entry point.

To add a language: copy `lang/en.py` to `lang/<code>.py`, translate the values, and build with `make AWGCTL_LANG=<code>`.

## Usage

```
awgctl <config> <command> [arguments] [options]
```

`<config>` — path to the config **or** short name: `awg0` expands to `/etc/amnezia/amneziawg/awg0.conf` (the `.conf` extension is added automatically). For example: `awgctl.py awg0 list`, `awgctl.py awg0 add ivan`.

Commands follow the `ip` style — abbreviated to any unambiguous prefix (`a`=add, `g`=get, `l`=list, `i`=init; for `d`-/`r`-/`s`-commands a distinguishing prefix is needed: `del`/`def`=defaults, `res`=restart, `rek`=rekey, `ren`=rename, `se`=set, `sh`=show):

Detailed help per command — `awgctl.py <command> -h` (config can be omitted, e.g. `awgctl.py add -h`).

- `init [--host=<host>] [-y] [--rekey-imported]` — initialize the server config **and import existing `[Peer]`s** under management.
  - Role is determined by `ListenPort` in `[Interface]` (server even without clients); client config (without `ListenPort`) is rejected.
  - Names are taken from `# BEGIN <name>` / `#_Name = <name>` or auto-generated from IP; interactively confirmed/changed (`-y`/`--yes` — accept auto-names without questions).
  - Degenerate peers (gateway `/16`, site-to-site with `Endpoint`, without `AllowedIPs`) are adopted **as-is** with a warning; original functional fields (`AdvancedSecurity`, `Endpoint`, `PresharedKey`) are preserved, service `#_`-comments are cleaned up.
  - `#_PrivateKey` (Amnezia desktop format) is taken → client is immediately fully manageable. Others without a private key are offered `rekey` (`--rekey-imported` — immediately, without asking).
  - Repeated `init` on an already initialized config only updates the host via `--host`, clients are not touched.
  - `--dry` (`--dry-run`) — **preview**: shows config role, initialization state, and for each `[Peer]` — proposed name (from config or auto-gen), type, parsed fields (`PublicKey`/`AllowedIPs`/`Endpoint`/`PSK`/`PrivateKey`) and remarks (no `PublicKey`, degenerate type, no `client_priv`). Does not write anything or take a lock.
- `list [--json]` — list of clients. `--json` outputs machine-readable array (fields `name/ip/allow/routes/endpoint/keepalive/client_pub` + booleans `has_client_priv`/`has_psk`); secrets (private keys, PSK) are not output.
- `add <name...>` — add one or more clients (for multiple names configs are separated by `# ==== <name> ====`, `--json` outputs an array): generates keys, computes server public key from its PrivateKey, assigns next free IP, outputs client config to stdout and writes `[Peer]`+metadata to config.
  - `--client-allow=<cidr>` — AllowedIPs in SERVER `[Peer]` (networks behind client — for VPN-gateway), default is `Client IP/32`.
  - `--client-routes=<cidr>` — AllowedIPs in CLIENT config (what client routes through VPN), default — from config defaults (`defaults`).
  - `--keepalive=<n>` — PersistentKeepalive (in client config), default — from config defaults.
  - `--dns=<list>` — client DNS, default — from config defaults.
  - `--endpoint=<host:port>` — custom client endpoint (full host:port, fixed for the client). If not specified — endpoint is **dynamic**: built from default host in section + actual server `ListenPort` on each issuance.
  - `--ssh=<host>` — operate on the remote server, including key generation.
- `del <name...> | --all` — delete one or more clients (and their `[Peer]`) or all at once via `--all`.
- `get <name>` — output saved client config to stdout. If `client_priv` is missing (import without private key), warns and outputs incomplete config — `rekey` needed.
- `rename <old-name> <new-name>` — rename a client, e.g. `awgctl awg0 rename client-10-0-0-2 phone` (short form: `ren`). Preserves keys, IP and settings; no restart or new client config is needed. New names may contain letters, digits, `_`, `.` and `-`; existing names are rejected. Renaming to the same name succeeds without writing. Supports `--ssh` and `--sudo`.
- `rekey <name...> | --all` — rotate keys for one or more clients (new pair + PSK, update `[Peer]` and meta) or all via `--all`. Changes keys — clients need new configs distributed. Makes imported client without a key fully manageable.
- `set <name...> | --all [options]` — change parameters of existing clients **without key rotation**, with **bulk** support (multiple names or `--all`):
  - `--dns=<list>`, `--routes=<cidr>`, `--keepalive=<n>`, `--host=<host>`, `--endpoint=<host:port>` — affect only the issued client config (`get`);
  - `--allow=<cidr>` — changes **server** `AllowedIPs` in `[Peer]` (and meta).
  - Endpoint priority for client: `--endpoint` (full `host:port`) > per-client `--host` (host:ListenPort) > default config `host`.
  - After changing, distribute new configs to affected clients (`get <name>`).
  - `set --defaults [--host= --dns= --routes= --keepalive=]` — change not clients, but **config defaults** (equivalent to `defaults` command; names/`--all`/`--endpoint`/`--allow` are not allowed here).
- `defaults [--host= --dns= --routes= --keepalive=]` — show (without flags) or change default client parameters. `host` is stored as `# AWGCTL-HOST` string (same as `init --host`), `dns/routes/keepalive` — as `# AWGCTL-DEFAULTS` string; substituted in `add` when corresponding flag is not set. Defaults only fill **empty** client fields (for imported ones `keepalive`/`routes` are already set — for bulk change use `set --all`).
- `show [--json]` — **live tunnel status** from `awg show <iface> dump`: for each client name (matched by public key from AWGCTL zone), last handshake time, received/transmitted, endpoint. Requires running interface and root (locally) or `--ssh --sudo`.
- `restart` — restart tunnel locally via `awg-quick` (if interface is running).

`--json` is also available for `add`, `get`, and `init --dry` — machine output (`add`/`get` object contains client fields and ready `config` string; `init --dry --json` — structured parsing).

Flag `-r | --restart` for `init`/`add`/`del`/`rekey` restarts tunnel immediately after operation (e.g. `awgctl.py awg0.conf add ivan -r`).

### Config Overview (`configs`)

Global command — **not bound to a single config** (no config slot needed), written as first argument:

```
awgctl.py configs [DIRECTORY] [--json] [--ssh ... --sudo]
```

Shows all `*.conf` in directory (default `/etc/amnezia/amneziawg`, or specified `DIRECTORY`) with classification of each:

- **client** — client config (no `ListenPort`);
- **unmanaged** — server config without AWGCTL markup;
- **managed** — server config under `awgctl` management.

For servers shows number of clients (for managed — from AWGCTL zone) or `[Peer]` (for unmanaged). `--json` — machine output. Works via `--ssh` too (scans directory on remote server). Command can be abbreviated by prefix (`c`, `conf`, ...); therefore short config name that is itself a prefix of `configs` (e.g. `con`) must be specified with full path or `.conf`.

### Remote Mode (SSH)

Any command can work with config **on a remote server** — the entire cycle (read, edit, `restart`, key generation) runs there. Connection options are **global**: they can be placed anywhere in command line (before or after command) and with any command, including global `configs` (`awgctl.py --ssh admin@vpn --sudo configs`):

- `--ssh [USER@]HOST[:PORT]` — server or alias from `~/.ssh/config`. OpenSSH resolves the user and port; explicit `USER` and `PORT` override config values. A matching `Host` profile uses OpenSSH settings (including the local username if the profile omits `User`); without a matching profile, the utility uses `root@HOST`. Key authentication works natively; if key fails, `--ask-pass` asks for SSH password (self-contained via `pty`, without `sshpass`/`paramiko`). One connection per process via `ControlMaster`.
- `--ssh-config PATH` — use a local OpenSSH config file (`ssh -F PATH`); requires `--ssh`. Otherwise OpenSSH reads its normal user and system configuration.
- `--sudo` — privileged commands on server via `sudo` (passwordless `-n` or `-S` with password; password is reused from SSH password or requested separately). Passwords are not written to disk.
- `--ask-pass` — ask for SSH password if key didn't work.

Examples:

```
awgctl.py /etc/amnezia/amneziawg/awg0.conf list --ssh admin@vpn.example.com --sudo
awgctl.py awg0.conf init --host vpn.example.com --ssh admin@vpn:22 --sudo -r
```

Remote write is atomic (`base64 | tee` + `mv`), with `.bak` backup; locking on server — via `mkdir <config>.lockd` (survives individual ssh calls).

Example `~/.ssh/config`:

```sshconfig
Host vpn
    HostName vpn.example.com
    User admin
    Port 2222
    IdentityFile ~/.ssh/vpn_ed25519
    # ProxyJump bastion
```

```bash
awgctl awg0 list --ssh vpn --sudo
awgctl awg0 list --ssh vpn --ssh-config ./ssh.conf --sudo
awgctl awg0 list --ssh root@vpn:2200
```

OpenSSH handles `Host`, `Include`, `IdentityFile`, `ProxyJump` and other connection settings. The `--ssh-config` file is local.
Profile detection uses `ssh -G -v` without connecting and respects `Include`, `Host` patterns and exclusions. A generic `Host *` block is defaults, not a separate profile: unknown hosts still use root. An explicit user (`--ssh admin@vpn`) always wins. Configuration errors stop the operation rather than silently falling back to root.

### Non-Interactive Mode (`--batch`) — for software integration

The entire cycle (`init`/`add`/`del`/`rekey`/`set`/`restart` via SSH+sudo) can run **without any interactive input**. Global flags:

- `--batch` (`--non-interactive`) — no prompts at all. Any moment where input would be required (SSH/sudo password, question) without given source/flag → **clear error immediately**, not a hang. Does not depend on TTY presence (safe even under pty).
- `--ssh-pass=<source>` — SSH password source (if key didn't work).
- `--sudo-pass=<source>` — sudo password source.

Secret source: **`fd:N`** (read from file descriptor — not visible in `ps`/`env`/fs; primary method) or **`env:VAR`** (environment variable — simpler, but visible in `/proc/<pid>/environ`). Secret is read without trailing newline and does not end up on disk/in argv.

Privileged/destructive actions in `--batch` are performed **only by explicit flags** (otherwise — skip with warning):

- `init --fix-perms` — fix config permissions (`chmod 600` + `chown root:root`); without flag in batch permissions are only checked with warning.
- `init --rekey-imported` — rotate keys for imported clients without private key.

Client names on import in `--batch`/`-y` are taken automatically (from `# BEGIN`/`#_Name`/from IP).

Examples:

```
# init remote server fully automatically (SSH password from fd 3,
# sudo with same password; fix permissions; rotate imported keys)
awgctl.py awg0 init --batch --host vpn.example.com --fix-perms \
  --rekey-imported --ssh admin@vpn --sudo --ssh-pass=fd:3 3<pw.txt

# add via environment (sudo password separate), machine JSON output
AWG_SSH=... AWG_SUDO=... awgctl.py awg0 add phone --json --batch \
  --ssh admin@vpn --sudo --ssh-pass=env:AWG_SSH --sudo-pass=env:AWG_SUDO
```

Client IP mask in client config is taken from server `Address`. Each record markup is stored in `# AWGCTL |...|` comment, client configs are NOT saved to files — only stdout. Mutating commands take lock `<config>.lock`, write atomically, and leave backup `<config>.bak`.

### Server Config Permissions and Root

The server config contains **private keys** (server and clients), and the interface is brought up via `awg-quick` only with root privileges (netlink, routes). Therefore the target model is **`root:root`, mode `0600`** (as `wg-quick` does via `umask 077`). A separate unprivileged "awg-user" makes no sense: they can't manage the interface, and access to config = access to all keys.

- All mutations write file immediately with `0600` (atomic replace doesn't "expose" permissions).
- On any interaction, if permissions are insecure (group/other access or owner not root), a warning is printed (suppressed in `--json` modes to not break the stream).
- `init` with insecure permissions **offers to fix** (`chmod 600` + `chown root:root`; `-y` — immediately). For chown root/`--sudo` is needed.

### IPv6 Address Space Protection

Client IPs are allocated from the **IPv4** subnet of the server: if `Address` has both IPv4 and IPv6, IPv4 is chosen for allocation (iterating hosts in IPv6 `/64` = 2^64 is meaningless). Address iteration is limited from above (`MAX_IP_SCAN`) to avoid hanging on giant spaces.

## Tests

```bash
make test
```

Tests use stdlib, temporary files and a fake key generator; no root, network
or installed `awg` is required. They cover both builds (en/ru), client lifecycle,
imports, failure atomicity, JSON, SSH configuration, sudo, locks and backups.
`show` and `restart` use mocked system calls; no real tunnel is restarted.
OpenSSH `ssh -G` checks are skipped if SSH is unavailable.

### Optional smoke test (manual only)

`tests/server_smoke.py` is an **optional** real-server check. It is excluded
from `make test` and automatic `unittest` discovery, never runs during builds,
and is not required before a commit. Run it only with the explicit command
below. For normal development, `make test` is sufficient.

Real-server checks are explicitly **read-only**: `configs`, `init --dry --json`,
`list` for managed configs and `show` for active interfaces. Config checksums
are compared before and after each check.

```bash
make
python3 tests/server_smoke.py --ssh awg-test --ssh-config /tmp/ssh_config
```

Use `--directory /path/to/configs` if needed. `--sudo` is opt-in. Key-based
noninteractive authentication is required (`--batch`). In restricted environments,
set `XDG_RUNTIME_DIR=/tmp` for the local SSH socket. The script never prints
client private keys or PSKs.
