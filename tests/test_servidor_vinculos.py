from web.routes.cidade import _agrupar_vinculos_servidor


def vinculo(municipio="Cidade A", codigo_ug="123", matricula="001",
            cargo="Secretario", admissao="2025-07-01", primeiro="202601",
            ultimo="202608", salario=16000):
    return {
        "municipio": municipio, "codigo_ug": codigo_ug, "matricula": matricula,
        "descricao_cargo": cargo, "data_admissao": admissao,
        "primeiro_registro": primeiro, "ultimo_registro": ultimo,
        "maior_salario": salario,
    }


def test_consolida_municipio_nulo_e_sentinela_sem_duplicar_cargo():
    registros = [
        vinculo(),
        vinculo(municipio="\\N", primeiro="202507", ultimo="202511", salario=11000),
        vinculo(municipio=None, primeiro="202507", ultimo="202511", salario=11000),
        vinculo(municipio="\\N", matricula="002", cargo="Diretor",
                admissao="2025-01-01", primeiro="202501", ultimo="202507", salario=11000),
        vinculo(municipio=None, matricula="002", cargo="Diretor",
                admissao="2025-01-01", primeiro="202501", ultimo="202507", salario=11000),
    ]
    resultado = _agrupar_vinculos_servidor(registros)
    assert len(resultado) == 2
    assert all(v["municipio"] == "Cidade A" for v in resultado)
    assert resultado[0]["primeiro_registro"] == "202507"
    assert resultado[0]["ultimo_registro"] == "202608"
    assert resultado[0]["maior_salario"] == 16000
    assert resultado[1]["descricao_cargo"] == "Diretor"
    assert registros[1]["municipio"] == "\\N"
    assert all("matricula" not in v and "codigo_ug" not in v for v in resultado)


def test_preserva_vinculos_de_outras_unidades_matriculas_e_admissoes():
    registros = [
        vinculo(), vinculo(matricula="002"),
        vinculo(codigo_ug="456"), vinculo(admissao="2025-08-01"),
    ]
    assert len(_agrupar_vinculos_servidor(registros)) == 4


def test_municipio_ambiguo_ou_outra_ug_nao_e_inferido():
    registros = [
        vinculo(municipio="Cidade A"),
        vinculo(municipio="Cidade B"),
        vinculo(municipio="\\N"),
        vinculo(municipio=None, codigo_ug="456"),
    ]
    resultado = _agrupar_vinculos_servidor(registros)
    assert len(resultado) == 4
    assert sum(v["municipio"] == "Municipio nao informado" for v in resultado) == 2
    assert {v["municipio"] for v in resultado} == {
        "Cidade A", "Cidade B", "Municipio nao informado",
    }


def test_sentinelas_sem_nome_valido_preservam_historico_e_salario():
    registros = [
        vinculo(municipio=valor, primeiro="202501", ultimo=None, salario=None)
        for valor in (None, "", "  ", "\\N", "NULL", "-")
    ]
    registros.append(vinculo(municipio=" - ", primeiro=None, ultimo="202508", salario=12000))
    assert _agrupar_vinculos_servidor(registros) == [{
        "municipio": "Municipio nao informado",
        "descricao_cargo": "Secretario", "data_admissao": "2025-07-01",
        "primeiro_registro": "202501", "ultimo_registro": "202508",
        "maior_salario": 12000,
    }]
