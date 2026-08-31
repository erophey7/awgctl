#!/usr/bin/env python3
"""Build awgctl single-file executable from src/ modules + lang/ localization."""

import argparse
import os
import re
import sys

SRC_ORDER = [
    "src/constants.py",
    "src/i18n.py",
    "src/backend.py",
    "src/utils.py",
    "src/config.py",
    "src/importer.py",
    "src/commands.py",
    "src/cli.py",
]


def extract_messages(lang_path):
    ns = {}
    with open(lang_path) as f:
        exec(compile(f.read(), lang_path, "exec"), ns)
    return ns["MESSAGES"]


def strip_local_imports(lines):
    """Drop local (relative) imports — the flattened file is one namespace.

    Handles both single-line `from .x import a, b` and parenthesized
    multi-line `from .x import (\\n a,\\n b,\\n)` forms, as well as
    function-local imports (indented).
    """
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if re.match(r'^\s*from\s+\.', line) or re.match(r'^\s*import\s+\.', line):
            # consume a parenthesized multi-line import fully
            if '(' in line and ')' not in line:
                i += 1
                while i < n and ')' not in lines[i]:
                    i += 1
                i += 1  # skip the closing ')' line
                continue
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def build(args):
    lang = args.lang
    out = args.output
    lang_path = os.path.join("lang", f"{lang}.py")
    if not os.path.exists(lang_path):
        print(f"Language file not found: {lang_path}", file=sys.stderr)
        sys.exit(1)

    messages = extract_messages(lang_path)

    license_text = ""
    if os.path.exists("LICENSE"):
        with open("LICENSE") as f:
            license_text = f.read()

    parts = []
    parts.append("#!/usr/bin/env python3")
    parts.append('"""')
    parts.append("awgctl — AmneziaWG client management utility")
    if license_text:
        parts.append("")
        parts.append(license_text)
    parts.append('"""')

    std_imports = [
        "import argparse",
        "import atexit",
        "import base64",
        "import contextlib",
        "import fcntl",
        "import getpass",
        "import ipaddress",
        "import json",
        "import os",
        "import pty",
        "import re",
        "import shlex",
        "import shutil",
        "import subprocess",
        "import sys",
        "import time",
    ]
    parts.extend(std_imports)
    parts.append("")

    for path in SRC_ORDER:
        if not os.path.exists(path):
            print(f"Missing source: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path) as f:
            lines = f.read().splitlines()
        lines = strip_local_imports(lines)
        parts.append(f"# ---------- {path} ----------")
        parts.extend(lines)
        parts.append("")
        if path == "src/i18n.py":
            # load the selected language into i18n's MESSAGES (used by _t)
            parts.append("# ---------- injected messages ----------")
            parts.append("MESSAGES = " + repr(messages))
            parts.append("")

    parts.append('if __name__ == "__main__":')
    parts.append('    try:')
    parts.append('        main()')
    parts.append('    except (RuntimeError, subprocess.CalledProcessError) as e:')
    parts.append('        # message templates already carry a localized prefix')
    parts.append('        print(str(e), file=sys.stderr)')
    parts.append('        sys.exit(1)')
    parts.append('    except KeyboardInterrupt:')
    parts.append(r'        print("\nInterrupted.", file=sys.stderr)')
    parts.append('        sys.exit(130)')

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write("\n".join(parts) + "\n")
    os.chmod(out, 0o755)
    print(f"Built {out} (lang={lang})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build awgctl")
    p.add_argument("--lang", default="en", choices=["en", "ru"])
    p.add_argument("--output", default="build/awgctl")
    args = p.parse_args()
    build(args)
