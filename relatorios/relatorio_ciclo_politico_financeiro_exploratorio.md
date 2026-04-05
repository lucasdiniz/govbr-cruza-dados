# Relatorio Exploratorio: Ciclo Politico-Financeiro e Limites dos Achados Atuais

**Data de Geracao:** 5 de Abril de 2026
**Escopo:** `Q56`, `Q57`, `Q72`, `Q79`, com apoio de `Q34` e `Q37`
**Objetivo:** testar se o repositorio ja sustenta, com seguranca, uma narrativa de ciclo entre `doacao eleitoral`, `emenda`, `eleicao` e `recebimento de recursos publicos`.

> **Conclusao central:** o recorte originalmente pensado para a Paraiba nao fechou com densidade suficiente. O melhor material atual esta em um caso nacional forte da `Q56`, alguns casos secundarios que exigem validacao adicional e um bloco de resultados negativos/limitados para `PB`.

---

## 1. Resumo Executivo

O cruzamento politico-financeiro foi testado em quatro frentes:

- `Q56`: doador de campanha -> contrato PNCP
- `Q57`: emenda parlamentar -> doacao TSE
- `Q72`: doador de campanha -> prefeito eleito -> pagamento municipal
- `Q79`: credor PF do estado da Paraiba -> candidato TSE

O resultado foi misto.

### 1.1. O que apareceu com forca

A melhor evidencia atualmente publicavel esta na `Q56`:

- **SE / Valmir dos Santos Costa / FM Producoes e Eventos**
- **26 contratos pos-eleicao**
- **R$ 5.220.000,00** em contratos distintos
- janela de **5 de julho de 2024** a **16 de janeiro de 2026**

Esse caso e o unico em que:

- o CNPJ doador e consistente com a empresa na Receita Federal;
- o nome do fornecedor no PNCP conta a mesma historia;
- a sequencia temporal e clara.

### 1.2. O que apareceu, mas ainda nao esta pronto para relatorio afirmativo

- A `Q57` gera hits, mas os maiores casos atuais parecem refletir **sobreposicao de CNPJ institucional** ou problema semantico na interpretacao do doador.
- A `Q56` tambem traz alguns casos secundarios em que o CNPJ bate, mas o campo `nm_doador` do TSE nao conta a mesma historia do CNPJ.
- A `Q79` encontrou apenas **9 pessoas fisicas** que receberam pagamentos do estado da Paraiba e tambem aparecem como candidatos no TSE, em valores modestos.

### 1.3. O que nao apareceu

No recorte diretamente paraibano, os cruzamentos mais fortes vieram vazios:

- `Q56` com contrato em `PB`: **0**
- `Q57` com candidato `PB` ou favorecido `PB`: **0**
- `Q72`: **0**
- `Q37`: **0**

Isso significa que, com as regras atuais, **nao ha base suficiente para um relatorio afirmativo de ciclo politico-financeiro na Paraiba**.

---

## 2. Metodologia

### 2.1. Criterio de confianca

Para considerar um achado como utilizavel em texto investigativo, foram exigidos tres testes:

1. **coerencia de CNPJ**
   o CNPJ doador precisava apontar para um ator empresarial verificavel;

2. **coerencia de nome**
   a razao social da RFB precisava ser compativel com o fornecedor do contrato ou com o favorecido da emenda;

3. **coerencia temporal**
   o contrato ou recebimento precisava ocorrer depois da eleicao ou depois da doacao.

Quando um hit passava no join tecnico, mas falhava nesses testes de consistencia, ele foi tratado como **exploratorio** e nao como prova narrativa.

### 2.2. Limites das queries

- `Q56` usa correspondencia por **base de 8 digitos** do CNPJ, o que exige validacao adicional por nome.
- `Q57` hoje junta emenda e doacao pelo mesmo criterio de base de CNPJ e, nos maiores casos, produziu pares institucionalmente estranhos.
- `Q79`, apesar do nome, hoje cobre apenas a parte **credor PF = candidato**, e nao a parte "ou doador".

---

## 3. Caso Forte: FM Producoes e Eventos e a campanha de Valmir dos Santos Costa

### 3.1. O que fecha nesse caso

Este foi o caso mais consistente da `Q56`.

- **UF do candidato:** `SE`
- **Candidato:** `VALMIR DOS SANTOS COSTA`
- **Cargo:** `Governador`
- **Partido:** `PL`
- **CNPJ doador:** `45.226.544/0001-04`
- **Razao social na RFB:** `FM PRODUCOES E EVENTOS LTDA`
- **Total doado considerado na analise:** **R$ 147.000,00**

Depois da eleicao, o mesmo CNPJ aparece como fornecedor em:

- **26 contratos distintos**
- **R$ 5.220.000,00** em valor global somado
- periodo entre **5 de julho de 2024** e **16 de janeiro de 2026**

### 3.2. Distribuicao dos contratos

Os contratos se concentram em eventos e shows municipais, com forte presenca em Sergipe e tambem ocorrencias em Alagoas e Bahia.

Exemplos:

- `13110408000168-2-000005/2026`
  - `MUNICIPIO DE SIRIRI`
  - `SE`
  - **R$ 250.000,00**
  - assinatura em **16 de janeiro de 2026**
- `13107180000157-2-000004/2026`
  - `MUNICIPIO DE RIACHAO DO DANTAS`
  - `SE`
  - **R$ 250.000,00**
  - assinatura em **16 de janeiro de 2026**
- `13098181000182-2-000001/2026`
  - `MUNICIPIO DE ITABAIANINHA`
  - `SE`
  - **R$ 250.000,00**
  - assinatura em **5 de janeiro de 2026**
- `12207403000195-2-000002/2026`
  - `MUNICIPIO DE LIMOEIRO DE ANADIA`
  - `AL`
  - **R$ 250.000,00**
  - assinatura em **14 de janeiro de 2026**

### 3.3. Leitura investigativa

O caso nao prova troca direta de favor, mas e forte porque:

- o doador e a empresa contratada sao o mesmo ator empresarial;
- a sequencia temporal e clara;
- ha repeticao de contratos depois da disputa eleitoral;
- o objeto contratual e homogeneo, o que reduz ruido interpretativo.

Entre todos os cruzamentos testados nesta sessao, este foi o **melhor caso disponivel para aprofundamento manual**.

---

## 4. Caso Secundario: CNPJ da Facebook em campanhas locais de RO

### 4.1. O que o join encontrou

A `Q56` tambem encontrou tres candidatos a vereador em `RO` associados ao CNPJ:

- **CNPJ:** `13.347.016/0001-17`
- **Razao social na RFB:** `FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.`

Candidatos:

- `EUNICE EVANGELISTA`
- `JAZAM ANTONIO DA SILVA`
- `MARIA CIPRIANO MOREIRA`

Contratos pos-eleicao vinculados ao mesmo CNPJ/base:

- **3 contratos**
- **R$ 550.000,00**
- orgaos como `IFSP` e `FURB`
- periodo entre **27 de junho de 2024** e **1 de dezembro de 2025**

### 4.2. Por que este caso ainda nao e publicavel

Apesar de o CNPJ e a razao social fecharem com `FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.`, o campo `nm_doador` do TSE veio como:

- `Direcao Nacional`

Esse conflito entre **CNPJ** e **nome do doador** impede leitura segura sem validacao no dado bruto do TSE.

Leitura correta neste momento:

- o caso e **interessante**;
- o caso **nao deve ser publicado como afirmacao fechada** sem reabrir a origem do TSE.

---

## 5. Q57: Sinal existe, mas a query ainda nao esta pronta para relatorio final

### 5.1. O que a query encontrou

A `Q57` retornou **92 linhas** com os filtros atuais.

Os maiores casos incluem combinacoes como:

- `ESTADO DE MINAS GERAIS` recebendo emendas e aparecendo tambem como CNPJ doador em registros do TSE ligados a `JAZY GUEDES SILVA`;
- `ESTADO DO TOCANTINS` com padrao parecido em torno de `STALIN JUAREZ GOMES BUCAR`;
- `MUNICIPIO DE BATURITE` com padrao semelhante para `JOSE LUCIANO SILVA`.

### 5.2. Por que isso e um problema

Nos maiores hits, o mesmo CNPJ aparece como:

- ente favorecido por emenda
- e doador registrado no TSE

Esse padrao pode ate esconder algo real, mas do jeito que esta ele sugere pelo menos uma destas situacoes:

- semantica inadequada do campo de doador no TSE;
- sobreposicao de CNPJ institucional;
- necessidade de distinguir partido, direcao partidaria e ente favorecido antes do join.

Conclusao:

- a `Q57` e util como radar;
- a `Q57` **nao esta pronta para sustentar texto afirmativo** neste momento.

---

## 6. O que o recorte paraibano mostrou

### 6.1. Achados negativos

Para o recorte originalmente planejado para `PB`, o resultado atual foi:

- `Q56` com contrato em `PB`: **0**
- `Q57` com candidato `PB` ou favorecido `PB`: **0**
- `Q72`: **0**
- `Q37`: **0**

Isso vale ser documentado porque evita forcar uma narrativa que o banco nao entrega.

### 6.2. O unico sinal local aproveitavel: Q79

A `Q79` encontrou **9 pessoas fisicas** que receberam pagamentos do estado da Paraiba e tambem aparecem como candidatos no TSE.

Top casos:

- `FABIO GOMES DA SILVA`
  - **R$ 111.265,62**
  - candidato relacionado: `EDIO VIEIRA DE SOUZA`
  - cargo: `DEPUTADO FEDERAL`
- `MAGNA SUELY DOS SANTOS GUEDES QUER`
  - **R$ 80.617,62**
  - candidata relacionada: `CLECIUS VINICIUS PINTO`
  - cargo: `VICE-PREFEITO`
- `JOSE GOMES DE DEUS`
  - **R$ 56.211,68**
  - candidato relacionado: `FRANZ WALLACE DA SILVA GRANA`
  - cargo: `VEREADOR`

Mas esse bloco ainda e fraco para um relatorio central porque:

- os valores sao relativamente modestos;
- os candidatos vinculados nao sao atores do ecossistema politico da Paraiba;
- o cruzamento atual e apenas `credor PF = candidato`, sem camada de doador ou contrato.

---

## 7. Conclusoes

O repositorio ainda **nao sustenta** um relatorio forte de ciclo politico-financeiro na Paraiba.

O que ele sustenta hoje e:

1. **um caso nacional forte e coerente**, envolvendo `FM PRODUCOES E EVENTOS LTDA` e a campanha de `VALMIR DOS SANTOS COSTA`;
2. **um caso nacional secundario**, envolvendo o CNPJ da `FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.`, que depende de validacao do TSE;
3. **uma frente exploratoria em Q57**, ainda nao pronta para publicacao;
4. **um pequeno bloco de pagamentos estaduais a PFs com vinculo eleitoral**, insuficiente para narrativa robusta em `PB`.

---

## 8. Proximos Passos

1. Revisar `Q56` para diferenciar melhor:
   - CNPJ completo
   - base de CNPJ
   - fornecedor pessoa fisica
2. Reprocessar `Q57` com validacao adicional de:
   - tipo de favorecido
   - natureza do doador
   - distincao entre ente publico e direcao partidaria
3. Completar `Q79` com a parte prometida no titulo:
   - `credor PF = doador TSE`
4. So depois disso retomar um relatorio especificamente paraibano.

---

## Fontes

1. `queries/fraude_superfaturamento.sql` (`Q56`, `Q57`)
2. `queries/fraude_tse.sql` (`Q34`, `Q37`)
3. `queries/fraude_tce_pb.sql` (`Q72`)
4. `queries/fraude_dados_pb.sql` (`Q79`)
5. `resultados/q34_doador_de_campanha_que_tamb_m_fornecedor_do_governo.csv`
6. `resultados/q56_doador_de_campanha_contrato_pncp.csv`
7. `resultados/q72_doador_de_campanha_prefeito_eleito_pagamento_municipal.csv`
8. `resultados/q79_credor_pf_do_estado_candidato_ou_doador_tse.csv`
