# English localization for awgctl
MESSAGES = {
    "description": "Manage AmneziaWG clients in a server config.",
    "epilog": (
        "Commands abbreviate to any unambiguous prefix (a=add, i=init, l=list, "
        "g=get; ambiguous need more: del/def, res/rek, se/sh). "
        "Global command: configs. Per-command help: awgctl <command> -h."
    ),
    "conn_group": "connection options (global)",
    "help_ssh": "operate on remote server via SSH (read/write/restart there)",
    "help_sudo": "run privileged commands on remote server via sudo",
    "help_ask_pass": "ask for SSH password if key auth fails",
    "help_ssh_pass": "SSH password source without prompt: fd:N or env:VAR",
    "help_sudo_pass": "sudo password source without prompt: fd:N or env:VAR",
    "help_batch": "non-interactive mode: no prompts; missing secret → immediate error",
    "help_config": "path to server config OR short name (searched in /etc/amnezia/amneziawg, .conf appended)",
    "help_restart_flag": "restart tunnel via awg-quick after operation (if running)",
    "init_help": "add AWGCTL markup / import existing peers",
    "init_desc": (
        "Mark up the server config with an AWGCTL zone and import existing "
        "[Peer] sections. Role is detected by ListenPort (client configs are "
        "rejected); degenerate peers (gateway/s2s/no AllowedIPs) are adopted "
        "with a warning. Re-running only updates the default host (--host)."
    ),
    "init_epilog": (
        "Examples:\n"
        "  awgctl awg0 init --dry              # preview parsing without writing\n"
        "  awgctl awg0 init --host vpn.example.com\n"
        "  awgctl awg0 init -y                 # auto names, no questions\n"
        "  awgctl awg0 init --rekey-imported   # rotate keys immediately\n"
        "  awgctl awg0 init --ssh root@vpn --sudo\n"
        "  awgctl awg0 init --batch --fix-perms --host vpn  # non-interactive"
    ),
    "help_host": "default domain/IP for clients (port from server ListenPort); stored in awgctl section",
    "help_yes": "do not ask interactively: accept auto-generated names on import",
    "help_rekey_imported": "immediately rotate keys for clients without a private key",
    "help_fix_perms": "fix config permissions (chmod 600 + chown root:root) without asking",
    "help_dry": "only show what would be parsed (role, peers, names, warnings), do NOT write",
    "help_json": "machine-readable output",
    "list_help": "list clients",
    "list_desc": "Show clients from the AWGCTL marked zone: name, IP, server AllowedIPs, client routes, endpoint, keepalive.",
    "list_epilog": "Examples:\n  awgctl awg0 list\n  awgctl awg0 list --json",
    "add_help": "add a client",
    "add_desc": "Generate a new key pair + PSK, allocate a free IP from the server subnet, add [Peer] to the AWGCTL zone and output the ready client config to stdout (not saved to file).",
    "add_epilog": (
        "Examples:\n"
        "  awgctl awg0 add phone\n"
        "  awgctl awg0 add phone laptop tablet         # several at once\n"
        "  awgctl awg0 add site --client-allow '192.168.5.0/24'  # gateway\n"
        "  awgctl awg0 add phone --dns '10.0.0.1' --endpoint vpn:51820"
    ),
    "help_name": "client name",
    "help_client_allow": "AllowedIPs in server [Peer] (networks behind client, for VPN gateway); default is client IP/32",
    "help_client_routes": "AllowedIPs in client config (what client routes through VPN); default from config defaults",
    "help_keepalive": "PersistentKeepalive; default from config defaults",
    "help_dns": "client DNS; default from config defaults",
    "help_endpoint": "custom client endpoint host:port",
    "del_help": "delete a client",
    "del_desc": "Remove one or more clients (meta + [Peer]) from the AWGCTL zone. Supports --all.",
    "del_epilog": "Examples:\n  awgctl awg0 del phone\n  awgctl awg0 del phone laptop\n  awgctl awg0 del --all",
    "get_help": "output client config",
    "get_desc": "Rebuild and output to stdout the client config of an existing client (keys are taken from the AWGCTL zone).",
    "get_epilog": "Example:\n  awgctl awg0 get phone > phone.conf",
    "rekey_help": "rotate client keys (new pair + PSK)",
    "rekey_desc": "Rotate keys (new pair + PSK) for one or more clients and output new configs. Supports --all. Old configs stop connecting until clients fetch the new ones.",
    "rekey_epilog": "Examples:\n  awgctl awg0 rekey phone\n  awgctl awg0 rekey phone laptop\n  awgctl awg0 rekey --all",
    "set_help": "change client parameters (bulk)",
    "set_desc": (
        "Change parameters of existing clients without rotating keys.\n"
        "Multiple names or --all (bulk) are supported. --allow changes\n"
        "server AllowedIPs in [Peer]; others only affect the issued client\n"
        "config (get). After changes, distribute new configs to affected clients."
    ),
    "set_epilog": (
        "Examples:\n"
        "  awgctl awg0 set phone --dns 10.0.0.1\n"
        "  awgctl awg0 set phone laptop --keepalive 15\n"
        "  awgctl awg0 set --all --host vpn2.example.com\n"
        "  awgctl awg0 set --all --routes '0.0.0.0/0, ::/0'\n"
        "  awgctl awg0 set site --allow '192.168.5.0/24, 10.0.0.0/8'"
    ),
    "help_names": "client names (or use --all)",
    "help_all": "apply to all clients",
    "help_set_host": "client host (endpoint built as host:ListenPort); overrides default host but not --endpoint",
    "help_set_endpoint": "full endpoint host:port (highest priority)",
    "help_set_allow": "server AllowedIPs in [Peer] (networks behind client)",
    "help_set_defaults": "apply to config DEFAULTS instead of clients (equivalent to defaults command)",
    "defaults_help": "show/change default client parameters",
    "defaults_desc": "Without flags — show current defaults (host/dns/routes/keepalive) used in add when a flag is not set. With flags — save new defaults in the config markup zone.",
    "defaults_epilog": (
        "Examples:\n"
        "  awgctl awg0 defaults\n"
        "  awgctl awg0 defaults --host vpn.example.com\n"
        "  awgctl awg0 defaults --dns '10.0.0.1'\n"
        "  awgctl awg0 defaults --routes '10.0.0.0/8' --keepalive 15"
    ),
    "show_help": "live tunnel status (handshake/traffic per client)",
    "show_desc": "Show live interface status from 'awg show <iface> dump': per peer — name (matched from AWGCTL zone), last handshake time, received/sent, endpoint. Requires running interface and root (local) or --ssh --sudo.",
    "show_epilog": (
        "Examples:\n"
        "  awgctl awg0 show\n"
        "  awgctl awg0 show --json\n"
        "  awgctl awg0 show --ssh root@vpn --sudo"
    ),
    "restart_help": "restart tunnel via awg-quick (local or via SSH)",
    "restart_desc": "Restart interface via awg-quick down/up (if running). Interface name is taken from the config file name.",
    "restart_epilog": "Example:\n  awgctl awg0 restart",
    "configs_help": "overview of configs in directory with statuses",
    "configs_desc": (
        "Overview of *.conf in directory with statuses:\n"
        "  client            — client config (no ListenPort);\n"
        "  unmanaged         — server without AWGCTL markup;\n"
        "  managed           — server under awgctl management."
    ),
    "configs_epilog": (
        "Examples:\n"
        "  awgctl configs\n"
        "  awgctl configs --json\n"
        "  awgctl configs /some/dir\n"
        "  awgctl configs --ssh root@vpn --sudo"
    ),
    "help_dir": f"search directory (*.conf), default /etc/amnezia/amneziawg",
    "err_no_wg": "Error: awg/wg not found (locally or on remote with --ssh).",
    "err_invalid_name": "Error: invalid client name.",
    "err_bad_cidr": "Error: invalid CIDR in {what}: '{part}'.",
    "err_no_markup": "Error: client markup missing. Run init first.",
    "err_exists": "Error: client '{name}' already exists.",
    "err_no_address": "Error: no Address (VPN subnet) in config.",
    "err_no_free_ip": "Error: no free address in subnet.",
    "err_no_server_priv": "Error: no PrivateKey in [Interface] — cannot compute server public key.",
    "err_server_pub_fail": "Error: failed to compute server public key.",
    "err_client_config": "Error: this is a client config (no ListenPort in [Interface]) — cannot turn into server. Aborted.",
    "err_not_found": "Error: config '{name}' not found (checked as path and in {dir}/).",
    "err_peer_not_found": "Error: client '{name}' not found.",
    "err_no_params": "Error: no parameters specified for change (--dns/--routes/--keepalive/--endpoint/--allow).",
    "err_no_names": "Error: specify client name(s) or --all.",
    "err_missing_clients": "Error: clients not found: {names}.",
    "err_defaults_conflict": "Error: --defaults cannot be combined with names/--all.",
    "err_bad_defaults": "Error: for defaults these are not allowed: {bad} (only host/dns/routes/keepalive).",
    "err_keepalive_num": "Error: keepalive must be a number, not '{v}'.",
    "err_remote_write": "Error: remote write failed: {msg}",
    "err_ssh_auth": "Error: ssh {target}: password auth failed (rc={rc}).",
    "err_ssh_batch": "Error: ssh {target}: key failed and --batch forbids prompt. Pass --ssh-pass=fd:N|env:VAR. {err}",
    "err_ssh_no_tty": "Error: ssh {target}: key failed, password unavailable (add --ask-pass/--ssh-pass or use a key). {err}",
    "err_sudo_batch": "Error: sudo on {target} requires password but --batch forbids prompt. Pass --sudo-pass=fd:N|env:VAR.",
    "err_sudo_no_tty": "Error: sudo on {target} requires password but no TTY. Pass --sudo-pass=fd:N|env:VAR.",
    "err_sudo_stdin": "Error: internal error: sudo with password incompatible with stdin data.",
    "err_no_secret_src": "Error: secret: environment variable '{var}' not set.",
    "err_bad_fd": "Error: secret: invalid descriptor in '{spec}'.",
    "err_read_fd": "Error: secret: failed to read fd:{fd}: {e}",
    "err_unknown_secret": "Error: secret: unknown source '{spec}' (expected fd:N or env:VAR).",
    "err_lock_busy": "Error: failed to acquire remote lock {lockd} (busy? remove manually if stuck).",
    "err_import_no_priv": "Error: no PrivateKey in [Interface] — cannot compute server public key for import.",
    "warn_perms": "⚠ Unsafe permissions {path}: {issues}. Config contains private keys — fix: chmod 600 + chown root:root (or run init to be offered a fix).",
    "warn_perms_init": "⚠ Unsafe permissions {path}: {issues}.",
    "warn_perms_fix_fail": "⚠ Could not fix permissions {path}{err} (needs root/--sudo).",
    "warn_no_host": "Warning: --host not specified. Default endpoint for clients is not set.",
    "warn_no_host_init": "Warning: --host not set — client endpoint will be empty.",
    "warn_no_wg_import": "  ⚠ rekey skipped: awg/wg not available locally (run 'rekey <name> --ssh' later).",
    "warn_server_pub_missing": "Warning: could not determine server public key (awg/wg not available locally).",
    "warn_client_priv_missing": "Warning: '{name}' has no private key (imported without it) — config incomplete, run 'rekey {name}'.",
    "info_perms_fixed": "  Permissions fixed: root:root 0600.",
    "info_imported": "Imported clients: {count} -> {path}",
    "info_rekeyed": "Rekeyed clients during import: {count}",
    "info_added": "# Added client '{name}' -> {path}",
    "info_deleted": "Client '{name}' deleted.",
    "info_rekeyed_client": "# Client '{name}' keys rotated — distribute new config.",
    "info_changed": "Changed clients: {count} ({fields})",
    "info_restart": "Tunnel '{iface}' restarted.",
    "info_not_running": "Interface '{iface}' is not running. Doing nothing.",
    "info_markup_exists": "Markup already present.",
    "info_host_updated": "Default host updated: {host}",
    "info_markup_added": "Markup added to {path}",
    "info_dry_role_server": "Role: SERVER (ListenPort present in [Interface]).",
    "info_dry_role_client": "Role: CLIENT (no ListenPort in [Interface]).",
    "info_dry_rejected": "init would REJECT this config — cannot turn client into server.",
    "info_dry_managed": "Status: MANAGED (AWGCTL markup already present), clients: {count}.",
    "info_dry_no_peers": "No peers found — init would simply add empty AWGCTL markup at the end.",
    "info_dry_peers_found": "Found [Peer]: {count}. Parsing each:",
    "info_dry_peer": "  #{idx}  name={name} ({src})   type={kind}",
    "info_dry_peer_pubkey": "      PublicKey   : {pubkey}",
    "info_dry_peer_allowed": "      AllowedIPs  : {allowed}",
    "info_dry_peer_endpoint": "      Endpoint    : {endpoint}",
    "info_dry_peer_advsec": "      AdvancedSecurity: {advsec}",
    "info_dry_peer_psk": "      PresharedKey: {psk}",
    "info_dry_peer_priv": "      PrivateKey  : {priv}",
    "info_dry_summary": "Total: {count} peers, with warnings: {flagged}. Run without --dry to import.",
    "info_backup_fail": "Warning: could not create backup: {e}",
    "status_client": "client",
    "status_unmanaged": "unmanaged",
    "status_managed": "managed",
    "status_error": "error",
    "status_no_access": "no access",
    "label_name": "NAME",
    "label_ip": "IP",
    "label_allow": "ALLOW(srv)",
    "label_routes": "ROUTES(cl)",
    "label_endpoint": "ENDPOINT",
    "label_ka": "KA",
    "label_config": "CONFIG",
    "label_status": "STATUS",
    "label_clients": "CLIENTS/PEERS",
    "label_handshake": "HANDSHAKE",
    "label_rx": "RX",
    "label_tx": "TX",
    "label_unknown": "(unknown)",
    "label_never": "never",
    "label_just_now": "just now",
    "label_sec_ago": "{n} sec ago",
    "label_min_ago": "{n} min ago",
    "label_hour_ago": "{n} h ago",
    "label_day_ago": "{n} days ago",
    "msg_distribute": "Distribute updated configs to affected clients (awgctl get <name>).",
    "msg_no_clients": "No clients.",
    "msg_total_clients": "Total: {count}",
    "msg_total_configs": "Total configs: {count} (directory: {dir})",
    "msg_no_configs": "No configs (*.conf) found in {dir}.",
    "msg_peer_none": "Interface '{iface}' is running, no peers.",
    "msg_peers_count": "Peers: {count} (interface {iface})",
    "msg_import_count": "Found peers to import: {count}",
    "msg_peer_summary": "  peer: pub={pub}… allow={allow} kind={kind} priv={priv}",
    "msg_degenerate": "  ⚠ {name}: type '{kind}' — importing as-is, full management/rekey limited.",
    "msg_no_client_priv": "  ⚠ {name}: no client_priv — get will produce incomplete config, rekey needed.",
    "prompt_fix_perms": "  Fix now (chmod 600 + chown root:root)? y/N",
    "prompt_name": "  name",
    "prompt_name_taken": "  '{name}' is taken, another",
    "prompt_rekey": "Rotate keys for {count} clients without private key now (issue new configs)? y/N",
    "dry_run_notice": "[dry-run] init {path} — nothing is written",
    "perm_issues_notice": "⚠ Config permissions: {issues} (init without --dry would offer to fix).",
}
