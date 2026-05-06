"""Advisory lock helpers para serialização full vs incremental.

Lock session-level (não TX) em conexão dedicada — sobrevive a commits internos
do main_conn. pg_advisory_lock(int4, int4) overload determinístico via
hashtext::int (R6 fix vs single-bigint que tinha overload ambíguo).

Princípio P2: full e incremental compartilham o mesmo lock helper para
serialização garantida (mesmo que em runners diferentes).
"""

from __future__ import annotations

from .conn import LockConn


def acquire_etl_table_locks(lock_conn: LockConn, source: str, table: str) -> None:
    """Adquire 2 locks session-level: per-table + global.

    Lock 1 (per-table): serializa runs distintas no mesmo (source, table)
    Lock 2 (global per-source-table): para coordenação cross-mode (full vs incr)
    """
    # Per-table lock
    with lock_conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_lock(hashtext(%s)::int, hashtext(%s)::int)",
            (source, table),
        )
        # Global lock para serialização cross-mode
        cur.execute(
            "SELECT pg_advisory_lock(hashtext(%s)::int, hashtext(%s)::int)",
            ("global", f"{source}.{table}"),
        )


def release_etl_table_locks(lock_conn: LockConn, source: str, table: str) -> None:
    """Libera locks na ordem inversa. Idempotent: ignora se já foram liberados."""
    with lock_conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT pg_advisory_unlock(hashtext(%s)::int, hashtext(%s)::int)",
                ("global", f"{source}.{table}"),
            )
            cur.execute(
                "SELECT pg_advisory_unlock(hashtext(%s)::int, hashtext(%s)::int)",
                (source, table),
            )
        except Exception:
            pass


def try_acquire_etl_table_locks(lock_conn: LockConn, source: str, table: str) -> bool:
    """Não-bloqueante: retorna False se outro processo já tem o lock.

    Útil para preflight detection antes de tentar acquire bloqueante.
    """
    with lock_conn.cursor() as cur:
        cur.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s)::int, hashtext(%s)::int)",
            (source, table),
        )
        got_table = cur.fetchone()[0]
        if not got_table:
            return False
        cur.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s)::int, hashtext(%s)::int)",
            ("global", f"{source}.{table}"),
        )
        got_global = cur.fetchone()[0]
        if not got_global:
            # Liberar o per-table que já pegou
            cur.execute(
                "SELECT pg_advisory_unlock(hashtext(%s)::int, hashtext(%s)::int)",
                (source, table),
            )
            return False
    return True
