"""Publicação manual das quatro chaves do perfil por competência. Ver docs/cache.md."""

import argparse
import hashlib
import json
from contextlib import closing

import psycopg2

from web import warm_cache as warm


CHAVES = [f"{p}:{q}" for p in ("ANO", "12M") for q in ("PERFIL", "KPI_SUMMARY")]
SOMBRAS = [warm.sombra_perfil_datado(q) for q in CHAVES]
DEPENDENCIAS = ["PERFIL", *(f"{p}:TOP_{q}" for p in ("ANO", "12M")
                            for q in ("FORNECEDORES", "SERVIDORES"))]


def _assinatura(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False).encode()).hexdigest()


def _estado(cur, dia, *, completo):
    """Assina cadastro, baseline (inclusive ausências), dependências e geração candidata."""
    cur.execute("SET LOCAL TIME ZONE 'UTC'")
    cur.execute("SELECT municipio FROM mv_municipio_pb_risco WHERE municipio IS NOT NULL ORDER BY municipio")
    municipios = [r[0] for r in cur]
    if not municipios or not all(m.strip() for m in municipios) or len(set(municipios)) != len(municipios):
        raise ValueError("Cadastro municipal vazio, inválido ou duplicado")
    cur.execute("""
        SELECT query_id, municipio, row_count,
               encode(sha256(convert_to(to_jsonb(c)::text, 'UTF8')), 'hex')
        FROM web_cache c
        WHERE query_id = ANY(%s) OR (query_id = ANY(%s) AND municipio = ANY(%s))
        ORDER BY query_id, municipio
    """, (CHAVES + SOMBRAS, DEPENDENCIAS, municipios))
    base, sombras = [], []
    for qid, mun, n, assinatura in cur:
        if mun not in municipios:
            raise ValueError("Município fora do escopo em chave do perfil datado")
        (sombras if qid in SOMBRAS else base).append((qid, mun, n, assinatura))

    deps = {(q, m) for q, m, n, _ in base if q in DEPENDENCIAS and (q != "PERFIL" or n == 1)}
    if deps != {(q, m) for q in DEPENDENCIAS for m in municipios}:
        raise ValueError("Dependências do KPI incompletas")
    esperado = {(q, m) for q in SOMBRAS for m in municipios} if completo else set()
    if {(q, m) for q, m, _, _ in sombras} != esperado or any(n != 1 for _, _, n, _ in sombras):
        raise ValueError("Sombras ausentes, residuais ou incompletas")

    baseline = _assinatura([dia.isoformat(), municipios, base])
    deps_sha = _assinatura([item for item in base if item[0] in DEPENDENCIAS])
    return municipios, baseline, _assinatura([baseline, sombras]), deps_sha


def preparar(conn):
    if not warm._somente_perfil_datado():
        raise ValueError("Defina WARM_REWARM_KEYS=ANO:PERFIL,12M:PERFIL")
    dia = warm._today_gmt3()
    with conn, conn.cursor() as cur:
        municipios, inicial, _, _ = _estado(cur, dia, completo=False)
    for periodo, params in warm._parametros_datados(dia).items():
        ok, falhas = warm._warm_query_across_munis(
            periodo + ":PERFIL", warm.PERFIL_MUNICIPIO_LIVE, municipios, params,
            warm.TIMEOUT_PERFIL_LIVE, True,
        )
        if falhas or ok != len(municipios):
            raise ValueError(f"{periodo}:PERFIL incompleto; nenhuma promoção")
        ok, falhas = warm._warm_kpi_summary_across_munis(municipios, periodo, True)
        if falhas or ok != len(municipios):
            raise ValueError(f"{periodo}:KPI_SUMMARY incompleto; nenhuma promoção")
    with conn, conn.cursor() as cur:
        _, final, manifesto, _ = _estado(cur, warm._today_gmt3(), completo=True)
    if final != inicial:
        raise ValueError("Dia, cadastro, live ou dependências mudaram durante a preparação")
    return manifesto


def _conferir_imagem(cur, manifesto, anterior=False):
    cur.execute("""
        SELECT count(*) = min(b.tamanho) AND bool_and(b.manifesto = %s AND
            to_jsonb(c) IS NOT DISTINCT FROM CASE WHEN %s THEN b.anterior ELSE b.publicada END)
        FROM web_cache_perfil_reversao b
        LEFT JOIN web_cache c ON c.query_id = b.publicada->>'query_id'
                             AND c.municipio = b.publicada->>'municipio'
    """, (manifesto, anterior))
    if not cur.fetchone()[0]:
        raise ValueError("Geração incorreta, inversa incompleta ou live alterado")


def publicar(conn, operacao, manifesto):
    """Transação curta: fixa escritores (inclusive chaves ausentes), permite leitores."""
    with conn, conn.cursor() as cur:
        cur.execute("SET LOCAL lock_timeout = '2s'")
        cur.execute("SET LOCAL statement_timeout = '15s'")
        cur.execute("SET LOCAL TIME ZONE 'UTC'")
        cur.execute("LOCK TABLE web_cache IN SHARE ROW EXCLUSIVE MODE NOWAIT")
        if operacao == "promover":
            _, _, atual, deps_sha = _estado(cur, warm._today_gmt3(), completo=True)
            if atual != manifesto:
                raise ValueError("Geração diferente da aprovada")
            # Sem IF NOT EXISTS: nunca sobrescrever a única inversa disponível.
            cur.execute("""
                CREATE TABLE web_cache_perfil_reversao AS
                SELECT %s::text AS manifesto, %s::text AS deps_sha, count(*) OVER () AS tamanho,
                       to_jsonb(l) AS anterior,
                       to_jsonb(s) || jsonb_build_object('query_id', k.qid) AS publicada
                FROM unnest(%s::text[], %s::text[]) k(qid, sombra)
                JOIN web_cache s ON s.query_id = k.sombra
                LEFT JOIN web_cache l ON l.query_id = k.qid AND l.municipio = s.municipio
            """, (manifesto, deps_sha, CHAVES, SOMBRAS))
            cur.execute("DELETE FROM web_cache WHERE query_id = ANY(%s)", (CHAVES,))
            cur.execute("""
                UPDATE web_cache SET query_id = k.qid FROM unnest(%s::text[], %s::text[]) k(qid, sombra)
                WHERE query_id = k.sombra
            """, (CHAVES, SOMBRAS))
            _conferir_imagem(cur, manifesto)
        elif operacao == "reverter":
            _conferir_imagem(cur, manifesto)
            # Escopo da inversa, não o dia/cadastro corrente. A mesma leitura
            # sob lock protege ausência, conteúdo e reescrita das dependências.
            cur.execute("""
                SELECT query_id, municipio, row_count,
                       encode(sha256(convert_to(to_jsonb(c)::text, 'UTF8')), 'hex')
                FROM web_cache c WHERE query_id = ANY(%s) AND municipio IN
                    (SELECT publicada->>'municipio' FROM web_cache_perfil_reversao)
                ORDER BY query_id, municipio
            """, (DEPENDENCIAS,))
            deps_sha = _assinatura(cur.fetchall())
            cur.execute("SELECT bool_and(deps_sha IS NOT DISTINCT FROM %s) FROM web_cache_perfil_reversao",
                        (deps_sha,))
            if not cur.fetchone()[0]:
                raise ValueError("Dependências do KPI alteradas; reversão bloqueada")
            cur.execute("""
                DELETE FROM web_cache c USING web_cache_perfil_reversao b
                WHERE c.query_id = b.publicada->>'query_id' AND c.municipio = b.publicada->>'municipio'
            """)
            cur.execute("""
                INSERT INTO web_cache SELECT (jsonb_populate_record(NULL::web_cache, anterior)).*
                FROM web_cache_perfil_reversao WHERE anterior IS NOT NULL
            """)
            _conferir_imagem(cur, manifesto, anterior=True)
        else:
            raise ValueError("Operação desconhecida")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="operacao", required=True)
    subs.add_parser("preparar")
    for nome in ("promover", "reverter"):
        subs.add_parser(nome).add_argument("sha256_aprovado")
    args = parser.parse_args()
    with closing(psycopg2.connect(warm.DSN)) as conn:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended('perfil-datado-pb', 0))")
            if not cur.fetchone()[0]:
                raise RuntimeError("Outra operação de perfil datado está em execução")
        if args.operacao == "preparar":
            print("Sombras prontas para conferência; SHA-256:", preparar(conn))
        else:
            publicar(conn, args.operacao, args.sha256_aprovado)


if __name__ == "__main__":
    main()
