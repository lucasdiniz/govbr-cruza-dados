"""Orquestrador: executa todas as fases do ETL na ordem correta."""

import os
import shutil
import sys
import time
import traceback

from etl.config import DATA_DIR


def _emit_notice(message: str):
    """Destaca marcos importantes no GitHub Actions."""
    print(message, flush=True)
    if os.getenv("GITHUB_ACTIONS") == "true":
        escaped = (
            message.replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
        )
        print(f"::notice::{escaped}", flush=True)


# Mapeamento: módulo ETL → subdiretórios de CSVs que podem ser removidos após
# a fase completar com sucesso.  A fase de download (00_download) nunca é
# listada aqui — ela cria os diretórios; a limpeza acontece *depois* da carga.
_CSV_DIRS: dict[str, list[str]] = {
    "etl.02_dominio":       ["rfb"],          # usa Cnaes/Motivos/etc de rfb/
    "etl.03_rfb":           ["rfb"],
    "etl.04_pncp":          ["pncp", "pncp_contratos"],
    "etl.04b_pncp_itens":   ["pncp_itens", "pncp_resultados"],
    "etl.05_emendas":       ["emendas"],
    "etl.06_cpgf":          ["cpgf"],
    "etl.07_pgfn":          ["pgfn"],
    "etl.08_renuncias":     ["renuncias"],
    "etl.09_complementar":  ["bndes"],
    "etl.12_siape":         ["siape"],
    "etl.13_sancoes":       ["sancoes"],
    "etl.14_viagens":       ["viagens"],
    "etl.16_tse":           ["tse"],
    # NOTA: etl.17_bolsa_familia removida deste mapa — Bolsa Familia agora
    # roda via framework incremental (etl_phase=incremental), que cuida da
    # propria limpeza de CSVs. A fase classica e no-op (ver ADR-0010).
    "etl.18_tse_prestacao": ["tse"],          # mesma pasta que 16_tse
    "etl.19_tce_pb":        ["tce_pb"],
    "etl.20_dados_pb":      ["dados_pb"],
    # 23_tce_pb_doe nao registra dir aqui: faz cleanup proprio (streaming).
}

# Diretórios que são compartilhados entre fases — só limpamos depois que
# *todas* as fases que os usam tenham concluído com sucesso.
_SHARED_DIRS: dict[str, list[str]] = {
    "rfb": ["etl.02_dominio", "etl.03_rfb"],
    "tse": ["etl.16_tse", "etl.18_tse_prestacao"],
}


def _cleanup_csvs(module_name: str, succeeded_modules: set[str]):
    """Remove CSVs brutos após carga bem-sucedida para liberar disco."""
    dirs = _CSV_DIRS.get(module_name, [])
    for dirname in dirs:
        # Se o diretório é compartilhado, espera todas as fases dependentes
        required = _SHARED_DIRS.get(dirname, [module_name])
        if not all(m in succeeded_modules for m in required):
            continue

        target = DATA_DIR / dirname
        if target.is_dir():
            size_mb = sum(
                f.stat().st_size for f in target.rglob("*") if f.is_file()
            ) / (1024 * 1024)
            shutil.rmtree(target)
            print(f"    Limpeza: {target} removido ({size_mb:,.0f} MB liberados)", flush=True)


def main():
    start = time.time()

    phases = [
        ("Fase 0: Download de dados brutos", "etl.00_download"),
        ("Fase 1: Schema", "etl.01_schema"),
        ("Fase 2: Dominio", "etl.02_dominio"),
        ("Fase 3: RFB (Empresas, Estabelecimentos, Socios, Simples)", "etl.03_rfb"),
        ("Fase 4.1-4.2: PNCP", "etl.04_pncp"),
        ("Fase 4.3-4.5: Emendas", "etl.05_emendas"),
        ("Fase 4.6: CPGF", "etl.06_cpgf"),
        ("Fase 4.7-4.8+5.2: Complementar (BNDES, Holdings, ComprasNet)", "etl.09_complementar"),
        ("Fase 5.1: PGFN", "etl.07_pgfn"),
        ("Fase 5.3: Renuncias Fiscais", "etl.08_renuncias"),
        ("Fase 6: Indices", "etl.10_indices"),
        ("Fase 7: Entity Resolution (Pessoa)", "etl.11_pessoa"),
        ("Fase 8: SIAPE (Servidores)", "etl.12_siape"),
        ("Fase 9: Sancoes (CEIS/CNEP/CEAF/Acordos)", "etl.13_sancoes"),
        ("Fase 10: Viagens a Servico", "etl.14_viagens"),
        ("Fase 11: TSE Candidatos e Bens", "etl.16_tse"),
        ("Fase 12: Bolsa Familia", "etl.17_bolsa_familia"),
        ("Fase 13: TSE Prestacao de Contas", "etl.18_tse_prestacao"),
        ("Fase 14: TCE-PB (Despesas, Servidores, Licitacoes, Receitas)", "etl.19_tce_pb"),
        ("Fase 15: Dados PB (Pagamento, Empenho, Contratos, Saude, Convenios)", "etl.20_dados_pb"),
        ("Fase 16: PNCP Itens", "etl.04b_pncp_itens"),
        ("Fase 17: Normalizacao (colunas CPF/CNPJ + indices)", "etl.15_normalizar"),
        # TCE-PB DOE roda ANTES das MVs: mv_empresa_tce_pb (em sql/12_views.sql)
        # le tce_pb_decisao/tce_pb_decisao_cnpj. Se rodasse depois, MVs ficariam vazias
        # ate o proximo refresh manual.
        ("Fase 18: TCE-PB DOE (decisoes - download, parse, load)", "etl.23_tce_pb_doe"),
        ("Fase 19: Views materializadas", "etl.21_views"),
        ("Fase 20: MV sitemap empresa-municipio", "etl.22_mv_sitemap"),
    ]

    errors = []
    succeeded: set[str] = set()

    # Permite rodar fase específica:
    #   python -m etl.run_all 3        -> roda da Fase 3 ate o fim
    #   python -m etl.run_all --only 18 -> roda APENAS a Fase 18
    # Modo --only e necessario para deploys cirurgicos que NAO querem disparar
    # fases subsequentes (ex.: rodar so a Fase 18 sem disparar Fase 19=Views
    # que faz DROP CASCADE de todas as MVs). Adicionado em PR #202 (ADR-0014).
    start_phase = 0
    only_phase: int | None = None
    args = sys.argv[1:]
    if args and args[0] == "--only":
        if len(args) < 2:
            print("Uso: python -m etl.run_all --only <fase>", flush=True)
            sys.exit(1)
        try:
            only_phase = int(args[1]) - 1
        except ValueError:
            print(f"Uso: python -m etl.run_all --only <fase>", flush=True)
            print(f"  Fases: 1-{len(phases)}", flush=True)
            sys.exit(1)
        if only_phase < 0 or only_phase >= len(phases):
            print(f"Fase fora do intervalo: 1-{len(phases)}", flush=True)
            sys.exit(1)
        start_phase = only_phase
    elif args:
        try:
            start_phase = int(args[0]) - 1
        except ValueError:
            print(f"Uso: python -m etl.run_all [fase_inicial]", flush=True)
            print(f"     python -m etl.run_all --only <fase>", flush=True)
            print(f"  Fases: 1-{len(phases)}", flush=True)
            sys.exit(1)

    # Fases puladas por --start são consideradas bem-sucedidas (já rodaram antes)
    for j in range(start_phase):
        succeeded.add(phases[j][1])

    for i, (name, module_name) in enumerate(phases):
        if i < start_phase:
            continue
        if only_phase is not None and i > only_phase:
            break

        phase_start = time.time()
        print(f"\n{'='*60}", flush=True)
        _emit_notice(f"[{i+1}/{len(phases)}] {name}")
        print(f"{'='*60}", flush=True)

        ok = False
        try:
            module = __import__(module_name, fromlist=["run"])
            module.run()
            ok = True
        except Exception as e:
            _emit_notice(f"ERRO na {name}: {e}")
            print(f"  Para retomar a partir desta fase: python -m etl.run_all {i+1}", flush=True)
            traceback.print_exc()
            errors.append((name, str(e)))

        elapsed = time.time() - phase_start
        _emit_notice(f"Concluído {name} em {elapsed:.1f}s")

        if ok:
            succeeded.add(module_name)
            _cleanup_csvs(module_name, succeeded)

    total = time.time() - start
    print(f"\n{'='*60}", flush=True)
    if errors:
        print(f"ETL completo com {len(errors)} erro(s) em {total/60:.1f} minutos:", flush=True)
        for name, err in errors:
            print(f"  - {name}: {err}", flush=True)
        print(f"{'='*60}", flush=True)
        sys.exit(1)
    else:
        _emit_notice(f"ETL completo em {total/60:.1f} minutos")
        print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
