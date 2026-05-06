"""Typed connection wrappers (D12).

3 tipos de conexões com semântica TX distinta:
- MainTxConn: TX-managed (autocommit OFF). Onde data writes acontecem.
- LockConn: session-level advisory lock (autocommit ON ou OFF, mas dedicada).
- AutocommitDlqConn: DLQ writes (autocommit ON, persiste mesmo em rollback).

Wrapper classes (não NewType — NewType é mypy-only e some em runtime).
__init__ valida autocommit para evitar miswiring (R6 BLOCKING fix).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


class WiringError(RuntimeError):
    """Connection foi passada com configuração errada."""


class _ConnWrapper:
    """Forward attribute access para a connection underlying."""
    __slots__ = ("_c",)

    def __init__(self, conn):
        self._c = conn

    def __getattr__(self, name):
        return getattr(self._c, name)

    def __repr__(self):
        return f"{type(self).__name__}({self._c!r})"


class MainTxConn(_ConnWrapper):
    """TX-managed conn. autocommit MUST be False."""

    def __init__(self, conn):
        if getattr(conn, "autocommit", None) is True:
            raise WiringError(
                "MainTxConn requires autocommit=False (got autocommit=True)"
            )
        super().__init__(conn)


class LockConn(_ConnWrapper):
    """Session-level conn dedicada para advisory lock. autocommit pode ser
    True (mais comum para evitar TX que prendam locks pra sempre)."""
    pass


class AutocommitDlqConn(_ConnWrapper):
    """DLQ writes em autocommit. autocommit MUST be True."""

    def __init__(self, conn):
        if getattr(conn, "autocommit", None) is not True:
            raise WiringError(
                "AutocommitDlqConn requires autocommit=True"
            )
        super().__init__(conn)


@dataclass(frozen=True)
class IncrementalLoadContext:
    """Container imutável das 3 conexões + run metadata.

    Runtime checks em __post_init__: identidades distintas (R6 fix).
    """

    main: MainTxConn
    lock: LockConn
    dlq: AutocommitDlqConn
    run_id: uuid.UUID
    bucket_token: uuid.UUID

    def __post_init__(self):
        # Distinct connection identities (R6 BLOCKING fix)
        ids = {id(self.main._c), id(self.lock._c), id(self.dlq._c)}
        if len(ids) != 3:
            raise WiringError(
                "IncrementalLoadContext: main/lock/dlq must be DISTINCT connections"
            )
