# Glossário

Vocabulário do domínio público brasileiro usado no `govbr-cruza-dados`. Inclui termos legais, contábeis e técnicos das fontes integradas. Cada termo tem definição curta + onde aparece no projeto + fonte/lei quando aplicável.

Para o catálogo completo de **colunas** das tabelas TCE-PB e dados.pb.gov.br, veja [`dicionario_dados_pb.md`](dicionario_dados_pb.md).

## Sumário por categoria

- [Ciclo orçamentário](#ciclo-orçamentário)
- [Licitação](#licitação)
- [Estrutura governamental](#estrutura-governamental)
- [Sanções e cadastros de irregularidade](#sanções-e-cadastros-de-irregularidade)
- [Empresas e pessoas](#empresas-e-pessoas)
- [Programas sociais e folha](#programas-sociais-e-folha)
- [Crédito e financiamento](#crédito-e-financiamento)
- [Eleições](#eleições)
- [Conflitos de interesse e fraudes](#conflitos-de-interesse-e-fraudes)
- [Regulação de dados](#regulação-de-dados)

---

## Ciclo orçamentário

### Empenho

Ato administrativo que **reserva** dotação orçamentária para um gasto futuro. É o primeiro estágio da despesa pública: o município "promete" pagar X reais a Y fornecedor por Z motivo. Não é pagamento — é compromisso.

- **Tabelas**: `tce_pb_despesa`, `pb_empenho`, `pncp_contratacao`, `pb_pagamento.numero_empenho`
- **Base legal**: Lei 4.320/1964, art. 58
- **Onde aparece**: queries Q01, Q03, Q43-Q58, dialogs de empresa/servidor

### Liquidação

Segundo estágio: verifica que o fornecedor cumpriu sua parte (entregou a mercadoria, prestou o serviço). Sem liquidação, o pagamento é ilegal.

- **Tabelas**: `pb_liquidacao_despesa`, `pb_liquidacao_cge`
- **Base legal**: Lei 4.320/1964, art. 63
- **Caveat investigativo**: empenhos pagos *sem* liquidação correspondente sinalizam fraude (Q101, Q103)

### Pagamento

Terceiro estágio: efetivo desembolso financeiro. Pode ser parcial em relação ao empenho.

- **Tabelas**: `pb_pagamento`, `pb_pagamento_anulacao`, `tce_pb_despesa.valor_pago`
- **Base legal**: Lei 4.320/1964, art. 64

### Anulação de empenho

Cancela total ou parcialmente um empenho não-pago. Comum quando o gasto não vai acontecer (fornecedor desistiu, processo cancelado, ano fiscal acabou).

- **Tabelas**: `pb_empenho_anulacao`, `pb_pagamento_anulacao`
- **Padrão suspeito**: ciclo `empenho → anulação → re-empenho` próximo de eleições (queima de orçamento)

### Suplementação orçamentária

Aumento de dotação em uma rubrica que já existia, durante o exercício. Exige decreto ou lei autorizando.

- **Tabela**: `pb_empenho_suplementacao`
- **Padrão suspeito**: suplementações concentradas em poucos fornecedores ou véspera de eleição (relatório `relatorio_empenhos_semente.md`)

### Dotação orçamentária

Recurso autorizado pela LOA (Lei Orçamentária Anual) para uma despesa específica. Define o teto inicial.

- **Tabela**: `pb_dotacao`
- **Base legal**: Constituição Federal art. 165 + Lei 4.320/1964

### Restos a pagar

Empenhos do exercício anterior que ainda não foram pagos ao fim do ano. Carregam para o exercício seguinte. Grande estoque de restos sinaliza descontrole.

- **Aparece em**: `tce_pb_despesa` filtrável por `exercicio_origem` vs `data_pagamento`

### Subelemento de despesa

Classificação detalhada do que está sendo comprado (4 dígitos): material de consumo, equipamento, serviço de terceiros, etc. Permite agregação por tipo.

- **Coluna**: `tce_pb_despesa.subelemento`, `pb_empenho.subelemento`
- **Codificação**: Portaria STN 163/2001

### Natureza de despesa

Classificação macro (8 dígitos): pessoal, dívida, capital, custeio. Engloba subelemento.

- **Codificação**: Portaria STN 163/2001

### Receita

Entrada de recursos no caixa público — tributos, transferências, royalties, etc.

- **Tabelas**: `tce_pb_receita`, `pb_extras` (alguns datasets)

### Convênio

Acordo formal entre ente público e ONG/outro ente para repasse de recursos com fim específico. NÃO usa licitação.

- **Tabela**: `pb_convenio`, `pb_aditivo_convenio`
- **Padrão suspeito**: convênios com entidades que têm dívida ativa PGFN (Q107)

---

## Licitação

### Licitação

Processo administrativo para escolher fornecedor, exigido pela Constituição e Lei 14.133/2021 (nova Lei de Licitações; substitui parcialmente a 8.666/93).

### Modalidade de licitação

Tipo do processo. Em ordem aproximada de rigor:

- **Concorrência** — valor alto, regras estritas
- **Tomada de preços** — valor médio
- **Convite** — valor baixo, ~3 convidados
- **Pregão (eletrônico ou presencial)** — bens e serviços comuns
- **Concurso** — escolha de trabalho técnico/artístico
- **Leilão** — venda de bens

### Dispensa de licitação

Compra sem processo licitatório formal, autorizada por exceções legais (valor baixo, emergência, calamidade, fornecedor único técnico, etc.).

- **Base legal**: Lei 14.133/2021, art. 75 (era art. 24 da Lei 8.666/93)
- **Caveat**: dispensa por valor (até R$ 50.000 para obras/serviços, R$ 17.600 para outras) é a mais comum e a mais abusada — fracionamento de despesa para ficar abaixo do limite

### Inexigibilidade

Subtipo de dispensa para casos onde competição é impossível (fornecedor exclusivo, artista consagrado, serviço técnico singular).

- **Base legal**: Lei 14.133/2021, art. 74
- **Caveat**: notoria especialidade frequentemente fabricada

### ARP — Ata de Registro de Preços

Sistema onde uma licitação resulta numa **ata** com preços e fornecedor selecionados, e outros órgãos podem aderir à ata sem fazer licitação própria.

- **Base legal**: Lei 14.133/2021, art. 82-83
- **Padrão suspeito**: "carona" (adesão de órgão muito diferente do que motivou a ata original) é frequentemente abusivo

### Pregão eletrônico

Modalidade preferencial para bens e serviços comuns. Disputa em tempo real online via SIASG/ComprasNet ou pregão BB/Banrisul.

- **Base legal**: Lei 10.520/2002, agora absorvida pela Lei 14.133/2021

### Credenciamento

Procedimento para pré-qualificar **todos** os fornecedores que cumprem requisitos, sem competição entre eles. Comum em saúde (médicos, hospitais).

- **Tabela**: `pb_saude` em alguns datasets
- **Padrão suspeito**: credenciamento + concentração em poucos credenciados = monopólio mascarado (`relatorio_monopolios_terceiro_setor_pb.md`)

### Proponente único

Licitação com apenas 1 empresa apresentando proposta. Tecnicamente legal, mas estatisticamente raro em mercados competitivos.

- **MV**: `mv_municipio_pb_risco.pct_proponente_unico`
- **Caveat**: > 40% de licitações com proponente único = score 25/100 no risco composto

### Aditivos (de contrato)

Alterações no contrato após assinatura: valor, prazo, escopo. Limite legal 25% do valor original (50% para reforma de edifício).

- **Tabela**: `pb_aditivo_contrato`, `pb_aditivo_convenio`
- **Base legal**: Lei 14.133/2021, art. 125
- **Padrão suspeito**: aditivos > 25% acumulados (relatorio `relatorio_aditivos_abusivos_estado_pb.md`)

### Sem licitação

Compras em que não houve processo licitatório identificável — pode ser dispensa, inexigibilidade, ARP-carona ou ausência de dado na fonte.

- **MV**: `mv_municipio_pb_risco.pct_sem_licitacao`
- **Caveat**: lógica em revisão (issue [#141](https://github.com/lucasdiniz/govbr-cruza-dados/issues/141))

---

## Estrutura governamental

### UG — Unidade Gestora

Subdivisão organizacional dentro de um órgão público que executa orçamento próprio. Uma prefeitura pode ter UG da Secretaria de Saúde, UG da Educação, etc.

- **Coluna**: `tce_pb_despesa.codigo_ug`, `tce_pb_licitacao.codigo_ug`
- **Tabela**: `pb_unidade_gestora`
- **Caveat**: licitação canônica = `(municipio, ano, codigo_ug, modalidade, numero_licitacao)` — sem `codigo_ug` você junta licitações de UGs diferentes com mesmo `numero_licitacao`

### Esfera de governo

Federal, Estadual, Municipal. Determina jurisdição de fiscalização (TCU para Federal, TCE para Estadual e Municipal).

- **Coluna**: `ceis_sancao.esfera_orgao_sancionador`
- **Caveat**: abrangência de sanção depende da esfera (ver abaixo)

### Município

Menor ente da federação brasileira. Brasil tem 5570 municípios; Paraíba 223.

- **Slug**: `web/utils/slug.py:slugify` — `'João Pessoa'` → `'joao-pessoa'`
- **Coluna canônica**: `nome_municipio` (não `municipio`, que tem variações)

### TCE-PB — Tribunal de Contas do Estado da Paraíba

Órgão estadual que fiscaliza contas dos 223 municípios + governo estadual. Publica dados consolidados em [dados-abertos.tce.pb.gov.br](https://dados-abertos.tce.pb.gov.br).

- **Tabelas**: `tce_pb_despesa`, `tce_pb_servidor`, `tce_pb_licitacao`, `tce_pb_receita`

### PNCP — Portal Nacional de Contratações Públicas

Sistema unificado nacional para publicar todas as contratações públicas, exigido pela Lei 14.133/2021.

- **Tabelas**: `pncp_contratacao`, `pncp_contrato`, `pncp_item`
- **Identificador**: `numero_controle_pncp`

### dados.pb.gov.br

Portal de dados abertos do governo estadual da Paraíba — pagamentos, empenhos, contratos, convênios.

- **Tabelas**: `pb_pagamento`, `pb_empenho`, `pb_contrato`, `pb_convenio`, `pb_*` (~16 tabelas)

### RFB — Receita Federal do Brasil

Mantém a base oficial de CNPJs (~58GB raw), cadastros de empresas, sócios, estabelecimentos. Atualizada mensalmente.

- **Tabelas**: `empresa`, `estabelecimento`, `socio`, `simples`
- **Fonte**: [dadosabertos.rfb.gov.br/CNPJ](https://dadosabertos.rfb.gov.br/CNPJ/)
- **Encoding**: latin-1 (usar `latin1_lines` em `etl/utils.py`)

### SIAPE — Sistema Integrado de Administração de Pessoal

Folha de pagamento do Executivo federal. Dados publicados no Portal da Transparência.

- **Tabelas**: `siape_cadastro`, `siape_remuneracao`

### CGU — Controladoria-Geral da União

Órgão federal de controle interno e transparência. Mantém CEIS, CNEP, CEAF, e outros cadastros.

---

## Sanções e cadastros de irregularidade

### CEIS — Cadastro de Empresas Inidôneas e Suspensas

Lista pública de empresas impedidas de contratar com a administração pública por algum período, em algum escopo. Mantida pela CGU.

- **Tabela**: `ceis_sancao`
- **Fonte**: [Portal da Transparência → CEIS](https://portaldatransparencia.gov.br/sancoes/ceis)
- **Atributos chave**: `tipo_sancao`, `abrangencia`, `data_inicio_sancao`, `data_final_sancao`, `orgao_sancionador`

### CNEP — Cadastro Nacional de Empresas Punidas

Sanções aplicadas em **acordos de leniência** ou condenações da Lei Anticorrupção (12.846/2013). Inclui multas.

- **Tabela**: `cnep_sancao`
- **Fonte**: Portal da Transparência

### CEAF — Cadastro de Expulsões da Administração Federal

Lista de **servidores públicos federais** expulsos (demissão, destituição, cassação). Aplica-se a pessoas físicas, não empresas.

- **Tabela**: `ceaf_expulsao`
- **Match key**: `cpf_digitos_6` + nome normalizado (raramente CPF completo)

### Inidoneidade

Status onde a empresa é declarada incapaz de contratar com **toda** administração pública até cumprir requisitos. Sanção mais grave.

- **Caveat**: empresa inidônea que recebe empenho de qualquer ente público = ilegalidade (relatorio `relatorio_inidoneidade_ilegal_pb.md`)

### Acordo de Leniência

Empresa que confessa irregularidade em troca de redução de multa e cooperação. Status muda em CNEP.

- **Tabela**: `acordo_leniencia`
- **Base legal**: Lei 12.846/2013, art. 16

### Abrangência de sanção

Escopo onde a sanção é válida: nacional, estadual (UF), municipal. Determina se um empenho do município X é ilegal ou só "ruim".

- **Coluna**: `ceis_sancao.abrangencia` (e similares)
- **Caveat investigativo**: empresa com CEIS de abrangência nacional + empenho de qualquer município = vermelho. CEIS municipal de outra UF + empenho aqui = amarelo (informativo)

### Situação cadastral (RFB)

Status da empresa na Receita Federal:
- `2 = Ativa`
- `3 = Suspensa`
- `4 = Inapta`
- `8 = Baixada`

- **Coluna**: `estabelecimento.situacao_cadastral`
- **Padrão suspeito**: empresa baixada/inapta recebendo empenho = fraude (Q14, Q56)

---

## Empresas e pessoas

### CPF — Cadastro de Pessoas Físicas

Identificador único de pessoa física brasileira, 11 dígitos. Frequentemente aparece **mascarado** em fontes públicas (privacidade LGPD).

- **Formatos mascarados**: `***.NNN.NNN-**` (6 dígitos), `***NNN***` (3 dígitos), formato PGFN `XXXNNN.NNNXX`
- **Coluna normalizada**: `cpf_digitos` (6 centrais) ou `cpf_cnpj_norm` (completo se disponível)
- **Convenção do projeto**: mascarar como `***.NNN.NNN-**` em relatórios

### CNPJ — Cadastro Nacional da Pessoa Jurídica

Identificador único de empresa brasileira, 14 dígitos.

- **Estrutura**: `XX.YYY.YYY/ZZZZ-WW`
  - `XX.YYY.YYY` (8 dígitos) = CNPJ básico (identifica a empresa-mãe)
  - `ZZZZ` (4 dígitos) = estabelecimento (matriz = `0001`, filiais = `0002+`)
  - `WW` = dígitos verificadores

### CNPJ básico

Primeiros 8 dígitos do CNPJ. Identifica a **empresa-mãe** (todas as filiais compartilham mesmo CNPJ básico).

- **Caveat crítico**: em queries, NUNCA use `cnpj_basico` para identificar fornecedor — sofre colisão com CPFs cujos primeiros 8 dígitos coincidem. Use `cpf_cnpj` (14 dígitos) com `EXISTS (estabelecimento)`.

### Matriz vs filial

Cada CNPJ completo (14) é um estabelecimento. Filiais compartilham a mesma empresa-mãe (CNPJ básico). Estabelecimento `0001` é a matriz.

- **Coluna**: `estabelecimento.identificador_matriz_filial` (1=matriz, 2=filial)

### Sócio

Pessoa física ou jurídica que detém participação na empresa. Pode ser administrador, representante, sócio-cotista.

- **Tabela**: `socio`
- **Coluna chave**: `qualificacao_socio` (sócio-administrador, sócio-quotista, etc.)
- **Caveat**: CPF do sócio aparece mascarado em `socio.cpf_socio`

### QSA — Quadro de Sócios e Administradores

Lista atual de sócios de uma empresa. Junção de `empresa` + `socio` filtrando ativos.

### Razão social vs nome fantasia

- **Razão social** (`empresa.razao_social`) — nome jurídico oficial
- **Nome fantasia** (`estabelecimento.nome_fantasia`) — nome comercial (opcional)

### Capital social

Valor declarado de investimento dos sócios. Indicador frágil — pode ser fictício.

- **Caveat investigativo**: capital social baixo + recebimento alto = `flag_capital_desproporcional` (`mv_empresa_pb`)

---

## Programas sociais e folha

### Bolsa Família

Programa de transferência de renda federal. Beneficiário identificado por NIS (Número de Identificação Social), município, valor mensal.

- **Tabela**: `bolsa_familia`
- **CPF**: mascarado (`***.NNN.NNN-**`)
- **`cpf_digitos`**: tem **6 dígitos** centrais (não 11 como em outras tabelas — ver ADR-0010 e `COMMENT ON COLUMN bolsa_familia.cpf_digitos`).
- **ETL**: incremental (snapshots mensais cumulativos, ADR-0010). `etl_phase=incremental` carrega tudo; `incremental_only=bolsa_familia.bolsa_familia` só BF.
- **NK**: synthetic md5 das 9 cols (padrão `pb_extras`, `sql/35a-d`). Coluna `_nk_md5` + trigger `BEFORE INSERT`.
- **Caveat investigativo**: servidor público recebendo Bolsa Família simultaneamente = `flag_servidor_bolsa_familia` (`mv_servidor_pb_risco`). Histórico completo agora visível em `/api/servidor/detalhes` (não apenas "Sim/Não" como antes do ADR-0010).

### Novo Bolsa Família

Substituiu o Auxílio Brasil em **março/2023**. Mesma estrutura de tabela (`bolsa_familia`), mesma fonte (Portal da Transparência), URL diferente (`/download-de-dados/novo-bolsa-familia/{YYYYMM}`). `etl/incremental/specs/bolsa_familia.py:_enumerate_buckets` começa em 2023-03.

### NIS — Número de Identificação Social

Identificador para benefícios sociais (Bolsa Família, Auxílio Brasil, INSS). Não é CPF.

### CPGF — Cartão de Pagamento do Governo Federal

Cartão corporativo emitido pelo Banco do Brasil para órgãos federais comprarem itens de pequeno valor.

- **Tabela**: `cpgf_transacao`
- **Padrão suspeito**: fracionamento (vários gastos < R$ 800 do mesmo portador no mesmo dia/loja), conflito com sócios

---

## Crédito e financiamento

### BNDES — Banco Nacional de Desenvolvimento Econômico e Social

Banco federal de fomento. Concede empréstimos a empresas para investimento.

- **Tabela**: `bndes_contrato`
- **Padrão suspeito**: sócio de empresa tomadora de BNDES doando para campanhas eleitorais (`fraude_cruzamentos_avancados.sql` Q307)

### PGFN — Procuradoria-Geral da Fazenda Nacional

Cobra dívida ativa da União (impostos federais não-pagos). Mantém cadastro público.

- **Tabela**: `pgfn_divida`
- **Padrão investigativo**: empresa devedora PGFN recebendo empenho público = `flag_divida_pgfn` no `mv_empresa_pb`

### Dívida ativa

Conjunto de débitos não-pagos inscritos em CDA (Certidão de Dívida Ativa). Cobrança via Procuradoria.

- **Base legal**: Lei 6.830/1980

---

## Eleições

### TSE — Tribunal Superior Eleitoral

Órgão máximo da Justiça Eleitoral. Publica dados de candidatos, doadores, prestação de contas, patrimônio declarado.

- **Tabelas**: `tse_candidato`, `tse_bem_candidato`, `tse_receita_candidato`, `tse_despesa_candidato`

### Doador eleitoral

Pessoa física ou jurídica que doa para candidato ou partido. Limites legais por eleição.

- **Tabela**: `tse_receita_candidato`
- **Padrão investigativo**: sócio de fornecedor doando para prefeito do município que contrata a empresa (Q33, Q34)

### Patrimônio declarado

Bens declarados pelo candidato no momento da candidatura. Evolução entre candidaturas indica enriquecimento.

- **Tabela**: `tse_bem_candidato`

---

## Conflitos de interesse e fraudes

### Conflito de interesses

Situação em que interesse privado de servidor público entra em conflito com sua função. Pode ser legal (servidor público com empresa privada em outro setor) ou ilegal (servidor que decide compra contrata empresa onde é sócio).

- **Caveat investigativo central** do projeto — atravessa servidor × empresa × empenho × Bolsa Família × CEAF

### Porta giratória

Servidor público que se torna sócio/empregado de empresa do setor que regulava (ou vice-versa).

- **Caveat**: no projeto, "porta giratória" também é usado para servidor ativo que é sócio de empresa fornecedora do mesmo município (Q302)

### Pejotização

Servidor público "contratado como empresa" (CNPJ) em vez de via concurso, fugindo da Constituição. Quando empresa do servidor recebe empenhos do órgão onde ele atua = fraude flagrante.

- **Relatórios**: `relatorio_pejotizacao_*.md`

### Empresa fenix

Empresa com CNPJ que fecha (baixada) e reabre com CNPJ novo mantendo sócios/atividade. Estratégia para fugir de sanção CEIS herdada.

- **Detecção**: sócios em comum + atividade similar + datas próximas

### Empresa laranja

Empresa registrada em nome de pessoa sem capacidade financeira/técnica para a atividade — usada para esconder beneficiário real.

- **Sinais**: capital social baixo + recebimento alto, sócio com Bolsa Família

### Cartel

Grupo de empresas que combinam preços ou divisão de mercado em licitações.

- **Detecção**: mesmo endereço cadastral, sócios em comum, propostas em sequência numérica

### Queima de orçamento (de dezembro)

Concentração anormal de empenhos no fim do ano fiscal para não "perder" dotação.

- **MV**: `mv_municipio_pb_risco.pct_dezembro` (peso 20 do score composto)
- **Query**: Q66

### Bid rigging

Combinação prévia entre licitantes para manipular o resultado. Sub-tipo de cartel.

- **Sinal**: empresas-fachada apresentando "propostas-cobertura" para que uma específica ganhe

### Empenho-semente

Suplementação orçamentária concentrada em poucos fornecedores, pouco antes de eleição.

- **Relatório**: `relatorio_empenhos_semente.md`

---

## Regulação de dados

### LGPD — Lei Geral de Proteção de Dados (Lei 13.709/2018)

Marco legal brasileiro para proteção de dados pessoais.

- **Bases legais que o projeto usa**:
  - **Art. 7º III** — administração pública para execução de políticas públicas
  - **Art. 7º IV** — realização de estudos por órgão de pesquisa
  - **Art. 26** — uso compartilhado de dados pelo Poder Público
- **Doc**: [`../DATA-LICENSE.md`](../DATA-LICENSE.md), [`privacidade.md`](privacidade.md)

### LAI — Lei de Acesso à Informação (Lei 12.527/2011)

Garante acesso público a dados governamentais. Fundamenta a publicação de quase todas as fontes do projeto.

### ANPD — Autoridade Nacional de Proteção de Dados

Órgão regulador da LGPD. Pode aplicar sanções, ordenar bloqueio/eliminação de dados pessoais tratados sem base legal.

### Dado pessoal sensível

Categoria especial da LGPD (Art. 5º II): saúde, orientação política, religiosa, sexual, dados biométricos. Bolsa Família **não** se enquadra mecanicamente, mas combinação com município + nome se aproxima.

### Mascaramento

Técnica de redução de identificabilidade de dado pessoal. No projeto, padrão canônico para CPF é `***.NNN.NNN-**` (mantém 6 dígitos centrais), validado por `scripts/audit_report_identifiers.py --strict`.

### Anonimização

Processo de remover identificabilidade direta e indireta. **Diferente** de mascaramento — anonimização exige que o dado não possa ser re-identificado por qualquer meio. CPF mascarado em 6 dígitos centrais + nome + município ainda é re-identificável → não é anonimização técnica.

---

## Referências

- **Lei 14.133/2021** — Nova Lei de Licitações e Contratos
- **Lei 8.666/1993** — Lei de Licitações (antiga, ainda vigente para alguns processos)
- **Lei 12.846/2013** — Lei Anticorrupção / Improbidade
- **Lei 12.527/2011** — Lei de Acesso à Informação (LAI)
- **Lei 13.709/2018** — Lei Geral de Proteção de Dados (LGPD)
- **Lei 4.320/1964** — Normas Gerais de Direito Financeiro
- **Lei 10.520/2002** — Pregão (absorvida pela 14.133)
- **Lei 6.830/1980** — Execução Fiscal / Dívida Ativa
- **Portaria STN 163/2001** — Classificação da despesa pública
- **Constituição Federal**, art. 37 XXI — Princípio da licitação obrigatória
