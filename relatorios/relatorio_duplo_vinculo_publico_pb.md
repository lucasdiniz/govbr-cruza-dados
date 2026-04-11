# Relatorio de Investigacao: Duplo Vinculo Publico na Paraiba

**Data de Geracao:** 11 de abril de 2026
**Base de Dados:** Query Q301 -- `siape_cadastro` x `tce_pb_servidor`
**Metodologia:** cruzamento de servidores federais lotados na PB (SIAPE) com servidores municipais (TCE-PB) por 6 digitos centrais do CPF + nome normalizado.

> **Disclaimer:** Este relatorio apresenta cruzamentos automatizados de dados publicos. A acumulacao de cargos publicos e permitida pela Constituicao em casos especificos (art. 37, XVI): dois cargos de professor, um cargo de professor com outro tecnico/cientifico, ou dois cargos privativos de profissional de saude com profissao regulamentada. A presenca nesta lista nao implica irregularidade automatica.

---

## 1. Resumo Executivo

A Query Q301 identificou **815 pessoas** que aparecem simultaneamente como servidores federais (SIAPE) e servidores municipais (TCE-PB).

| Metrica | Valor |
|---|---|
| Total de duplos vinculos | **815** |
| Servidores federais ativos | **704** (86%) |
| Municipios PB distintos | **124** de 223 |
| Orgaos federais distintos | **21** |
| Salario municipal medio | **R$ 10.310** |
| Maior salario municipal | **R$ 62.910** |

---

## 2. Concentracao por Municipio

| Municipio | Duplos vinculos |
|---|---|
| Joao Pessoa | **333** (41%) |
| Campina Grande | **94** (12%) |
| Cabedelo | **41** |
| Patos | **21** |
| Santa Rita | **20** |
| Bayeux | **17** |
| Conde | **12** |
| Sousa | **12** |
| Esperanca | **12** |
| Cajazeiras | **11** |

## 3. Concentracao por Orgao Federal

| Orgao federal | Duplos vinculos |
|---|---|
| Universidade Federal da Paraiba (UFPB) | **423** (52%) |
| Universidade Federal de Campina Grande (UFCG) | **212** (26%) |
| Instituto Federal da Paraiba (IFPB) | **101** (12%) |
| Ministerio da Previdencia Social | **25** |
| INSS | **14** |
| IBGE | **13** |
| ICMBio | **8** |
| Ministerio da Saude | **4** |

## 4. Tipo de Cargo Municipal

| Tipo | Quantidade |
|---|---|
| Efetivos | **396** (49%) |
| Contratacao por excepcional interesse publico | **208** (26%) |
| Efetivo | **98** (12%) |
| Cargo Comissionado | **58** (7%) |
| Inativos/Pensionistas | **23** (3%) |

---

## 5. Casos Prioritarios

### 5.1. Maiores salarios municipais acumulados

| Servidor | Cargo federal | Orgao federal | Municipio | Cargo municipal | Salario municipal |
|---|---|---|---|---|---|
| Geronimo Franco de Almeida | Medico PCCTAE | UFPB | Bayeux | Medico Endoscopista | R$ 62.910 |
| Adriana Suely de Oliveira Melo | Professor Magisterio Superior | UFCG | Campina Grande | Medico II | R$ 62.805 |
| Waldemar de Albuquerque Aranha Neto | Professor Magisterio Superior | UFPB | Joao Pessoa | Ag. Fisc. Aud. de Tributos | R$ 61.335 |
| Mayra Pereira dos Santos | Professor Magisterio Superior | UFCG | Campina Grande | Medico II | R$ 59.822 |
| Sandra Giovana Muniz de Macedo Mendes | Medico PCCTAE | UFPB | Cabedelo | Medico Pediatra 40H | R$ 58.920 |
| Tomazia Rakielle Estrela de Oliveira | Medico PCCTAE | IFPB | Sousa | Medico Socorrista | R$ 57.404 |

### 5.2. Padrao medico-professor dominante

O padrao mais recorrente e de **medicos e professores universitarios federais** que simultaneamente atuam como medicos municipais. Dos 815 casos, a maioria dos top 50 sao medicos da UFPB/UFCG que tambem atuam no SUS municipal, com salarios municipais de R$ 25.000-62.000. A acumulacao medico+medico e permitida (art. 37, XVI, "c" CF), mas exige compatibilidade de horarios e carga total de 60h semanais.

### 5.3. Casos com maior risco de irregularidade

Os casos de **maior risco** sao aqueles onde o cargo federal NAO e de saude nem de professor:

- **Assistente em Administracao** (UFPB/UFCG) + cargo municipal efetivo -- nao se enquadra nas excecoes constitucionais
- **Secretario Executivo** + Professor municipal
- **Tecnico em Assuntos Educacionais** + cargo municipal administrativo
- **Arquivista** + cargo municipal
- **Tecnico Desportivo** + Professor municipal

Estes cargos tecnicos/administrativos federais acumulados com cargos municipais provavelmente violam o art. 37, XVI da Constituicao, que so permite acumulacao nos tres casos listados no disclaimer.

---

## 6. Padroes Transversais

### 6.1. Contratacoes temporarias como porta de entrada
208 casos (26%) envolvem "Contratacao por excepcional interesse publico" no municipio. Contratacoes temporarias sao mais faceis de criar e menos fiscalizadas, podendo servir como mecanismo para acomodar servidores federais em folha municipal sem concurso.

### 6.2. Cargos comissionados
58 casos envolvem Cargo Comissionado municipal, sugerindo indicacao politica de servidores federais para cargos de confianca nos municipios.

### 6.3. Inativos federais em cargo municipal
23 casos envolvem inativos/pensionistas federais que aparecem em folha municipal. Aposentados podem acumular com cargo publico apenas nos mesmos casos permitidos para ativos (art. 37, XVI e §10 CF).

---

## 7. Fundamentacao Juridica

- **Art. 37, XVI da CF/88:** veda a acumulacao remunerada de cargos publicos, exceto: (a) dois cargos de professor; (b) um de professor com outro tecnico/cientifico; (c) dois cargos privativos de profissional de saude com profissao regulamentada.
- **Art. 37, XVII da CF/88:** a proibicao se estende a autarquias, fundacoes, empresas publicas e sociedades de economia mista.
- **Art. 132, XII da Lei 8.112/90:** demissao por acumulacao ilegal de cargos.
- **Sumula Vinculante 46 do STF:** a definicao dos cargos de natureza tecnica para efeito de acumulacao deve considerar a atribuicao do cargo.

---

## 8. Recomendacoes

1. **Priorizar investigacao dos cargos administrativos federais** (Assistente em Administracao, Secretario Executivo, Tecnico em Arquivo) acumulados com cargos municipais -- estes NAO se enquadram nas excecoes constitucionais.
2. **Verificar compatibilidade de horarios** nos casos de medicos e professores -- a acumulacao e permitida, mas exige que a soma das cargas horarias nao exceda 60h semanais.
3. **Auditar contratacoes temporarias municipais** de servidores federais -- 208 casos sugerem uso do mecanismo para contornar vedacao.
4. **Cruzar com folha de pagamento completa** para calcular remuneracao total (federal + municipal) e verificar se excede o teto constitucional.
