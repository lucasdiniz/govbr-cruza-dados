"""Sonda somente os metadados; nao conecta ao banco nem baixa os ZIPs."""
import logging
from datetime import datetime, timedelta, timezone

from etl.rfb_sync import SYNC_ORDER, _candidate_months, expected_zips, head_file

log = logging.getLogger(__name__)


def mes_estavel(meses: list[str], agora: datetime) -> str:
    nomes = expected_zips(SYNC_ORDER)
    for mes in meses:
        cnaes = head_file(mes, "Cnaes.zip")
        if cnaes is None:
            log.info("%s: Cnaes.zip ainda nao publicado", mes)
            continue
        recente = cnaes[1]
        faltantes = []
        for nome in nomes:
            if nome == "Cnaes.zip":
                continue
            info = head_file(mes, nome)
            if info is None:
                faltantes.append(nome)
            else:
                recente = max(recente, info[1])
        if faltantes:
            log.info("%s: aguardando %s", mes, ", ".join(faltantes))
        elif agora - recente < timedelta(hours=24):
            log.info("%s: aguardando 24h desde %s", mes, recente.isoformat())
        else:
            log.info("%s: %d ZIPs completos; alteracao mais recente: %s", mes, len(nomes), recente.isoformat())
            return mes
    return ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("month=" + mes_estavel(_candidate_months(3), datetime.now(timezone.utc)))
