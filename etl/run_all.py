"""Orquestrador: executa todas as fases do ETL na ordem correta."""

import sys
import time


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
        ("Fase 18: Views materializadas", "etl.21_views"),
    ]

    # Permite rodar fase específica: python -m etl.run_all 3
    start_phase = 0
    if len(sys.argv) > 1:
        try:
            start_phase = int(sys.argv[1]) - 1
        except ValueError:
            print(f"Uso: python -m etl.run_all [fase_inicial]")
            print(f"  Fases: 1-{len(phases)}")
            sys.exit(1)

    for i, (name, module_name) in enumerate(phases):
        if i < start_phase:
            continue

        phase_start = time.time()
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(phases)}] {name}")
        print(f"{'='*60}")

        try:
            module = __import__(module_name, fromlist=["run"])
            module.run()
        except Exception as e:
            print(f"\n  ERRO na {name}: {e}")
            print(f"  Para retomar a partir desta fase: python -m etl.run_all {i+1}")
            raise

        elapsed = time.time() - phase_start
        print(f"  Concluído em {elapsed:.1f}s")

    total = time.time() - start
    print(f"\n{'='*60}")
    print(f"ETL completo em {total/60:.1f} minutos")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
