# Relatório de Auditoria: Sobrepreço em Itens de Contratações Públicas (PNCP)

**Data de Geração:** 4 de Abril de 2026
**Base de Dados:** pncp_item | pncp_contratacao (Portal Nacional de Contratações Públicas)
**Metodologia:** Três abordagens complementares — desvio estatístico nacional (Q92), divergência regional entre UFs (Q94) e jogo de planilha intracontratual (Q97). Dados restritos a itens homologados.

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de sobrepreço, não conclusões de irregularidade ou ilicitude. Preços muito acima da média podem ter explicações legítimas (itens de nicho, especificações técnicas diferenciadas, erros de digitação não corrigidos no sistema). A apuração de eventual irregularidade compete exclusivamente aos órgãos competentes (CGU, TCU, MPF/MPE, controladorias estaduais). Os dados originam-se do PNCP, sistema oficial do Governo Federal.

---

## 1. Resumo Executivo

A análise de aproximadamente **2,7 milhões de itens homologados** no PNCP identificou três padrões distintos de potencial sobrepreço em contratações públicas federais, estaduais e municipais.

| Indicador | Resultado |
|-----------|-----------|
| Itens com preço > média + 3σ nacional (Q92) | **10.034 itens** |
| Pares UF com razão de preço > 5× para o mesmo item (Q94) | Centenas de pares |
| Itens com jogo de planilha detectado (Q97) | **4.092 itens** |
| UF com maior volume de outliers (Q92) | DF — 1.280 itens |
| Caso de maior valor absoluto identificado | Flanela — R$ 103 milhões |

Os achados apontam que o problema não é isolado geograficamente: todas as regiões do Brasil apresentam itens fora do padrão estatístico. Os casos mais graves concentram-se em insumos hospitalares, materiais de limpeza e equipamentos de segurança.

---

## 2. Metodologia

### 2.1. Q92 — Sobrepreço Nacional (desvio padrão)

A query opera em duas fases para contornar limitações de memória com 2,7 milhões de registros:

1. **Fase 1 (tabela temporária):** agrupa itens pela descrição normalizada (`UPPER(TRIM(descricao))`) e calcula média e desvio padrão (`AVG`, `STDDEV`) por grupo. Exige mínimo de 10 itens por grupo para relevância estatística.
2. **Fase 2 (join por hash MD5):** localiza itens individuais cujo `valor_unitario_estimado` supera `media + 3 * desvio_padrao`. Em grupos sem variação (desvio = 0), usa a própria média como substituto do desvio.

**Filtros de sanidade:** apenas itens com `valor_total` entre R$ 10.000 e R$ 1 bilhão (acima de R$ 1B são descartados como prováveis erros de digitação). Baseline mínimo: `media >= R$ 1`.

**Limiar:** preço unitário superior a 3 desvios padrão acima da média nacional do grupo — abrange aproximadamente 0,3% de uma distribuição normal, mas na prática o PNCP tem distribuições altamente assimétricas.

### 2.2. Q94 — Variação Regional entre UFs

Calcula o preço médio por UF para cada descrição normalizada, exigindo mínimo de 5 itens por estado. Em seguida, cruza pares de UFs buscando casos onde o estado mais caro cobra mais de 5× o preço do estado mais barato, com impacto financeiro mínimo de R$ 100.000.

### 2.3. Q97 — Jogo de Planilha

Usa window function com `EXCLUDE CURRENT ROW` para calcular a média dos demais itens da mesma contratação sem contaminar o cálculo com o próprio outlier. Flageia itens que simultaneamente:
- Custam mais de 10× a média dos demais itens da contratação
- Representam mais de 30% do valor total da contratação
- Têm valor total superior a R$ 50.000

O critério dos 30% é central: num jogo de planilha real, o fornecedor não apenas cobra caro — ele concentra o valor do contrato naquele item específico.

---

## 3. Achados Principais

### 3.1. Q92 — Sobrepreço por Item (Nacional)

Foram identificados **10.034 itens** com preço unitário superior à média nacional em mais de 3 desvios padrão, distribuídos em todas as UFs do país.

**Distribuição por UF (top 10):**

| UF | Itens outliers |
|----|---------------|
| DF | 1.280 |
| RJ | 965 |
| BA | 942 |
| MG | 715 |
| SP | 695 |
| PR | 546 |
| PE | 487 |
| CE | 465 |
| GO | 459 |
| MA | 390 |

O Distrito Federal lidera com folga, o que reflete a alta concentração de órgãos federais e autarquias na capital, que registram contratações de maior volume e variedade. Rio de Janeiro e Bahia aparecem em segundo e terceiro, estados com redes hospitalares federais expressivas (EBSERH).

O padrão dominante entre os outliers são **insumos hospitalares** — luvas, aventais, materiais cirúrgicos, medicamentos — adquiridos pela rede EBSERH e hospitais universitários a preços unitários muito superiores à média. Em alguns casos, a discrepância é atribuível a erros de digitação (preço unitário inserido igual ao valor total do lote), mas esses registros permanecem no sistema sem correção.

### 3.2. Q94 — Divergência Regional entre UFs

A comparação entre estados revela **centenas de pares** com razão de preço superior a 5× para o mesmo item. Isso significa que, para produtos com descrição idêntica, um estado paga em média mais de 5 vezes o que outro estado paga.

Esse padrão pode decorrer de:
- Especificações técnicas distintas mascaradas por descrições iguais (ex.: "luva cirúrgica" de marcas e padrões diferentes)
- Ausência de pesquisa de preços adequada em estados com mercado fornecedor menos competitivo
- Sobrepreço deliberado em estados onde o controle social e institucional é mais frágil

A query não permite discriminar entre essas causas — ela indica onde investigar, não a causa da divergência.

### 3.3. Q97 — Jogo de Planilha

Foram detectados **4.092 itens** com o padrão clássico de jogo de planilha: um único item domina mais de 30% do valor de uma contratação multiitem e tem preço unitário superior a 10× a média dos demais itens do mesmo contrato.

Essa técnica é usada para dificultar a comparação de preços nas fases de habilitação e julgamento: ao apresentar preços baixos nos itens facilmente comparáveis e inflados nos itens de difícil verificação, o fornecedor ganha a licitação aparentemente mais barato e extrai o lucro nos itens inflados.

---

## 4. Casos de Destaque

### 4.1. Flanela — R$ 103 milhões (Q92 e Q97)

O caso de maior valor absoluto identificado em ambas as análises envolve a compra de **flanelas** a **R$ 22.478 por unidade**, contra uma média nacional de R$ 57,95 — uma razão de **388× a média**.

O valor total do lote foi de **R$ 103 milhões**, e esse único item representava **99,6% do valor total da contratação**. É o caso mais emblemático de jogo de planilha na amostra: os demais itens do contrato têm valores residuais, e toda a substância financeira foi concentrada na flanela.

Este caso requer investigação urgente pelos órgãos de controle. Mesmo considerando que "flanela" possa ser descrição genérica para materiais têxteis mais caros, uma razão de 388× a média de 900+ compras nacionais não encontra explicação técnica plausível.

### 4.2. EBSERH-PB — Avental Descartável (Q92)

O Hospital Universitário de Campina Grande (EBSERH, rede federal) registrou a compra de **avental descartável** a **R$ 1.083.540 por unidade**, contra uma média nacional de R$ 12.856 — razão de **84× a média**. O valor total foi de R$ 1,08 milhão.

A hipótese mais provável é erro de digitação: o operador pode ter inserido o valor total do lote no campo de preço unitário, registrando implicitamente quantidade 1. O dado, porém, está presente no PNCP sem qualquer retificação. Isso evidencia uma fragilidade sistêmica: o portal não realiza validações básicas de consistência entre `valor_unitario_estimado`, `quantidade` e `valor_total`.

Independentemente da causa, o PNCP apresenta dados oficiais incorretos que distorcem análises de mercado, cotações futuras e rankings de sobrepreço.

### 4.3. Arma Não-Letal — R$ 448 milhões (Q97)

Um item categorizado como **arma não-letal** foi detectado com valor total de **R$ 448 milhões**, representando parcela dominante de sua contratação, com preço unitário superior a 10× a média dos demais itens do mesmo processo.

Equipamentos de segurança pública são itens de difícil comparação de preço por terem especificações técnicas sigilosas ou restritas. Esse contexto pode ser explorado por fornecedores para justificar preços inflados sem possibilidade de contestação efetiva durante o julgamento da licitação.

---

## 5. Limitações e Próximos Passos

### 5.1. Limitações Metodológicas

| Limitação | Impacto | Correção Pendente |
|-----------|---------|-------------------|
| Uso de AVG (média aritmética) em Q92 e Q94 | Sensível a outliers — um único preço extremo distorce a média do grupo, gerando falsos positivos ou mascarando verdadeiros sobrepreços | Substituir por `PERCENTILE_CONT(0.5)` (mediana) e IQR |
| Normalização de descrições apenas por `UPPER(TRIM())` | Itens com unidades diferentes (UN, UNID, Unidade, CX, PCT) são tratados como grupos distintos ou agrupados incorretamente | Implementar dicionário de unidades e clustering de descrições similares |
| Cobertura de NCM apenas 1,4% | Não é possível usar código NCM como chave de agrupamento na maioria dos casos | Ampliar via enriquecimento por NLP ou mapeamento manual de categorias-chave |
| Filtro de R$ 1B exclui possíveis erros graves | Itens com valor total acima de R$ 1B são descartados como prováveis erros, mas podem ser sobrepreços reais | Criar fila separada para revisão manual de itens acima de R$ 1B |
| Ausência de série temporal | Análise é um corte transversal — não detecta evolução de preço ao longo do tempo no mesmo órgão | Adicionar análise de variação ano a ano por órgão/item |

### 5.2. Próximos Passos Recomendados

1. **Corrigir Q92 e Q94** para usar mediana (`PERCENTILE_CONT`) em vez de média aritmética, reduzindo falsos positivos e aumentando a robustez do ranking.
2. **Cruzar outliers Q92 com fornecedores vencedores** (tabela `pncp_contrato`) para identificar se os sobrepreços se concentram em fornecedores específicos.
3. **Cruzar casos Q97** com o banco de sanções (CEIS/CNEP) e com o score de risco de empresas, verificando se fornecedores com histórico de irregularidades reaparecem nos casos de jogo de planilha.
4. **Encaminhar os casos de maior valor** (flanela R$ 103M, arma não-letal R$ 448M) aos órgãos competentes (CGU, TCU) para triagem de investigação formal.
5. **Implementar alerta em tempo real** para novos itens publicados no PNCP que excedam 5× a média do grupo, antes da homologação.

---

## 6. Conclusão

A análise estatística de itens homologados no PNCP revela **14.126 ocorrências** suspeitas de sobrepreço (10.034 via desvio padrão nacional + 4.092 via jogo de planilha), com casos individuais chegando a centenas de milhões de reais.

Os achados sugerem três categorias de problema distintas:

- **Erros de digitação não corrigidos** (como o avental EBSERH-PB a R$ 1M/unidade), que distorcem o banco de dados e podem inflar estimativas de mercado em licitações futuras.
- **Sobrepreço por ausência de pesquisa de mercado adequada**, especialmente em UFs com mercado menos competitivo e em itens hospitalares de nicho.
- **Manipulação deliberada de planilha de preços**, evidenciada pela concentração extrema do valor do contrato em um único item outlier — padrão clássico do jogo de planilha.

A metodologia atual, baseada em média aritmética, tende a superestimar o número de falsos positivos em grupos com distribuição assimétrica. Com a substituição para mediana e IQR (correção pendente), espera-se produzir um ranking mais preciso e confiável para os órgãos de controle.

Os dados estão disponíveis para cruzamento com as demais bases do pipeline (CNPJ, CEIS, PGFN, TSE) para aprofundamento dos perfis dos fornecedores envolvidos nos casos de maior valor absoluto.
