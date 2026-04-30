"""Rotating file handler that writes one Fernet-encrypted line per log record."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Any


class FernetRotatingFileHandler(RotatingFileHandler):
    """Each ``emit`` becomes one ASCII line: Fernet ciphertext (url-safe base64) + newline."""

    def __init__(self, *args, fernet: Any, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fernet = fernet

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if self.terminator:
                msg = msg + self.terminator
            line = self._fernet.encrypt(msg.encode("utf-8")).decode("ascii") + "\n"
            line_b = line.encode("utf-8")
            if self.stream is None:
                self.stream = self._open()
            if self.maxBytes > 0:
                self.stream.seek(0, 2)
                if self.stream.tell() + len(line_b) >= self.maxBytes:
                    self.doRollover()
                    if self.stream is None:
                        self.stream = self._open()
            self.stream.write(line)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
