# Relatório de Investigação: Servidora Destituída pela CGU em Cargo Municipal de Mesma Pasta — Caso Maria do Socorro Gadelha Campos de Lira

**Data de Geração:** 11 de maio de 2026
**Base de Dados:** CEAF (Cadastro de Expulsões da Administração Federal, CGU) × folha de pessoal do município de João Pessoa (TCE-PB) × Diário Oficial da União (DOU) × dados abertos do CNPJ/RFB.
**Metodologia:** o painel municipal do transparenciapb.org cruza automaticamente os 6 dígitos centrais do CPF e o nome normalizado de cada servidor da folha municipal contra o CEAF/CGU; o caso foi sinalizado pelo cruzamento e a cronologia abaixo foi reconstruída a partir das publicações oficiais do DOU, do Portal da Transparência e do site oficial da Prefeitura de João Pessoa.

> **Disclaimer:** Este relatório consolida fatos publicados em fontes oficiais (DOU, Portal da Transparência da CGU, SAPL da Assembleia Legislativa da Paraíba e portais oficiais dos órgãos citados). Cada afirmação está vinculada à sua fonte primária. Os fatos jurídicos descritos — exoneração, instauração de PAD, conversão em destituição, registro em CEAF — são atos administrativos com publicidade legal e estão íntegros nas URLs citadas. Eventual recurso administrativo ou judicial em curso não foi localizado nas fontes públicas consultadas; cabe aos órgãos de controle e ao Ministério Público a apuração subsequente quanto à compatibilidade de manutenção em cargo municipal de natureza equivalente.

---

## 1. Resumo Executivo

A servidora **Maria do Socorro Gadelha Campos de Lira** (CPF nº ***.256.054-**, matrícula federal nº 2933908) foi punida pela Controladoria-Geral da União (CGU) em 29 de dezembro de 2022 (publicação no DOU em 02/01/2023) com a sanção de **destituição de cargo em comissão**, com base no Art. 127, V, c/c Art. 135 da Lei nº 8.112/90, por **descumprir os deveres de zelo, observância às normas legais e regulamentares e moralidade administrativa** previstos nos incisos I, III e IX do Art. 116 da mesma Lei. O ato — Portaria CGU nº 3.655, de 29/12/2022 — converteu retroativamente sua exoneração de 1º de janeiro de 2019 (Portaria nº 438 do Ministro Chefe da Casa Civil) na penalidade de destituição, no Processo Administrativo Disciplinar nº 00190.101924/2020-94.

A sanção foi registrada no Cadastro de Expulsões da Administração Federal (CEAF) sob o número 278654.

Apesar dessa punição federal, a servidora segue há mais de quatro anos no cargo de **Secretária Municipal de Habitação Social** (Semhab) de João Pessoa, na gestão do prefeito Cícero Lucena (PP) — nomeada em janeiro de 2021, mantida durante todo o primeiro mandato, recolocada após a reeleição de outubro de 2024 e ainda no cargo em maio de 2026. Em 26 de agosto de 2025, a Assembleia Legislativa da Paraíba aprovou (Projeto de Resolução nº 356/2025, de autoria do deputado estadual Hervázio Bezerra, PSB) a concessão a ela da Medalha Epitácio Pessoa "pelos relevantes serviços prestados à sociedade brasileira, especialmente no âmbito da habitação social".

O currículo oficial submetido por ela própria à ALPB para justificar a honraria **omite** o cargo do qual foi punida pela CGU (Secretária-Executiva do Ministério do Desenvolvimento Regional).

O caso foi sinalizado **automaticamente** pelo painel municipal de João Pessoa no transparenciapb.org, no card "Servidores já expulsos da Adm. Federal" do bloco de triagem rápida.

**Indicadores-chave:**

| Indicador | Valor |
|---|---|
| Cadastro CEAF | 278654 |
| Tipo de sanção | Destituição (Art. 135 c/c Art. 127 V, Lei 8.112/90) |
| Data da sanção | 29/12/2022 (Portaria CGU 3.655/2022) |
| Publicação no DOU | 02/01/2023, Edição 1-C, Seção 2, pág. 62 |
| Processo administrativo | PAD 00190.101924/2020-94 |
| Órgão sancionador | Controladoria-Geral da União |
| Ministro signatário | Wagner de Campos Rosario |
| Tempo no cargo municipal após a sanção (até a data deste relatório) | > 40 meses |
| Tempo até a homenagem pela ALPB após a sanção | ≈ 31 meses |
| Cargo federal punido | Secretária-Executiva, Ministério do Desenvolvimento Regional |
| Cargo municipal atual | Secretária Municipal de Habitação Social, Prefeitura de João Pessoa |
| Prefeito responsável pela nomeação e manutenção | Cícero Lucena (PP) |

---

## 2. Metodologia: Como o Caso Foi Identificado

### 2.1. Cruzamento Automatizado CEAF × Folha Municipal

O portal transparenciapb.org constrói, para cada um dos 223 municípios da Paraíba, um painel de risco que inclui o card **"Servidores já expulsos da Adm. Federal"**. Esse card é alimentado por uma materialized view (`mv_servidor_pb_risco`) que cruza:

1. Servidores da folha de pagamento municipal (fonte: SAGRES/TCE-PB), por mês de exercício.
2. Registros do CEAF — Cadastro de Expulsões da Administração Federal, mantido pela CGU e publicado em dados abertos no Portal da Transparência.

O matching usa duas condições simultâneas:
- Os 6 dígitos centrais do CPF (única parte normalmente preservada nas duas bases, já que ambas mascaram o CPF).
- Nome normalizado (sem acentuação, em maiúsculas, com pontuação removida).

Quando os dois campos coincidem entre uma linha do CEAF e uma linha da folha municipal, o servidor é sinalizado no painel. O CPF ***.256.054-** (parcial) e o nome MARIA DO SOCORRO GADELHA CAMPOS DE LIRA coincidem nas duas bases.

### 2.2. Link Direto para o Caso no Painel

```
https://transparenciapb.org/cidade/joao-pessoa?d=servidor&d_cpf6=256054&d_nome=MARIA+DO+SOCORRO+GADELHA+CAMPOS+DE+LIRA&d_snome=MARIA+DO+SOCORRO+GADELHA+CAMPOS+DE+LIRA&d_cnpjs=13519354&d_tab=dialog-section-3
```

### 2.3. Validação Manual das Fontes Oficiais

Cada elemento da narrativa foi confirmado em fonte oficial. As fontes estão consolidadas na seção 6.

---

## 3. Cronologia Documentada

| Data | Fato | Fonte oficial |
|---|---|---|
| **27/10/1960** | Nascimento da servidora. | CV oficial submetido à ALPB (matéria 130965/2025). |
| **Ago/1982 – Mar/2011** | Bancária da Caixa Econômica Federal. | CV oficial. |
| **Jul/2007 – Jan/2009** | Cedida pela Caixa, exerce a presidência da Companhia Estadual de Habitação Popular da Paraíba (CEHAP). | CV oficial. |
| **Jan/2013 – Jan/2018** | Secretária Municipal de Habitação Social de João Pessoa, gestão Luciano Cartaxo. | CV oficial. |
| **29/12/2017** | Nomeada Secretária Nacional de Habitação do Ministério das Cidades pelo Ministro Chefe da Casa Civil Eliseu Padilha (governo Temer). | DOU 29/12/2017. |
| **01/01/2019** | **Exonerada** do cargo de Secretária Nacional de Habitação do Ministério das Cidades (DAS 101.6). Portaria nº 438 do Ministro Chefe da Casa Civil Onyx Dornelles Lorenzoni (governo Bolsonaro), publicada no DOU em 11/01/2019, Seção 2. **Exoneração comum, sem mancha.** | DOU 11/01/2019, Seção 2. |
| **2019 – Ago/2020** | Volta a ocupar a Secretaria Municipal de Habitação Social de João Pessoa (gestão Luciano Cartaxo), conforme próprio CV. Há discrepância potencial entre o CV (que indica retorno em janeiro de 2019) e a exoneração federal em 01/01/2019. | CV oficial. |
| **2020** | CGU instaura o Processo Administrativo Disciplinar nº 00190.101924/2020-94. | Portaria CGU 3.655/2022 (texto). |
| **Ago/2020 – Dez/2020** | Trabalha como consultora privada (Consultoria Um – C1). | CV oficial. |
| **01/01/2021** | Cícero Lucena (PP) toma posse na Prefeitura de João Pessoa. | público. |
| **Janeiro/2021** | **Nomeada Secretária Municipal de Habitação Social** de João Pessoa por Cícero Lucena. Primeira matéria publicada pelo site oficial da PMJP confirmando-a no cargo é de 17/01/2021. | site oficial PMJP. |
| **25/02/2022** | Parecer nº 00060/2022/CONJUR-CGU/CGU/AGU recomenda a conversão de exoneração em destituição. | Portaria CGU 3.655/2022 (texto). |
| **29/12/2022** | Ministro da CGU Wagner de Campos Rosario assina a **Portaria nº 3.655**, que **"converte a exoneração da Senhora Maria do Socorro Gadelha Campos de Lira na penalidade de destituição de cargo em comissão"**, com fundamento no Art. 127, V, c/c Art. 135 da Lei 8.112/90, por descumprir os deveres dos incisos I, III e IX do Art. 116. Cadastro CEAF nº 278654. | Portaria CGU 3.655/2022, DOU 02/01/2023, Edição 1-C, Seção 2, p. 62. |
| **02/01/2023** | Publicação da Portaria CGU 3.655/2022 no DOU. | DOU 02/01/2023. |
| **06/01/2023** | Quatro dias após a publicação da sanção, o site oficial da Prefeitura publica matéria normal com ela exercendo o cargo de secretária. A Prefeitura nunca a exonerou. | site oficial PMJP. |
| **04/06/2024** | Apresenta a Lei de Diretrizes Orçamentárias 2025 na Câmara Municipal como secretária da pasta. | site oficial CMJP. |
| **Out/2024** | Cícero Lucena é reeleito prefeito de João Pessoa. | público. |
| **01/01/2025** | Mantida no cargo no segundo mandato. | público. |
| **12/03/2025** | Deputado estadual **Hervázio Bezerra (PSB)** protocola na ALPB o **Projeto de Resolução nº 356/2025**, concedendo à servidora a **Medalha Epitácio Pessoa** "em reconhecimento aos relevantes serviços prestados à sociedade brasileira, especialmente no âmbito da habitação social". | SAPL/ALPB, matéria 130965. |
| **26/08/2025** | A ALPB aprova o projeto. | SAPL/ALPB. |

---

## 4. Os Dois Atos Centrais — Transcrições

### 4.1. Portaria CGU nº 3.655, de 29/12/2022 (sanção)

Trecho dispositivo do ato, conforme publicado no DOU em 02/01/2023, Edição 1-C, Seção 2, página 62 (Controladoria-Geral da União/Gabinete do Ministro):

> "O MINISTRO DE ESTADO DA CONTROLADORIA-GERAL DA UNIÃO, no exercício das atribuições conferidas pelos artigos 51 e 52 da Lei nº 13.844, de 18 de junho de 2019, pela Lei nº 8.112, de 11 de dezembro de 1990, e pelo Decreto nº 3.035, de 26 de abril de 1999, adota, como fundamento deste ato, o Parecer nº 00060/2022/CONJUR-CGU/CGU/AGU, de 25 de fevereiro de 2022, aprovado pelos Despachos de nºs 00064/2022/CONJUR-CGU/CGU/AGU e 840/2022/CONJUR-CGU/CGU/AGU, da Consultoria Jurídica junto a esta Controladoria-Geral da União, nos autos do Processo Administrativo Disciplinar nº 00190.101924/2020-94, resolve:
>
> Converter a exoneração da Senhora Maria do Socorro Gadelha Campos de Lira (CPF nº \*\*\*.256.054-\*\* e matrícula nº 2933908) na penalidade de destituição de cargo em comissão, com fundamento no artigo 127, inciso V, c/c o artigo 135, caput e parágrafo único, da Lei nº 8.112, de 11 de dezembro de 1990, por ter descumprido os deveres contidos nos incisos I, III e IX, do artigo 116, da Lei nº 8.112, de 1990.
>
> WAGNER DE CAMPOS ROSARIO"

Os incisos invocados do Art. 116 da Lei 8.112/90:

| Inciso | Texto |
|---|---|
| I | "exercer com zelo e dedicação as atribuições do cargo" |
| III | "observar as normas legais e regulamentares" |
| IX | **"manter conduta compatível com a moralidade administrativa"** |

O Art. 127 da Lei 8.112/90 elenca as penalidades disciplinares. O inciso V é "destituição de cargo em comissão" — a penalidade aplicada. O Art. 135 esclarece que essa destituição "será aplicada nos casos de infração sujeita às penalidades de suspensão e de demissão", e em seu parágrafo único equipara seus efeitos à demissão. Em síntese: a sanção é equivalente, na hierarquia disciplinar federal, à demissão.

### 4.2. Portaria nº 438, de 11/01/2019 (exoneração originária)

Trecho dispositivo da portaria do Ministro Chefe da Casa Civil Onyx Dornelles Lorenzoni, publicada no DOU em 11/01/2019, Seção 2:

> "Nº 438 - EXONERAR MARIA DO SOCORRO GADELHA CAMPOS DE LIRA do cargo de Secretária Nacional de Habitação do Ministério das Cidades, código DAS 101.6, a partir de 1º de janeiro de 2019."

Observação técnica: a exoneração originária foi de cargo do extinto Ministério das Cidades; o registro CEAF lista o cargo final como "Secretária-Executivo" no Ministério do Desenvolvimento Regional (órgão sucessor a partir de 01/01/2019, MP 870/2019). Essa distinção é meramente nominal — a sanção da CGU se aplica à mesma pessoa física e à mesma matrícula (2933908).

---

## 5. A Homenagem Posterior à Sanção (ALPB, 2025)

### 5.1. Projeto de Resolução nº 356/2025

A Assembleia Legislativa da Paraíba aprovou em 26/08/2025 o Projeto de Resolução nº 356/2025, de autoria do deputado estadual **Hervázio Bezerra (PSB)**, protocolado em 12/03/2025 (Protocolo nº 1414/2025).

Ementa textual:

> "Concessão da Medalha Epitácio Pessoa a Secretária Municipal de João Pessoa/PB, Sra. Maria Do Socorro Gadelha Campos Lira em reconhecimento aos relevantes serviços prestados à sociedade brasileira, especialmente no âmbito da habitação social."

### 5.2. Omissão no Currículo Oficial Submetido à ALPB

O currículo oficial submetido pela homenageada à ALPB como peça instrutória do Projeto de Resolução 356/2025 lista as seguintes experiências profissionais (na ordem):

- Secretária Municipal de Habitação Social (Janeiro/2021 – Atual): Prefeitura de João Pessoa.
- Consultora de Convênios e Contratos de Repasse (Agosto/2020 – Dezembro/2020): Consultoria Um – C1.
- Secretária Municipal de Habitação Social (Janeiro/2019 – Agosto/2020): Prefeitura de João Pessoa.
- Secretária Nacional de Habitação (Dezembro/2017 – Janeiro/2019): Ministério das Cidades.
- Secretária Municipal de Habitação Social (Janeiro/2013 – Janeiro/2018): Prefeitura de João Pessoa.
- Diretora Nacional de Programas (Abril/2012 – Dezembro/2012): Ministério das Cidades.

O CV **não lista** o cargo de Secretária-Executiva do Ministério do Desenvolvimento Regional — exatamente o cargo cuja exoneração foi convertida em destituição pela CGU.

---

## 6. Fontes Oficiais

| Fonte | URL |
|---|---|
| Painel do caso no transparenciapb.org | https://transparenciapb.org/cidade/joao-pessoa?d=servidor&d_cpf6=256054&d_nome=MARIA+DO+SOCORRO+GADELHA+CAMPOS+DE+LIRA |
| Sanção da CGU registrada no CEAF (Portal da Transparência) | https://portaldatransparencia.gov.br/sancoes/consulta/278654 |
| Portaria CGU nº 3.655/2022 (DOU) | https://www.in.gov.br/web/dou/-/portaria-n-3.655-de-29-de-dezembro-de-2022-455412918 |
| DOU Seção 2 de 02/01/2023, página 62 (visualização) | https://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?jornal=529&pagina=62&data=02/01/2023 |
| Portaria nº 438 de 2019 (exoneração) — DOU 11/01/2019 | https://www.in.gov.br/web/dou/-/portarias-de-11-de-janeiro-de-2019-58913898 |
| Matéria da PMJP confirmando-a como secretária em 17/01/2021 | https://www.joaopessoa.pb.gov.br/noticias/secretaria-de-habitacao-promove-regularizacao-fundiaria-e-planeja-novos-empreendimentos-sociais/ |
| Matéria da PMJP de 06/01/2023 (4 dias após a sanção) | https://www.joaopessoa.pb.gov.br/noticias/prefeitura-investe-em-programa-e-projetos-habitacionais-para-reduzir-deficit-de-moradia-em-joao-pessoa/ |
| Apresentação da LDO 2025 na Câmara Municipal (04/06/2024) | https://joaopessoa.pb.leg.br/secretaria-de-habitacao-detalha-projetos-para-2025-em-audiencia-publica/ |
| Página institucional da Semhab/JP | https://www.joaopessoa.pb.gov.br/secretaria/semhab/ |
| Matéria legislativa 130965/2025 (Medalha Epitácio Pessoa) — SAPL/ALPB | https://sapl3.al.pb.leg.br/materia/130965 |
| Autoria do PR 356/2025 (dep. Hervázio Bezerra, PSB) | https://sapl3.al.pb.leg.br/materia/130965/autoria |
| CV oficial submetido à ALPB | https://sapl3.al.pb.leg.br/media/sapl/public/materialegislativa/2025/130965/socorro_merged_1.pdf |
| Lei nº 8.112/90 (estatuto dos servidores civis da União) | https://www.planalto.gov.br/ccivil_03/leis/l8112cons.htm |
| Nomeação dela como Secretária Nacional de Habitação em 29/12/2017 | https://jornaldaparaiba.com.br/politica/padilha-nomeia-socorro-gadelha-para-secretaria-nacional-de-habitacao |

---

## 7. Implicações e Recomendações

### 7.1. Compatibilidade da Sanção com a Manutenção em Cargo Equivalente Municipal

A sanção de destituição prevista no Art. 135 da Lei 8.112/90 produz efeitos no âmbito federal. Sua extensão automática a outros entes federativos depende de previsão na legislação local. A Prefeitura de João Pessoa pode ser provocada — pelos canais legais (TCE-PB, MP-PB, Câmara Municipal, Controladoria Geral do Município) — a manifestar-se sobre a compatibilidade ética e administrativa de manter no cargo de Secretária Municipal de Habitação Social, há mais de quatro anos, pessoa punida pela CGU por descumprimento de dever de moralidade administrativa em cargo de natureza federal equivalente (habitação social).

### 7.2. Eventual Apuração Pelo MP-PB

O Ministério Público do Estado da Paraíba pode avaliar a abertura de procedimento para verificar:
- Se a manutenção em cargo de confiança municipal configura ofensa aos princípios constitucionais da Administração Pública (Art. 37, CF/88).
- Se a homenagem aprovada pela ALPB conheceu a íntegra do histórico funcional da homenageada.
- Eventual responsabilização por omissão de informações em peça instrutória de processo legislativo (CV apresentado à ALPB).

### 7.3. Eventual Apuração Pelo TCE-PB

O Tribunal de Contas do Estado da Paraíba pode incluir o tema em fiscalização ordinária da PMJP, considerando que pessoa expulsa da Administração Federal por violação de dever funcional segue ordenadora de despesas significativas em pasta municipal de mesma área temática.

### 7.4. Replicabilidade

O cruzamento CEAF × folha de pessoal municipal é realizado pelo transparenciapb.org para todos os 223 municípios paraibanos. Casos análogos podem ser apurados pelo painel municipal correspondente. Recomenda-se a auditoria periódica deste cruzamento como prática institucional pelos órgãos de controle.

---

## 8. Reprodutibilidade

Este relatório foi construído sem qualquer dado restrito ou base privada. Todo o material está em fontes públicas, com URLs estáveis ao tempo de redação, e pode ser replicado a partir das fontes da seção 6. O cruzamento CEAF × folha municipal está implementado no código aberto do transparenciapb.org e a sinalização aparece no card "Servidores já expulsos da Adm. Federal" do painel de qualquer município.

