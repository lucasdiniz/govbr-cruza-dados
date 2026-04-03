# Relatório de Auditoria: Score de Risco de Servidores Públicos na Paraíba

**Data de Geração:** 3 de Abril de 2026
**Base de Dados:** mv_servidor_pb_risco — score composto de 5 indicadores de risco por servidor
**Metodologia:** Score de 0-100 baseado em: (1) conflito de interesses — servidor sócio de empresa fornecedora do mesmo município (peso 40), (2) alto salário com sociedade empresarial (peso 20), (3) recebimento de Bolsa Família concomitante ao vínculo (peso 15), (4) duplo vínculo estadual (peso 15), (5) sócio de 3 ou mais empresas (peso 10). Dados SIAPE/TCE-PB/CNPJ/CadÚnico, 2022-2026.

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de risco, não conclusões de irregularidade. Scores altos indicam padrões que merecem atenção, mas podem ter explicações legítimas (médicos com clínica privada regularmente constituída, empresas inativas, participações societárias herdadas, etc.). A apuração de irregularidades compete exclusivamente aos órgãos de controle competentes (CGE-PB, TCE-PB, MPF, CGU).

---

## 1. Resumo Executivo

Foram avaliados **353.177 servidores** vinculados a municípios da Paraíba. Do total, **30.962 servidores (8,8%)** apresentam pelo menos um indicador de risco (score > 0). A grande maioria dos casos recai na faixa baixa de risco, mas **73 servidores atingem score alto (>= 70)**, todos eles acumulando simultaneamente conflito de interesses e sociedade em múltiplas empresas.

Um padrão estrutural se destaca: **18 dos 20 servidores de maior risco são médicos**. Isso reflete uma característica sistêmica da profissão — médicos frequentemente constituem pessoas jurídicas para prestação de serviços, e muitos atuam simultaneamente no setor público e privado. Essa sobreposição gera conflito de interesses formal quando a empresa do servidor presta serviços ao mesmo ente público que o emprega. O fenômeno não é necessariamente fraudulento, mas alguns casos, pela magnitude financeira envolvida, justificam aprofundamento.

**Distribuição de risco:**
| Faixa | Servidores | % |
|-------|-----------|---|
| Alto (>= 70) | 73 | 0,02% |
| Médio (40-69) | 2.545 | 0,72% |
| Baixo (1-39) | 28.344 | 8,0% |
| Sem risco (= 0) | 322.215 | 91,2% |
| **Total** | **353.177** | **100%** |

---

## 2. Metodologia

O score de risco individual é calculado pela view materializada `mv_servidor_pb_risco`, que cruza dados de folha de pagamento (TCE-PB/SIAPE), quadro societário de empresas (CNPJ/Receita Federal), contratos públicos (PNCP/TCE-PB), transferências sociais (CadÚnico/Bolsa Família) e vínculos empregatícios estaduais.

### 2.1. Flags e Pontuações

| Flag | Pontos | Descrição |
|------|--------|-----------|
| `flag_conflito_interesses` | 40 | Servidor é sócio de empresa que fornece ao mesmo município onde é servidor |
| `flag_alto_salario_socio` | 20 | Servidor com remuneração elevada e participação societária ativa |
| `flag_bolsa_familia` | 15 | Servidor recebendo Bolsa Família concomitantemente ao vínculo público |
| `flag_duplo_vinculo_estado` | 15 | Duplo vínculo no funcionalismo estadual |
| `flag_multi_empresa` | 10 | Sócio de 3 ou mais empresas simultaneamente |

### 2.2. Interpretação do Score

Um score de **70** indica, necessariamente, a combinação de: conflito de interesses (40 pts) + multi-empresa (10 pts) + um terceiro fator (20 pts — alto salário, ou 15 pts de Bolsa Família mais 5 de arredondamento não aplicável). Na prática, todos os 73 servidores com score 70 acumulam conflito de interesses, multi-empresa e ao menos mais um indicador.

---

## 3. Distribuição de Risco

### 3.1. Flags Individuais

| Indicador | Servidores Afetados |
|-----------|-------------------|
| Recebendo Bolsa Família | 25.883 |
| Conflito de interesses | 2.618 |
| Sócio de 3+ empresas (multi-empresa) | 1.033 |

O indicador mais prevalente — **Bolsa Família concomitante ao vínculo público** — afeta 25.883 servidores (73% de todos com algum risco). Isoladamente, esse flag não configura irregularidade automática: o servidor pode ter sido incluído no programa antes da nomeação, estar em processo de exclusão, ou o cruzamento pode incluir homônimos. Contudo, a escala do fenômeno sugere que o processo de exclusão de beneficiários ao assumir cargo público é sistematicamente falho no estado.

O **conflito de interesses** afeta 2.618 servidores — situação em que a empresa do servidor tem contratos com o mesmo município que o remunera. Esse é o indicador de maior gravidade potencial, pois pode indicar direcionamento de contratos ou irregularidade nos processos de contratação.

### 3.2. Concentração Profissional

A dominância de médicos no topo do ranking reflete a estrutura do mercado de saúde pública na Paraíba: municípios contratam serviços de saúde via pessoa jurídica (CNPJ do médico), enquanto o mesmo profissional mantém vínculo empregatício direto com o município ou com o estado. Esse modelo é comum especialmente no interior, onde a oferta de especialistas é escassa e a mesma pessoa física é simultaneamente servidor e prestador de serviços via empresa.

---

## 4. Casos de Maior Risco (Score >= 70)

Todos os 73 servidores de score máximo têm score igual a 70. Os 20 casos com maiores valores de contratos em conflito de interesses são listados abaixo:

| Nome | Cargo | Empresas | Conflito R$ | Municípios |
|------|-------|----------|-------------|------------|
| NARAYANE DE OLIVEIRA SILVA SOARES | MEDICO PLANTONISTA CLIN GERAL | 3 | R$ 4,29M | Amparo, Caraúbas, Sumé, Zabelê |
| REGIS COSTA BOMFIM | MEDICO | 10 | R$ 1,38M | João Pessoa, Santa Rita |
| GUSTAVO ANACLETO LOURENCO COELHO | MEDICO OFTALMOLOGISTA | 3 | R$ 1,95M | Cajazeiras |
| RAFAEL DE ARRUDA SOUSA PINTO | MEDICO | 5 | R$ 1,08M | Cruz do Espírito Santo, Guarabira, João Pessoa, São Bento |
| PATRICIA CATAO CARTAXO LOUREIRO ARRUDA | MEDICO II | 3 | R$ 334,3K | Campina Grande |
| SILVIO ROMERO GONCALVES MONTEIRO SOBRINHO | MEDICO | 7 | R$ 315,9K | Campina Grande, João Pessoa |
| ANDRE LUIZ DE OLIVEIRA SILVA | MEDICO PLANTONISTA - POLICLINICA | 3 | R$ 980,3K | Santa Luzia, Teixeira |
| LEONARDO FRANCO FELIPE | MEDICO | 4 | R$ 533,5K | João Pessoa, Santa Rita |
| ITALO LUSTOSA ROLIM | MEDICO CIRURGIAO VASCULAR - CONTRATADO | 3 | R$ 84,9K | Cajazeiras, Uiraúna |
| RENATA GIZANI DE MOURA LEITE | MEDICO GASTROENTEROLOGISTA - CONTRATADO | 3 | R$ 64,5K | Cajazeiras |
| ROSINETE GUEDES LOPES BARRETO | PROFESSOR EDUCACAO BASICA 2 | 3 | R$ 53,4K | Campina Grande |
| ALYSSON GUIMARAES PASCOAL | MEDICO II PLANTONISTA | 3 | R$ 53,2K | Campina Grande |
| ANTONIO COUTINHO MADRUGA NETO | MEDICO | 4 | R$ 28,9K | João Pessoa |
| FABIO DA SILVA DELGADO | MEDICO | 3 | R$ 28,9K | João Pessoa |
| POLLYANNA SOUSA FERREIRA PAIVA CESARINO | MEDICO | 4 | R$ 22,7K | João Pessoa |
| ROMEU DE AZEVEDO MENEZES NETO | MEDICO(A) | 5 | R$ 22,7K | Cruz do Espírito Santo, João Pessoa |
| ANA PAULA PONTES RODRIGUES | MEDICO PSF | 4 | R$ 7K | João Pessoa, Mataraca |
| FULVIO SOARES PETRUCCI | MEDICO | 5 | R$ 4,1K | João Pessoa |
| MELISSA MEDEIROS LEITE FERRANTTI | MEDICO | 5 | R$ 1,2K | João Pessoa |
| FABIANA DE OLIVEIRA MELO | MEDICO - CTR | 3 | R$ 2,9K | Boa Vista, Pocinhos |

### 4.1. Casos que Merecem Aprofundamento

**NARAYANE DE OLIVEIRA SILVA SOARES** — R$ 4,29M em conflito de interesses distribuídos por **4 municípios pequenos** (Amparo, Caraúbas, Sumé e Zabelê). A concentração de contratos em municípios de baixa população e a diversidade geográfica são características atípicas. A magnitude financeira justifica verificação dos processos licitatórios em cada município.

**REGIS COSTA BOMFIM** — sócio de **10 empresas**, com R$ 1,38M em contratos conflitantes em João Pessoa e Santa Rita. A quantidade de CNPJs é o maior da lista e sugere estrutura societária complexa que merece análise da finalidade de cada empresa.

**GUSTAVO ANACLETO LOURENCO COELHO** — R$ 1,95M em contratos com Cajazeiras, sendo que atua como médico oftalmologista contratado pelo mesmo município. Especialidade única, alto volume, município único — padrão que pode indicar exclusividade de fato.

**RAFAEL DE ARRUDA SOUSA PINTO** — R$ 1,08M em contratos distribuídos por **4 municípios** (Cruz do Espírito Santo, Guarabira, João Pessoa, São Bento), com 5 empresas. A atuação simultânea em múltiplos municípios distantes geograficamente é atípica.

**ROSINETE GUEDES LOPES BARRETO** — único caso de não-médico no topo da lista: **professora** do ensino básico em Campina Grande, sócia de 3 empresas com R$ 53,4K em contratos com o município. Merece atenção por ser exceção ao padrão e pela natureza incompatível da atividade empresarial com o cargo docente.

---

## 5. Padrões Observados

### 5.1. Predominância de Médicos

**18 dos 20 servidores** de maior risco são médicos. Esse padrão não é aleatório: reflete características estruturais do sistema de saúde pública brasileiro.

Médicos frequentemente operam via pessoa jurídica (PJ) para prestação de serviços — modelo incentivado pela legislação tributária e consolidado como prática de mercado. Municípios, especialmente no interior, contratam especialistas por ausência de concurso para determinadas especialidades, utilizando contratos com CNPJ do próprio servidor ou de empresa por ele controlada.

O resultado é que o mesmo profissional pode acumular: (a) remuneração como servidor estatutário ou celetista, e (b) pagamentos a empresa da qual é sócio, pelos mesmos serviços ou serviços conexos. Isso configura conflito de interesses formal — e potencialmente acúmulo ilegal de remuneração — mas pode também ser estrutura plenamente regular, dependendo da natureza dos serviços contratados e das autorizações existentes.

### 5.2. Concentração Geográfica

Os municípios mais frequentes entre os casos de alto risco são **João Pessoa** (capital, aparece em 13 dos 20 casos) e **Campina Grande** (segunda maior cidade, 5 casos). Cajazeiras, no sertão, aparece 3 vezes — possivelmente por ser polo regional de saúde com elevada dependência de especialistas contratados via PJ.

### 5.3. Escala do Fenômeno Bolsa Família

Os 25.883 servidores recebendo Bolsa Família concomitantemente representam **7,3% do total de servidores** avaliados. Ainda que parte possa decorrer de defasagem nos cadastros, a magnitude indica falha sistêmica nos mecanismos de cruzamento e cancelamento de benefícios ao ingresso no serviço público. O valor agregado transferido indevidamente pode ser expressivo.

---

## 6. Correlação com Outros Achados

| Município | Servidores no Top 20 | Outros relatórios relacionados |
|-----------|---------------------|-------------------------------|
| João Pessoa | 13 | Relatorio risco municipal (Score 49), Q47 (R$96M fotovoltaico), Q53 (Doutor Work R$42M) |
| Campina Grande | 5 | Relatorio risco municipal (Score 48), Q59 (HSM2 R$2,2M) |
| Santa Rita | 2 | Relatorio risco municipal (Score 51), Q74 (servidores+BF) |
| Cajazeiras | 3 | Polo regional de saúde — padrão de contratação via PJ |

---

## 7. Limitações

1. **Homônimos:** O cruzamento por nome/CPF pode gerar falsos positivos, especialmente para nomes comuns no Bolsa Família.
2. **Empresas inativas:** CNPJs de empresas baixadas ou inativas ainda figuram no cruzamento societário — sócio formal não implica atividade econômica atual.
3. **Autorizações legais:** Médicos com acúmulo autorizado pelo órgão competente não configuram irregularidade, mas o dado de autorização não está disponível nesta análise.
4. **Score estático:** O score reflete o período analisado (2022-2026); situações resolvidas antes do período ou após o corte não são capturadas.
5. **Conflito de interesses — valor:** O valor de R$ atribuído ao conflito representa o total contratado pela empresa com o município, não necessariamente o valor que reverte ao servidor sócio (depende da participação societária e distribuição de lucros).

---

## Fontes

1. **TCE-PB SAGRES:** Folha de servidores municipais 2022-2026
2. **Receita Federal:** Quadro societário de empresas (CNPJ)
3. **PNCP / TCE-PB:** Contratos e empenhos municipais 2022-2026
4. **MDS / CadÚnico:** Beneficiários do Bolsa Família
5. **SIAPE:** Vínculos no funcionalismo estadual
6. **mv_servidor_pb_risco:** View materializada com score composto por servidor
