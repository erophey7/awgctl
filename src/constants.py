"""Constants and global configuration for awgctl."""

import sys

BEGIN = "# === AWGCTL-CLIENTS-BEGIN ==="
END = "# === AWGCTL-CLIENTS-END ==="

COMMANDS = ("init", "list", "add", "del", "get", "rekey", "rename", "restart",
            "set", "defaults", "show")
# глобальные команды: не привязаны к одному конфигу (config-слот не нужен)
GLOBAL_COMMANDS = ("configs",)
STD_CONFIG_DIR = "/etc/amnezia/amneziawg"

# неинтерактивный режим (--batch): промптов нет, отсутствующий секрет → ошибка.
# main() выставляет через set_batch(); влияет на _ask и запрос паролей в SSH.
# noninteractive()/set_batch() живут здесь (рядом с BATCH), чтобы значение
# читалось «вживую» и в модульной форме (не копия from-import), и в собранном
# одном файле (общий global).
BATCH = False


def set_batch(value):
    """Выставить неинтерактивный режим (вызывается из main)."""
    global BATCH
    BATCH = value


def noninteractive():
    """True, если нельзя спрашивать пользователя (batch или нет TTY)."""
    return BATCH or not sys.stdin.isatty()

# порядок полей meta-строки клиента (# AWGCTL |...|). Расширяемо: parse_meta
# читает любые k=v, поэтому старые meta без новых полей читаются штатно.
META_FIELDS = ("name", "ip", "allow", "routes", "keepalive", "endpoint",
               "host", "dns", "psk", "server_pub", "client_pub", "client_priv")

# дефолты параметров клиента (жёсткий фолбэк). Могут переопределяться на уровне
# конфига строкой # AWGCTL-DEFAULTS в зоне разметки (см. get_defaults).
DEFAULT_PARAMS = {
    "dns": "1.1.1.1, 1.0.0.1",
    "routes": "0.0.0.0/0, ::/0",
    "keepalive": "25",
}
# какие параметры пользователя можно менять командой set (per-client)
CLIENT_PARAMS = ("dns", "routes", "keepalive", "endpoint", "host", "allow")
# какие параметры можно задавать дефолтами (defaults), на уровне конфига
DEFAULT_KEYS = ("host", "dns", "routes", "keepalive")

MASKING_KEYS = {"jc", "jmin", "jmax", "s1", "s2", "s3", "s4",
                "h1", "h2", "h3", "h4", "i1", "i2", "i3", "i4", "i5",
                "headerprotectionkey", "contentpaddingaddition",
                "rekeyaftertime", "rekeytimeout", "rejectaftertime",
                "keepalivetimeout", "maxhandshakeattempts",
                "randomtrailers", "disablecookies"}

HOST_LINE_PREFIX = "# AWGCTL-HOST ="
DEFAULTS_PREFIX = "# AWGCTL-DEFAULTS"

# верхняя граница перебора адресов (защита от зависания на IPv6-пространствах)
MAX_IP_SCAN = 100000
