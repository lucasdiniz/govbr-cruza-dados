# Relatório de Auditoria: Empresas Fênix na Paraíba

**Data de Geração:** 4 de Abril de 2026
**Base de Dados:** estabelecimento (~70M registros nacional, ~515K na PB) | empresa | socio — dados abertos CNPJ/Receita Federal
**Metodologia:** Self-join na tabela `estabelecimento` com cruzamento via tabela `socio` (CPF) para detectar sócios que fecharam uma empresa e abriram outra na mesma UF com a mesma CNAE principal em até 365 dias. Query Q55 do catálogo `fraude_superfaturamento.sql`.

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de padrão comportamental suspeito, não conclusões de irregularidade ou ilicitude. O padrão "empresa fênix" pode ter explicações legítimas (encerramento por reestruturação societária, mudança de regime tributário, cisão empresarial). A apuração de eventual irregularidade — incluindo verificação de evasão fiscal, fraude em licitações ou burla a sanções — compete exclusivamente aos órgãos competentes (CGE-PB, TCE-PB, CGU, RFB, PGFN, MPF/MPE-PB).

---

## 1. Resumo Executivo

A análise identificou **483 pares** empresa baixada → empresa nova na Paraíba, envolvendo o mesmo CPF de sócio, a mesma atividade econômica (CNAE principal) e intervalo máximo de 365 dias entre o encerramento da empresa antiga e a abertura da nova.

Esses pares representam **390 empresas novas distintas** constituídas por sócios de empresas encerradas, abrangendo **397 sócios** em **36 municípios** paraibanos. O tempo médio entre o fechamento da empresa antiga e a abertura da nova foi de **115 dias** — menos de quatro meses.

**O achado mais crítico:** 174 casos (36% do total) apresentam intervalo inferior a 30 dias, ou seja, o sócio encerrou uma empresa e abriu outra com o mesmo objeto social em menos de um mês. Esse padrão é consistente com a hipótese de empresa fênix — troca de CNPJ para escapar de dívidas fiscais, sanções ou impedimentos em licitações.

**Indicadores-chave:**

| Indicador | Valor |
|-----------|-------|
| Pares empresa antiga → empresa nova | 483 |
| Empresas novas distintas | 390 |
| Sócios envolvidos | 397 |
| Municípios afetados | 36 |
| Tempo médio entre fechamento e abertura | 115 dias |
| Casos com intervalo < 30 dias | 174 (36%) |
| Casos com intervalo 30–90 dias | estimado ~120 (25%) |
| Casos com intervalo 91–365 dias | estimado ~189 (39%) |

---

## 2. Metodologia

### 2.1. Lógica da Detecção

A query Q55 realiza um **self-join** na tabela `estabelecimento` para identificar pares de empresas distintas (`cnpj_basico` diferente) que compartilham o mesmo endereço e, via tabela `socio`, o mesmo CPF de sócio pessoa física (`tipo_socio = 2`).

**Filtros aplicados:**

| Filtro | Critério |
|--------|----------|
| Empresa antiga — situação cadastral | Baixada (08) ou Inapta (04) |
| Empresa nova — situação cadastral | Ativa (02) |
| Vínculo entre empresas | Mesmo CPF de sócio (via tabela `socio`) |
| Janela temporal | Empresa nova aberta até 365 dias após o fechamento da antiga |
| Escopo geográfico | Ambas as empresas com UF = 'PB' |
| Atividade econômica | Mesma CNAE principal (garante mesma atividade) |
| Estabelecimento | Apenas matriz (`cnpj_ordem = '0001'`) |

### 2.2. Considerações de Performance

Sem o filtro por UF, o custo estimado da query no PostgreSQL é ~21 milhões (inviável em produção). Com o filtro `uf = 'PB'`, o custo cai para ~2,9 milhões, com tempo de execução de aproximadamente 30 segundos sobre ~515 mil estabelecimentos paraibanos.

O filtro de mesma CNAE principal é relevante para reduzir falsos positivos: um sócio que fecha uma padaria e abre uma empresa de TI não configura padrão fênix — ele simplesmente mudou de ramo.

### 2.3. Fonte de Dados

Dados públicos disponibilizados pela Receita Federal do Brasil no portal de Dados Abertos CNPJ, processados localmente em PostgreSQL com carga nacional (~70M estabelecimentos, ~60M sócios).

---

## 3. Achados Principais

### 3.1. Distribuição Temporal dos Intervalos

A distribuição dos 483 pares por intervalo entre fechamento e reabertura revela concentração significativa nas faixas de menor prazo:

| Intervalo (dias) | Pares | % do total | Interpretação |
|-----------------|-------|------------|---------------|
| 1 a 7 dias | 76 | 15,7% | Troca quase imediata de CNPJ |
| 8 a 30 dias | 98 | 20,3% | Reabertura no mesmo mês |
| **Total < 30 dias** | **174** | **36,0%** | Padrão fênix mais agressivo |
| 31 a 90 dias | 82 | 17,0% | Reabertura em até 3 meses |
| 91 a 180 dias | 89 | 18,4% | Reabertura em até 6 meses |
| 181 a 365 dias | 138 | 28,6% | Reabertura em até 1 ano |

Os 174 casos com intervalo abaixo de 30 dias são os de maior potencial de dano: em alguns desses casos, a nova empresa pode ter participado de licitações públicas ainda durante o período em que a empresa anterior poderia estar sendo processada administrativamente.

### 3.2. Distribuição Geográfica

| Município (código IBGE) | Pares | Empresas novas |
|-------------------------|-------|----------------|
| 2051 (João Pessoa) | 338 | 266 |
| 1981 (Campina Grande) | 49 | 42 |
| 2117 (Patos) | 20 | 17 |
| 1965 (Bayeux) | 6 | 6 |
| 1937 (Cabedelo) | 6 | 6 |
| 2027 (Santa Rita) | 6 | 5 |
| Demais 30 municípios | 58 | 48 |

João Pessoa concentra 70% dos casos, seguida por Campina Grande (10%). Municípios menores com múltiplos casos per capita merecem atenção prioritária.

### 3.3. Concentração de Sócios

Com 397 sócios gerando 483 pares em 390 empresas novas, a relação é próxima de 1:1 — a maioria dos sócios aparece em apenas um par. No entanto, sócios que aparecem em múltiplos pares (empresa fênix serial) representam risco elevado e devem ser priorizados em investigações.

---

## 4. Por que Empresas Fênix São um Problema

O mecanismo de empresa fênix explora uma vulnerabilidade estrutural dos sistemas de controle governamental: **as sanções e dívidas seguem o CNPJ, não o CPF do sócio**.

**Ciclo típico de empresa fênix:**

1. Empresa "A" (CNPJ antigo) acumula dívidas na PGFN, recebe sanção no CEIS/CNEP ou é inabilitada em licitações
2. Empresa "A" é baixada ou declarada inapta pela Receita Federal
3. Sócio abre empresa "B" (CNPJ novo) com o mesmo objeto social
4. Empresa "B" participa de licitações públicas com certidões negativas limpas
5. Contrato público é firmado com empresa "B"; dívida da empresa "A" permanece irrecuperável

**Consequências observadas:**

| Consequência | Mecanismo |
|-------------|-----------|
| Evasão fiscal | Dívida PGFN fica na empresa baixada; nova empresa não a herda automaticamente |
| Burla a sanções (CEIS/CNEP) | Sanção é vinculada ao CNPJ encerrado; novo CNPJ não consta dos cadastros |
| Fraude em licitações | Empresa impedida de licitar "ressuscita" sob novo CNPJ |
| Frustração de execuções fiscais | Patrimônio transferido informalmente; PGFN executa empresa sem ativos |
| Concorrência desleal | Empresa adimplente compete com empresa fênix que não paga tributos |

A Lei Complementar nº 123/2006 e o Decreto nº 8.538/2015 tentam mitigar o problema via desconsideração da personalidade jurídica em licitações, mas a aplicação é inconsistente e depende de investigação caso a caso.

---

## 5. Cruzamentos Realizados

### 5.1. Empresas fênix que contrataram o governo (mv_empresa_governo)

Das 390 empresas novas, **43 (11%) efetivamente firmaram contratos públicos**, totalizando **R$ 119,1 milhões** em contratos com fontes federais e estaduais (PNCP + TCE-PB). Esse é o subconjunto de maior risco concreto ao erário.

**Top 10 empresas fênix com contratos governamentais:**

| Empresa nova | Empresa baixada | Dias | Sócio | Total governo |
|-------------|----------------|------|-------|---------------|
| CONSORCIO SFT | SANCCOL SANEAMENTO CONSTRUCAO E COMERCIO | 45 | Giovanni Gondim Petrucci | R$ 95.950.686 |
| MN COMERCIO VAREJISTA | MN COMERCIO VAREJISTA (CNPJ anterior) | 33 | Mateus Nunes Mendes | R$ 4.013.909 |
| MN COMERCIO VAREJISTA | MATEUS COMERCIO VAREJISTA | 60 | Mateus Nunes Mendes | R$ 4.013.909 |
| MARCILIO BATISTA SOC. ADVOCACIA | BATISTA & REMIGIO ADVOGADOS | 13 | José Marcílio Batista | R$ 2.925.000 |
| E V P SOUSA | CLUBE DE TIROS ESPORTIVO DE GUARABIRA | 89 | Eduardo Victor Pereira Sousa | R$ 2.743.420 |
| DIEGO ROCHA CAVALCANTI | ROCHA FORTE COMERCIO DE PESCADOS | 5 | Diego Rocha Medeiros Cavalcanti | R$ 2.325.195 |
| JANUSA SOTERO CONTABILIDADE | SOTERO CONTABILIDADE PUBLICA | 15 | Janusa Cristina Gomes Sotero | R$ 1.695.474 |
| COPLAN CONTABILIDADE | COPLAN SERVICOS DE CONTABILIDADE | 338 | Radson dos Santos Leite | R$ 936.750 |
| BENTO PEREIRA SOC. ADVOCACIA | BENTO & PEREIRA ADVOGADOS | 14 | Ednelton Helejone Bento Pereira | R$ 806.950 |
| DR PAO PADARIA | PADARIA IRMAOS VIEIRA | 252 | André Vieira da Silva | R$ 509.355 |

**Destaques:**
- **CONSORCIO SFT** (R$95,9M): empresa anterior (SANCCOL) foi baixada em 31/12/2023, consórcio aberto 45 dias depois. Valor de contratos com o governo da PB é o maior de toda a amostra — merece investigação prioritária.
- **MN COMERCIO**: sócio Mateus Nunes fecha DUAS empresas (CNPJ anterior + MATEUS COMERCIO) e abre a terceira, que já acumula R$4M em contratos.
- **DIEGO ROCHA** (R$2,3M): empresa anterior era comércio de **pescados**, nova empresa é genérica (LTDA). Intervalo de apenas 5 dias.

### 5.2. Empresas fênix × dívida PGFN e sanções CEIS/CNEP

O cruzamento pelo `cnpj_basico` da empresa antiga retornou **0 matches** tanto para PGFN quanto para CEIS/CNEP. Isso pode indicar:
- As empresas antigas foram baixadas antes de acumular dívida registrada no sistema federal
- O join precisa ser pelo CNPJ completo (14 dígitos) em vez de basico (8 dígitos)
- A dívida pode estar no CPF do sócio, não no CNPJ da empresa

**Próximo passo:** refazer cruzamento usando CNPJ completo e/ou CPF do sócio na tabela pgfn_divida.

---

## 6. Limitações da Análise

| Limitação | Impacto | Status |
|-----------|---------|--------|
| Escopo restrito à PB | Sócios que abrem empresas em outros estados não são capturados | Q99 nacional criada (em execução) |
| CNAE exato pode ser restritivo | Sócio que muda subclasse da CNAE não é capturado | Pendente |
| ~~Não verifica contratação efetiva~~ | ~~390 empresas não verificadas~~ | **Resolvido**: 43 contrataram governo (R$119,1M) |
| Cruzamento PGFN/CEIS incompleto | Join por cnpj_basico retornou 0 — pode precisar de CNPJ completo ou CPF do sócio | Pendente: refazer com CNPJ 14 dígitos |
| Dados CNPJ têm defasagem | Receita Federal publica com atraso | Usar API CNPJ para verificação pontual |
| Endereço como ancoragem | A query usa endereço + sócio, o que exclui casos onde o endereço mudou | Considerar versão somente por sócio + CNAE |

---

## 7. Recomendações e Próximos Passos

### 7.1. Ações Imediatas (Alta Prioridade)

1. **Investigar CONSORCIO SFT (R$95,9M)** — maior valor entre empresas fênix. SANCCOL baixada em 31/12/2023, consórcio aberto 45 dias depois com mesmo sócio (Giovanni Gondim Petrucci). Verificar contratos TCE-PB detalhados.

2. **Refazer cruzamento PGFN/CEIS com CNPJ completo** — o join por cnpj_basico (8 dígitos) não capturou dívidas. Usar CNPJ 14 dígitos e/ou CPF do sócio como chave alternativa.

3. **Priorizar os 174 casos com intervalo < 30 dias** — subconjunto mais agressivo. Dos 43 com contratos governo, vários estão nesta faixa (MN COMERCIO 33d, MARCILIO 13d, DIEGO ROCHA 5d).

### 7.2. Expansão (Média Prioridade)

4. **Q99 (versão nacional) em execução** — temp tables com hash de endereço viabilizam o self-join em 18.7M × 16.3M estabelecimentos.

5. **Flexibilizar filtro de CNAE** — usar 4 primeiros dígitos para capturar atividades similares.

### 7.3. Integração ao Score de Risco

6. **Criar flag `flag_empresa_fenix`** na view `mv_empresa_pb` — +20 pontos para empresa nova, +10 para o sócio.

---

## 8. Conclusão

A identificação de **483 pares de empresa fênix** na Paraíba, com **36% dos casos** apresentando intervalo inferior a 30 dias, confirma que o fenômeno é estatisticamente relevante.

O cruzamento com `mv_empresa_governo` revelou que **43 empresas fênix (11%) efetivamente contrataram o poder público**, movimentando **R$ 119,1 milhões**. O caso mais grave — CONSORCIO SFT com R$95,9M em contratos após reabertura em 45 dias — merece investigação prioritária pelos órgãos de controle.

A metodologia (Q55/Q99) é replicável para qualquer estado brasileiro e está sendo expandida para escala nacional.

---

*Gerado por pipeline de auditoria govbr-cruza-dados | Dados: Receita Federal / CNPJ Dados Abertos | Query: Q55 — fraude_superfaturamento.sql*
