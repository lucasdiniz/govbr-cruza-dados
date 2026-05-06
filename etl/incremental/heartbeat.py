"""Heartbeat thread + master watchdog (D7).

Heartbeat thread daemon atualiza etl_run_log.last_heartbeat a cada 30s.
- Se rowcount=0 (run foi fenced por preflight de outro processo), thread
  setea fence_event para main thread abortar.
- Master watchdog signal.alarm garante hard-stop após MAX_RUNTIME.

Use:
    fence_event = threading.Event()
    hb = HeartbeatThread(run_id, dsn, fence_event)
    hb.start()
    try:
        ...do work...
        if fence_event.is_set():
            raise RunFencedError(...)
    finally:
        hb.stop()
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)


class RunFencedError(RuntimeError):
    """Run foi marcada como aborted por outro processo (heartbeat rowcount=0)."""


class HeartbeatThread(threading.Thread):
    """Daemon thread que atualiza etl_run_log.last_heartbeat a cada interval_s.

    Se etl_admin.heartbeat_run retornar FALSE (run foi fenced):
      - Setea fence_event (main thread checa periodicamente)
      - Para o loop e sai
    """

    def __init__(
        self,
        run_id,
        dsn: str,
        fence_event: threading.Event,
        interval_s: float = 30.0,
    ):
        super().__init__(daemon=True, name=f"heartbeat-{run_id}")
        self.run_id = run_id
        self.dsn = dsn
        self.fence_event = fence_event
        self.interval_s = interval_s
        self.stop_event = threading.Event()
        self._consecutive_failures = 0
        self.MAX_FAILURES = 3

    def stop(self, timeout: float = 5.0):
        self.stop_event.set()
        if self.is_alive():
            self.join(timeout=timeout)

    def run(self):
        # Conexão dedicada autocommit
        conn = None
        try:
            conn = psycopg2.connect(self.dsn)
            conn.autocommit = True

            while not self.stop_event.is_set():
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT etl_admin.heartbeat_run(%s)", (str(self.run_id),)
                        )
                        alive = cur.fetchone()[0]
                    if not alive:
                        logger.warning(
                            "heartbeat run %s returned FALSE — fenced", self.run_id
                        )
                        self.fence_event.set()
                        return
                    self._consecutive_failures = 0
                except psycopg2.Error as e:
                    self._consecutive_failures += 1
                    logger.warning(
                        "heartbeat error %s (consecutive=%d): %s",
                        self.run_id, self._consecutive_failures, e,
                    )
                    if self._consecutive_failures >= self.MAX_FAILURES:
                        logger.error(
                            "heartbeat for run %s: %d consecutive failures, fencing",
                            self.run_id, self._consecutive_failures,
                        )
                        self.fence_event.set()
                        return
                    # Reconectar em próxima iteração
                    try:
                        conn.close()
                    except Exception:
                        pass
                    try:
                        conn = psycopg2.connect(self.dsn)
                        conn.autocommit = True
                    except psycopg2.Error:
                        pass

                self.stop_event.wait(timeout=self.interval_s)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


class MasterWatchdog:
    """signal.alarm-based watchdog com max_runtime_s.

    Posix only (signal.alarm). Windows: noop (use só HeartbeatThread).
    """

    def __init__(self, max_runtime_s: int = 6 * 3600):
        self.max_runtime_s = max_runtime_s
        self._installed = False

    def __enter__(self):
        if hasattr(signal, "SIGALRM"):
            signal.alarm(self.max_runtime_s)
            self._installed = True
        return self

    def __exit__(self, *exc_info):
        if self._installed:
            signal.alarm(0)
