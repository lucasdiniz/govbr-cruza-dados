"""Sync mensal RFB (CNPJ): atualiza empresa/estabelecimento/simples/socio in-place.

## Por que existe

A RFB publica um snapshot COMPLETO por mes. A fase classica (etl/03_rfb.py)
so serve para a carga inicial: pula tabelas ja populadas e usa
`ON CONFLICT DO NOTHING`, entao mudancas de situacao cadastral, razao social,
empresas novas e socios que entram/saem nunca chegavam ao site.

O framework incremental (etl/incremental/) nao se aplica: a fonte eh snapshot
(nao append-only) e o sync precisa de UPDATE/DELETE, proibidos pelo P2.

## Como funciona (por tabela)

1. Baixa os ZIPs do mes (WebDAV RFB) um a um, com tamanho conferido contra o
   PROPFIND, extrai e carrega numa staging UNLOGGED tipada `_rfb_sync_<tabela>`.
   Cada CSV eh apagado assim que carregado (pico de disco = 1 arquivo + staging).
2. GUARDS (antes de qualquer escrita na tabela live):
   - staging nao pode ser menor que a live alem de `max_shrink_pct` (download
     truncado/incompleto apagaria metade da base);
   - linhas a remover nao podem passar de `max_delete_pct` da live.
   Guard violado -> aborta SEM tocar na live (exit 2).
3. Aplica o diff em 100 lotes por prefixo de cnpj_basico ('00'..'99'), cada lote
   uma transacao curta: DELETE (sumiu) -> UPDATE (mudou, IS DISTINCT FROM) ->
   INSERT (novo). Leitores nunca sao bloqueados (MVCC; so ROW EXCLUSIVE).
   - socio nao tem chave natural: identidade = md5 de SOCIO_IDENTITY
     (etl/rfb_common.py). Vinculos que sairam sao MOVIDOS para socio_historico.
   - estabelecimentos inseridos/removidos vao para rfb_sync_estab_delta
     (re-ligacao direcionada de cnpj_basico nas tabelas PB).
4. Tabelas de dominio (dom_cnae etc.) sao substituidas numa transacao.
5. Refresh pos-sync (refresh_post_incremental.refresh_for_rfb): re-liga
   cnpj_basico nas tabelas PB + REFRESH das MVs L1 -> L2. O mes so eh marcado
   `success` em rfb_sync_log depois do refresh.

Idempotente: rodar de novo o mesmo mes converge (diff vazio). Mes ja
sincronizado com sucesso eh pulado (a menos de --force). Mes anterior ao
ultimo sucesso eh recusado (nunca regride a base). Advisory lock impede dois
syncs simultaneos.

## CLI

    python -m etl.rfb_sync                      # mes mais recente publicado
    python -m etl.rfb_sync --month 2026-09
    python -m etl.rfb_sync --month 2026-09 --force   # re-sync + ignora guards

Exit codes: 0 = sincronizado ou ja estava em dia; 1 = erro; 2 = guard/pre-check
recusou (nada foi alterado na tabela que disparou o guard).
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import re
import shutil
import socket
import sys
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import psycopg2
import psycopg2.extras

from etl.rfb_common import (
    RFB_TABLES,
    SOCIO,
    SOCIO_ATTRS,
    SOCIO_IDENTITY,
    RfbTable,
    socio_identity_sql,
    staging_copy,
)

logger = logging.getLogger("rfb_sync")

WEBDAV_BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
# Token PUBLICO do share Nextcloud da RFB (mesmo de etl/00_download.py).
_WEBDAV_AUTH = "Basic " + base64.b64encode(b"YggdBLfdninEJX9:").decode()
_UA = "transparenciapb-rfb-sync/1.0"

SYNC_ORDER = ("empresa", "estabelecimento", "simples", "socio")

# zip -> (tabela, colunas). Espelha etl/02_dominio.py.
DOMAIN_FILES = {
    "Cnaes": "dom_cnae",
    "Municipios": "dom_municipio",
    "Naturezas": "dom_natureza_juridica",
    "Paises": "dom_pais",
    "Qualificacoes": "dom_qualificacao",
    "Motivos": "dom_motivo",
}

# Limites conservadores calibrados com publicacoes reais (ver PR). A primeira
# execucao em prod cobre varios meses acumulados — por isso folga acima do
# observado mes-a-mes. Ajustar via CLI se um guard disparar legitimamente.
DEFAULT_MAX_DELETE_PCT = {"empresa": 1.0, "estabelecimento": 1.0, "simples": 2.0, "socio": 10.0}
DEFAULT_MAX_SHRINK_PCT = 1.0
DEFAULT_MIN_FREE_GB = 40.0

ADVISORY_LOCK_KEY = 4517_0031  # arbitrario; unico para o rfb_sync
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_N_BATCHES = 100


class GuardError(RuntimeError):
    """Pre-check recusou o sync (nada alterado na tabela em questao)."""


# ──────────────────────────────────────────────────────────────────────────
# WebDAV RFB
# ──────────────────────────────────────────────────────────────────────────

@contextmanager
def _ipv4_only():
    """arquivos.receitafederal.gov.br nao responde em IPv6."""
    orig = socket.getaddrinfo
    socket.getaddrinfo = lambda *a, **kw: [r for r in orig(*a, **kw) if r[0] == socket.AF_INET]
    try:
        yield
    finally:
        socket.getaddrinfo = orig


def _propfind(path: str) -> list[tuple[str, int | None]]:
    """Lista (nome, tamanho) dos itens de um diretorio WebDAV (Depth: 1)."""
    url = f"{WEBDAV_BASE}/{path.strip('/')}/" if path.strip("/") else f"{WEBDAV_BASE}/"
    req = Request(url, method="PROPFIND", headers={
        "Depth": "1", "Authorization": _WEBDAV_AUTH, "User-Agent": _UA,
    })
    with _ipv4_only(), urlopen(req, timeout=120) as resp:
        body = resp.read()
    ns = {"d": "DAV:"}
    out = []
    for r in ElementTree.fromstring(body).findall("d:response", ns):
        href = unquote(r.findtext("d:href", default="", namespaces=ns)).rstrip("/")
        name = href.rsplit("/", 1)[-1]
        size_txt = r.findtext(".//d:getcontentlength", default=None, namespaces=ns)
        out.append((name, int(size_txt) if size_txt else None))
    return out


def list_months() -> list[str]:
    return sorted(n for n, _ in _propfind("") if _MONTH_RE.match(n))


def list_files(month: str) -> dict[str, int]:
    return {n: s for n, s in _propfind(month) if n.endswith(".zip") and s is not None}


def expected_zips(tables: tuple[str, ...]) -> list[str]:
    names = [f"{f}.zip" for t in tables for f in RFB_TABLES[t].file_names()]
    return names + [f"{f}.zip" for f in DOMAIN_FILES]


def resolve_month(arg: str) -> str:
    if arg == "latest":
        months = list_months()
        if not months:
            raise RuntimeError("nenhum mes publicado encontrado no WebDAV RFB")
        return months[-1]
    if not _MONTH_RE.match(arg):
        raise ValueError(f"--month invalido: {arg!r} (use 'latest' ou YYYY-MM)")
    return arg


def download_zip(month: str, name: str, expected_size: int, dest_dir: Path, retries: int = 3) -> Path:
    """Baixa {month}/{name} conferindo o tamanho exato (download truncado = erro)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size == expected_size:
        return dest
    part = dest.with_name(dest.name + ".part")
    url = f"{WEBDAV_BASE}/{month}/{name}"
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            req = Request(url, headers={"Authorization": _WEBDAV_AUTH, "User-Agent": _UA})
            with _ipv4_only(), urlopen(req, timeout=300) as resp, open(part, "wb") as f:
                shutil.copyfileobj(resp, f, length=4 * 1024 * 1024)
            got = part.stat().st_size
            if got != expected_size:
                raise IOError(f"{name}: tamanho {got} != esperado {expected_size}")
            part.replace(dest)
            logger.info("baixado %s/%s (%.1f MB em %.0fs)", month, name, got / 1e6, time.time() - t0)
            return dest
        except (HTTPError, URLError, OSError) as e:
            last_err = e
            part.unlink(missing_ok=True)
            logger.warning("download %s tentativa %d/%d falhou: %s", name, attempt, retries, e)
            time.sleep(10 * attempt)
    raise RuntimeError(f"download de {month}/{name} falhou apos {retries} tentativas: {last_err}")


def extract_single(zip_path: Path, dest: Path) -> Path:
    """Extrai o unico membro do ZIP para `dest` (nome interno da RFB varia por mes).

    Leitura completa valida o CRC — ZIP corrompido levanta BadZipFile.
    """
    with zipfile.ZipFile(zip_path) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        if len(members) != 1:
            raise RuntimeError(f"{zip_path.name}: esperado 1 arquivo, encontrado {len(members)}")
        with z.open(members[0]) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out, length=4 * 1024 * 1024)
    zip_path.unlink()
    return dest


# ──────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────

def _exec(conn, sql: str, params=None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def _scalar(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def apply_schema(conn) -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / "45_rfb_sync.sql"
    _exec(conn, path.read_text(encoding="utf-8"))
    conn.commit()


def column_types(conn, table: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname, format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
            """,
            (table,),
        )
        return dict(cur.fetchall())


def _ensure_socio_norm_column(conn) -> None:
    """Garante socio.cpf_cnpj_norm (criada pela fase 17). Em prod ja existe.

    Checa o catalogo ANTES: `ALTER ... ADD COLUMN IF NOT EXISTS` pega
    ACCESS EXCLUSIVE mesmo quando a coluna ja existe e enfileiraria leitores
    do site atras de qualquer query longa.
    """
    if "cpf_cnpj_norm" not in column_types(conn, "socio"):
        _exec(conn, "ALTER TABLE socio ADD COLUMN cpf_cnpj_norm TEXT")
        conn.commit()


def _batch_bounds() -> list[tuple[str, str | None]]:
    out = []
    for i in range(_N_BATCHES):
        lo = f"{i:02d}"
        hi = f"{i + 1:02d}" if i + 1 < _N_BATCHES else None
        out.append((lo, hi))
    return out


def _range_pred(alias: str, lo: str, hi: str | None) -> str:
    pred = f"{alias}.cnpj_basico >= '{lo}'"
    if hi is not None:
        pred += f" AND {alias}.cnpj_basico < '{hi}'"
    return pred


def _staging_name(spec: RfbTable) -> str:
    return f"_rfb_sync_{spec.table}"


# ──────────────────────────────────────────────────────────────────────────
# Staging
# ──────────────────────────────────────────────────────────────────────────

def build_staging(conn, spec: RfbTable, csv_files: Iterator[Path]) -> int:
    """Carrega todos os CSVs da tabela numa staging tipada (mesmos tipos da live).

    Chave duplicada no snapshot: primeira ocorrencia vence (mesma semantica do
    ON CONFLICT DO NOTHING da carga classica).
    """
    stg = _staging_name(spec)
    raw = f"{stg}_raw"
    types = column_types(conn, spec.table)
    missing = [c for c in spec.columns if c not in types]
    if missing:
        raise RuntimeError(f"{spec.table}: colunas ausentes na tabela live: {missing}")

    col_defs = [f"{c} {types[c]}" for c in spec.columns]
    if spec is SOCIO:
        col_defs.append("_id TEXT NOT NULL")
        col_defs.append("UNIQUE (cnpj_basico, _id)")
    else:
        col_defs.append(f"PRIMARY KEY ({', '.join(spec.key)})")
    _exec(conn, f"DROP TABLE IF EXISTS {stg}")
    _exec(conn, f"CREATE UNLOGGED TABLE {stg} ({', '.join(col_defs)})")
    conn.commit()

    cols = ", ".join(spec.columns)
    if spec is SOCIO:
        # Identidade calculada com os MESMOS tipos da live (cast explicito),
        # senao ROW(...)::text divergiria entre staging e live.
        typed = ", ".join(f"x.{c}::{types[c]}" for c in SOCIO_IDENTITY)
        insert_sql = (
            f"INSERT INTO {stg} ({cols}, _id)\n"
            f"SELECT x.*, md5(ROW({typed})::text) FROM (\n{spec.select_sql(raw)}\n) x\n"
            "ON CONFLICT DO NOTHING"
        )
    else:
        insert_sql = f"INSERT INTO {stg} ({cols})\n{spec.select_sql(raw)}\nON CONFLICT DO NOTHING"

    for csv_path in csv_files:
        t0 = time.time()
        staging_copy(conn, raw, spec.n_cols, csv_path)
        n = _exec(conn, insert_sql)
        _exec(conn, f"DROP TABLE IF EXISTS {raw}")
        conn.commit()
        csv_path.unlink(missing_ok=True)
        logger.info("staging %s <- %s: %d linhas (%.0fs)", spec.table, csv_path.name, n, time.time() - t0)

    _exec(conn, f"ANALYZE {stg}")
    conn.commit()
    return int(_scalar(conn, f"SELECT COUNT(*) FROM {stg}"))


# ──────────────────────────────────────────────────────────────────────────
# Diff
# ──────────────────────────────────────────────────────────────────────────

def _key_eq(spec: RfbTable, a: str, b: str) -> str:
    return " AND ".join(f"{a}.{k} = {b}.{k}" for k in spec.key)


def _socio_match(t: str, s: str) -> str:
    return f"{s}.cnpj_basico = {t}.cnpj_basico AND {s}._id = {socio_identity_sql(t)}"


def plan_table(conn, spec: RfbTable, staging_rows: int) -> dict:
    """Conta linhas a remover (anti-join live -> staging) para os guards."""
    stg = _staging_name(spec)
    live = int(_scalar(conn, f"SELECT COUNT(*) FROM {spec.table}"))
    if spec is SOCIO:
        match = _socio_match("t", "s")
    else:
        match = _key_eq(spec, "s", "t")
    to_delete = int(_scalar(
        conn,
        f"SELECT COUNT(*) FROM {spec.table} t WHERE NOT EXISTS (SELECT 1 FROM {stg} s WHERE {match})",
    ))
    conn.commit()
    return {"live_antes": live, "staging": staging_rows, "a_remover": to_delete}


def check_guards(spec: RfbTable, plan: dict, max_delete_pct: float, max_shrink_pct: float) -> None:
    live, stg, rem = plan["live_antes"], plan["staging"], plan["a_remover"]
    if stg == 0:
        raise GuardError(f"{spec.table}: snapshot vazio — download/parse falhou")
    if live == 0:
        return  # carga inicial via sync: nada a proteger
    if stg < live * (1 - max_shrink_pct / 100):
        raise GuardError(
            f"{spec.table}: snapshot com {stg:,} linhas < live {live:,} - {max_shrink_pct}% "
            "(publicacao incompleta ou download truncado?)"
        )
    if rem > live * max_delete_pct / 100:
        raise GuardError(
            f"{spec.table}: {rem:,} linhas a remover = {100 * rem / live:.2f}% da live "
            f"(limite {max_delete_pct}%)"
        )


def apply_keyed(conn, spec: RfbTable, month: str) -> dict:
    stg = _staging_name(spec)
    data_cols = [c for c in spec.columns if c not in spec.key]
    t_cols = ", ".join(f"t.{c}" for c in data_cols)
    s_cols = ", ".join(f"s.{c}" for c in data_cols)
    all_cols = ", ".join(spec.columns)
    s_all = ", ".join(f"s.{c}" for c in spec.columns)
    is_estab = spec.table == "estabelecimento"
    totals = {"removidas": 0, "atualizadas": 0, "inseridas": 0}

    if is_estab:
        _exec(conn, "DELETE FROM rfb_sync_estab_delta")
        conn.commit()

    for lo, hi in _batch_bounds():
        rt, rs = _range_pred("t", lo, hi), _range_pred("s", lo, hi)
        delete_sql = (
            f"DELETE FROM {spec.table} t WHERE {rt} "
            f"AND NOT EXISTS (SELECT 1 FROM {stg} s WHERE {_key_eq(spec, 's', 't')})"
        )
        insert_sql = (
            f"INSERT INTO {spec.table} ({all_cols}) SELECT {s_all} FROM {stg} s WHERE {rs} "
            f"AND NOT EXISTS (SELECT 1 FROM {spec.table} t WHERE {_key_eq(spec, 't', 's')})"
        )
        if is_estab:
            delete_sql = (
                f"WITH d AS ({delete_sql} RETURNING t.cnpj_completo) "
                "INSERT INTO rfb_sync_estab_delta (cnpj_completo, mudanca, rfb_mes) "
                f"SELECT cnpj_completo, 'removido', %(mes)s FROM d"
            )
            insert_sql = (
                f"WITH i AS ({insert_sql} RETURNING cnpj_completo) "
                "INSERT INTO rfb_sync_estab_delta (cnpj_completo, mudanca, rfb_mes) "
                f"SELECT cnpj_completo, 'inserido', %(mes)s FROM i"
            )
        totals["removidas"] += _exec(conn, delete_sql, {"mes": month})
        totals["atualizadas"] += _exec(
            conn,
            f"UPDATE {spec.table} t SET ({', '.join(data_cols)}) = ROW({s_cols}) "
            f"FROM {stg} s WHERE {_key_eq(spec, 't', 's')} AND {rt} "
            f"AND ({t_cols}) IS DISTINCT FROM ({s_cols})",
        )
        totals["inseridas"] += _exec(conn, insert_sql, {"mes": month})
        conn.commit()
    return totals


def apply_socio(conn, month: str) -> dict:
    stg = _staging_name(SOCIO)
    cols = list(SOCIO.columns)
    t_attrs = ", ".join(f"t.{c}" for c in SOCIO_ATTRS)
    s_attrs = ", ".join(f"s.{c}" for c in SOCIO_ATTRS)
    hist_cols = ", ".join(["id", *cols, "cpf_cnpj_norm"])
    totals = {"movidas_historico": 0, "atualizadas": 0, "inseridas": 0}

    for lo, hi in _batch_bounds():
        rt, rs = _range_pred("t", lo, hi), _range_pred("s", lo, hi)
        totals["movidas_historico"] += _exec(
            conn,
            f"WITH gone AS (DELETE FROM socio t WHERE {rt} "
            f"AND NOT EXISTS (SELECT 1 FROM {stg} s WHERE {_socio_match('t', 's')}) "
            f"RETURNING t.*) "
            f"INSERT INTO socio_historico ({hist_cols}, removido_em, rfb_mes_removido) "
            f"SELECT {hist_cols}, CURRENT_DATE, %(mes)s FROM gone",
            {"mes": month},
        )
        totals["atualizadas"] += _exec(
            conn,
            f"UPDATE socio t SET ({', '.join(SOCIO_ATTRS)}) = ROW({s_attrs}) "
            f"FROM {stg} s WHERE {rt} AND {_socio_match('t', 's')} "
            f"AND ({t_attrs}) IS DISTINCT FROM ({s_attrs})",
        )
        totals["inseridas"] += _exec(
            conn,
            f"INSERT INTO socio ({', '.join(cols)}, cpf_cnpj_norm) "
            f"SELECT {', '.join('s.' + c for c in cols)}, "
            f"REGEXP_REPLACE(s.cpf_cnpj_socio, '[^0-9]', '', 'g') "
            f"FROM {stg} s WHERE {rs} "
            f"AND NOT EXISTS (SELECT 1 FROM socio t WHERE {_socio_match('t', 's')})",
        )
        conn.commit()
    return totals


def sync_domain_tables(conn, month: str, files: dict[str, int], work_dir: Path) -> dict:
    """Substitui cada dom_* numa transacao (DELETE+INSERT: leitores veem antes OU depois)."""
    from etl.utils import parse_csv_line, safe_strip

    out = {}
    for prefix, table in DOMAIN_FILES.items():
        z = download_zip(month, f"{prefix}.zip", files[f"{prefix}.zip"], work_dir)
        csv_path = extract_single(z, work_dir / f"{prefix}.csv")
        rows = []
        with open(csv_path, encoding="latin-1", errors="replace") as f:
            for line in f:
                fields = parse_csv_line(line, delimiter=";")
                if len(fields) >= 2:
                    codigo, descricao = safe_strip(fields[0]), safe_strip(fields[1])
                    if codigo:
                        rows.append((codigo, descricao))
        csv_path.unlink(missing_ok=True)
        before = int(_scalar(conn, f"SELECT COUNT(*) FROM {table}"))
        if not rows or len(rows) < before * 0.9:
            raise GuardError(f"{table}: {len(rows)} linhas no arquivo vs {before} na base")
        _exec(conn, f"DELETE FROM {table}")
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur, f"INSERT INTO {table} (codigo, descricao) VALUES %s ON CONFLICT (codigo) DO NOTHING",
                rows, page_size=1000,
            )
        conn.commit()
        out[table] = {"antes": before, "depois": len(rows)}
    return out


# ──────────────────────────────────────────────────────────────────────────
# Orquestracao
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class SyncOptions:
    month: str = "latest"
    force: bool = False
    tables: tuple[str, ...] = SYNC_ORDER
    work_dir: Path | None = None
    min_free_gb: float = DEFAULT_MIN_FREE_GB
    max_delete_pct: dict | None = None
    max_shrink_pct: float = DEFAULT_MAX_SHRINK_PCT
    refresh: bool = True


def _csv_iter(month: str, spec: RfbTable, files: dict[str, int], work_dir: Path) -> Iterator[Path]:
    """Baixa+extrai 1 arquivo por vez (pico de disco = 1 CSV)."""
    for name in spec.file_names():
        z = download_zip(month, f"{name}.zip", files[f"{name}.zip"], work_dir)
        yield extract_single(z, work_dir / f"{name}.csv")


def _last_success(conn) -> str | None:
    return _scalar(
        conn,
        "SELECT MAX(rfb_mes) FROM rfb_sync_log "
        "WHERE status = 'success' AND NOT (stats ? 'tabelas_parciais')",
    )


def _update_log(conn, log_id: int, status: str, stats: dict, erro: str | None = None) -> None:
    final = status != "running"
    _exec(
        conn,
        "UPDATE rfb_sync_log SET status = %s, stats = %s::jsonb, erro = %s"
        + (", finalizado_em = NOW()" if final else "")
        + " WHERE id = %s",
        (status, json.dumps(stats, default=str), erro, log_id),
    )
    conn.commit()


def run_sync(dsn: str, opts: SyncOptions) -> int:
    from etl.config import DATA_DIR

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    _exec(conn, "SET datestyle = 'ISO, YMD'")
    conn.commit()

    if not _scalar(conn, "SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,)):
        logger.error("outro rfb_sync em andamento (advisory lock ocupado)")
        conn.close()
        return 1
    conn.commit()

    work_root = opts.work_dir or (DATA_DIR / "rfb_sync")
    log_id = None
    stats: dict = {}
    try:
        apply_schema(conn)
        month = resolve_month(opts.month)
        last = _last_success(conn)
        logger.info("mes alvo %s; ultimo sync completo: %s", month, last)
        if last and not opts.force:
            if last == month:
                logger.info("RFB %s ja sincronizado — nada a fazer", month)
                print("RFB_SYNC_RESULT=skipped")
                return 0
            if last > month:
                raise GuardError(f"mes {month} anterior ao ultimo sync ({last}) — regrediria a base")

        files = list_files(month)
        missing = [n for n in expected_zips(opts.tables) if n not in files]
        if missing:
            raise GuardError(f"publicacao {month} incompleta no WebDAV, faltam: {missing}")

        # Sobras de execucoes anteriores (outros meses ou falha no meio).
        if work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)
        work_dir = work_root / month
        work_dir.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(work_dir).free / 1e9
        if free_gb < opts.min_free_gb:
            raise GuardError(f"disco livre {free_gb:.0f} GB < minimo {opts.min_free_gb:.0f} GB")

        log_id = _scalar(
            conn, "INSERT INTO rfb_sync_log (rfb_mes, status) VALUES (%s, 'running') RETURNING id", (month,)
        )
        conn.commit()
        if set(opts.tables) != set(SYNC_ORDER):
            stats["tabelas_parciais"] = list(opts.tables)

        if "socio" in opts.tables:
            _ensure_socio_norm_column(conn)

        limits = {**DEFAULT_MAX_DELETE_PCT, **(opts.max_delete_pct or {})}
        for table in SYNC_ORDER:
            if table not in opts.tables:
                continue
            spec = RFB_TABLES[table]
            t0 = time.time()
            n_stg = build_staging(conn, spec, _csv_iter(month, spec, files, work_dir))
            plan = plan_table(conn, spec, n_stg)
            stats[table] = plan
            _update_log(conn, log_id, "running", stats)
            logger.info("%s: plano %s", table, plan)
            if not opts.force:
                check_guards(spec, plan, limits[table], opts.max_shrink_pct)

            applied = apply_socio(conn, month) if spec is SOCIO else apply_keyed(conn, spec, month)
            _exec(conn, f"DROP TABLE IF EXISTS {_staging_name(spec)}")
            conn.commit()
            conn.autocommit = True
            _exec(conn, f"ANALYZE {spec.table}")
            conn.autocommit = False
            plan.update(applied)
            plan["live_depois"] = int(_scalar(conn, f"SELECT COUNT(*) FROM {spec.table}"))
            plan["segundos"] = round(time.time() - t0)
            conn.commit()
            _update_log(conn, log_id, "running", stats)
            logger.info("%s: aplicado %s", table, plan)

        if not stats.get("tabelas_parciais"):
            stats["dominio"] = sync_domain_tables(conn, month, files, work_dir)
            _update_log(conn, log_id, "running", stats)

        if opts.refresh:
            from etl.refresh_post_incremental import refresh_for_rfb
            t0 = time.time()
            refresh_for_rfb(conn)
            stats["refresh_segundos"] = round(time.time() - t0)

        _update_log(conn, log_id, "success", stats)
        logger.info("RFB %s sincronizado: %s", month, json.dumps(stats, default=str))
        print("RFB_SYNC_RESULT=synced")
        return 0
    except GuardError as e:
        logger.error("GUARD: %s", e)
        if log_id is not None:
            conn.rollback()
            _update_log(conn, log_id, "aborted", stats, str(e))
        return 2
    except Exception as e:
        logger.exception("rfb_sync falhou")
        if log_id is not None:
            try:
                conn.rollback()
                _update_log(conn, log_id, "failed", stats, str(e)[:2000])
            except Exception:
                logger.exception("falha ao registrar erro em rfb_sync_log")
        return 1
    finally:
        try:
            conn.rollback()
            conn.autocommit = True
            for t in SYNC_ORDER:
                stg = _staging_name(RFB_TABLES[t])
                _exec(conn, f"DROP TABLE IF EXISTS {stg}_raw")
                _exec(conn, f"DROP TABLE IF EXISTS {stg}")
            _exec(conn, "SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        except Exception:
            logger.exception("cleanup de staging falhou")
        conn.close()
        shutil.rmtree(work_root, ignore_errors=True)


def _parse_pct_overrides(raw: list[str] | None) -> dict:
    out = {}
    for item in raw or []:
        table, _, pct = item.partition("=")
        if table not in RFB_TABLES or not pct:
            raise ValueError(f"--max-delete-pct invalido: {item!r} (use tabela=PCT)")
        out[table] = float(pct)
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Sync mensal RFB (diff in-place).")
    p.add_argument("--month", default="latest", help="'latest' (default) ou YYYY-MM")
    p.add_argument("--force", action="store_true",
                   help="re-sincroniza mes ja feito/anterior e IGNORA guards de remocao/encolhimento")
    p.add_argument("--tables", default=",".join(SYNC_ORDER),
                   help="subconjunto CSV (execucao parcial nao marca o mes como completo)")
    p.add_argument("--max-delete-pct", action="append", metavar="TABELA=PCT",
                   help="sobrescreve limite de remocao (ex: socio=15). Repetivel.")
    p.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    p.add_argument("--work-dir", type=Path, default=None)
    p.add_argument("--no-refresh", action="store_true", help="nao roda refresh de MVs (testes)")
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)

    tables = tuple(t.strip() for t in args.tables.split(",") if t.strip())
    unknown = [t for t in tables if t not in RFB_TABLES]
    if unknown:
        p.error(f"tabelas desconhecidas: {unknown}")
    if args.dsn is None:
        from etl.config import DSN
        args.dsn = DSN

    return run_sync(args.dsn, SyncOptions(
        month=args.month,
        force=args.force,
        tables=tables,
        work_dir=args.work_dir,
        min_free_gb=args.min_free_gb,
        max_delete_pct=_parse_pct_overrides(args.max_delete_pct),
        refresh=not args.no_refresh,
    ))


if __name__ == "__main__":
    sys.exit(main())
