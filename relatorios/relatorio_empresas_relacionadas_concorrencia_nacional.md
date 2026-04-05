# Relatorio de Auditoria: Empresas Relacionadas Competindo Entre Si ou Recebendo Juntas no Brasil

**Data de Geracao:** 4 de Abril de 2026
**Escopo:** `Q01`, `Q17` e `Q58`, com referencia complementar ao relatorio estadual da Paraiba
**Objetivo:** identificar, em escala nacional, dois tipos de risco:

- empresas do mesmo grupo formal aparecendo na mesma contratacao
- empresas com mesmo endereco aparecendo no mesmo certame

> **Recorte importante:** a `Q58` nacional exportada hoje nao e o universo completo do pais. Ela traz os **500 registros de maior valor estimado** e, depois de deduplicacao por `licitacao + par de CNPJs + endereco`, vira uma amostra de **294 casos unicos**. O relatorio nacional abaixo deve ser lido como **amostra de alto valor**, nao como censo exaustivo.

---

## 1. Resumo Executivo

O cruzamento nacional mostra dois padroes fortes.

Primeiro, a amostra nacional da `Q58` e quase toda formada por **credenciamentos de saude**:

- **294 casos unicos**
- **29 licitacoes**
- **8 UFs**
- **283 casos em modalidade `Credenciamento`**

As UFs mais frequentes nessa amostra sao:

- `RS`: **206** pares unicos
- `PR`: **51**
- `MG`: **32**

Segundo, a `Q01` mostra que o problema nao esta so em endereco compartilhado. Mesmo com filtro mais conservador para focar em nomes empresariais distintos, ainda aparecem:

- **124 casos**
- **58 licitacoes**
- **45 holdings**

Os achados nacionais mais relevantes se concentram em:

1. **consorcios intermunicipais de saude**, onde muitos CNPJs do mesmo endereco entram no mesmo credenciamento;
2. **grupos societarios formais**, onde empresas do mesmo grupo aparecem no mesmo certame;
3. **casos hibridos**, em que a leitura de grupo formal e reforcada por repeticao territorial ou setorial.

---

## 2. Metodologia e Limites

### 2.1. Como cada consulta foi usada

- **Q58:** mesmo endereco na mesma contratacao
- **Q01:** mesmo grupo formal na mesma contratacao
- **Q17:** medida de tamanho de rede por holding, usada com cautela

### 2.2. Ajustes metodologicos

Para este relatorio, foram aplicados tres filtros de prudencia:

1. A `Q58` foi deduplicada por `numero_controle_pncp + cnpj_1 + cnpj_2 + endereco_comum`.
2. A `Q01` foi lida com filtro adicional para separar casos de **nomes empresariais distintos** de meras variacoes de matriz/filial da mesma marca.
3. A `Q17` foi usada como evidencia de **estrutura societaria** e contagem de subsidiarias, nao como medida monetaria definitiva por holding, porque os totais ainda exigem deduplicacao mais rigorosa por base de CNPJ.

### 2.3. O que este relatorio nao afirma

- endereco compartilhado nao prova controle comum
- grupo societario comum nao prova combinacao ilicita
- credenciamento permite entrada de varios prestadores, entao o achado exige leitura contextual do edital e da forma de habilitacao

O valor do relatorio esta em apontar **casos onde varios sinais convergem**.

---

## 3. Caso 1: Araxa/MG e o bloco de credenciamentos do CIMINAS

O consorcio `CONSORCIO INTERFEDERATIVO MINAS GERAIS - CIMINAS`, em `Araxa/MG`, domina o topo da `Q58` nacional.

Casos centrais:

- licitacao `19493732000199-1-000162/2025`
- licitacao `19493732000199-1-000015/2025`
- ambas em `Credenciamento`
- valores estimados de **R$ 29,68 bi** e **R$ 29,59 bi**

No endereco `AIRES MANEIRA, 19`, aparecem tres prestadores no mesmo certame:

- `ASSOC DE ASSIST SOCIAL DA SANTA CASA DE MISERIC ARAXA`
- `RIOS & MOREIRA MEDICINA LTDA`
- `GONTIJO E CIOLETTI SERVICOS DE SAUDE LTDA`

Esse endereco sozinho gera:

- **6 pares unicos**
- **2 licitacoes**
- **1 municipio**

O caso fica mais forte porque o mesmo orgao ainda concentra outros enderecos recorrentes, no mesmo ciclo de credenciamento, como:

- `OTAVIO DE BRITO, 20`
- `JOAO ALVES DO NASCIMENTO, 1781`
- `JOSE AFONSO MENDES CARVALHO, 318`

Leitura investigativa:

- nao e um caso isolado de coincidencia cadastral;
- e um **ambiente contratual** em que varios enderecos compartilhados reaparecem dentro do mesmo consorcio;
- o setor e saude, onde credenciamento de grande escala pode mascarar concentracao real de prestadores.

---

## 4. Caso 2: Carlos Gomes, 700 - cluster medico recorrente no Rio Grande do Sul

O endereco `CARLOS GOMES, 700` e o maior cluster da amostra nacional por quantidade de pares.

Indicadores:

- **67 pares unicos**
- **14 CNPJs distintos**
- **2 licitacoes**
- municipios: `Ijui/RS` e `Lajeado/RS`

Licitacoes associadas:

- `02231696000192-1-000020/2024`
  - `CONSORCIO INTERMUNICIPAL DE SAUDE DO NOROESTE DO ESTADO DO RIO GRANDE DO SUL`
  - **R$ 954,48 mi**
- `07242772000189-1-000035/2025`
  - `CONSORCIO INTERMUNICIPAL DE SERVICOS DO VALE DO TAQUARI`
  - **R$ 1,84 bi**

Exemplos de empresas no mesmo endereco:

- `JULIA PIETROBELLI MIGLIORINI SERVICOS MEDICOS LTDA`
- `PAOLA RENATA KLEIN FAISTEL LTDA`
- `BRENDA NATASHA DIAS BUENO LTDA`
- `EVANDRO TATIM DA SILVA LTDA`
- `LUCAS JOSE MEDEIROS DA SILVA LTDA`

Leitura investigativa:

- o mesmo endereco aparece em dois consorcios diferentes;
- a maioria das empresas e do mesmo nicho medico;
- o volume de combinacoes sugere **pool operacional compartilhado** ou endereco-base de um grupo de prestadores PJ.

---

## 5. Caso 3: Maranhao, 790 - sete CNPJs no mesmo credenciamento em Cascavel/PR

No endereco `MARANHAO, 790`, a `Q58` registra:

- **21 pares unicos**
- **7 CNPJs**
- **1 licitacao**
- `Cascavel/PR`

Licitacao:

- `00944673000108-1-000026/2024`
- orgao: `CONSORCIO INTERMUNICIPAL DE SAUDE DO OESTE DO PARANA`
- valor estimado: **R$ 350 mi**
- modalidade: `Credenciamento`

Exemplos de empresas no mesmo endereco:

- `INSTITUTO DE CIRURGIA CARDIOVASCULAR DO PARANA LTDA`
- `OLDAN CLINICA MEDICA LTDA`
- `CLINICA DE PSIQUIATRIA DR RENATO UCHOA LTDA`
- `ECO SCAN DIAGNOSTICO POR IMAGEM LTDA`
- `CLINICA FREITAS SERVICOS MEDICOS LTDA.`

Leitura investigativa:

- aqui o sinal e mais concentrado que no RS;
- varias especialidades aparecem no mesmo endereco, no mesmo edital, no mesmo municipio;
- o caso e forte para revisar se o endereco funciona como estrutura comum de operacao, faturamento ou habilitacao.

---

## 6. Caso 4: Grupos formais na mesma contratacao

Os casos de `Q01` mostram um eixo diferente: nao importa se o endereco coincide; a relacao formal entre as empresas ja existe.

### 6.1. ZEN Participacoes e combustiveis para o COMAER

Caso:

- holding: `ZEN PARTICIPACOES E ADMINISTRACAO DE BENS LTDA`
- licitacao: `00394429000100-1-001006/2024`
- orgao: `COMANDO DA AERONAUTICA`
- municipio: `Sao Paulo/SP`
- valor estimado: **R$ 11,15 bi**

Empresas relacionadas:

- `RDC REVENDEDORA DE COMBUSTIVEIS LTDA`
- `PAULISTA REVENDEDORA DE COMBUSTIVEIS LTDA`

Leitura:

- sao empresas distintas no mesmo setor;
- o objeto e aquisicao por demanda de combustivel de aviacao;
- o caso e relevante porque combina **alto valor** com **grupo formal comum**.

### 6.2. ORBENK e PROFISER em servicos terceirizados

Caso:

- holding: `ORBENK PARTICIPACOES EIRELI`
- licitacao: `83102475000116-1-000065/2023`
- orgao: `MUNICIPIO DE GUARAMIRIM`
- municipio: `Guaramirim/SC`
- valor estimado: **R$ 10,28 mi**

Empresas relacionadas:

- `ORBENK SERVICOS DE SEGURANCA LTDA`
- `PROFISER SERVICOS PROFISSIONAIS LTDA`

Na estrutura societaria, a holding aparece com:

- **50 subsidiarias**
- **7 bases de CNPJ distintas**

Leitura:

- o caso combina grupo formal grande com contrato de servicos continuos terceirizados;
- e um bom candidato para revisar representacao comercial, propostas e distribuicao de lotes.

### 6.3. PRIME HOLDING como ponte com o relatorio estadual

O caso `PRIME HOLDING`, detalhado no relatorio da Paraiba, tambem entra no mapa nacional:

- **3 licitacoes** com nomes empresariais distintos na `Q01`
- casos em `PB`, `GO` e `RS`
- **10 subsidiarias** e **5 bases de CNPJ distintas** na estrutura do grupo

Isso faz dele um bom elo entre a visao nacional e a investigacao estadual ja documentada em [relatorio_empresas_relacionadas_concorrencia_pb.md](C:\Users\lucas\govbr-cruza-dados\relatorios\relatorio_empresas_relacionadas_concorrencia_pb.md).

---

## 7. Conclusoes

O recorte nacional sugere tres mensagens principais.

1. O risco mais recorrente da `Q58` nacional hoje esta em **credenciamentos de saude**.
2. O risco mais forte da `Q01` esta em **grupos formais com operadoras diferentes no mesmo certame**, especialmente quando o objeto e grande e o mercado e concentrado.
3. Os melhores casos para investigacao manual sao aqueles em que:
   - o mesmo endereco aparece com varios CNPJs;
   - o mesmo orgao repete o padrao em mais de um edital;
   - ou um mesmo grupo formal aparece com empresas distintas no mesmo mercado.

---

## 8. Proximos Passos

1. Criar uma versao **parametrizavel por UF** da `Q58`, para sair da dependencia do corte nacional por `LIMIT 500`.
2. Corrigir a agregacao monetaria da `Q17` por base de CNPJ, para uso seguro em relatorios.
3. Priorizar auditoria manual dos quatro casos deste texto:
   - `CIMINAS/Araxa`
   - `Carlos Gomes, 700`
   - `Maranhao, 790`
   - `ZEN / COMAER`
4. Usar o relatorio estadual da Paraiba como modelo para produzir recortes por UF quando o caso nacional apontar concentracao geografica.

---

## Fontes

1. `queries/fraude_licitacao.sql` (`Q01`)
2. `queries/fraude_rede_societaria.sql` (`Q17`)
3. `queries/fraude_superfaturamento.sql` (`Q58`)
4. `resultados/q01_empresas_do_mesmo_grupo_holding_em_licita_o_concorrente_bid_.csv`
5. `resultados/q17_cadeia_de_holdings_holding_controla_empresas_que_recebem_de_.csv`
6. `resultados/q58_fornecedores_com_mesmo_endere_o_participando_da_mesma_contra.csv`
