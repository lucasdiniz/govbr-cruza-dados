"""Sync mensal RFB (CNPJ): atualiza empresa/estabelecimento/simples/socio in-place.

## Por que existe

A RFB publica um snapshot COMPLETO por mes. A fase classica (etl/03_rfb.py)
so serve para a carga inicial: pula tabelas ja populadas e usa
`ON CONFLICT DO NOTHING`, entao mudancas de situacao cadastral, razao social,
empresas novas e socios que entram/saem nunca chegavam ao site.

O framework incremental (etl/incremental/) nao se aplica: a fonte eh snapshot
(nao append-only) e o sync precisa de UPDATE/DELETE, proibidos pelo P2.

## Como funciona

1. Baixa os ZIPs do mes (WebDAV RFB) um a um, com tamanho conferido contra o
   HEAD (Content-Length), extrai e carrega numa staging UNLOGGED tipada `_rfb_sync_<tabela>`.
   Cada CSV é apagado após a carga; as quatro stagings coexistem.
2. Pré-valida as quatro tabelas e os domínios antes do primeiro lote:
   - staging nao pode ser menor que a live alem de `max_shrink_pct` (download
     truncado/incompleto apagaria metade da base);
   - linhas a remover nao podem passar de `max_delete_pct` da live.
   - identidade múltipla em socio ou ocorrência descartada sem espelho
     idêntico na origem e na staging não têm tolerância.
   Guard violado -> aborta SEM escrita de negócio (exit 2).
3. Aplica o diff em 100 lotes por prefixo de cnpj_basico ('00'..'99'), cada lote
   uma transacao curta: DELETE (sumiu) -> UPDATE (mudou, IS DISTINCT FROM) ->
   INSERT (novo). Leitores nunca sao bloqueados (MVCC; so ROW EXCLUSIVE).
   - socio nao tem chave natural: identidade = md5 de SOCIO_IDENTITY
     (etl/rfb_common.py). Vinculos que sairam sao MOVIDOS para socio_historico.
   - estabelecimentos inseridos/removidos vao para rfb_sync_estab_delta
     (re-ligacao direcionada de cnpj_basico nas tabelas PB). O delta acumula
     entre tentativas e so eh limpo depois do relink (re-run seguro).
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

Saídas: 0 = integral ou já sincronizado; 1 = erro (pode haver lotes aplicados);
2 = recusa em pré-validação; 3 = escopo aplicado sem publicação (--tables
parcial ou --no-refresh). Ver limites de liberação em docs/etl-guide.md.
"""
from __future__ import annotations

import argparse
import base64
import json
import hashlib
import logging
import re
import shutil
import socket
import sys
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

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
    """Pré-validação recusou o sync antes das escritas de negócio."""


class DivergenciaParidade(RuntimeError):
    """Pós-condição violada; mensagem contém somente diagnósticos agregados."""


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


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):  # 3xx = nao eh o arquivo
        return None


def head_file(month: str, name: str) -> tuple[int, datetime] | None:
    """Metadados do ZIP; apenas 404/410 significam arquivo ausente."""
    req = Request(f"{WEBDAV_BASE}/{month}/{name}", method="HEAD",
                  headers={"Authorization": _WEBDAV_AUTH, "User-Agent": _UA})
    opener = build_opener(_NoRedirect)
    for attempt in range(1, 4):
        try:
            with _ipv4_only(), opener.open(req, timeout=60) as resp:
                tipo = resp.headers.get("Content-Type", "").partition(";")[0].strip().lower()
                size = resp.headers.get("Content-Length", "")
                if (resp.status != 200 or tipo not in {
                    "application/zip", "application/x-zip-compressed", "application/octet-stream"
                } or not size.isascii() or not size.isdigit() or int(size) <= 0):
                    raise ValueError(f"metadados inesperados: HTTP {resp.status}, tipo={tipo!r}, tamanho={size!r}")
                try:
                    alterado = parsedate_to_datetime(resp.headers.get("Last-Modified", ""))
                    if alterado.tzinfo is None:
                        raise ValueError("data sem fuso")
                except (ValueError, TypeError, OverflowError) as e:
                    raise ValueError("Last-Modified ausente/invalido") from e
                return int(size), alterado
        except HTTPError as e:
            if e.code in (404, 410):
                return None
            err = e
        except (URLError, OSError, HTTPException, ValueError) as e:
            err = e
        logger.warning("HEAD %s/%s tentativa %d falhou: %s", month, name, attempt, err)
        if attempt < 3:
            time.sleep(5 * attempt)
    raise RuntimeError(f"HEAD {month}/{name} falhou 3x: {err}") from err


def _candidate_months(n: int = 4) -> list[str]:
    from datetime import date

    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def list_months() -> list[str]:
    """Meses publicados entre os ultimos 4 (sonda Cnaes.zip, o menor arquivo)."""
    return sorted(mo for mo in _candidate_months() if head_file(mo, "Cnaes.zip"))


def list_files(month: str) -> dict[str, int]:
    """{zip: tamanho} dos arquivos ESPERADOS presentes no mes (via HEAD)."""
    out = {}
    for name in expected_zips(SYNC_ORDER):
        info = head_file(month, name)
        if info:
            out[name] = info[0]
    return out


def expected_zips(tables: tuple[str, ...]) -> list[str]:
    names = [f"{f}.zip" for t in tables for f in RFB_TABLES[t].file_names()]
    return names + [f"{f}.zip" for f in DOMAIN_FILES]


def resolve_month(arg: str) -> str:
    if arg == "latest":
        months = list_months()
        for mo in reversed(months):  # mais recente COMPLETO
            if len(list_files(mo)) == len(expected_zips(SYNC_ORDER)):
                return mo
        raise RuntimeError(f"nenhum mes completo publicado no WebDAV RFB (sondados: {months})")
    if not _MONTH_RE.match(arg):
        raise ValueError(f"--month invalido: {arg!r} (use 'latest' ou YYYY-MM)")
    return arg


def download_zip(month: str, name: str, expected_size: int, dest_dir: Path, retries: int = 8) -> Path:
    """Baixa {month}/{name} conferindo o tamanho exato (download truncado = erro).

    Retomavel: o servidor RFB derruba conexoes longas (reset no meio de
    arquivos de GBs); cada nova tentativa continua do byte onde parou via
    `Range` (206). Se o servidor ignorar o Range (200), recomeca do zero.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size == expected_size:
        return dest
    part = dest.with_name(dest.name + ".part")
    part.unlink(missing_ok=True)
    url = f"{WEBDAV_BASE}/{month}/{name}"
    last_err: Exception | None = None
    t0 = time.time()
    for attempt in range(1, retries + 1):
        have = part.stat().st_size if part.exists() else 0
        if have > expected_size:
            part.unlink()
            have = 0
        headers = {"Authorization": _WEBDAV_AUTH, "User-Agent": _UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            req = Request(url, headers=headers)
            with _ipv4_only(), urlopen(req, timeout=300) as resp:
                mode = "ab" if (have and resp.status == 206) else "wb"
                with open(part, mode) as f:
                    shutil.copyfileobj(resp, f, length=4 * 1024 * 1024)
            got = part.stat().st_size
            if got != expected_size:
                raise IOError(f"{name}: tamanho {got} != esperado {expected_size}")
            part.replace(dest)
            logger.info("baixado %s/%s (%.1f MB em %.0fs, %d tentativa(s))",
                        month, name, got / 1e6, time.time() - t0, attempt)
            return dest
        except HTTPError as e:
            last_err = e
            if e.code == 416:  # Range invalido: recomeca
                part.unlink(missing_ok=True)
        except (URLError, OSError) as e:
            last_err = e
        logger.warning("download %s tentativa %d/%d falhou (%s bytes ate aqui): %s",
                       name, attempt, retries,
                       part.stat().st_size if part.exists() else 0, last_err)
        time.sleep(min(10 * attempt, 60))
    part.unlink(missing_ok=True)
    raise RuntimeError(f"download de {month}/{name} falhou apos {retries} tentativas: {last_err}")


def extract_single(zip_path: Path, dest: Path, manifesto: dict) -> Path:
    """Extrai o unico membro do ZIP para `dest` (nome interno da RFB varia por mes).

    Leitura completa valida o CRC — ZIP corrompido levanta BadZipFile.
    """
    sha_zip, sha_csv = hashlib.sha256(), hashlib.sha256()
    with zip_path.open("rb") as fonte:
        for bloco in iter(lambda: fonte.read(4 * 1024 * 1024), b""):
            sha_zip.update(bloco)
    with zipfile.ZipFile(zip_path) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        if len(members) != 1:
            raise RuntimeError(f"{zip_path.name}: esperado 1 arquivo, encontrado {len(members)}")
        with z.open(members[0]) as src, open(dest, "wb") as out:
            for bloco in iter(lambda: src.read(4 * 1024 * 1024), b""):
                sha_csv.update(bloco)
                out.write(bloco)
    manifesto[zip_path.name] = {"zip_sha256": sha_zip.hexdigest(), "csv_sha256": sha_csv.hexdigest(),
                                "zip_bytes": zip_path.stat().st_size, "csv_bytes": dest.stat().st_size}
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


def not_null_columns(conn, table: str) -> set[str]:
    """Colunas NOT NULL (sem default gerado) da tabela live."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname FROM pg_attribute a
            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
              AND a.attnotnull AND a.attgenerated = ''
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def _required_cols(conn, spec: RfbTable) -> list[str]:
    """Colunas de dados (fora da chave) NOT NULL na live."""
    nn = not_null_columns(conn, spec.table)
    return [c for c in spec.columns if c in nn and c not in spec.key]


def _incomplete_pred(alias: str, cols: list[str]) -> str:
    """Linha do snapshot que violaria NOT NULL da live (registro incompleto da
    RFB — ex.: 2 empresas sem razao_social e natureza '0000' em 2026-09)."""
    return " OR ".join(f"{alias}.{c} IS NULL" for c in cols) if cols else "FALSE"


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

def build_staging(conn, spec: RfbTable, csv_files: Iterator[Path]) -> dict:
    """Carrega todos os CSVs da tabela numa staging tipada (mesmos tipos da live).

    Colisões só são aceitas com o mesmo registro na origem e os mesmos
    campos tipados, inclusive entre partes distintas da publicação.
    """
    stg = _staging_name(spec)
    raw = f"{stg}_raw"
    types = column_types(conn, spec.table)
    missing = [c for c in spec.columns if c not in types]
    if missing:
        raise RuntimeError(f"{spec.table}: colunas ausentes na tabela live: {missing}")

    col_defs = [f"{c} {types[c]}" for c in spec.columns]
    col_defs.append("_origem BYTEA NOT NULL")
    if spec is SOCIO:
        col_defs.append("_id TEXT NOT NULL")
        col_defs.append("UNIQUE (cnpj_basico, _id)")
    else:
        col_defs.append(f"PRIMARY KEY ({', '.join(spec.key)})")
    _exec(conn, f"DROP TABLE IF EXISTS {stg}")
    _exec(conn, f"CREATE UNLOGGED TABLE {stg} ({', '.join(col_defs)})")
    conn.commit()

    cols = ", ".join(spec.columns)
    origem = spec.select_sql(raw, com_assinatura=True)
    if spec is SOCIO:
        # Identidade calculada com os MESMOS tipos da live (cast explicito),
        # senao ROW(...)::text divergiria entre staging e live.
        typed = ", ".join(f"x.{c}::{types[c]}" for c in SOCIO_IDENTITY)
        chave = f"s.cnpj_basico = x.cnpj_basico AND s._id = md5(ROW({typed})::text)"
        insert_sql = (
            f"INSERT INTO {stg} ({cols}, _origem, _id)\n"
            f"SELECT x.*, md5(ROW({typed})::text) FROM (\n{origem}\n) x\n"
            "ON CONFLICT DO NOTHING"
        )
    else:
        chave = _key_eq(spec, "s", "x")
        insert_sql = f"INSERT INTO {stg} ({cols}, _origem)\n{origem}\nON CONFLICT DO NOTHING"

    inseridas = repetidas = 0
    for csv_path in csv_files:
        t0 = time.time()
        lidas = staging_copy(conn, raw, spec.n_cols, csv_path, assinar_registro=True)
        n = _exec(conn, insert_sql)
        if n != lidas:
            # ON CONFLICT pode esconder atributos divergentes (inclusive entre
            # ZIPs). Só explicar o descarte se cada ocorrência tem um espelho
            # completo na staging; uma raiz filtrada também falha na conta.
            igualdade = _mesma_linha(spec.columns, "s", "x")
            espelhadas = _scalar(conn, f"""
                SELECT count(*) FROM ({origem}) x
                WHERE EXISTS (SELECT 1 FROM {stg} s
                    WHERE {chave} AND s._origem = x._origem AND {igualdade})
            """)
            if espelhadas != lidas:
                raise GuardError(f"{spec.table}: {lidas - espelhadas} ocorrências sem espelho idêntico em {csv_path.name}")
            repetidas += lidas - n
        inseridas += n
        _exec(conn, f"DROP TABLE IF EXISTS {raw}")
        conn.commit()
        csv_path.unlink(missing_ok=True)
        logger.info("staging %s <- %s: %d linhas (%.0fs)", spec.table, csv_path.name, n, time.time() - t0)

    _exec(conn, f"ANALYZE {stg}")
    conn.commit()
    return {"staging": inseridas, "repeticoes_identicas": repetidas}


# ──────────────────────────────────────────────────────────────────────────
# Diff
# ──────────────────────────────────────────────────────────────────────────

def _key_eq(spec: RfbTable, a: str, b: str) -> str:
    return " AND ".join(f"{a}.{k} = {b}.{k}" for k in spec.key)


def _mesma_linha(colunas: tuple[str, ...], a: str, b: str) -> str:
    esq = ", ".join(f"{a}.{c}" for c in colunas)
    dir_ = ", ".join(f"{b}.{c}" for c in colunas)
    return f"ROW({esq}) IS NOT DISTINCT FROM ROW({dir_})"


def _socio_match(t: str, s: str) -> str:
    return (f"{s}.cnpj_basico = {t}.cnpj_basico AND {s}._id = {socio_identity_sql(t)} "
            f"AND {_mesma_linha(SOCIO_IDENTITY, t, s)}")


def _balanco_socio(conn, colunas: tuple[str, ...]) -> dict:
    """Compara multiconjuntos, sem depender de hash, saldo global ou id serial."""
    cols = ", ".join(colunas)
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT COALESCE(sum(l), 0), COALESCE(sum(l) FILTER (WHERE s = 0), 0),
                   count(*) FILTER (WHERE l = 0), count(*) FILTER (WHERE l > 1)
            FROM (
                SELECT count(*) FILTER (WHERE live) AS l, count(*) FILTER (WHERE NOT live) AS s
                FROM (SELECT {cols}, true AS live FROM socio UNION ALL
                      SELECT {cols}, false FROM {_staging_name(SOCIO)}) u
                GROUP BY {cols}
            ) por_chave
        """)
        return dict(zip(("live", "extras", "ausentes", "grupos_multiplos"), map(int, cur.fetchone())))


def plan_table(conn, spec: RfbTable, carga: dict) -> dict:
    """Planeja sócio por identidade completa; as demais tabelas já têm PK."""
    stg = _staging_name(spec)
    if spec is SOCIO:
        b = _balanco_socio(conn, SOCIO_IDENTITY)
        return {**carga, "live_antes": b["live"], "a_remover": b["extras"],
                "a_inserir": b["ausentes"], "identidades_multiplas_live": b["grupos_multiplos"]}
    match = _key_eq(spec, "s", "t")
    with conn.cursor() as cur:
        cur.execute(f"""SELECT count(*), count(*) FILTER (WHERE s.cnpj_basico IS NULL)
                        FROM {spec.table} t LEFT JOIN {stg} s ON {match}""")
        live, to_delete = cur.fetchone()
    incomplete = 0
    req = _required_cols(conn, spec)
    if req:
        incomplete = int(_scalar(conn, f"SELECT COUNT(*) FROM {stg} s WHERE {_incomplete_pred('s', req)}"))
    conn.commit()
    return {**carga, "live_antes": live, "a_remover": to_delete,
            "incompletas": incomplete}


# Registros incompletos tolerados (ignorados) antes de abortar. 2026-09 trouxe
# 2 em 70M; volume grande = formato/coluna deslocada -> abortar, nao ignorar.
MAX_INCOMPLETE_ROWS = 1000
MAX_INCOMPLETE_PCT = 0.01


def check_guards(spec: RfbTable, plan: dict, max_delete_pct: float, max_shrink_pct: float,
                 *, ignorar_percentuais: bool = False) -> None:
    live, stg, rem = plan["live_antes"], plan["staging"], plan["a_remover"]
    if plan.get("identidades_multiplas_live"):
        raise GuardError(f"socio: {plan['identidades_multiplas_live']} identidades múltiplas na live")
    if stg == 0:
        raise GuardError(f"{spec.table}: snapshot vazio — download/parse falhou")
    inc = plan.get("incompletas", 0)
    if inc > max(MAX_INCOMPLETE_ROWS, stg * MAX_INCOMPLETE_PCT / 100):
        raise GuardError(
            f"{spec.table}: {inc:,} linhas do snapshot com coluna NOT NULL vazia "
            f"(limite max({MAX_INCOMPLETE_ROWS}, {MAX_INCOMPLETE_PCT}%)) — mudanca de formato?"
        )
    if live == 0 or ignorar_percentuais:
        return
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
    totals = {"removidas": 0, "atualizadas": 0, "inseridas": 0, "incompletas_ignoradas": 0}
    # Registro incompleto (violaria NOT NULL): a linha live correspondente fica
    # intocada (nem UPDATE nem DELETE — a chave esta na staging) e nao ha
    # INSERT de chave nova. Volume limitado por check_guards ANTES daqui.
    req = _required_cols(conn, spec)
    complete = f"NOT ({_incomplete_pred('s', req)})"
    totals["incompletas_ignoradas"] = int(_scalar(
        conn, f"SELECT COUNT(*) FROM {stg} s WHERE NOT ({complete})"))
    if totals["incompletas_ignoradas"]:
        logger.warning("%s: %d linhas do snapshot com NOT NULL vazio (%s) ignoradas",
                       spec.table, totals["incompletas_ignoradas"], ", ".join(req))

    # rfb_sync_estab_delta NAO eh limpa aqui: eh trabalho pendente durável.
    # Se a execução falhar depois de aplicar estabelecimentos, o retry pode
    # encontrar diff vazio. Só a confirmação final do refresh baixa o delta.

    for lo, hi in _batch_bounds():
        rt, rs = _range_pred("t", lo, hi), _range_pred("s", lo, hi)
        delete_sql = (
            f"DELETE FROM {spec.table} t WHERE {rt} "
            f"AND NOT EXISTS (SELECT 1 FROM {stg} s WHERE {_key_eq(spec, 's', 't')})"
        )
        insert_sql = (
            f"INSERT INTO {spec.table} ({all_cols}) SELECT {s_all} FROM {stg} s WHERE {rs} AND {complete} "
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
            f"FROM {stg} s WHERE {_key_eq(spec, 't', 's')} AND {rt} AND {complete} "
            f"AND ({t_cols}) IS DISTINCT FROM ({s_cols})",
        )
        totals["inseridas"] += _exec(conn, insert_sql, {"mes": month})
        if hi is not None:  # último lote confirma junto com a barreira de pós-paridade
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
        if hi is not None:
            conn.commit()
    return totals


def preparar_dominios(conn, month: str, files: dict[str, int], work_dir: Path, manifesto: dict) -> dict:
    """Valida todos os pequenos domínios contra os tipos e PKs reais, sem aplicá-los."""
    from etl.utils import parse_csv_line, safe_strip

    out = {}
    for prefix, table in DOMAIN_FILES.items():
        z = download_zip(month, f"{prefix}.zip", files[f"{prefix}.zip"], work_dir)
        csv_path = extract_single(z, work_dir / f"{prefix}.csv", manifesto)
        rows = []
        with open(csv_path, encoding="latin-1", errors="replace") as f:
            for line in f:
                fields = parse_csv_line(line, delimiter=";")
                if len(fields) != 2 or not (codigo := safe_strip(fields[0])):
                    raise GuardError(f"{table}: linha de domínio inválida")
                rows.append((codigo, safe_strip(fields[1])))
        csv_path.unlink(missing_ok=True)
        before = int(_scalar(conn, f"SELECT COUNT(*) FROM {table}"))
        if not rows or len(rows) < before * 0.9:
            raise GuardError(f"{table}: {len(rows)} linhas no arquivo vs {before} na base")
        stg = f"_rfb_sync_{table}"
        _exec(conn, f"CREATE TEMP TABLE {stg} (LIKE {table} INCLUDING INDEXES)")
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, f"INSERT INTO {stg} (codigo, descricao) VALUES %s", rows)
        except (psycopg2.DataError, psycopg2.IntegrityError):
            raise GuardError(f"{table}: código repetido ou valor incompatível na publicação") from None
        out[table] = {"antes": before, "staging": len(rows)}
    return out


def aplicar_dominios(conn, planos: dict) -> None:
    for table, plano in planos.items():
        _exec(conn, f"DELETE FROM {table}")
        n = _exec(conn, f"INSERT INTO {table} (codigo, descricao) SELECT codigo, descricao FROM _rfb_sync_{table}")
        if n != plano["staging"]:
            raise RuntimeError(f"{table}: inserções de domínio divergentes do plano")
        plano["depois"] = n
    conn.commit()


def verificar_paridade(conn, spec: RfbTable, plano: dict) -> None:
    """Substitui o COUNT pós-aplicação; faltas e sobras não se compensam."""
    if spec is SOCIO:
        # Agora comparar também os atributos, não apenas as seis colunas da identidade.
        b = _balanco_socio(conn, SOCIO.columns)
        plano["live_depois"] = b["live"]
        if (b["extras"] or b["ausentes"] or b["grupos_multiplos"]
                or plano["a_remover"] != plano["movidas_historico"]
                or plano["a_inserir"] != plano["inseridas"]):
            raise DivergenciaParidade(f"socio: divergência após aplicação: {b}")
        return
    incompleta = _incomplete_pred("s", _required_cols(conn, spec))
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT count(t.cnpj_basico), count(*) FILTER (WHERE s.cnpj_basico IS NULL),
                   count(*) FILTER (WHERE NOT ({incompleta}) AND
                       (t.cnpj_basico IS NULL OR NOT ({_mesma_linha(spec.columns, 's', 't')})))
            FROM {spec.table} t FULL JOIN {_staging_name(spec)} s ON {_key_eq(spec, 't', 's')}
        """)
        plano["live_depois"], extras, divergentes = cur.fetchone()
    if extras or divergentes or plano["a_remover"] != plano["removidas"]:
        raise DivergenciaParidade(f"{spec.table}: divergência após aplicação: {extras} extras, {divergentes} divergentes")


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


def _csv_iter(month: str, spec: RfbTable, files: dict[str, int], work_dir: Path, manifesto: dict) -> Iterator[Path]:
    """Baixa+extrai 1 arquivo por vez (pico de disco = 1 CSV)."""
    for name in spec.file_names():
        z = download_zip(month, f"{name}.zip", files[f"{name}.zip"], work_dir)
        yield extract_single(z, work_dir / f"{name}.csv", manifesto)


def _last_success(conn) -> str | None:
    return _scalar(
        conn,
        "SELECT MAX(rfb_mes) FROM rfb_sync_log "
        "WHERE status = 'success' AND NOT (stats ? 'tabelas_parciais')",
    )


def _aplicacao_pendente(conn) -> tuple | None:
    # Só tentativas sob o novo contrato. Uma falha após commit de lote não
    # pode ser encoberta pelo skip de um sucesso anterior da mesma competência.
    with conn.cursor() as cur:
        cur.execute("""
        SELECT rfb_mes, stats->'manifesto', stats->>'paridade_nao_confirmada' FROM rfb_sync_log
        WHERE stats ? 'aplicacao_iniciada' AND id > (
            SELECT COALESCE(max(id), 0) FROM rfb_sync_log
            WHERE status = 'success' AND NOT (stats ? 'tabelas_parciais'))
        ORDER BY (stats ? 'paridade_nao_confirmada') DESC, id LIMIT 1
        """)
        return cur.fetchone()


def _mes_pendente(conn) -> str | None:
    pendente = _aplicacao_pendente(conn)
    return pendente[0] if pendente else None


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
        pendente = _aplicacao_pendente(conn)
        if pendente and pendente[2]:
            raise GuardError(f"{pendente[0]}: paridade de {pendente[2]} não confirmada após aplicação; "
                             "reconciliação obrigatória, sem retomada automática")
        month = resolve_month(opts.month)
        if not opts.tables or set(opts.tables) - set(SYNC_ORDER):
            raise GuardError("seleção de tabelas vazia ou desconhecida")
        parcial = set(opts.tables) != set(SYNC_ORDER)
        last = _last_success(conn)
        if pendente and pendente[0] != month:
            raise GuardError(f"há aplicação pendente de {pendente[0]}; recusada outra competência")
        logger.info("mes alvo %s; ultimo sync completo: %s", month, last)
        if last and last > month:
            raise GuardError(f"mes {month} anterior ao ultimo sync ({last}) — regrediria a base")
        if last and month > last:
            ano, mes = map(int, last.split("-"))
            seguinte = f"{ano + mes // 12:04d}-{mes % 12 + 1:02d}"
            if month != seguinte:
                raise GuardError(f"competência não contígua: após {last} é necessário aplicar {seguinte}")
        if last == month and not pendente and not opts.force:
            logger.info("RFB %s ja sincronizado — nada a fazer", month)
            print("RFB_SYNC_RESULT=skipped")
            return 0

        files = list_files(month)
        missing = [n for n in expected_zips(SYNC_ORDER) if n not in files]
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
        if parcial:
            stats["tabelas_parciais"] = list(opts.tables)
        stats["refresh_solicitado"] = opts.refresh
        manifesto = {}

        if not parcial and opts.refresh:
            from etl.refresh_post_incremental import destinos_relink_ausentes
            ausentes = destinos_relink_ausentes(conn)
            if ausentes:
                raise GuardError(f"destinos de publicação RFB incompletos: {', '.join(ausentes)}")
        limits = {**DEFAULT_MAX_DELETE_PCT, **(opts.max_delete_pct or {})}
        selecionadas = [t for t in SYNC_ORDER if t in opts.tables]
        # --tables limita a escrita, não a barreira de integridade do mês.
        for table in SYNC_ORDER:
            spec = RFB_TABLES[table]
            carga = build_staging(conn, spec, _csv_iter(month, spec, files, work_dir, manifesto))
            plan = plan_table(conn, spec, carga)
            stats[table] = plan
            _update_log(conn, log_id, "running", stats)
            logger.info("%s: plano %s", table, plan)
            check_guards(spec, plan, limits[table], opts.max_shrink_pct, ignorar_percentuais=opts.force)

        stats["dominio"] = preparar_dominios(conn, month, files, work_dir, manifesto)
        stats["manifesto"] = manifesto
        if set(manifesto) != set(expected_zips(SYNC_ORDER)):
            raise GuardError("manifesto não cobre todos os objetos da publicação")
        if pendente and pendente[1] != manifesto:
            raise GuardError("manifesto divergente da aplicação pendente; retomada recusada")

        stats["aplicacao_iniciada"] = True
        _update_log(conn, log_id, "running", stats)
        if "socio" in selecionadas:
            _ensure_socio_norm_column(conn)
        for table in selecionadas:
            t0 = time.time()
            spec = RFB_TABLES[table]
            plan = stats[table]
            applied = apply_socio(conn, month) if spec is SOCIO else apply_keyed(conn, spec, month)
            plan.update(applied)
            # Durável no commit do último lote. Mesmo se a consulta ou o log
            # de falha cair, a próxima tentativa não reinterpreta a live.
            stats["paridade_nao_confirmada"] = table
            _update_log(conn, log_id, "running", stats)
            verificar_paridade(conn, spec, plan)
            del stats["paridade_nao_confirmada"]
            _exec(conn, f"DROP TABLE IF EXISTS {_staging_name(spec)}")
            conn.commit()
            conn.autocommit = True
            _exec(conn, f"ANALYZE {spec.table}")
            conn.autocommit = False
            plan["segundos_aplicacao"] = round(time.time() - t0)
            conn.commit()
            _update_log(conn, log_id, "running", stats)
            logger.info("%s: aplicado %s", table, plan)

        if not parcial:
            aplicar_dominios(conn, stats["dominio"])
        stats["dados_aplicados"] = True
        if parcial or not opts.refresh:
            _update_log(conn, log_id, "publicacao_pendente", stats)
            print("RFB_SYNC_RESULT=publicacao_pendente")
            return 3

        _update_log(conn, log_id, "running", stats)
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
        # Erros de COPY/constraint podem incluir a linha inteira no DETAIL.
        if isinstance(e, DivergenciaParidade):
            stats["classe_falha"] = "divergencia_integridade"
            diagnostico = str(e)
        else:
            stats["classe_falha"] = ("integridade_nao_confirmada" if "paridade_nao_confirmada" in stats
                                     else "operacional")
            diagnostico = f"{type(e).__name__} (SQLSTATE {getattr(e, 'pgcode', None) or '-'})"
        logger.error("rfb_sync falhou: %s", diagnostico)
        if log_id is not None:
            try:
                conn.rollback()
                _update_log(conn, log_id, "failed", stats, diagnostico)
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
                   help="reavalia mês já feito; ignora apenas os limites de remoção e encolhimento")
    p.add_argument("--tables", default=",".join(SYNC_ORDER),
                   help="aplica só as tabelas selecionadas; subconjunto não publica (saída 3)")
    p.add_argument("--max-delete-pct", action="append", metavar="TABELA=PCT",
                   help="sobrescreve limite de remocao (ex: socio=15). Repetivel.")
    p.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    p.add_argument("--work-dir", type=Path, default=None)
    p.add_argument("--no-refresh", action="store_true", help="não publica nem consome o delta (saída 3)")
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)

    tables = tuple(t.strip() for t in args.tables.split(",") if t.strip())
    if not tables:
        p.error("--tables exige pelo menos uma tabela")
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
