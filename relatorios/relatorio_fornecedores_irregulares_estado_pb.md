# Relatório de Investigação: Fornecedores Irregulares Recebendo Empenhos do Estado da Paraíba

**Data de Geração:** 5 de abril de 2026  
**Base de Dados:** Queries Q102, Q103 e Q111  
**Metodologia:** cruzamento entre empenhos estaduais (`pb_empenho`), sanções federais (CEIS/CNEP), dívida ativa da PGFN e a materialized view `mv_fornecedor_pb_perfil`.

> **Disclaimer:** Este relatório consolida anomalias cadastrais e financeiras. A presença em CEIS/CNEP ou PGFN não implica automaticamente impedimento absoluto para todo e qualquer pagamento em todas as circunstâncias. Os achados indicam risco e necessidade de verificação documental e jurídica caso a caso.

---

## 1. Resumo Executivo

Os novos dados estaduais da Paraíba mostram que o problema não está restrito ao universo municipal. O cruzamento identificou:
- empresas sancionadas que continuam aparecendo em empenhos estaduais;
- grandes fornecedores com passivos bilionários na PGFN;
- perfis com múltiplas flags simultâneas na `mv_fornecedor_pb_perfil`.

O valor investigativo aqui é alto porque a evidência é objetiva: CNPJ coincidente, empenho registrado e base externa oficial de sanção ou dívida.

---

## 2. Empresas Sancionadas Com Empenhos Estaduais

### 2.1. ICE Cartões Especiais Ltda
- **CNPJ básico:** 01175647
- **Total empenhado no estado:** R$ 48,9 milhões
- **Origem da sanção:** CNEP
- **Sanções registradas:** multa e publicação extraordinária da decisão condenatória
- **Órgão sancionador:** Governo do Estado do Mato Grosso do Sul

**Leitura investigativa:** é o caso mais forte da Q102. O volume é alto demais para ser tratado como resíduo operacional. É necessário verificar datas exatas dos empenhos, vigência da sanção e eventual existência de contratos anteriores à penalidade.

### 2.2. Manupa Comércio Exportação Importação de Equipamentos e Veículos Adaptados Ltda
- **CNPJ básico:** 03093776
- **Total empenhado no estado:** R$ 13,3 milhões
- **Origem da sanção:** CNEP
- **Sanção:** multa
- **Órgão sancionador:** Prefeitura de Vitória/ES

**Leitura investigativa:** caso relevante por combinar penalidade formal e recebimento expressivo no estado da Paraíba. Merece checagem sobre circulação interestadual do impedimento e rotina de due diligence pré-contratação.

### 2.3. SOS Gás Ltda
- **CNPJ básico:** 09266128
- **Total empenhado no estado:** R$ 5,44 milhões
- **Origem da sanção:** CNEP
- **Sanções:** multa e publicação extraordinária
- **Órgão sancionador:** ECT

### 2.4. Aceco TI Ltda
- **CNPJ básico:** 43209436
- **Total empenhado no estado:** R$ 1,86 milhão
- **Origem da sanção:** CEIS
- **Sanção:** declaração de inidoneidade sem prazo determinado
- **Órgão sancionador:** CGU

**Leitura investigativa:** este caso merece prioridade elevada, porque a natureza da sanção é mais grave do que simples multa.

---

## 3. Corroboração Externa

### 3.1. ICE Cartões Especiais Ltda

O caso da **ICE Cartões Especiais Ltda** tem lastro externo robusto. Há resolução oficial da Controladoria-Geral do Estado de Mato Grosso do Sul, datada de **14 de fevereiro de 2025**, aplicando penalidades à empresa no âmbito de processo administrativo de responsabilização. Além disso, há cobertura jornalística ligando a empresa a investigações de fraude licitatória e pagamento de propina em contratos do Detran-MS.

Isso fortalece bastante a relevância da Q102: não se trata apenas de coincidência cadastral com base sancionatória, mas de empresa já formalmente sancionada em caso de corrupção administrativa.

### 3.2. Alerta Serviços Ltda

No universo da `mv_fornecedor_pb_perfil`, a **Alerta Serviços Ltda** aparece com `score_risco = 3` e volume expressivo de empenhos. A pesquisa externa encontrou documentação recente da **Central de Compras do Estado da Paraíba** e jurisprudência do **TJ-PB** ligada à habilitação da empresa em procedimentos licitatórios estaduais de apoio logístico e administrativo para unidades escolares.

O achado não equivale a sanção, mas mostra que a empresa já está no radar documental e contencioso de contratações relevantes do próprio estado.

---

## 4. Grandes Devedores da PGFN Com Empenhos Estaduais

### 3.1. Banco Santander (Brasil) S.A.
- **CNPJ básico:** 90400888
- **Total empenhado no estado:** R$ 1,8 milhão
- **Inscrições PGFN:** 456
- **Dívida consolidada:** R$ 2,425 trilhões

### 3.2. Banco Bradesco S.A.
- **CNPJ básico:** 60746948
- **Total empenhado no estado:** R$ 14,6 milhões
- **Inscrições PGFN:** 157
- **Dívida consolidada:** R$ 884,7 bilhões

### 3.3. Itaú Unibanco S.A.
- **CNPJ básico:** 60701190
- **Total empenhado no estado:** R$ 1,7 milhão
- **Inscrições PGFN:** 155
- **Dívida consolidada:** R$ 528,0 bilhões

### 3.4. Volkswagen Truck & Bus
- **CNPJ básico:** 06020318
- **Total empenhado no estado:** R$ 147,0 milhões
- **Inscrições PGFN:** 18
- **Dívida consolidada:** R$ 257,0 bilhões

### 3.5. OI S.A. — em recuperação judicial
- **CNPJ básico:** 76535764
- **Total empenhado no estado:** R$ 41,7 milhões
- **Inscrições PGFN:** 175
- **Dívida consolidada:** R$ 188,4 bilhões

**Leitura investigativa:** a Q103 mistura empresas de altíssimo porte com passivos tributários massivos. Nem todo caso aqui sugere fraude direta, mas o conjunto é útil para auditoria de habilitação fiscal, renegociação contratual e exposição do estado a fornecedores com grande passivo regulatório/judicial.

---

## 5. Perfis de Maior Risco Composto

A `mv_fornecedor_pb_perfil` já aponta empresas com `score_risco = 3`, combinando múltiplas flags:

- **Alerta Serviços Ltda** — R$ 590,8 milhões empenhados, 5 contratos, score 3
- **Ágape Construções e Serviços Ltda** — R$ 529,7 milhões empenhados, 18 contratos, score 3
- **Construtora Luiz Costa Ltda** — R$ 322,2 milhões empenhados, score 3
- **Contrate Serviços Ltda** — R$ 98,2 milhões empenhados, score 3
- **Maranata Prestadora de Serviços e Construções Ltda** — R$ 53,6 milhões empenhados, score 3
- **OI S.A.** — R$ 41,7 milhões empenhados, score 3

**Leitura investigativa:** este bloco é o melhor ponto de partida para priorização operacional. A view reduz o universo para fornecedores que acumulam sinais simultâneos e merecem dossiê próprio.

---

## 6. Encaminhamento Recomendado

1. Priorizar auditoria documental dos casos sancionados da Q102.
2. Separar, dentro da Q103, grandes conglomerados regulados dos casos empresariais típicos de contratação pública.
3. Usar a `mv_fornecedor_pb_perfil` para selecionar os 20 fornecedores com maior `score_risco` e maior volume empenhado.

## Fontes
1. Queries Q102, Q103 e Q111 — `queries/fraude_dados_pb_novos.sql`
2. Tabelas `pb_empenho`, `ceis_sancao`, `cnep_sancao`, `pgfn_divida`
3. Materialized view `mv_fornecedor_pb_perfil`
4. Resolução CGE/MS nº 125/2025 — penalidades à ICE Cartões: [PDF oficial](https://www.cge.ms.gov.br/wp-content/uploads/2025/02/Resolucao-CGE-no-125-2025-Penalidade-PAR-ICE-PSG-INOVVATI-SITE.pdf)
5. Midiamax — ICE Cartões e investigação sobre favorecimento/propina no Detran-MS: [reportagem](https://midiamax.com.br/politica/transparencia/2021/justica-nega-desbloqueio-r-18-milhoes-empresa-socio-investigados-propina-detran-ms/)
6. Central de Compras do Estado da Paraíba — documentos de diligência/habilitação da Alerta Serviços: [documento 1](https://appcentral.centraldecompras.pb.gov.br/appls/sgc/sgc_anexos19.nsf/E205237DA5522C2203258C2C003C339A/%24file/DILIG%C3%8ANCIAS%20DA%20PROPOSTA%20-%20ALERTA.pdf) e [documento 2](https://centraldecompras.pb.gov.br/appls/sgc/sgcapp.nsf/0/D974292E0E06A37603258C4A004C5C6B/%24file/PROPOSTA%20DESCLASSIFICA%C3%87%C3%83O%20-%20ALERTA.pdf)
7. TJ-PB — jurisprudência envolvendo habilitação da Alerta Serviços em licitações estaduais: [Jusbrasil / TJ-PB](https://www.jusbrasil.com.br/jurisprudencia/tj-pb/3964518854)
