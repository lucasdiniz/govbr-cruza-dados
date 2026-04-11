# Relatório de Investigação: Ciclo Empenho-Anulação-Reempenho em Empresas Fornecedoras do Estado da Paraíba

**Data de Geração:** 11 de abril de 2026  
**Base de Dados:** Query Q105 — `pb_empenho` × `pb_empenho_anulacao`  
**Metodologia:** identificação de credores PJ cujo valor anulado supera 50% do valor empenhado na mesma UG/exercício, com pelo menos 3 empenhos e R$ 1 milhão em anulações. Excluídos órgãos públicos do ranking principal.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Anulações de empenho podem decorrer de correção de erros, mudanças legítimas de planejamento ou encerramento de exercício. O padrão anulação-reempenho para o mesmo credor pode ter justificativa administrativa. A irregularidade não é presumida pelo cruzamento.

---

## 1. Resumo Executivo

A Query Q105 encontrou centenas de grupos credor×UG×exercício com ciclos anulação-reempenho. Quando filtrados apenas para **empresas privadas com taxa de anulação superior a 50%**, emergem casos onde praticamente todo o valor empenhado é anulado e reempenhado, o que pode indicar:
- reprocessamento orçamentário para mudar classificação de despesa;
- manipulação para evitar limites de dispensa;
- cancelamento e recontrataçao do mesmo fornecedor.

---

## 2. Casos Prioritários

### 2.1. Conecta Educação e Tecnologia Ltda — 100% de anulação (R$ 42,5 milhões)
- **CNPJ:** 09.242.037/0003-62 e 09.242.037/0001-09
- **UG:** 220001 (Secretaria de Educação)
- **Exercício:** 2024
- **Empenhos:** 4 empenhos originais, 4-5 anulações
- **Valor empenhado:** R$ 42,5 milhões
- **Valor anulado:** R$ 42,5 milhões (100%)

**Leitura investigativa:** empresa de educação e tecnologia que recebe R$ 42,5 milhões da Secretaria de Educação e tem 100% do valor anulado no mesmo exercício. Aparece com dois CNPJs (mesma raiz 09242037), ambos com taxa de anulação total. Caso agravado pelo fato de um terceiro nome de credor (`L.B. BEZERRA-COM. DE PROD E EQUIPAMENTOS`) compartilhar o mesmo CNPJ 09242037/0001-09 — pode indicar alteração societária ou uso indevido de CNPJ.

### 2.2. Engenharia de Avaliações — 80,2% de anulação (R$ 53,1 milhões)
- **CNPJ:** 13.348.041/0001-15
- **UG:** 220001 (Secretaria de Educação)
- **Exercício:** 2022
- **Empenhos:** 3 empenhos, 5 anulações
- **Valor empenhado:** R$ 66,2 milhões
- **Valor anulado:** R$ 53,1 milhões (80,2%)

**Leitura investigativa:** empresa de avaliações/engenharia com contrato de R$ 66 milhões na Educação, 80% anulado. O número de anulações (5) superior ao de empenhos (3) indica reprocessamento repetido dos mesmos empenhos.

### 2.3. Daten Tecnologia Ltda — 98,1% de anulação (R$ 33,8 milhões)
- **CNPJ:** 04.602.789/0001-01
- **UG:** 220001 (Secretaria de Educação)
- **Exercício:** 2022
- **Empenhos:** 6 empenhos, 4 anulações
- **Valor empenhado:** R$ 34,5 milhões
- **Valor anulado:** R$ 33,8 milhões (98,1%)

**Leitura investigativa:** empresa de tecnologia/informática com quase totalidade do valor anulado. A concentração na mesma UG (Secretaria de Educação) em 2022 reforça o padrão de ciclos de anulação nesse órgão.

### 2.4. Positivo Informática Ltda — 100% de anulação (R$ 15 milhões)
- **CNPJ:** 81.243.735/0001-48
- **UG:** 530001
- **Exercício:** 2021
- **Empenhos:** 3 empenhos, 3 anulações
- **Valor:** R$ 15 milhões (100% anulado)

**Leitura investigativa:** marca nacional de informática com empenho integralmente anulado. Pode indicar cancelamento de compra de equipamentos, mas o valor elevado e a anulação total merecem verificação.

### 2.5. Consórcio HCTP — 84,4% de anulação (R$ 18,9 milhões)
- **CNPJ:** 53.364.629/0001-87
- **UG:** 250001 (Secretaria de Saúde)
- **Exercício:** 2025
- **Empenhos:** 22 empenhos, 14 anulações
- **Valor empenhado:** R$ 22,4 milhões
- **Valor anulado:** R$ 18,9 milhões (84,4%)

**Leitura investigativa:** consórcio de saúde com alto volume de anulações. O número elevado de empenhos (22) e anulações (14) sugere instabilidade contratual ou reprocessamento frequente.

### 2.6. CS Brasil Frotas SA — 9.866% de anulação (R$ 9,2 milhões)
- **CNPJ:** 27.595.780/0001-16
- **UG:** 250001 (Secretaria de Saúde)
- **Exercício:** 2024
- **Empenhos:** 6 empenhos com nome "CS BRASIL FROTAS SA", 34 com nome "CS BRASIL FROTOS LTDA"
- **Valor empenhado (nome 1):** R$ 93 mil
- **Valor anulado:** R$ 9,2 milhões (9.866%)

**Leitura investigativa:** o percentual absurdo indica que os empenhos sob o nome "CS BRASIL FROTAS SA" foram de valor baixo, mas as anulações cobriram empenhos muito maiores (provavelmente lançados sob "CS BRASIL FROTOS LTDA" — mesmo CNPJ). A empresa aparece com dois nomes para o mesmo CNPJ, gerando distorção contábil.

---

## 3. Padrões Transversais

### 3.1. Concentração na Secretaria de Educação (UG 220001)
Conecta Educação, Engenharia de Avaliações, Daten Tecnologia e Empresa Paraibana de Comunicação — todos na mesma UG, todos com anulação acima de 80%. Isso sugere prática recorrente de anulação-reempenho nesse órgão, que merece auditoria de processos.

### 3.2. Empresas de tecnologia/informática predominam
Daten, Positivo, Classpad, Minsait — quatro empresas de TI com anulação quase total. Pode indicar padrão setorial de cancelamento de compras de equipamentos ou reprocessamento de contratos de TI.

### 3.3. Setor de saúde com ciclos de anulação em consórcios
Consórcio HCTP, Hospital Milagres, WM&M Serviços Médicos, Med Patos — empresas de saúde com anulações acima de 80%. O padrão pode refletir a dinâmica de contratação emergencial da saúde, mas o volume demanda fiscalização.

---

## 4. Fundamentação Jurídica

- **Art. 35 da Lei 4.320/64:** pertencem ao exercício as despesas nele legalmente empenhadas. Anulação e reempenho podem configurar manipulação de exercício financeiro.
- **Art. 59 da Lei 8.666/93:** os órgãos de controle devem verificar a regularidade dos atos de empenho, anulação e reempenho.
- **Art. 167, VI da CF/88:** veda a transposição, o remanejamento ou a transferência de recursos sem autorização legislativa.

---

## 5. Recomendações

1. **Auditar a Secretaria de Educação (UG 220001)** — concentra os maiores e mais frequentes ciclos de anulação-reempenho com fornecedores privados.
2. **Investigar Conecta Educação (CNPJ 09.242.037)** — dois CNPJs (filiais) com anulação total, e nome de credor divergente (L.B. BEZERRA) no mesmo CNPJ.
3. **Verificar a identidade de CS Brasil Frotas/Frotos** — mesmo CNPJ com dois nomes sugere problema cadastral que mascara o real volume de empenhos e anulações.
4. **Estabelecer alerta automático** para empenhos com taxa de anulação > 80% no mesmo exercício, por credor.
