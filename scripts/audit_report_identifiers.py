"""Audita CNPJs e CPFs citados em relatórios Markdown.

Uso:
    python scripts/audit_report_identifiers.py
    python scripts/audit_report_identifiers.py --report relatorios/relatorio_x.md
    python scripts/audit_report_identifiers.py --strict          # apenas checa CPFs nao-mascarados, offline (sem DB)

Saída:
    TSV em stdout com status por citação (modo padrao).
    Modo --strict: imprime CPFs nao-mascarados encontrados e retorna exit code
    1 se houver qualquer violacao (uso em CI / pre-commit).

Observações:
    - A validação de CNPJ usa a base local RFB (`empresa` + `estabelecimento`).
    - A validação de CPF só é tentada quando o CPF completo aparece no texto e quando
      existe uma tabela com pessoa física identificável na base local. Como a maior
      parte dos relatórios usa CPF mascarado, o status tende a ser `cpf_nao_validado`.
    - Modo --strict NAO conecta ao banco: faz apenas analise de texto, util em CI.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import unicodedata
from dataclasses import dataclass

# Import lazy: get_conn nao deve ser importado em modo --strict (que roda offline).
# A funcao audit_report() faz o import dentro do corpo quando precisa do banco.


STOPWORDS = {
    "LTDA",
    "LTD",
    "SA",
    "EIRELI",
    "ME",
    "MEI",
    "EPP",
    "EMPRESA",
    "COMERCIO",
    "SERVICOS",
    "SERVICO",
    "SOCIEDADE",
    "SOC",
    "ANONIMA",
    "DE",
    "DA",
    "DO",
    "DAS",
    "DOS",
    "E",
    "THE",
    "BRASIL",
    "INDUSTRIA",
    "IMPORTACAO",
    "EXPORTACAO",
    "PARAIBA",
    "CNPJ",
    "CPF",
}


NAME_CNPJ_PATTERNS = [
    re.compile(
        r"(?P<name>[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ0-9&\-\.,/ '\"]+?)\s*"
        r"\(CNPJ[: ]+?(?P<cnpj>\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})\)",
        re.I,
    ),
    re.compile(
        r"\*\*[^:\n]+:\*\*\s*(?P<name>[^\n]+?)\s*"
        r"\(CNPJ[: ]+?(?P<cnpj>\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})\)",
        re.I,
    ),
]

CNPJ_PATTERN = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b")
CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
# CPF formatado completo — pega so CPFs nao-mascarados, sem falsos positivos
# de codigos numericos de 11 digitos. Usado em --strict.
CPF_FORMATTED_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


@dataclass
class AuditRow:
    report: str
    kind: str
    identifier: str
    cited_name: str
    official_name: str
    status: str
    note: str


def normalize_text(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.upper()


def token_set(value: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[A-Z0-9]+", normalize_text(value))
        if len(tok) > 2 and tok not in STOPWORDS
    }


def find_named_cnpjs(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for pattern in NAME_CNPJ_PATTERNS:
        for match in pattern.finditer(text):
            cnpj = re.sub(r"\D", "", match.group("cnpj"))
            name = " ".join(match.group("name").strip().split())
            if len(cnpj) == 14 and name and cnpj not in found:
                found[cnpj] = name
    return found


def find_unmasked_cpfs(text: str) -> list[tuple[int, str, str]]:
    """Retorna lista de (linha, cpf, contexto) com CPFs formatados nao-mascarados.

    Considera nao-mascarado qualquer CPF no padrao `NNN.NNN.NNN-NN` sem `*` na
    string. O padrao canonico do projeto para CPF parcialmente exposto e
    `***.NNN.NNN-**` (mantem so os 6 digitos centrais).
    """
    violations: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in CPF_FORMATTED_PATTERN.finditer(line):
            # Ja-mascarado tem '*' na mesma string. CPF_FORMATTED_PATTERN nao
            # casa string com '*', entao todo match aqui e' nao-mascarado.
            cpf = match.group(0)
            start, end = match.span()
            ctx_start = max(0, start - 30)
            ctx_end = min(len(line), end + 30)
            context = line[ctx_start:ctx_end].strip()
            violations.append((lineno, cpf, context))
    return violations


# Raiz do repo, derivada do caminho fisico deste script. Garante que --strict
# rode da mesma forma independente do cwd (pre-commit hook, CI, chamada manual).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_RELATORIOS_DIR = _REPO_ROOT / "relatorios"


def list_reports(single_report: str | None) -> list[pathlib.Path]:
    if single_report:
        return [pathlib.Path(single_report)]
    return sorted(_RELATORIOS_DIR.glob("*.md"))


def audit_report(path: pathlib.Path) -> list[AuditRow]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    named_cnpjs = find_named_cnpjs(text)
    raw_cnpjs = {re.sub(r"\D", "", m) for m in CNPJ_PATTERN.findall(text)}
    raw_cpfs = {re.sub(r"\D", "", m) for m in CPF_PATTERN.findall(text)}

    rows: list[AuditRow] = []
    # Import lazy: so quem nao usa --strict abre conexao Postgres. Permite que
    # --strict rode em ambientes sem psycopg2/python-dotenv instalados.
    from etl.db import get_conn   # noqa: WPS433 — import dentro de funcao por design
    conn = get_conn()
    cur = conn.cursor()

    for cnpj in sorted(raw_cnpjs):
        if len(cnpj) != 14:
            continue
        cur.execute(
            """
            select e.razao_social, coalesce(est.nome_fantasia, '')
            from estabelecimento est
            join empresa e on e.cnpj_basico = est.cnpj_basico
            where est.cnpj_completo = %s
            limit 1
            """,
            (cnpj,),
        )
        row = cur.fetchone()
        cited_name = named_cnpjs.get(cnpj, "")
        if not row:
            rows.append(
                AuditRow(path.name, "CNPJ", cnpj, cited_name, "", "nao_encontrado_rfb", "CNPJ nao localizado na base RFB local")
            )
            continue

        official_name, trade_name = row
        if not cited_name:
            rows.append(
                AuditRow(
                    path.name,
                    "CNPJ",
                    cnpj,
                    "",
                    official_name,
                    "sem_nome_no_relatorio",
                    f"RFB: {official_name}" + (f" | fantasia: {trade_name}" if trade_name else ""),
                )
            )
            continue

        overlap_razao = len(token_set(cited_name) & token_set(official_name))
        overlap_fantasia = len(token_set(cited_name) & token_set(trade_name))
        if overlap_razao > 0 or overlap_fantasia > 0:
            rows.append(
                AuditRow(
                    path.name,
                    "CNPJ",
                    cnpj,
                    cited_name,
                    official_name,
                    "match",
                    f"fantasia={trade_name}" if trade_name else "",
                )
            )
        else:
            rows.append(
                AuditRow(
                    path.name,
                    "CNPJ",
                    cnpj,
                    cited_name,
                    official_name,
                    "suspeito",
                    f"fantasia={trade_name}" if trade_name else "",
                )
            )

    for cpf in sorted(raw_cpfs):
        if len(cpf) != 11:
            continue
        rows.append(
            AuditRow(
                path.name,
                "CPF",
                cpf,
                "",
                "",
                "cpf_nao_validado",
                "O repositório não tem uma tabela canônica única para validar nome por CPF completo em todos os relatórios.",
            )
        )

    cur.close()
    conn.close()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="Caminho de um relatório específico")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="So checa CPFs nao-mascarados (offline, sem DB). Exit 1 se houver violacoes.",
    )
    args = parser.parse_args()

    if args.strict:
        return run_strict(args.report)

    print("report\tkind\tidentifier\tcited_name\tofficial_name\tstatus\tnote")
    for report in list_reports(args.report):
        for row in audit_report(report):
            values = [
                row.report,
                row.kind,
                row.identifier,
                row.cited_name,
                row.official_name,
                row.status,
                row.note,
            ]
            print("\t".join(v.replace("\t", " ").replace("\n", " ") for v in values))
    return 0


def run_strict(single_report: str | None) -> int:
    """Modo strict — so analise de texto, sem DB. Exit 1 se algum CPF nao-mascarado.

    Anchored em `_RELATORIOS_DIR` (derivado de `__file__`), nao do cwd, para evitar
    falsos negativos silenciosos quando rodado de outro diretorio.
    """
    reports = list_reports(single_report)
    if not reports:
        print(
            "[strict] ERRO: nenhum relatorio encontrado. "
            f"Esperava .md em {_RELATORIOS_DIR} ou --report apontando para arquivo valido.",
            file=sys.stderr,
        )
        return 2

    total_violations = 0
    for report in reports:
        if not report.exists():
            print(f"[strict] ERRO: {report} nao existe.", file=sys.stderr)
            return 2
        text = report.read_text(encoding="utf-8", errors="ignore")
        violations = find_unmasked_cpfs(text)
        if violations:
            for lineno, cpf, context in violations:
                print(f"{report}:{lineno}: CPF nao-mascarado encontrado: {cpf} | contexto: {context}", file=sys.stderr)
            total_violations += len(violations)

    if total_violations > 0:
        print(
            f"\n[strict] {total_violations} CPF(s) nao-mascarado(s) encontrado(s). "
            "Mascarar com padrao ***.NNN.NNN-** (mantem so 6 digitos centrais).",
            file=sys.stderr,
        )
        return 1
    print(f"[strict] OK — {len(reports)} relatorio(s) auditado(s), nenhum CPF nao-mascarado encontrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
