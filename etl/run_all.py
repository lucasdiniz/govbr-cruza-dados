"""Orquestrador: executa todas as fases do ETL na ordem correta."""

import sys
import time


def main():
    start = time.time()

    phases = [
        ("Fase 1: Schema", "etl.01_schema"),
        ("Fase 2: Domínio", "etl.02_dominio"),
        ("Fase 3: RFB (Empresas, Estabelecimentos, Sócios, Simples)", "etl.03_rfb"),
        ("Fase 4.1-4.2: PNCP", "etl.04_pncp"),
        ("Fase 4.3-4.5: Emendas", "etl.05_emendas"),
        ("Fase 4.6: CPGF", "etl.06_cpgf"),
        ("Fase 4.7-4.8+5.2: Complementar (BNDES, Holdings, ComprasNet)", "etl.09_complementar"),
        ("Fase 5.1: PGFN", "etl.07_pgfn"),
        ("Fase 5.3: Renúncias Fiscais", "etl.08_renuncias"),
        ("Fase 6: Índices", "etl.10_indices"),
        ("Fase 7: Entity Resolution (Pessoa)", "etl.11_pessoa"),
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
