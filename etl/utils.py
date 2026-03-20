"""Funções utilitárias para normalização e parse de dados brasileiros."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation


def normalize_name(name: str | None) -> str | None:
    """Remove acentos, uppercase, colapsa espaços."""
    if not name:
        return None
    # Remove acentos
    nfkd = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Uppercase + colapsa espaços
    cleaned = re.sub(r"\s+", " ", without_accents.upper().strip())
    return cleaned if cleaned else None


def parse_date_br(date_str: str | None) -> date | None:
    """
    Converte datas brasileiras em vários formatos:
    - '20230115' → date(2023, 1, 15)
    - '15/01/2023' → date(2023, 1, 15)
    - '2023-01-15' → date(2023, 1, 15)
    - '' ou '00000000' → None
    """
    if not date_str:
        return None
    s = date_str.strip().strip('"')
    if not s or s == "00000000" or s == "0":
        return None

    try:
        if len(s) == 8 and s.isdigit():
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        if "/" in s:
            parts = s.split("/")
            if len(parts[0]) == 4:  # YYYY/MM/DD
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            else:  # DD/MM/YYYY
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
        if "-" in s:
            parts = s.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None
    return None


def parse_decimal_br(value_str: str | None) -> Decimal | None:
    """
    Converte decimais brasileiros: '120000000000,00' → Decimal('120000000000.00')
    Também aceita formato americano: '120000000000.00'
    """
    if not value_str:
        return None
    s = value_str.strip().strip('"')
    if not s or s == "-":
        return None

    try:
        # Se tem vírgula e não tem ponto, é formato BR
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        # Se tem ponto e vírgula, vírgula é decimal
        elif "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        return Decimal(s)
    except InvalidOperation:
        return None


def extract_cpf_masked(cpf_raw: str | None) -> str | None:
    """
    Extrai 6 dígitos centrais do CPF mascarado.
    '***240659**' → '240659'
    '***.246.579-**' → '246579'
    """
    if not cpf_raw:
        return None
    # Remove tudo que não é dígito ou asterisco
    digits = re.sub(r"[^\d]", "", cpf_raw.replace("*", ""))
    if len(digits) == 6:
        return digits
    # Tenta extrair posições 3-8 do CPF numérico completo
    if len(digits) >= 9:
        return digits[3:9]
    return digits if digits else None


def clean_cnpj(cnpj: str | None) -> str | None:
    """Remove pontuação e pad com zeros à esquerda."""
    if not cnpj:
        return None
    digits = re.sub(r"[^\d]", "", cnpj)
    if not digits:
        return None
    return digits.zfill(14)


def clean_cpf(cpf: str | None) -> str | None:
    """Remove pontuação e pad com zeros à esquerda."""
    if not cpf:
        return None
    digits = re.sub(r"[^\d]", "", cpf)
    if not digits:
        return None
    return digits.zfill(11)


def safe_strip(value: str | None) -> str | None:
    """Strip + retorna None se vazio."""
    if not value:
        return None
    s = value.strip().strip('"')
    return s if s else None


def latin1_lines(filepath: str):
    """Generator que lê arquivo Latin-1 e yielda linhas como str UTF-8."""
    with open(filepath, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            yield line


def parse_csv_line(line: str, delimiter: str = ";") -> list[str]:
    """
    Parse simples de uma linha CSV.
    Trata aspas duplas como quote character.
    """
    import csv
    import io
    reader = csv.reader(io.StringIO(line), delimiter=delimiter, quotechar='"')
    for row in reader:
        return [f.strip() for f in row]
    return []
