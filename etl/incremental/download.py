"""Download incremental via HTTP conditional GET (D15/D16).

HEAD probe → conditional GET com If-None-Match / If-Modified-Since.
Servidor responde 304 → arquivo local não é tocado, etl_download_log atualiza
last_checked_at.

Quando download bem-sucedido:
- sha256 do conteúdo computado streaming
- Se sha256 mudou vs etl_download_log.content_sha256 → invalidate_bucket_token

Resumable: download para `<dest>.partial`; rename atômico só quando completo.

Requests com User-Agent e timeout. Erros HTTP 5xx → marca failed; conditional
GET 304 → marca not_modified.
"""

from __future__ import annotations

import email.utils
import hashlib
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import db as etl_db

logger = logging.getLogger(__name__)

USER_AGENT = "govbr-cruza-dados/0.1 (+etl-incremental)"
DEFAULT_TIMEOUT = 600
CHUNK_SIZE = 1024 * 1024  # 1MB


@dataclass
class DownloadResult:
    """Resultado de um download attempt."""
    status: str                        # 'downloaded' | 'not_modified' | 'failed'
    content_changed: bool              # True se sha256 mudou (caller invalida)
    content_sha256: Optional[str]
    bytes_downloaded: int
    error: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_length: Optional[int] = None


def _read_existing_sha(
    govbr_conn,
    *,
    source: str,
    table: Optional[str],
    bucket_id: str,
    url: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Lê (etag, last_modified, content_sha256) do etl_download_log.

    Retorna (None, None, None) se nunca foi baixado.
    """
    with govbr_conn.cursor() as cur:
        cur.execute(
            """SELECT etag, last_modified, content_sha256
               FROM etl_download_log
               WHERE source = %s
                 AND table_name IS NOT DISTINCT FROM %s
                 AND bucket_id = %s
                 AND url = %s""",
            (source, table, bucket_id, url),
        )
        row = cur.fetchone()
        if row is None:
            return None, None, None
        return row


def conditional_download(
    *,
    govbr_conn,
    run_id: uuid.UUID,
    source: str,
    table: Optional[str],
    bucket_id: str,
    url: str,
    dest_path: Path,
    force_refetch: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> DownloadResult:
    """Download com conditional GET via etl_download_log.

    Retorna DownloadResult. Após success/304, caller deve usar
    `etl_db.upsert_download_log_done` ou `etl_db.upsert_download_log_check` para
    atualizar log; este método é puro (não escreve em DB).

    Caller deve checar `result.content_changed` e chamar `invalidate_bucket_token`
    se True.

    Args:
        govbr_conn: conn com SELECT em etl_download_log (pode ser etl_conn).
        force_refetch: se True, ignora etag/last_modified e re-baixa.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = dest_path.with_suffix(dest_path.suffix + ".partial")

    # Lê estado anterior
    if force_refetch:
        prev_etag = prev_lm = prev_sha = None
    else:
        prev_etag, prev_lm, prev_sha = _read_existing_sha(
            govbr_conn, source=source, table=table, bucket_id=bucket_id, url=url
        )

    # Build request
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    if not force_refetch:
        if prev_etag:
            headers["If-None-Match"] = prev_etag
        if prev_lm:
            headers["If-Modified-Since"] = prev_lm

    req = Request(url, headers=headers, method="GET")

    # Resumable: se .partial existe, tentar Range
    resume_from = 0
    if partial_path.exists() and not force_refetch:
        size = partial_path.stat().st_size
        if size > 0:
            resume_from = size
            req.add_header("Range", f"bytes={resume_from}-")

    try:
        with urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            new_etag = resp.headers.get("ETag")
            new_lm = resp.headers.get("Last-Modified")
            content_length = resp.headers.get("Content-Length")
            cl_int = int(content_length) if content_length else None

            # 304 só vem como HTTPError em urllib
            # 200/206 → leitura
            mode = "ab" if (status_code == 206 and resume_from > 0) else "wb"
            sha = hashlib.sha256()

            # Se mode='ab', reuse hash do partial
            if mode == "ab":
                with open(partial_path, "rb") as exist_f:
                    while True:
                        c = exist_f.read(CHUNK_SIZE)
                        if not c:
                            break
                        sha.update(c)

            bytes_dl = 0
            with open(partial_path, mode) as out_f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    sha.update(chunk)
                    bytes_dl += len(chunk)

            content_sha = sha.hexdigest()

            # Detect "Arquivo Sendo Processado" HTML page (server returns 200 OK
            # with HTML stub instead of CSV). Inspect the .partial file BEFORE
            # renaming to dest_path — otherwise we'd destroy the previously
            # cached good CSV when the server intermittently serves the stub.
            try:
                with open(partial_path, "rb") as fchk:
                    head = fchk.read(64)
                if head.lstrip().startswith(b"<!DOCTYPE") or head.lstrip().startswith(b"<html"):
                    logger.warning(
                        "server returned HTML placeholder for %s (likely 'Arquivo Sendo Processado'); "
                        "discarding new download, preserving any existing CSV",
                        partial_path.name,
                    )
                    partial_path.unlink()
                    return DownloadResult(
                        status="failed",
                        content_changed=False,
                        content_sha256=None,
                        bytes_downloaded=0,
                        error="server returned HTML placeholder (Arquivo Sendo Processado)",
                    )
            except FileNotFoundError:
                pass

            # Atomic rename .partial → final
            if dest_path.exists():
                dest_path.unlink()
            partial_path.rename(dest_path)

            content_changed = (prev_sha != content_sha)
            logger.info(
                "downloaded %s (%.1f MB, sha256=%s..., changed=%s)",
                dest_path.name, bytes_dl / 1e6, content_sha[:8], content_changed,
            )
            return DownloadResult(
                status="downloaded",
                content_changed=content_changed,
                content_sha256=content_sha,
                bytes_downloaded=bytes_dl,
                etag=new_etag,
                last_modified=new_lm,
                content_length=cl_int,
            )

    except HTTPError as e:
        if e.code == 304:
            logger.info("not_modified %s (304)", dest_path.name)
            return DownloadResult(
                status="not_modified",
                content_changed=False,
                content_sha256=prev_sha,
                bytes_downloaded=0,
            )
        msg = f"HTTPError {e.code}: {e.reason}"
        logger.warning("download %s failed: %s", url, msg)
        return DownloadResult(
            status="failed", content_changed=False, content_sha256=None,
            bytes_downloaded=0, error=msg,
        )
    except URLError as e:
        msg = f"URLError: {e!s}"
        logger.warning("download %s failed: %s", url, msg)
        return DownloadResult(
            status="failed", content_changed=False, content_sha256=None,
            bytes_downloaded=0, error=msg,
        )
    except Exception as e:
        logger.exception("download unexpected error")
        return DownloadResult(
            status="failed", content_changed=False, content_sha256=None,
            bytes_downloaded=0, error=str(e),
        )


def download_and_log(
    *,
    etl_conn,
    govbr_conn,
    run_id: uuid.UUID,
    source: str,
    table: Optional[str],
    bucket_id: str,
    url: str,
    dest_path: Path,
    force_refetch: bool = False,
) -> DownloadResult:
    """High-level: conditional_download + log + invalidate_bucket_token if changed.

    Args:
        etl_conn: conn com EXECUTE em etl_admin functions.
        govbr_conn: conn com SELECT em etl_download_log.
    """
    result = conditional_download(
        govbr_conn=govbr_conn,
        run_id=run_id,
        source=source,
        table=table,
        bucket_id=bucket_id,
        url=url,
        dest_path=dest_path,
        force_refetch=force_refetch,
    )

    # Update etl_download_log
    if result.status == "downloaded":
        try:
            etl_db.upsert_download_log_done(
                etl_conn,
                run_id=run_id,
                source=source,
                table=table,
                bucket_id=bucket_id,
                url=url,
                dest_path=str(dest_path),
                etag=result.etag,
                last_modified=result.last_modified,
                content_length=result.content_length or result.bytes_downloaded,
                content_sha256=result.content_sha256,
            )
            etl_conn.commit()
            # Se mudou, invalidate
            if result.content_changed and table is not None:
                etl_db.invalidate_bucket_token(
                    etl_conn,
                    run_id=run_id,
                    source=source,
                    table=table,
                    reason=f"content_sha256 changed for bucket {bucket_id}",
                )
                etl_conn.commit()
        except Exception as e:
            logger.warning("upsert_download_log_done failed: %s", e)
            etl_conn.rollback()
    elif result.status in ("not_modified", "failed"):
        try:
            etl_db.upsert_download_log_check(
                etl_conn,
                run_id=run_id,
                source=source,
                table=table,
                bucket_id=bucket_id,
                url=url,
                dest_path=str(dest_path),
                etag=None,
                last_modified=None,
                content_length=None,
                status=result.status,
            )
            etl_conn.commit()
        except Exception as e:
            logger.warning("upsert_download_log_check failed: %s", e)
            etl_conn.rollback()

    return result
