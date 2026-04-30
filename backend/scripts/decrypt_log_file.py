#!/usr/bin/env python3
"""
Decrypt a log file produced with FernetRotatingFileHandler (LOG_ENCRYPTION_KEY).

  export LOG_ENCRYPTION_KEY='...'
  python scripts/decrypt_log_file.py logs/audit.log

Or pass the key (avoid shell history on shared machines — prefer env):

  python scripts/decrypt_log_file.py --key-file /secure/fernet.key logs/audit.log
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Decrypt Fernet line-encrypted log files.")
    p.add_argument("logfile", type=Path, help="Path to encrypted .log file")
    p.add_argument(
        "--key-file",
        type=Path,
        default=None,
        help="File containing LOG_ENCRYPTION_KEY (otherwise uses env LOG_ENCRYPTION_KEY)",
    )
    args = p.parse_args()

    if args.key_file is not None:
        raw = args.key_file.read_text(encoding="utf-8").strip()
    else:
        raw = (os.environ.get("LOG_ENCRYPTION_KEY") or "").strip()
    if not raw:
        print("Set LOG_ENCRYPTION_KEY or use --key-file", file=sys.stderr)
        return 1

    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        print("Install cryptography: pip install cryptography", file=sys.stderr)
        raise SystemExit(1) from e

    f = Fernet(raw.encode("utf-8"))
    text = args.logfile.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            plain = f.decrypt(line.encode("ascii"))
            sys.stdout.buffer.write(plain)
        except Exception as e:
            print(f"[decrypt error] {e!s}: {line[:80]}...", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
