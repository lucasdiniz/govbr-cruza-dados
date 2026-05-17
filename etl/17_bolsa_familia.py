"""Bolsa Familia — fase classica desativada (migrada para framework incremental).

A carga de Bolsa Familia agora roda via `etl/incremental/specs/bolsa_familia.py`
(framework P1-P6, snapshots mensais acumulativos). Esta fase classica permanece
no orquestrador `etl/run_all.py` apenas como no-op para preservar o indice de
fases (etl_phase numerico do deploy.yml e tests).

Acionamento:
- `etl_phase=incremental` (com `incremental_only=bolsa_familia.bolsa_familia` opcional)
- Schema canonico (`sql/17_schema_bolsa_familia.sql`) continua sendo aplicado
  pela fase 1 (`etl.01_schema`) de forma idempotente (CREATE IF NOT EXISTS).
- Migration `sql/41_bolsa_familia_incremental.sql` aplicada pelo step
  "ETL: Incremental" do deploy.

Ver ADR-0010 para a decisao completa.
"""


def run():
    print(
        "    SKIP: Bolsa Familia migrou para ETL incremental "
        "(etl_phase=incremental, spec bolsa_familia.bolsa_familia). "
        "Ver ADR-0010 e docs/etl-incremental-guide.md.",
        flush=True,
    )
    return


if __name__ == "__main__":
    run()
