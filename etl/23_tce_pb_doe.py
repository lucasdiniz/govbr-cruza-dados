"""Fase 20: TCE-PB DOE eletronico - decisoes individuais.

Baixa, parseia e carrega decisoes (acordaos/decisoes singulares/resolucoes) do
Tribunal de Contas do Estado da Paraiba a partir de https://publicacao.tce.pb.gov.br.

Cada PDF e uma decisao individual. Um processo (NNNNN/AA) agrupa 1..N decisoes
ao longo do tempo (decisao inicial, embargos, recurso). Ver ADR-0014.

Pipeline por PDF:
  1. Listar hashes via index HTML (decisao.php?ano=YYYY).
  2. Baixar PDF se ainda nao temos (4 workers + retry exp em {520,429,503,timeout}).
  3. Extrair texto via pdfminer.six.
  4. Classificar tipo_materia (filename slug + fallback header).
  5. Classificar resultado (regex calibradas em N=9.935 PDFs - ver ADR-0014).
  6. Extrair CNPJs, valor multa/debito, municipio inferido, data_sessao.
  7. UPSERT em tce_pb_decisao (PK=_nk_md5, parser_version) + CASCADE em tce_pb_decisao_cnpj.
  8. Descartar PDF apos persistir (pipeline streaming - nao armazenar).

Uso:
  python -m etl.23_tce_pb_doe                       # backfill completo (2008-hoje)
  python -m etl.23_tce_pb_doe --anos 2024,2025
  python -m etl.23_tce_pb_doe --only-recent 30      # ultimos N dias (incremental)
  python -m etl.23_tce_pb_doe --skip-download       # so reprocessa PDFs ja em disco
  python -m etl.23_tce_pb_doe --reprocess-all       # forca reparse mesmo se parser_version match
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from html.parser import HTMLParser
from multiprocessing import Pool
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from etl.config import DATA_DIR, SQL_DIR
from etl.db import get_conn, table_count

PARSER_VERSION = 1

DOE_DIR = DATA_DIR / "tce_pb_doe"
DOE_INDEX = "https://publicacao.tce.pb.gov.br/decisao.php?ano={ano}"
DOE_PDF = "https://publicacao.tce.pb.gov.br/{hash}"

_UA = "transparenciapb-etl/1.0"
_DOWNLOAD_WORKERS = 4
_DOWNLOAD_BACKOFF_MAX = 30
_DOWNLOAD_MAX_RETRIES = 5
_PARSE_WORKERS = 8

# Anos disponiveis no portal (verificado em 2026-05).
DEFAULT_ANO_INICIO = 2008


# ── Padroes de filename TCE-PB ─────────────────────────────────────────────
# Exemplo completo (truncado para 73 chars no HTML do index):
#   proc_04498_22_decisao_singular_ds2tc_00125_24_decisao_inicial_sessao_13_03_2024.pdf
# Truncado:
#   proc_04498_22_decisao_singular_ds2tc_00125_24_decisao_inicial_sessao_13_03_202
# Regex tolera truncamento — captura o que conseguir, completa data via texto.
_PAT_FILENAME = re.compile(
    r"^proc_(\d{4,5})_(\d{2})_"          # num_processo, ano_processo (YY)
    r"([a-z_]+?)_"                       # tipo_decisao slug (acordao | decisao_singular | resolucao_processual...)
    r"([a-z0-9]{3,6})_"                  # orgao slug (apltc/ac1tc/ac2tc/ds1tc/ds2tc/dspltc/rc1tc...)
    r"(\d{3,5})_(\d{2})_"                # num_decisao, ano_decisao (YY)
    r"([a-z0-9_]+?)_"                    # fase slug
    r"sessao_(\d{2})_(\d{2})_(\d{2,4})", # data sessao (DD MM YYYY, com YYYY truncado as vezes)
    re.IGNORECASE,
)

_PAT_DATA_SESSAO = re.compile(
    r"Sess[ãa]o\s+(?:do\s+dia\s+)?(\d{2})/(\d{2})/(\d{4})",
    re.IGNORECASE,
)

_PAT_CNPJ = re.compile(r"\b(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})\b")

# Classificador de tipo_materia por slug do tipo_decisao
_TIPO_MATERIA_FROM_SLUG = {
    "atos_pessoal": "atos_pessoal",
    "aposentadoria": "atos_pessoal",
    "pensao": "atos_pessoal",
}

# Heuristicas calibradas em N=9.935 PDFs (ver ADR-0014).
_PAT_IRREGULAR = re.compile(
    r"\bjulgar?\s+irregular|contas?\s+irregulares?|julgou-se\s+irregular",
    re.IGNORECASE,
)
_PAT_REG_RESSALVA = re.compile(
    r"regular(?:es)?\s+com\s+ressalva|aprova[çc][ãa]o\s+com\s+ressalva",
    re.IGNORECASE,
)
_PAT_REGULAR = re.compile(
    r"\bjulgar?\s+regular(?!\s+(?:com\s+ressalva|irregular))"
    r"|\bparecer\s+favor[áa]vel\b",
    re.IGNORECASE,
)
_PAT_MULTA = re.compile(
    r"aplicar?\s+multa|impor?\s+multa|aplicac[ãa]o\s+de\s+multa",
    re.IGNORECASE,
)
_PAT_DEBITO = re.compile(
    r"imputa[çc][ãa]o\s+de\s+d[ée]bito|imputar?\s+d[ée]bito|ressarcimento[^\n]{0,40}R\$",
    re.IGNORECASE,
)
_PAT_VALOR_MULTA = re.compile(
    r"multa[^\n]{0,80}R\$\s*([\d\.\,]+)",
    re.IGNORECASE,
)
_PAT_VALOR_DEBITO = re.compile(
    r"d[ée]bito[^\n]{0,80}R\$\s*([\d\.\,]+)",
    re.IGNORECASE,
)
_PAT_MUNICIPIO = re.compile(
    r"(?:Munic[íi]pio|Prefeitura\s+Municipal)\s+(?:de\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s\-']{2,50}?)(?=\s*[\,\.\-/]|\s+e\s+)",
)


# ─────────────────────────────────────────────────────────────────────────
# Crawl da listagem (extrai pares hash/filename do HTML do index)
# ─────────────────────────────────────────────────────────────────────────


class _DOEIndexParser(HTMLParser):
    """Extrai (hash, filename) de cada <a href='/HASH'>NAME</a>."""

    def __init__(self):
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._cur_hash: str | None = None
        self._cur_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        m = re.match(r"^/?([a-f0-9]{32})$", href)
        if m:
            self._cur_hash = m.group(1)
            self._cur_text = []

    def handle_data(self, data):
        if self._cur_hash:
            self._cur_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._cur_hash:
            name = "".join(self._cur_text).strip()
            if name:
                self.items.append((self._cur_hash, name))
            self._cur_hash = None
            self._cur_text = []


def fetch_doe_index(ano: int) -> list[tuple[str, str]]:
    """Retorna lista de (hash, filename_truncado) para um ano do DOE TCE-PB."""
    url = DOE_INDEX.format(ano=ano)
    req = Request(url, headers={"User-Agent": _UA})
    with urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", errors="replace")
    p = _DOEIndexParser()
    p.feed(html)
    return p.items


# ─────────────────────────────────────────────────────────────────────────
# Download (4 workers + exp backoff em 520/429/503/timeout)
# ─────────────────────────────────────────────────────────────────────────


def _download_one(item) -> tuple[str, str, int]:
    """Worker: baixa um PDF. Retorna (hash, status, bytes)."""
    h, dest_dir = item
    path = dest_dir / f"{h}.pdf"
    if path.exists() and path.stat().st_size > 1000:
        return (h, "skip", path.stat().st_size)
    backoff = 2
    for _ in range(_DOWNLOAD_MAX_RETRIES):
        try:
            req = Request(DOE_PDF.format(hash=h), headers={"User-Agent": _UA})
            with urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1000:
                return (h, "err:tiny", 0)
            path.write_bytes(data)
            return (h, "ok", len(data))
        except Exception as e:
            msg = str(e).lower()
            transitorio = any(c in msg for c in ("520", "429", "503")) or "timed out" in msg
            if transitorio:
                time.sleep(backoff)
                backoff = min(backoff * 2, _DOWNLOAD_BACKOFF_MAX)
                continue
            return (h, f"err:{type(e).__name__}", 0)
    return (h, "err:max_retries", 0)


def download_decisoes(hashes: list[str], dest_dir: Path) -> dict:
    """Baixa os PDFs em paralelo (4 workers + backoff). Idempotente.

    Retorna stats {ok, skip, err, bytes}.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Limpa zero-bytes/tiny files de runs anteriores
    for f in dest_dir.glob("*.pdf"):
        if f.stat().st_size < 1000:
            f.unlink()

    items = [(h, dest_dir) for h in hashes]
    t0 = time.time()
    ok = skip = err = 0
    total_bytes = 0
    errors_sample: list[str] = []

    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
        futs = [pool.submit(_download_one, it) for it in items]
        for i, fut in enumerate(as_completed(futs), 1):
            h, status, sz = fut.result()
            if status == "ok":
                ok += 1
                total_bytes += sz
            elif status == "skip":
                skip += 1
                total_bytes += sz
            else:
                err += 1
                if len(errors_sample) < 20:
                    errors_sample.append(f"{h}: {status}")
            if i % 100 == 0 or i == len(items):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed else 0
                eta = (len(items) - i) / rate if rate else 0
                mb = total_bytes / 1024 / 1024
                print(
                    f"    [{i:5d}/{len(items)}] ok={ok} skip={skip} err={err} | "
                    f"{mb:.1f}MB ({mb/elapsed if elapsed else 0:.2f}MB/s) | "
                    f"rate={rate:.1f}/s ETA={eta:.0f}s",
                    flush=True,
                )

    if errors_sample:
        print("    Sample de erros:", flush=True)
        for e in errors_sample:
            print(f"      {e}", flush=True)

    return {"ok": ok, "skip": skip, "err": err, "bytes": total_bytes}


# ─────────────────────────────────────────────────────────────────────────
# Parse (pdfminer + classificadores calibrados)
# ─────────────────────────────────────────────────────────────────────────


def _parse_filename(name: str) -> dict:
    """Best-effort: extrai campos do filename (que vem truncado em 73 chars do HTML)."""
    m = _PAT_FILENAME.match(name or "")
    if not m:
        return {}
    g = m.groups()
    yyyy = g[9]
    if len(yyyy) == 2:
        yyyy = "20" + yyyy
    return {
        "num_processo": g[0].lstrip("0") or "0",
        "ano_processo": int("20" + g[1]),
        "tipo_decisao_slug": g[2].lower(),
        "orgao_julgador": g[3].lower(),
        "num_decisao": g[4].lstrip("0") or "0",
        "ano_decisao": int("20" + g[5]),
        "fase": g[6].lower(),
        "data_sessao": f"{yyyy}-{g[8]}-{g[7]}" if len(yyyy) == 4 else None,
    }


def _classify_tipo_materia(slug_decisao: str, text_head: str) -> str:
    if slug_decisao:
        s = slug_decisao.lower()
        if s in _TIPO_MATERIA_FROM_SLUG:
            return _TIPO_MATERIA_FROM_SLUG[s]
    head = (text_head or "").upper()
    if "APOSENTADORIA" in head or "PENSÃO" in head or "PENSAO" in head or "REFORMA" in head:
        return "atos_pessoal"
    if "DENÚNCIA" in head or "DENUNCIA" in head:
        return "denuncia"
    if "REPRESENTAÇÃO" in head or "REPRESENTACAO" in head:
        return "representacao"
    if "PRESTAÇÃO DE CONTAS" in head or "PRESTACAO DE CONTAS" in head:
        return "pca"
    if "TOMADA DE CONTAS" in head:
        return "tce_especial"
    if "LICITAÇÃO" in head or "LICITACAO" in head or "PREGÃO" in head or "PREGAO" in head:
        return "licitacao"
    if "CONTRATO" in head:
        return "contrato"
    if "EMBARGOS" in head:
        return "embargos"
    if "RECURSO" in head or "AGRAVO" in head:
        return "recurso"
    return "indef"


def _classify_resultado(text: str) -> str:
    if _PAT_IRREGULAR.search(text):
        return "irregular"
    if _PAT_REG_RESSALVA.search(text):
        return "regular_ressalva"
    if _PAT_REGULAR.search(text):
        return "regular"
    return "indef"


def _parse_brl(s: str) -> float | None:
    if not s:
        return None
    s = s.strip().rstrip(".,")
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
        if v <= 0 or v > 1e10:
            return None
        return round(v, 2)
    except ValueError:
        return None


def _extract_municipio(text_head: str) -> str | None:
    m = _PAT_MUNICIPIO.search(text_head or "")
    if not m:
        return None
    name = m.group(1).strip().rstrip(",.").strip()
    return name[:120] if name else None


def _extract_data_sessao(text: str) -> str | None:
    m = _PAT_DATA_SESSAO.search(text or "")
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def parse_pdf(pdf_path: Path, filename_hint: str) -> dict | None:
    """Lê um PDF e retorna dict com campos extraidos. None se filename irreparavel."""
    # Importacao lazy — pdfminer e dep heavy.
    from pdfminer.high_level import extract_text

    try:
        text = extract_text(str(pdf_path)) or ""
    except Exception as e:
        return {"error": f"pdfminer:{type(e).__name__}", "raw_error": str(e)[:200]}

    text = text.replace("\u00a0", " ")
    head = text[:2000]
    body = text  # full body para regex de resultado/valor/cnpj

    fn = _parse_filename(filename_hint)
    if not fn:
        return {"error": "filename_unparseable", "filename": filename_hint}

    tipo_materia = _classify_tipo_materia(fn.get("tipo_decisao_slug", ""), head)
    resultado = _classify_resultado(body)
    data_sessao = fn.get("data_sessao") or _extract_data_sessao(body)

    aplicou_multa = bool(_PAT_MULTA.search(body))
    imputou_debito = bool(_PAT_DEBITO.search(body))
    valor_multa = None
    valor_debito = None
    if aplicou_multa:
        m = _PAT_VALOR_MULTA.search(body)
        if m:
            valor_multa = _parse_brl(m.group(1))
    if imputou_debito:
        m = _PAT_VALOR_DEBITO.search(body)
        if m:
            valor_debito = _parse_brl(m.group(1))

    cnpjs: set[str] = set()
    for m in _PAT_CNPJ.finditer(body):
        cnpjs.add("".join(m.groups()))

    municipio = _extract_municipio(head)

    text_hash = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()

    # Tipo decisao "humanizado"
    slug = fn.get("tipo_decisao_slug", "")
    tipo_decisao = slug.replace("_", " ") if slug else None

    return {
        "hash_publicacao": pdf_path.stem,
        "num_processo": fn["num_processo"],
        "ano_processo": fn["ano_processo"],
        "tipo_decisao": tipo_decisao[:40] if tipo_decisao else None,
        "orgao_julgador": fn.get("orgao_julgador", "")[:10] or None,
        "num_decisao": fn["num_decisao"],
        "ano_decisao": fn["ano_decisao"],
        "fase": fn["fase"][:60],
        "data_sessao": data_sessao,
        "tipo_materia": tipo_materia,
        "resultado": resultado,
        "aplicou_multa": aplicou_multa,
        "imputou_debito": imputou_debito,
        "valor_multa_rs": valor_multa,
        "valor_debito_rs": valor_debito,
        "municipio_inferido": municipio,
        "text_sha256": text_hash,
        "cnpjs": sorted(cnpjs),
    }


def _nk_md5_of(parsed: dict) -> str:
    nk = "|".join([
        parsed["num_processo"],
        str(parsed["ano_processo"]),
        parsed.get("tipo_decisao") or "",
        parsed["num_decisao"],
        str(parsed["ano_decisao"]),
        parsed["fase"],
    ])
    return hashlib.md5(nk.encode("utf-8")).hexdigest()


def _parse_worker(args):
    pdf_path_s, filename_hint = args
    pdf_path = Path(pdf_path_s)
    try:
        parsed = parse_pdf(pdf_path, filename_hint)
        return (pdf_path.stem, parsed)
    except Exception as e:
        return (pdf_path.stem, {"error": f"worker:{type(e).__name__}", "raw_error": str(e)[:200]})


# ─────────────────────────────────────────────────────────────────────────
# Carga (UPSERT em tce_pb_decisao + tce_pb_decisao_cnpj)
# ─────────────────────────────────────────────────────────────────────────

_UPSERT_DECISAO = """
INSERT INTO tce_pb_decisao (
    _nk_md5, hash_publicacao, num_processo, ano_processo, tipo_decisao,
    orgao_julgador, num_decisao, ano_decisao, fase, data_sessao,
    tipo_materia, resultado, aplicou_multa, imputou_debito,
    valor_multa_rs, valor_debito_rs, municipio_inferido, text_sha256,
    parser_version
) VALUES (
    %(_nk_md5)s, %(hash_publicacao)s, %(num_processo)s, %(ano_processo)s,
    %(tipo_decisao)s, %(orgao_julgador)s, %(num_decisao)s, %(ano_decisao)s,
    %(fase)s, %(data_sessao)s, %(tipo_materia)s, %(resultado)s,
    %(aplicou_multa)s, %(imputou_debito)s, %(valor_multa_rs)s,
    %(valor_debito_rs)s, %(municipio_inferido)s, %(text_sha256)s,
    %(parser_version)s
)
ON CONFLICT (_nk_md5) DO UPDATE SET
    hash_publicacao    = EXCLUDED.hash_publicacao,
    tipo_decisao       = EXCLUDED.tipo_decisao,
    orgao_julgador     = EXCLUDED.orgao_julgador,
    data_sessao        = EXCLUDED.data_sessao,
    tipo_materia       = EXCLUDED.tipo_materia,
    resultado          = EXCLUDED.resultado,
    aplicou_multa      = EXCLUDED.aplicou_multa,
    imputou_debito     = EXCLUDED.imputou_debito,
    valor_multa_rs     = EXCLUDED.valor_multa_rs,
    valor_debito_rs    = EXCLUDED.valor_debito_rs,
    municipio_inferido = EXCLUDED.municipio_inferido,
    text_sha256        = EXCLUDED.text_sha256,
    parser_version     = EXCLUDED.parser_version,
    ingerido_em        = now()
WHERE tce_pb_decisao.parser_version < EXCLUDED.parser_version
   OR tce_pb_decisao.text_sha256 IS DISTINCT FROM EXCLUDED.text_sha256
"""


def _persist_batch(conn, batch: list[dict]) -> None:
    if not batch:
        return
    with conn.cursor() as cur:
        for p in batch:
            p["_nk_md5"] = _nk_md5_of(p)
            p["parser_version"] = PARSER_VERSION
            cur.execute(_UPSERT_DECISAO, p)
            # Substitui o bag de CNPJs (CASCADE em delete via FK).
            cur.execute("DELETE FROM tce_pb_decisao_cnpj WHERE decisao_md5 = %s",
                        (p["_nk_md5"],))
            if p["cnpjs"]:
                args = [(p["_nk_md5"], c) for c in p["cnpjs"]]
                cur.executemany(
                    "INSERT INTO tce_pb_decisao_cnpj (decisao_md5, cnpj) VALUES (%s, %s)"
                    " ON CONFLICT DO NOTHING",
                    args,
                )
    conn.commit()


def parse_and_load(conn, pdf_pairs: list[tuple[Path, str]],
                   reprocess_all: bool = False) -> dict:
    """Roda parsing em pool de processos e persiste em batches de 200.

    pdf_pairs: lista de (pdf_path, filename_hint).
    """
    if not pdf_pairs:
        return {"parsed": 0, "errors": 0, "skipped": 0}

    # Filtra ja-processados (mesma parser_version) se nao reprocess_all.
    if not reprocess_all:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT hash_publicacao FROM tce_pb_decisao "
                "WHERE parser_version >= %s",
                (PARSER_VERSION,),
            )
            done = {r[0] for r in cur.fetchall()}
        before = len(pdf_pairs)
        pdf_pairs = [(p, n) for (p, n) in pdf_pairs if p.stem not in done]
        skipped = before - len(pdf_pairs)
        if skipped:
            print(f"    Skipping {skipped} PDFs ja na parser_version {PARSER_VERSION}.",
                  flush=True)
    else:
        skipped = 0

    print(f"    Parseando {len(pdf_pairs)} PDFs com {_PARSE_WORKERS} workers...",
          flush=True)

    t0 = time.time()
    parsed = errors = 0
    batch: list[dict] = []
    args_list = [(str(p), n) for (p, n) in pdf_pairs]

    error_samples: list[str] = []
    with Pool(processes=_PARSE_WORKERS) as pool:
        for i, (h, result) in enumerate(
            pool.imap_unordered(_parse_worker, args_list, chunksize=8), 1
        ):
            if result is None or "error" in result:
                errors += 1
                if len(error_samples) < 10:
                    err_desc = (result or {}).get("error", "unknown")
                    error_samples.append(f"{h}: {err_desc}")
            else:
                batch.append(result)
                if len(batch) >= 200:
                    _persist_batch(conn, batch)
                    parsed += len(batch)
                    batch = []
            if i % 200 == 0 or i == len(args_list):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed else 0
                eta = (len(args_list) - i) / rate if rate else 0
                print(
                    f"    [{i:5d}/{len(args_list)}] parsed={parsed} err={errors} "
                    f"rate={rate:.1f}/s ETA={eta:.0f}s",
                    flush=True,
                )

    if batch:
        _persist_batch(conn, batch)
        parsed += len(batch)

    if error_samples:
        print("    Sample de erros de parse:", flush=True)
        for e in error_samples:
            print(f"      {e}", flush=True)

    return {"parsed": parsed, "errors": errors, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────


def _ensure_schema(conn) -> None:
    sql = (SQL_DIR / "42_tce_pb_decisao.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _list_local_pdfs(dest_dir: Path,
                     index_map: dict[str, str]) -> list[tuple[Path, str]]:
    """Cruza PDFs ja em disco com filenames do index. Filename hint vem do index."""
    pairs: list[tuple[Path, str]] = []
    for f in dest_dir.glob("*.pdf"):
        if f.stat().st_size < 1000:
            continue
        h = f.stem
        if h in index_map:
            pairs.append((f, index_map[h]))
    return pairs


def _filter_recent(items: list[tuple[str, str]], days: int) -> list[tuple[str, str]]:
    """Filtra items do index para os ultimos N dias (usando data_sessao do filename)."""
    cutoff = date.today() - timedelta(days=days)
    out: list[tuple[str, str]] = []
    for h, name in items:
        fn = _parse_filename(name)
        ds = fn.get("data_sessao")
        if not ds:
            continue
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        if d >= cutoff:
            out.append((h, name))
    return out


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="etl.23_tce_pb_doe")
    parser.add_argument("--anos", help="Anos comma-separated (default: backfill)")
    parser.add_argument("--only-recent", type=int, metavar="N",
                        help="Apenas decisoes dos ultimos N dias (modo incremental)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Nao baixa - apenas reparseia PDFs ja em disco")
    parser.add_argument("--reprocess-all", action="store_true",
                        help="Reparseia mesmo PDFs ja na parser_version atual")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="Nao apaga PDFs apos persistir (default: apaga)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.anos:
        anos = [int(a) for a in args.anos.split(",")]
    elif args.only_recent:
        anos = [date.today().year]
        if date.today().month <= 2:
            anos.append(date.today().year - 1)
    else:
        anos = list(range(DEFAULT_ANO_INICIO, date.today().year + 1))

    DOE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  TCE-PB DOE: anos={anos}, only_recent={args.only_recent}, "
          f"parser_version={PARSER_VERSION}", flush=True)

    # ── 1. Fetch index para todos os anos ───────────────────────────────
    all_items: list[tuple[str, str]] = []
    for ano in anos:
        print(f"    Fetching index ano={ano}...", flush=True)
        try:
            items = fetch_doe_index(ano)
        except Exception as e:
            print(f"    ERRO index ano={ano}: {e}", flush=True)
            continue
        print(f"      {len(items)} decisoes listadas.", flush=True)
        all_items.extend(items)

    if args.only_recent:
        before = len(all_items)
        all_items = _filter_recent(all_items, args.only_recent)
        print(f"    Filtrado para ultimos {args.only_recent} dias: "
              f"{len(all_items)}/{before}", flush=True)

    if not all_items:
        print("    Nenhuma decisao a processar.", flush=True)
        return

    index_map = {h: n for h, n in all_items}

    # ── 2. Download ─────────────────────────────────────────────────────
    if args.skip_download:
        print("    --skip-download: pulando download.", flush=True)
    else:
        print(f"    Baixando {len(all_items)} PDFs...", flush=True)
        stats = download_decisoes([h for h, _ in all_items], DOE_DIR)
        print(f"    Download: ok={stats['ok']} skip={stats['skip']} "
              f"err={stats['err']} ({stats['bytes']/1024/1024:.0f}MB)", flush=True)

    # ── 3. Parse + carga ────────────────────────────────────────────────
    conn = get_conn()
    try:
        _ensure_schema(conn)
        print("    Schema TCE-PB DOE garantido.", flush=True)

        pdf_pairs = _list_local_pdfs(DOE_DIR, index_map)
        print(f"    PDFs em disco a processar: {len(pdf_pairs)}", flush=True)

        stats = parse_and_load(conn, pdf_pairs, reprocess_all=args.reprocess_all)
        print(f"    Parse: parsed={stats['parsed']} errors={stats['errors']} "
              f"skipped={stats['skipped']}", flush=True)

        # Contagens finais
        print(f"    tce_pb_decisao: {table_count(conn, 'tce_pb_decisao'):,}", flush=True)
        print(f"    tce_pb_decisao_cnpj: {table_count(conn, 'tce_pb_decisao_cnpj'):,}",
              flush=True)
    finally:
        conn.close()

    # ── 4. Cleanup (PDFs sao streaming) ─────────────────────────────────
    if not args.no_cleanup:
        n = 0
        for f in DOE_DIR.glob("*.pdf"):
            f.unlink()
            n += 1
        print(f"    Cleanup: {n} PDFs removidos (streaming - nao armazenamos).",
              flush=True)


if __name__ == "__main__":
    run()
