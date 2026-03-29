# Relatório de Auditoria: Score de Risco Municipal na Paraíba

**Data de Geração:** 28 de Março de 2026
**Base de Dados:** mv_municipio_pb_risco — score composto de 5 indicadores de risco fiscal
**Metodologia:** Score de 0-100 baseado em: (1) % empenhos sem licitação (peso 30), (2) % licitações com proponente único (peso 25), (3) concentração em dezembro (peso 20), (4) % não executado (peso 15), (5) folha/receita (peso 10). Dados SAGRES/TCE-PB, 2022-2026.

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de risco fiscal, não conclusões de irregularidade. Scores altos indicam padrões que merecem atenção, mas podem ter explicações legítimas (municípios pequenos com poucos fornecedores, sazonalidade orçamentária, etc.). A apuração compete aos órgãos de controle.

---

## 1. Resumo Executivo

Foram avaliados **223 municípios** da Paraíba. O score de risco varia de 25 a 52 (máximo teórico: 100). A distribuição é concentrada na faixa 35-50, indicando que os problemas são **sistêmicos** — não há municípios com score extremamente alto ou extremamente baixo, mas a maioria apresenta indicadores preocupantes em pelo menos 2-3 dimensões.

**Faixas de risco:**
| Faixa | Municípios | % |
|-------|-----------|---|
| Alto (≥ 48) | 34 | 15% |
| Médio-Alto (43-47) | 62 | 28% |
| Médio (38-42) | 61 | 27% |
| Médio-Baixo (33-37) | 63 | 28% |
| Baixo (< 33) | 3 | 1% |

---

## 2. Municípios de Maior Risco (Score ≥ 48)

### 2.1. Lucena — Score 52 (maior do estado)
- **Empenhos:** 34.108 | **Empenhado:** R$ 353,7M | **Pago:** R$ 304,2M
- **Sem licitação:** 0,0% | **Proponente único:** 44,1% | **Dezembro:** 10,2%
- **Fornecedores:** 2.568 | **Licitações:** 227
- **Análise:** Score impulsionado pela altíssima taxa de proponente único (44%) — quase metade das licitações tem apenas um participante. A taxa zero de empenhos sem licitação é positiva, mas pode indicar que dispensas são registradas de outra forma.

### 2.2. Princesa Isabel — Score 51
- **Empenhos:** 84.252 | **Empenhado:** R$ 524,8M | **Pago:** R$ 490M
- **Proponente único:** 41,9% | **Dezembro:** 13,5%
- **Fornecedores:** 7.465 | **Licitações:** 296
- **Análise:** Alta concentração de proponente único (42%) e gastos em dezembro (13,5% vs 8,3% esperado).

### 2.3. Santa Rita — Score 51
- **Empenhos:** 31.314 | **Empenhado:** R$ 2.230,6M | **Pago:** R$ 2.020,7M
- **Proponente único:** 43,3% | **Dezembro:** 10,9%
- **Fornecedores:** 2.920 | **Licitações:** 644
- **Análise:** Segundo maior volume de empenhos do estado (R$2,2B). Proponente único em 43% das licitações.

### 2.4. João Pessoa — Score 49
- **Empenhos:** 159.532 | **Empenhado:** R$ 17.520,9M | **Pago:** R$ 15.866,3M
- **Proponente único:** 76,7% | **Dezembro:** 8,9%
- **Fornecedores:** 17.743 | **Licitações:** 4.368
- **Análise:** Capital do estado com o maior volume absoluto. **76,7% de proponente único** é o indicador mais alto de todos os municípios — 3 em cada 4 licitações têm apenas 1 participante. Isso pode refletir especificidade técnica dos objetos ou barreiras à competição.

### 2.5. Campina Grande — Score 48
- **Empenhos:** 95.475 | **Empenhado:** R$ 8.049M | **Pago:** R$ 7.207,1M
- **Proponente único:** 50,3% | **Dezembro:** 8,2%
- **Fornecedores:** 7.401 | **Licitações:** 2.580
- **Análise:** Segunda maior cidade. Metade das licitações com proponente único.

---

## 3. Indicadores Destacados

### 3.1. Proponente Único (Peso 25)
Os 5 municípios com maior taxa de proponente único:

| Município | % Proponente Único | Licitações |
|-----------|-------------------|------------|
| João Pessoa | 76,7% | 4.368 |
| Algodão de Jandaíra | 67,1% | 258 |
| Serra Redonda | 57,0% | 179 |
| Riachão do Poço | 57,6% | 125 |
| Pirpirituba | 56,9% | 399 |

**Nota:** Em licitações com apenas 1 proponente, não há competição de preços. Percentuais acima de 50% indicam mercado concentrado ou especificações direcionadas.

### 3.2. Concentração em Dezembro (Peso 20)
- Distribuição uniforme esperada: 8,33% por mês
- Municípios com >12%: **38 municípios** (17%)
- Faixa típica observada: 8-13%
- **Risco:** Empenhar volume desproporcional em dezembro sugere "queima de orçamento" para não devolver recursos.

### 3.3. Sem Licitação (Peso 30)
- Todos os municípios mostram 0,0% — provavelmente os campos `numero_licitacao` estão preenchidos para todos os empenhos no SAGRES, ou dispensas não são distinguíveis
- **Nota:** Este indicador precisa de revisão metodológica. A ausência de variação sugere problema na captura do dado, não ausência real de dispensas.

---

## 4. Correlação com Outros Achados

| Município | Score | Outros relatórios |
|-----------|-------|-------------------|
| João Pessoa | 49 | Q47 (R$96M fotovoltaico sábado), Q53 (Doutor Work R$42M), Q59 (I2 Saúde R$23M) |
| Bayeux | — | Q59 (I2 Saúde R$23M), Q74 (841 servidores+BF) |
| Campina Grande | 48 | Q59 (HSM2 R$2.2M), Q74 (838 servidores+BF) |
| Santa Rita | 51 | Q74 (603 servidores+BF) |
| Sapé | 49 | Q59 (Rosário de Maria R$2.9M), Q74 (544 servidores+BF) |

---

## 5. Limitações

1. **Sem licitação**: O indicador "% sem licitação" está zerado para todos os municípios, sugerindo que o SAGRES preenche `numero_licitacao` mesmo para dispensas. Revisão metodológica necessária.
2. **Folha/receita**: O indicador `pct_folha_receita` está nulo para vários municípios — faltam dados de receita arrecadada para parte deles.
3. **Score relativo**: Com range de 25-52, a discriminação entre municípios é limitada. Uma recalibração dos pesos poderia ampliar o range.

---

## 6. Recomendações

1. **TCE-PB**: Priorizar auditorias nos municípios com score ≥48, especialmente Lucena, Princesa Isabel e Santa Rita
2. **CGE-PB**: Investigar a taxa de proponente único em João Pessoa (76,7%) — por que 3/4 das licitações da capital têm apenas 1 participante?
3. **Metodologia**: Revisar o indicador de "sem licitação" para captar dispensas de licitação corretamente no SAGRES
4. **Transparência**: Publicar o score de risco municipal como ferramenta de transparência e priorização de auditorias

## Fontes
1. **TCE-PB SAGRES:** Despesas municipais 2022-2026
2. **TCE-PB SAGRES:** Licitações municipais 2022-2026
3. **TCE-PB SAGRES:** Receitas municipais 2022-2026
4. **TCE-PB SAGRES:** Folha de servidores 2022-2026
5. **mv_municipio_pb_risco:** View materializada com score composto
