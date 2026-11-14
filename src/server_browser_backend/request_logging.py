"""Request-local console log context, including synchronous endpoint workers."""

import logging
from contextvars import ContextVar
from ipaddress import ip_address
from typing import Any, Mapping

request_scope: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "request_log_scope", default=None
)


def requestor_ip(scope: Mapping[str, Any] | None) -> str:
    client = scope.get("client") if scope is not None else None
    try:
        return str(ip_address(client[0])) if client else "-"
    except ValueError:
        return "-"


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        scope = request_scope.get()
        record.requestor_ip = requestor_ip(scope)
        if scope is None and record.exc_info:
            record.requestor_ip = getattr(record.exc_info[1], "_request_log_ip", "-")
        return super().format(record)
