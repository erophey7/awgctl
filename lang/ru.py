# Russian localization for awgctl
MESSAGES = {
    "description": "Управление клиентами AmneziaWG в серверном конфиге.",
    "epilog": (
        "Команду можно сокращать префиксом (a=add, i=init, l=list, g=get; для "
        "неоднозначных: del/def, res/rek/ren, se/sh). "
        "Глобальная команда: configs. Help по команде: awgctl <команда> -h."
    ),
    "conn_group": "опции подключения (глобальные)",
    "help_ssh": "работать с конфигом на удалённом сервере по SSH (read/write/restart там же)",
    "help_ssh_config": "файл настроек OpenSSH (-F); нужен --ssh; по умолчанию обычный SSH-конфиг",
    "err_ssh_config_without_ssh": "Ошибка: --ssh-config требует --ssh.",
    "err_ssh_config": "Ошибка чтения SSH-конфига: {err}",
    "help_sudo": "выполнять привилегированные команды на сервере через sudo",
    "help_ask_pass": "спросить SSH-пароль, если ключ не подошёл",
    "help_ssh_pass": "источник SSH-пароля без промпта: fd:N или env:VAR",
    "help_sudo_pass": "источник sudo-пароля без промпта: fd:N или env:VAR",
    "help_batch": "неинтерактивный режим: без промптов; нет секрета — ошибка сразу",
    "help_config": "путь до серверного конфига ИЛИ короткое имя (ищется в /etc/amnezia/amneziawg, .conf добавляется)",
    "help_restart_flag": "перезапустить туннель через awg-quick после операции (если запущен)",
    "init_help": "добавить разметку AWGCTL / импортировать peer'ов",
    "init_desc": (
        "Разметить серверный конфиг зоной AWGCTL и импортировать существующие "
        "[Peer]. Роль определяется по ListenPort (клиентский конфиг "
        "отклоняется); вырожденные peer'ы (gateway/s2s/без AllowedIPs) "
        "адоптируются с предупреждением. Повторный init лишь обновляет host (--host)."
    ),
    "init_epilog": (
        "Примеры:\n"
        "  awgctl awg0 init --dry              # предпросмотр разбора, без записи\n"
        "  awgctl awg0 init --host vpn.example.com\n"
        "  awgctl awg0 init -y                 # авто-имена, без вопросов\n"
        "  awgctl awg0 init --rekey-imported   # сразу ротировать ключи\n"
        "  awgctl awg0 init --ssh root@vpn --sudo\n"
        "  awgctl awg0 init --batch --fix-perms --host vpn  # без промптов"
    ),
    "help_host": "дефолтный domain/IP клиентов (порт из ListenPort сервера); сохраняется в секцию awgctl",
    "help_yes": "не спрашивать интерактивно: авто-имена при импорте",
    "help_rekey_imported": "при импорте сразу ротировать ключи клиентов без приватного ключа",
    "help_fix_perms": "починить права конфига (chmod 600 + chown root:root) без вопроса",
    "help_dry": "только показать, что удалось распарсить (роль, peer'ы, имена, замечания), НИЧЕГО не записывая",
    "help_json": "машинный вывод",
    "list_help": "список клиентов",
    "list_desc": "Показать клиентов из размеченной зоны AWGCTL: имя, IP, серверный AllowedIPs, маршруты клиента, endpoint, keepalive.",
    "list_epilog": "Примеры:\n  awgctl awg0 list\n  awgctl awg0 list --json",
    "add_help": "добавить клиента",
    "add_desc": "Сгенерировать новую пару ключей + PSK, выделить свободный IP из подсети сервера, добавить [Peer] в зону AWGCTL и вывести готовый клиентский конфиг в stdout (в файл не сохраняется).",
    "add_epilog": (
        "Примеры:\n"
        "  awgctl awg0 add phone\n"
        "  awgctl awg0 add phone laptop tablet         # несколько сразу\n"
        "  awgctl awg0 add site --client-allow '192.168.5.0/24'  # gateway\n"
        "  awgctl awg0 add phone --dns '10.0.0.1' --endpoint vpn:51820"
    ),
    "help_name": "имя клиента",
    "help_new_name": "новое имя клиента (буквы, цифры, подчёркивания, точки, дефисы)",
    "rename_help": "переименовать клиента",
    "rename_desc": "Изменить имя клиента с сохранением ключей, IP и настроек peer. Перезапуск туннеля и новый клиентский конфиг не нужны. Новое имя должно быть свободным.",
    "rename_epilog": "Пример:\n  awgctl awg0 rename client-10-0-0-2 phone",
    "info_renamed": "Клиент '{name}' переименован в '{new_name}'.",
    "info_name_unchanged": "Клиент '{name}' уже носит это имя; изменений нет.",
    "help_client_allow": "AllowedIPs в серверном [Peer] (сети за клиентом, для VPN-gateway), по умолчанию IP клиента с /32",
    "help_client_routes": "AllowedIPs в клиентском конфиге (что клиент гонит через VPN), по умолчанию — из дефолтов конфига",
    "help_keepalive": "PersistentKeepalive, по умолчанию — из дефолтов конфига",
    "help_dns": "DNS клиента, по умолчанию — из дефолтов конфига",
    "help_endpoint": "кастомный endpoint клиента host:port",
    "del_help": "удалить клиента",
    "del_desc": "Удалить одного или нескольких клиентов (meta + [Peer]) из зоны AWGCTL. Поддерживает --all.",
    "del_epilog": "Примеры:\n  awgctl awg0 del phone\n  awgctl awg0 del phone laptop\n  awgctl awg0 del --all",
    "get_help": "вывести конфиг клиента",
    "get_desc": "Пересобрать и вывести в stdout клиентский конфиг ранее созданного клиента (ключи берутся из зоны AWGCTL).",
    "get_epilog": "Пример:\n  awgctl awg0 get phone > phone.conf",
    "rekey_help": "ротация ключей клиента (новая пара + PSK)",
    "rekey_desc": "Ротация ключей (новая пара + PSK) для одного или нескольких клиентов, с выводом новых конфигов. Поддерживает --all. Старые конфиги перестанут коннектиться, пока клиенты не заберут новые.",
    "rekey_epilog": "Примеры:\n  awgctl awg0 rekey phone\n  awgctl awg0 rekey phone laptop\n  awgctl awg0 rekey --all",
    "set_help": "изменить параметры клиента(ов) (bulk)",
    "set_desc": (
        "Изменить параметры существующих клиентов без ротации ключей.\n"
        "Можно указать несколько имён или --all (bulk). Параметр --allow\n"
        "меняет серверный AllowedIPs в [Peer]; остальные — только выдачу\n"
        "клиентского конфига (get). После изменения раздайте новый конфиг."
    ),
    "set_epilog": (
        "Примеры:\n"
        "  awgctl awg0 set phone --dns 10.0.0.1\n"
        "  awgctl awg0 set phone laptop --keepalive 15\n"
        "  awgctl awg0 set --all --host vpn2.example.com\n"
        "  awgctl awg0 set --all --routes '0.0.0.0/0, ::/0'\n"
        "  awgctl awg0 set site --allow '192.168.5.0/24, 10.0.0.0/8'"
    ),
    "help_names": "имена клиентов (или используйте --all)",
    "help_all": "применить ко всем клиентам",
    "help_set_host": "host клиента (endpoint строится как host:ListenPort); перекрывает дефолтный host, но не --endpoint",
    "help_set_endpoint": "полный endpoint host:port (высший приоритет)",
    "help_set_allow": "серверный AllowedIPs в [Peer] (сети за клиентом)",
    "help_set_defaults": "применить к ДЕФОЛТАМ конфига, а не к клиентам (эквивалент команды defaults)",
    "defaults_help": "показать/изменить дефолты параметров клиента",
    "defaults_desc": "Без флагов — показать текущие дефолты (host/dns/routes/keepalive), которые подставляются в add, когда соответствующий флаг не задан. С флагами — сохранить новые дефолты в зону разметки конфига.",
    "defaults_epilog": (
        "Примеры:\n"
        "  awgctl awg0 defaults\n"
        "  awgctl awg0 defaults --host vpn.example.com\n"
        "  awgctl awg0 defaults --dns '10.0.0.1'\n"
        "  awgctl awg0 defaults --routes '10.0.0.0/8' --keepalive 15"
    ),
    "show_help": "живой статус туннеля (handshake/трафик по клиентам)",
    "show_desc": "Показать живой статус интерфейса из 'awg show <iface> dump': по каждому peer — имя (из зоны AWGCTL), время последнего handshake, принято/передано, endpoint. Нужен запущенный интерфейс и root (локально) или --ssh --sudo.",
    "show_epilog": (
        "Примеры:\n"
        "  awgctl awg0 show\n"
        "  awgctl awg0 show --json\n"
        "  awgctl awg0 show --ssh root@vpn --sudo"
    ),
    "restart_help": "перезапустить туннель через awg-quick (локально или по SSH)",
    "restart_desc": "Перезапустить интерфейс через awg-quick down/up (если запущен). Имя интерфейса берётся из имени файла конфига.",
    "restart_epilog": "Пример:\n  awgctl awg0 restart",
    "configs_help": "обзор конфигов в каталоге со статусами",
    "configs_desc": (
        "Обзор *.conf в каталоге со статусами:\n"
        "  client            — клиентский конфиг (нет ListenPort);\n"
        "  не подконтрольный — сервер без разметки AWGCTL;\n"
        "  подконтрольный    — сервер под управлением awgctl."
    ),
    "configs_epilog": (
        "Примеры:\n"
        "  awgctl configs\n"
        "  awgctl configs --json\n"
        "  awgctl configs /some/dir\n"
        "  awgctl configs --ssh root@vpn --sudo"
    ),
    "help_dir": "каталог поиска (*.conf), по умолчанию /etc/amnezia/amneziawg",
    "err_no_wg": "Ошибка: нет awg/wg (локально или на сервере при --ssh).",
    "err_invalid_name": "Ошибка: недопустимое имя клиента.",
    "err_bad_cidr": "Ошибка: недопустимый CIDR в {what}: '{part}'.",
    "err_no_markup": "Ошибка: разметка клиентов отсутствует. Сначала выполните init.",
    "err_exists": "Ошибка: клиент '{name}' уже существует.",
    "err_no_address": "Ошибка: в конфиге нет Address (подсеть VPN).",
    "err_no_free_ip": "Ошибка: нет свободного адреса в подсети.",
    "err_no_server_priv": "Ошибка: в [Interface] нет PrivateKey — нельзя вычислить публичный ключ сервера.",
    "err_server_pub_fail": "Ошибка: не удалось вычислить публичный ключ сервера.",
    "err_client_config": "Ошибка: это клиентский конфиг (нет ListenPort в [Interface]) — превратить в серверный нельзя. Отмена.",
    "err_not_found": "Ошибка: конфиг '{name}' не найден (искал как путь и в {dir}/).",
    "err_peer_not_found": "Ошибка: клиент '{name}' не найден.",
    "err_no_params": "Ошибка: не задан ни один параметр для изменения (--dns/--routes/--keepalive/--endpoint/--allow).",
    "err_no_names": "Ошибка: укажите имя(имена) клиентов или --all.",
    "err_missing_clients": "Ошибка: не найдены клиенты: {names}.",
    "err_defaults_conflict": "Ошибка: --defaults нельзя совмещать с именами/--all.",
    "err_bad_defaults": "Ошибка: для дефолтов недопустимы: {bad} (только host/dns/routes/keepalive).",
    "err_keepalive_num": "Ошибка: keepalive должен быть числом, а не '{v}'.",
    "err_remote_write": "Ошибка: удалённая запись не удалась: {msg}",
    "err_ssh_auth": "Ошибка: ssh {target}: авторизация по паролю не удалась (rc={rc}).",
    "err_ssh_batch": "Ошибка: ssh {target}: ключ не подошёл, а --batch запрещает промпт. Передайте --ssh-pass=fd:N|env:VAR. {err}",
    "err_ssh_no_tty": "Ошибка: ssh {target}: ключ не подошёл, пароль недоступен (добавьте --ask-pass/--ssh-pass или используйте ключ). {err}",
    "err_sudo_batch": "Ошибка: sudo на {target} требует пароль, а --batch запрещает промпт. Передайте --sudo-pass=fd:N|env:VAR.",
    "err_sudo_no_tty": "Ошибка: sudo на {target} требует пароль, но TTY нет. Передайте --sudo-pass=fd:N|env:VAR.",
    "err_sudo_stdin": "Ошибка: внутренняя ошибка: sudo с паролем несовместим с stdin-данными.",
    "err_no_secret_src": "Ошибка: секрет: переменная окружения '{var}' не задана.",
    "err_bad_fd": "Ошибка: секрет: неверный дескриптор в '{spec}'.",
    "err_read_fd": "Ошибка: секрет: не удалось прочитать fd:{fd}: {e}",
    "err_unknown_secret": "Ошибка: секрет: неизвестный источник '{spec}' (ожидается fd:N или env:VAR).",
    "err_lock_busy": "Ошибка: не удалось взять удалённый лок {lockd} (занят? удалите вручную, если завис).",
    "err_import_no_priv": "Ошибка: в [Interface] нет PrivateKey — нельзя вычислить публичный ключ сервера для импорта.",
    "warn_perms": "⚠ Небезопасные права {path}: {issues}. В конфиге приватные ключи — почините: chmod 600 + chown root:root (или `awgctl init` предложит).",
    "warn_perms_init": "⚠ Небезопасные права {path}: {issues}.",
    "warn_perms_fix_fail": "⚠ Не удалось починить права {path}{err} (нужен root/--sudo).",
    "warn_no_host": "Предупреждение: --host не указан. Дефолтный endpoint для клиентов не задан.",
    "warn_no_host_init": "Предупреждение: --host не задан — endpoint клиентов пуст.",
    "warn_no_wg_import": "  ⚠ rekey пропущен: нет awg/wg локально (укажите потом 'rekey <name> --ssh').",
    "warn_server_pub_missing": "Предупреждение: не удалось определить публичный ключ сервера (нет awg/wg локально).",
    "warn_client_priv_missing": "Предупреждение: у '{name}' нет приватного ключа (импортирован без него) — конфиг неполный, нужен 'rekey {name}'.",
    "info_perms_fixed": "  Права исправлены: root:root 0600.",
    "info_imported": "Импортировано клиентов: {count} -> {path}",
    "info_rekeyed": "Отрекеино клиентов при импорте: {count}",
    "info_added": "# Добавлен клиент '{name}' -> {path}",
    "info_deleted": "Клиент '{name}' удалён.",
    "info_rekeyed_client": "# Ключи клиента '{name}' ротированы — раздайте новый конфиг.",
    "info_changed": "Изменено клиентов: {count} ({fields})",
    "info_restart": "Туннель '{iface}' перезапущен.",
    "info_not_running": "Интерфейс '{iface}' не запущен. Ничего не делаю.",
    "info_markup_exists": "Разметка уже присутствует.",
    "info_host_updated": "Дефолтный host обновлён: {host}",
    "info_markup_added": "Разметка добавлена в {path}",
    "info_dry_role_server": "Роль: SERVER (в [Interface] есть ListenPort).",
    "info_dry_role_client": "Роль: CLIENT (в [Interface] нет ListenPort).",
    "info_dry_rejected": "init ОТКЛОНИЛ бы этот конфиг — превратить клиентский в серверный нельзя.",
    "info_dry_managed": "Статус: ПОДКОНТРОЛЬНЫЙ (разметка AWGCTL уже есть), клиентов: {count}.",
    "info_dry_no_peers": "Peer'ов не найдено — init просто добавил бы пустую разметку AWGCTL в конец.",
    "info_dry_peers_found": "Найдено [Peer]: {count}. Разбор каждого:",
    "info_dry_peer": "  #{idx}  имя={name} ({src})   тип={kind}",
    "info_dry_peer_pubkey": "      PublicKey   : {pubkey}",
    "info_dry_peer_allowed": "      AllowedIPs  : {allowed}",
    "info_dry_peer_endpoint": "      Endpoint    : {endpoint}",
    "info_dry_peer_advsec": "      AdvancedSecurity: {advsec}",
    "info_dry_peer_psk": "      PresharedKey: {psk}",
    "info_dry_peer_priv": "      PrivateKey  : {priv}",
    "info_dry_summary": "Итог: {count} peer'ов, с замечаниями: {flagged}. Запусти без --dry, чтобы импортировать.",
    "info_backup_fail": "Предупреждение: не удалось создать бэкап: {e}",
    "status_client": "client",
    "status_unmanaged": "не подконтрольный",
    "status_managed": "подконтрольный",
    "status_error": "error",
    "status_no_access": "нет доступа",
    "label_name": "ИМЯ",
    "label_ip": "IP",
    "label_allow": "ALLOW(серв)",
    "label_routes": "ROUTES(кл)",
    "label_endpoint": "ENDPOINT",
    "label_ka": "KA",
    "label_config": "КОНФИГ",
    "label_status": "СТАТУС",
    "label_clients": "КЛИЕНТОВ/PEER'ОВ",
    "label_handshake": "HANDSHAKE",
    "label_rx": "RX",
    "label_tx": "TX",
    "label_unknown": "(неизв.)",
    "label_never": "никогда",
    "label_just_now": "только что",
    "label_sec_ago": "{n} сек назад",
    "label_min_ago": "{n} мин назад",
    "label_hour_ago": "{n} ч назад",
    "label_day_ago": "{n} дн назад",
    "msg_distribute": "Раздайте затронутым клиентам обновлённый конфиг (awgctl get <имя>).",
    "msg_no_clients": "Клиентов нет.",
    "msg_total_clients": "Всего: {count}",
    "msg_total_configs": "Всего конфигов: {count} (каталог: {dir})",
    "msg_no_configs": "В {dir} конфигов (*.conf) не найдено.",
    "msg_peer_none": "Интерфейс '{iface}' запущен, peer'ов нет.",
    "msg_peers_count": "Пиров: {count} (интерфейс {iface})",
    "msg_import_count": "Найдено peer'ов для импорта: {count}",
    "msg_peer_summary": "  peer: pub={pub}… allow={allow} kind={kind} priv={priv}",
    "msg_degenerate": "  ⚠ {name}: тип '{kind}' — импортирую как есть, полное управление/rekey ограничены.",
    "msg_no_client_priv": "  ⚠ {name}: нет client_priv — get даст неполный конфиг, нужен rekey.",
    "prompt_fix_perms": "  Починить сейчас (chmod 600 + chown root:root)? y/N",
    "prompt_name": "  имя",
    "prompt_name_taken": "  '{name}' занято, другое",
    "prompt_rekey": "Ротировать ключи {count} клиентов без приватного ключа сейчас (выдать новые конфиги)? y/N",
    "dry_run_notice": "[dry-run] init {path} — ничего не записывается",
    "perm_issues_notice": "⚠ Права конфига: {issues} (init без --dry предложил бы починить).",
}
