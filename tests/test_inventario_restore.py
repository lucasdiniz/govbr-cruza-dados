"""Exercita a função fixa do workflow manual sem executar o passo na VM."""
import ast
from pathlib import Path
from textwrap import dedent

import pytest


def _funcoes(workflow):
    arquivo = Path(__file__).resolve().parents[1] / ".github/workflows" / workflow
    arvore = ast.parse(dedent(arquivo.read_text().split("run: |\n", 1)[1]))
    corpo = [item for item in arvore.body if isinstance(item, (ast.Import, ast.FunctionDef))]
    namespace = {}
    exec(compile(ast.Module(body=corpo, type_ignores=[]), "<inventario>", "exec"), namespace)
    return namespace


def _inventario():
    return _funcoes("inventario-restore.yml")["inventario"]


def test_somente_metadados_de_candidatos_regulares(tmp_path):
    funcao = _inventario()
    nome = tmp_path / "govbr-privado.dump"
    nome.write_bytes(b"fixture")
    (tmp_path / "govbr-latest.dump").symlink_to(nome)
    (tmp_path / "govbr-vazio.dump").touch()
    (tmp_path / "govbr-diretorio.dump").mkdir()
    resultado = funcao(tmp_path)
    assert set(resultado) == {"estado", "quantidade", "modificado_utc", "tamanho_mib"}
    assert (resultado["estado"], resultado["quantidade"], resultado["tamanho_mib"]) == ("candidato_local", 1, 1)


def test_ausencia_link_e_limite_nao_simulam_um_restore(tmp_path):
    funcao = _inventario()
    assert funcao(tmp_path / "ausente") == {"estado": "sem_candidato_verificado"}
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    assert funcao(link) == {"estado": "inconclusivo_diretorio"}
    for i in range(257):
        (tmp_path / str(i)).touch()
    assert funcao(tmp_path) == {"estado": "inconclusivo_limite"}


def test_snapshot_do_mesmo_nome_nao_prova_mesma_origem():
    resumir = _funcoes("inventario-restore-azure.yml")["resumir"]
    disco = {"id": "/grupo/disco", "uid": "atual"}
    valido = {"origem": "/GRUPO/DISCO", "uid": "atual", "estado": "Succeeded", "data": "2026-11-25T01:00Z"}
    copias = [valido, dict(valido, uid="anterior"), dict(valido, origem="/outro/disco"),
              dict(valido, estado="Failed")]
    assert resumir(disco, copias) == (1, "2026-11-25")
    assert resumir(disco, []) == (0, "nenhuma")
    with pytest.raises(ValueError):
        resumir({}, [])


@pytest.mark.parametrize("texto,esperado", [
    (b"(AuthorizationFailed) /recurso/privado", "sem_permissao"),
    (b"(MissingSubscriptionRegistration) recurso", "provedor_indisponivel"),
    (b"erro desconhecido /recurso/privado", "erro_cli"),
])
def test_classifica_falha_sem_reproduzir_a_resposta(texto, esperado):
    assert _funcoes("inventario-restore-azure.yml")["categoria_cli"](texto) == esperado
