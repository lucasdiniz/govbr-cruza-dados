"""Orquestrador: executa todas as fases do ETL na ordem correta."""

import os
import re
import sys
import time
import traceback


PHASES = [
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


def _list_phases():
    """Lista todas as fases com step number e label."""
    print("Fases disponiveis:", flush=True)
    print(f"  {'Step':>4}  {'Label':<12}  Descricao", flush=True)
    print(f"  {'----':>4}  {'-----':<12}  ---------", flush=True)
    for i, (name, module) in enumerate(PHASES):
        # Extract "Fase X" label from name
        label = name.split(":")[0]
        desc = name.split(":", 1)[1].strip() if ":" in name else ""
        print(f"  {i+1:>4}  {label:<12}  {desc}  ({module})", flush=True)


def _resolve_phase(arg: str) -> int:
    """Resolve um argumento de fase para o indice (0-based) na lista PHASES.

    Aceita:
      - Fase label (prioridade): "6", "4.6", "5.1" (matched against "Fase N" in the name)
      - "fase6", "fase 6", "Fase 6" (prefix variations)
      - Step number (fallback): numbers not matching any Fase label are treated as 1-based positions

    Note: Fase labels have priority. "6" matches "Fase 6: Indices" (step 11),
    not step 6. Use --list to see the full mapping.

    Returns the 0-based index into PHASES, or raises ValueError.
    """
    arg = arg.strip()

    # Try "faseN" / "fase N" prefix (case-insensitive)
    m = re.match(r'^[Ff]ase\s*(.+)$', arg)
    label = m.group(1).strip() if m else arg

    # 1) Try matching against phase labels ("Fase 6", "Fase 4.6", etc.)
    for i, (name, _) in enumerate(PHASES):
        # Extract the label part, e.g. "6" from "Fase 6: Indices"
        # or "4.1-4.2" from "Fase 4.1-4.2: PNCP"
        phase_m = re.match(r'^Fase\s+([\d.+\-]+)', name)
        if phase_m:
            phase_label = phase_m.group(1)
            if label == phase_label:
                return i
            # Also match just the first number for ranges: "4" matches "Fase 4.1-4.2"
            if '.' not in label and '-' not in label:
                if phase_label.startswith(label) and (
                    len(phase_label) == len(label)
                    or phase_label[len(label)] in '.+-'
                ):
                    return i

    # 2) Try as step number (1-based position in the list)
    try:
        step = int(label)
        if 1 <= step <= len(PHASES):
            return step - 1
    except ValueError:
        pass

    raise ValueError(
        f"Fase '{arg}' nao encontrada. Use --list para ver as fases disponiveis."
    )


def _print_usage():
    print("Uso: python -m etl.run_all [opcoes] [fase_inicial]", flush=True)
    print("", flush=True)
    print("  fase_inicial  Label da fase (ex: 6, 4.6, fase6) ou step number (fallback)", flush=True)
    print("", flush=True)
    print("Opcoes:", flush=True)
    print("  --list        Lista todas as fases e sai", flush=True)
    print("  --help        Mostra esta ajuda", flush=True)
    print("", flush=True)
    print("Exemplos:", flush=True)
    print("  python -m etl.run_all              # ETL completo", flush=True)
    print("  python -m etl.run_all 6            # A partir da Fase 6 (Indices)", flush=True)
    print("  python -m etl.run_all fase6        # Mesmo que '6'", flush=True)
    print("  python -m etl.run_all 4.6          # A partir da Fase 4.6 (CPGF)", flush=True)
    print("  python -m etl.run_all --list       # Lista todas as fases", flush=True)


def main():
    start = time.time()

    phases = PHASES
    errors = []

    # Parse arguments
    start_phase = 0
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        _print_usage()
        sys.exit(0)

    if "--list" in args:
        _list_phases()
        sys.exit(0)

    if args:
        try:
            start_phase = _resolve_phase(args[0])
        except ValueError as e:
            print(f"Erro: {e}", flush=True)
            print("", flush=True)
            _print_usage()
            sys.exit(1)

    if start_phase > 0:
        print(f"Iniciando a partir do step {start_phase + 1}: "
              f"{phases[start_phase][0]}", flush=True)

    for i, (name, module_name) in enumerate(phases):
        if i < start_phase:
            continue

        phase_start = time.time()
        print(f"\n{'='*60}", flush=True)
        _emit_notice(f"[{i+1}/{len(phases)}] {name}")
        print(f"{'='*60}", flush=True)

        try:
            module = __import__(module_name, fromlist=["run"])
            module.run()
        except Exception as e:
            # Extract the phase label for a friendlier resume command
            phase_label = re.match(r'^(Fase\s+[\d.+\-]+)', name)
            label_hint = phase_label.group(1).replace("Fase ", "") if phase_label else str(i + 1)
            _emit_notice(f"ERRO na {name}: {e}")
            print(f"  Para retomar: python -m etl.run_all {label_hint}", flush=True)
            traceback.print_exc()
            errors.append((name, str(e)))

        elapsed = time.time() - phase_start
        _emit_notice(f"Concluído {name} em {elapsed:.1f}s")

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
