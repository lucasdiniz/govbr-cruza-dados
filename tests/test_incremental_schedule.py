"""Regressoes offline da decisao executada pelo agendador GitHub-hosted."""

import io
import json
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "incremental-schedule.yml"
CODIGO = textwrap.dedent(
    WORKFLOW.read_text(encoding="utf-8").split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
)
PREPARO, DECISAO = CODIGO.split('runs = json.loads(gh("run"', 1)
DECISAO = 'runs = json.loads(gh("run"' + DECISAO


@pytest.fixture
def agendador(monkeypatch, tmp_path):
    monkeypatch.setenv("REPO", "teste/repo")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.setenv("TCE_INTERVAL_DAYS", "28")
    monkeypatch.setenv("BF_MAX_MONTHS", "1")
    monkeypatch.setenv("BF_BASELINE", "2026-08")
    namespace = {}
    exec(PREPARO, namespace)
    monkeypatch.setattr(namespace["time"], "sleep", lambda _: None)
    return namespace


def resposta(conteudo, headers=None, url="https://exemplo.gov.br/arquivo.zip"):
    r = io.BytesIO(conteudo)
    r.headers = headers or {}
    r.geturl = lambda: url
    return r


def test_lista_oficial_identifica_meses_sem_sondar_zip(agendador, monkeypatch):
    html = b"""
    arquivos.push({"ano":"2026","mes":"08","origem":"NovoBolsaFamilia"});
    arquivos.push({"ano":"2026","mes":"09","origem":"OutroBeneficio"});
    """
    abrir = Mock(return_value=resposta(html))
    monkeypatch.setattr(agendador["urllib"].request, "urlopen", abrir)
    assert agendador["bf_publicados"]() == {"2026-08"}
    assert abrir.call_count == 1


@pytest.mark.parametrize("conteudo", [b"<html>Access denied</html>", b"arquivos.push({invalido});"])
def test_lista_ilegivel_falha_em_vez_de_sucesso_sem_trabalho(agendador, monkeypatch, conteudo):
    monkeypatch.setattr(
        agendador["urllib"].request, "urlopen",
        lambda *args, **kwargs: resposta(conteudo),
    )
    with pytest.raises(RuntimeError, match="Lista oficial BF falhou"):
        agendador["bf_publicados"](tries=1)


def test_403_de_zip_nao_e_tratado_como_mes_nao_publicado(agendador, monkeypatch):
    abrir = Mock(side_effect=HTTPError("https://exemplo.gov.br", 403, "Forbidden", {}, None))
    monkeypatch.setattr(agendador["urllib"].request, "urlopen", abrir)
    with pytest.raises(RuntimeError, match="403"):
        agendador["probe"]("https://exemplo.gov.br", ranged=True, tries=2)
    assert abrir.call_count == 2


def test_probe_recupera_erro_transitorio_e_le_tamanho_total(agendador, monkeypatch):
    abrir = Mock(side_effect=[
        URLError("timeout"),
        resposta(b"P", {"Content-Type": "application/octet-stream",
                        "Content-Range": "bytes 0-0/330703661"}),
    ])
    monkeypatch.setattr(agendador["urllib"].request, "urlopen", abrir)
    assert agendador["probe"]("https://exemplo.gov.br/202609", ranged=True, tries=2) == (True, 330703661)
    assert abrir.call_args.args[0].get_header("Range") == "bytes=0-0"


def preparar_decisao(agendador):
    agora = datetime.now(timezone.utc)
    ultimo_mes = (agora.replace(day=1) - timedelta(days=32)).strftime("%Y%m")
    agendador["os"].environ["BF_BASELINE"] = ultimo_mes
    agendador["gh"] = lambda *args: json.dumps([{
        "databaseId": 1, "displayTitle": "Deploy to Azure VM - incremental todas [2026]",
        "status": "completed", "conclusion": "success", "createdAt": agora.isoformat(),
    }]) if args[0] == "run" else '{"artifacts":[]}'
    agendador["probe"] = Mock(return_value=(True, 100_000_000))
    ano, mes = int(ultimo_mes[:4]), int(ultimo_mes[4:])
    return f"{ano + 1}-01" if mes == 12 else f"{ano}-{mes + 1:02d}"


def test_mes_nao_listado_nao_dispara_nem_sonda_zip(agendador):
    proximo = preparar_decisao(agendador)
    agendador["bf_publicados"] = lambda: {f"{int(proximo[:4]) - 1}-12"}
    with pytest.raises(SystemExit) as exc:
        exec(DECISAO, agendador)
    assert exc.value.code == 0
    assert all("novo-bolsa-familia" not in c.args[0] for c in agendador["probe"].call_args_list)
    assert Path(agendador["os"].environ["GITHUB_OUTPUT"]).read_text() == "dispatch=false\n"


def test_mes_listado_dispara_apenas_bf_e_um_mes(agendador):
    proximo = preparar_decisao(agendador)
    ano, mes = map(int, proximo.split("-"))
    seguinte = f"{ano + 1}-01" if mes == 12 else f"{ano}-{mes + 1:02d}"
    agendador["bf_publicados"] = lambda: {proximo, seguinte}
    exec(DECISAO, agendador)
    output = Path(agendador["os"].environ["GITHUB_OUTPUT"]).read_text()
    assert "dispatch=true\n" in output
    assert "specs=bolsa_familia.bolsa_familia\n" in output
    assert f"buckets={proximo}\n" in output


def test_mes_listado_com_zip_invalido_falha(agendador):
    proximo = preparar_decisao(agendador)
    agendador["bf_publicados"] = lambda: {proximo}
    agendador["probe"] = Mock(side_effect=[(True, 100_000_000), (False, 0)])
    with pytest.raises(RuntimeError, match="ZIP indisponivel/invalido"):
        exec(DECISAO, agendador)


@pytest.mark.parametrize("baseline", ["", "2026-13", "2026-00", "invalido"])
def test_watermark_desconhecido_ou_invalido_falha(agendador, baseline):
    preparar_decisao(agendador)
    agendador["os"].environ["BF_BASELINE"] = baseline
    with pytest.raises(SystemExit) as exc:
        exec(DECISAO, agendador)
    assert exc.value.code == 1
