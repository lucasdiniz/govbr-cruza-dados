# Relatorio de Auditoria: Empresas Relacionadas Competindo Entre Si ou Recebendo Juntas na Paraiba

**Data de Geracao:** 4 de Abril de 2026
**Escopo:** combinacao de `Q01`, `Q17`, `Q58` e `Q71`
**Objetivo:** identificar grupos empresariais, empresas com endereco compartilhado e redes de controle que aparecem:

- na mesma contratacao
- no mesmo mercado municipal
- ou nas duas situacoes ao mesmo tempo

> **Disclaimer:** nenhum dos achados abaixo prova conluio, fraude ou simulacao de concorrencia por si so. O valor investigativo esta na combinacao de sinais independentes: controle formal comum, endereco comum, repeticao em varios municipios e atuacao no mesmo nicho economico.

---

## 1. Resumo Executivo

O cruzamento entre `Q01`, `Q17`, `Q58` e `Q71` aponta tres frentes de risco na Paraiba:

1. **Controle formal comum no mesmo certame**
   A `Q01` encontrou um caso direto em `PB` de duas empresas do mesmo grupo participando da mesma contratacao: `VMI TECNOLOGIAS LTDA.` e `ALFA MED SISTEMAS MEDICOS LTDA`, ambas vinculadas a `PRIME HOLDING E SERVICOS LTDA`, em licitacao do Fundo Municipal de Saude de Joao Pessoa.

2. **Mesmo endereco na mesma contratacao e repeticao em varios municipios**
   A variante `PB` da `Q58` identificou **48 pares unicos** de fornecedores com mesmo endereco participando da mesma contratacao, distribuidos em **28 licitacoes**, **25 enderecos** e **14 municipios**.

3. **Clusters persistentes de pagamento municipal**
   A `Q71` mostra que alguns desses mesmos enderecos nao aparecem so em um certame isolado; eles reaparecem em dezenas de municipios com alto volume de pagamentos.

Os dois casos mais fortes para aprofundamento manual sao:

- `BOSSUET WANDERLEY, 411`:
  tres empresas medicas no mesmo certame em Santa Luzia e, ao mesmo tempo, presenca em **51 municipios** com **R$ 11,09 mi** em **5.471 empenhos**.
- `BR 101 SUL, S/N`:
  tres distribuidoras/fornecedoras da area de saude aparecendo em **8 licitacoes** de `PB` e tambem em **31 municipios** na `Q71`, com **R$ 20,64 mi** em **2.310 empenhos**.

---

## 2. Metodologia

### 2.1. Evidencias combinadas

O relatorio usa quatro tipos de evidencia:

- **Q01:** empresas do mesmo grupo formal (holding) na mesma contratacao
- **Q17:** holdings com varias subsidiarias recebendo de multiplas fontes
- **Q58:** fornecedores com mesmo endereco participando da mesma contratacao PNCP
- **Q71:** fornecedores com mesmo endereco recebendo no mesmo municipio na base do TCE-PB

### 2.2. Leitura investigativa

Cada consulta mede uma coisa diferente:

- `Q01` testa **controle societario formal**
- `Q17` testa **capacidade de captura por grupo**
- `Q58` testa **co-presenca no mesmo certame**
- `Q71` testa **recorrencia territorial e comercial**

O melhor caso nao e o maior valor isolado, e sim o caso em que mais de um desses sinais aparece ao mesmo tempo.

### 2.3. Observacao tecnica sobre a Q58

Para a analise em `PB`, foi usada uma variante local da `Q58` com o mesmo criterio logico da query original, mas filtrada por `cc.uf = 'PB'` para viabilizar execucao exploratoria no banco local.

---

## 3. Caso 1: PRIME HOLDING em licitacao da saude de Joao Pessoa

### 3.1. Achado principal

A `Q01` encontrou **1 caso em PB** de empresas do mesmo grupo formal aparecendo na mesma contratacao:

- **Holding:** `PRIME HOLDING E SERVICOS LTDA` (`10328635000176`)
- **Empresas relacionadas:**
  - `VMI TECNOLOGIAS LTDA.` (`02659246000103`)
  - `ALFA MED SISTEMAS MEDICOS LTDA` (`11405384000149`)
- **Orgao:** `FUNDO MUNICIPAL DE SAUDE`
- **Municipio:** `Joao Pessoa`
- **Licitacao:** `08715618000140-1-000094/2024`
- **Objeto:** aquisicao de equipamentos medicos e de diagnostico por imagem para a rede municipal

### 3.2. Relevancia adicional da Q17

Na `Q17`, a mesma holding aparece com **10 subsidiarias** e **5 bases de CNPJ distintas**, o que reforca que nao se trata de um ator isolado.

Para este caso, a `Q17` foi usada como evidencia de **estrutura de grupo** e nao como medida monetaria definitiva, porque os totais agregados por holding ainda exigem deduplicacao adicional por base de CNPJ para evitar inflacao por matriz/filial.

Esse nao e um caso de "mesmo endereco" ou mera semelhanca nominal. E um caso de **controle formal comum** no mesmo mercado de saude, dentro do mesmo certame.

### 3.3. Hipotese investigativa

Esse tipo de achado deve ser tratado como prioridade alta porque:

- a relacao societaria e objetiva
- o objeto e de alto valor e tecnicamente sensivel
- a contratacao envolve equipamentos de saude e diagnostico, setor em que a concorrencia aparente importa muito

O ponto a verificar manualmente e se houve:

- disputa efetiva entre propostas
- lances ou propostas com comportamento coordenado
- sobreposicao de representantes, procuradores ou documentacao

### 3.4. Contexto historico do grupo em Joao Pessoa

O relatorio antigo sobre equipamentos medicos em Joao Pessoa foi absorvido aqui porque tratava do mesmo nucleo factual com base mais estreita. O que permanece relevante e:

- o grupo `PRIME HOLDING` ja aparecia associado a certames de equipamentos medicos e diagnostico por imagem no municipio;
- a `ALFA MED SISTEMAS MEDICOS LTDA` tambem aparece com presenca relevante em contratos municipais na Paraiba;
- o valor investigativo do caso nao esta em afirmar "cartel", mas em documentar **participacao simultanea de controladas do mesmo grupo no mesmo mercado publico sensivel**.

---

## 4. Caso 2: Bossuet Wanderley, 411 - rede medica que compete e recebe em escala

### 4.1. Evidencia da Q58

Na variante `PB` da `Q58`, o endereco `BOSSUET WANDERLEY, 411` aparece em **1 licitacao** relevante:

- **Municipio/Orgao:** `MUNICIPIO DE SANTA LUZIA`
- **Licitacao:** `09090689000167-1-000085/2025`
- **Valor estimado:** **R$ 11,41 mi**
- **Empresas no mesmo endereco:**
  - `NEUREDERM SERVICOS MEDICOS LTDA` (`24055312`)
  - `MAIA XAVIER SAUDE E BEM ESTAR LTDA` (`29748462`)
  - `DR SERGIO MEDEIROS - CARDIOLOGISTA E ECOCARDIOGRAFISTA LTDA` (`51807646`)

Ou seja: tres empresas do mesmo endereco aparecem juntas no mesmo certame.

### 4.2. Evidencia da Q71

O mesmo endereco ja era um dos clusters mais fortes da `Q71`:

- **51 municipios**
- **R$ 11.090.155,72** em pagamentos agregados
- **5.471 empenhos**

Exemplos de municipios com volume relevante:

- `Patos`: **R$ 2,32 mi**
- `Sao Jose do Sabugi`: **R$ 1,08 mi**
- `Passagem`: **R$ 803 mil**
- `Santa Luzia`: **R$ 727 mil**
- `Mae d'Agua`: **R$ 684 mil**

### 4.3. Leitura

Esse e um dos casos mais fortes do repositorio porque combina:

- **mesmo endereco**
- **mesmo certame**
- **mesmo nicho setorial (saude)**
- **presenca em dezenas de municipios**

Separadamente, cada sinal ainda admite explicacao legitima. Em conjunto, o caso passa a merecer auditoria manual de contratos, escalas, socios, administradores e objetos pagos.

---

## 5. Caso 3: BR 101 Sul, S/N - distribuidores de saude em varios certames e municipios

### 5.1. Evidencia da Q58

O endereco `BR 101 SUL, S/N` foi o caso mais recorrente na amostra `PB` da `Q58`:

- **8 licitacoes**
- **20 ocorrencias de pares**
- **3 CNPJs distintos**
- **4 municipios contratantes:** `Cabedelo`, `Joao Pessoa`, `Pombal` e `Uirauna`

Empresas envolvidas:

- `MEDVIDA DISTRIBUIDORA DE MEDICAMENTOS HOSPITALAR LTDA` (`06132785`)
- `CIRURGICA MONTEBELLO LTDA` (`08674752`)
- `SO SAUDE PRODUTOS HOSPITALAR LTDA` (`29775313`)

Maior caso observado:

- `FUNDO MUNICIPAL DE SAUDE`, `Joao Pessoa`
- licitacao `08715618000140-1-000021/2025`
- **R$ 20.836.159,52**

### 5.2. Evidencia da Q71

O mesmo endereco tambem aparece com forte capilaridade na `Q71`:

- **31 municipios**
- **R$ 20.639.508,63** em pagamentos agregados
- **2.310 empenhos**

Entre os municipios com mais volume no cluster:

- `Joao Pessoa`: **R$ 6,20 mi**
- `Areia`: **R$ 3,72 mi**
- `Pombal`: **R$ 1,59 mi**
- `Uirauna`: **R$ 1,20 mi**
- `Mamanguape`: **R$ 986 mil**

### 5.3. Leitura

O sinal aqui e menos "clinico" que o da Bossuet, mas ainda e forte:

- as empresas compartilham endereco
- reaparecem em varios certames
- operam no mesmo segmento de insumos/saude
- aparecem tanto na PNCP quanto na despesa municipal do TCE-PB

Esse tipo de padrao e compativel com:

- operador comercial comum
- centro logistico/administrativo compartilhado
- pulverizacao de fornecimento entre CNPJs proximos

---

## 6. Caso 4: Liberdade, 3230 - sinal mais fraco, mas repetido

O endereco `LIBERDADE, 3230` aparece em quatro licitacoes na amostra `PB` da `Q58`:

- `SEGINFO COMERCIO & SERVICOS EMPRESARIAIS LTDA`
- `GWC INDUSTRIA, IMPORTACAO E DISTRIBUICAO DE ELETRONICOS LTDA`
- `LEGACY DISTRIBUIDORA DE INFORMATICA E ELETROELETRONICOS LTDA`

Municipios encontrados na `Q58`:

- `Alagoa Nova`
- `Sao Bento`
- `Patos`
- `Itaporanga`

Na `Q71`, o mesmo endereco aparece, mas com intensidade muito menor:

- **3 municipios**
- **R$ 88.875,13**
- **22 empenhos**

Este e um caso util como contraste: mostra um padrao de endereco comum com recorrencia, mas ainda sem a mesma forca probatoria dos clusters da saude.

---

## 7. Conclusoes

O repositorio ja permite separar tres niveis de risco:

1. **Risco alto**
   Casos em que ha mais de um sinal ao mesmo tempo: mesmo endereco, mesmo certame, mesmo setor e repeticao territorial. `BOSSUET WANDERLEY, 411` e `BR 101 SUL, S/N` entram aqui.

2. **Risco alto com base formal**
   Casos de mesmo grupo societario na mesma contratacao. O caso `PRIME HOLDING` entra aqui.

3. **Risco moderado**
   Casos com endereco compartilhado e repeticao limitada, mas sem corroboracao suficiente por setor ou escala. `LIBERDADE, 3230` entra aqui.

O principal ganho metodologico deste relatorio e mostrar que o problema nao esta so em "mesmo endereco" nem so em "mesmo grupo". O padrao mais valioso surge quando diferentes linhas de evidencia convergem sobre os mesmos atores ou os mesmos enderecos.

---

## 8. Recomendacoes

1. Priorizar auditoria manual do caso `BOSSUET WANDERLEY, 411`.
2. Revisar o processo da licitacao `08715618000140-1-000094/2024` em `Joao Pessoa` para verificar a atuacao de empresas ligadas a `PRIME HOLDING`.
3. Cruzar os tres CNPJs do endereco `BR 101 SUL, S/N` com:
   - socios e administradores
   - atas e contratos da SES-PB e do Fundo Municipal de Saude de Joao Pessoa
   - objetos e lotes por item
4. Criar uma `Q58_PB` dedicada em `queries/` para analise estadual, sem depender de ajuste de planner em sessao.
5. Produzir um segundo relatorio focado no bloco politico-financeiro (`Q56`, `Q57`, `Q72`, `Q79`).

---

## Fontes

1. `queries/fraude_licitacao.sql` (`Q01`)
2. `queries/fraude_rede_societaria.sql` (`Q17`)
3. `queries/fraude_superfaturamento.sql` (`Q58`)
4. `queries/fraude_tce_pb.sql` (`Q71`)
5. Saida exploratoria local derivada da `Q58` com filtro `cc.uf = 'PB'`
6. `resultados/q71_fornecedores_com_mesmo_endere_o_comercial_recebendo_no_mesmo.csv`
