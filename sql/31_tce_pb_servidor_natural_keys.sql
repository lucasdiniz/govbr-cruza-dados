-- TCE-PB servidor: dedupe + UNIQUE INDEX expression-based
--
-- NK 10 cols: (municipio, codigo_ug, cpf_cnpj, matricula, ano_mes,
--              tipo_cargo, valor_vantagem, descricao_cargo, nome_servidor,
--              data_admissao)
-- Pos cleanup de 23 grupos full-row identical, NK eh unique.

-- Step 1: remover full-row dup groups (mantem 1 ocorrencia por NK)
DELETE FROM tce_pb_servidor
WHERE id IN (
  SELECT id FROM (
    SELECT id, ROW_NUMBER() OVER (
      PARTITION BY municipio, codigo_ug, cpf_cnpj, matricula, ano_mes,
                   tipo_cargo, valor_vantagem, descricao_cargo,
                   nome_servidor, data_admissao
      ORDER BY id
    ) AS rn
    FROM tce_pb_servidor
    WHERE municipio IS NOT NULL AND codigo_ug IS NOT NULL
      AND cpf_cnpj IS NOT NULL AND matricula IS NOT NULL AND ano_mes IS NOT NULL
  ) ranked WHERE rn > 1
);
