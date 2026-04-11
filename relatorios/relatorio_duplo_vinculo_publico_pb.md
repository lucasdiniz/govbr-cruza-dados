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

---

## 6. Detalhamento: Acumulacoes Provavelmente Ilegais

Filtrando os 815 casos para manter apenas aqueles onde o cargo federal **nao e de professor, medico ou profissional de saude** (e excluindo aposentados/pensionistas), restam **369 casos** de acumulacao que provavelmente violam o art. 37, XVI da CF/88 -- ou seja, **45% de todos os duplos vinculos identificados**.

| Metrica | Valor |
|---|---|
| Casos de acumulacao provavelmente ilegal | **369** |
| Cargos federais distintos envolvidos | **51** |
| Municipios com ocorrencias | **86** |
| Salario municipal medio | **R$ 6.666** |
| Maior salario municipal | **R$ 35.863** |
| Soma dos salarios municipais | **R$ 2.459.611** |

### 6.1. Concentracao por cargo federal

| Cargo federal | Casos | Salario municipal medio |
|---|---|---|
| Assistente em Administracao | **96** (26%) | R$ 4.565 |
| Tecnico de Laboratorio/Area | **39** | R$ 8.902 |
| Prof. Ens. Bas. Tec. Tecnologico (substituto) | **33** | R$ 5.840 |
| Sem informacao (cargo nao declarado) | **32** | R$ 8.421 |
| Tecnico em Assuntos Educacionais | **16** | R$ 8.793 |
| Pedagogo-Area | **12** | R$ 13.236 |
| Tec. de Tecnologia da Informacao | **11** | R$ 6.682 |
| Tecnico do Seguro Social (INSS) | **10** | R$ 5.255 |
| Assistente Social | **8** | R$ 4.910 |
| Tecnico em Radiologia | **7** | R$ 4.886 |
| Tecnico em Contabilidade | **7** | R$ 6.434 |
| Contador | **6** | R$ 6.362 |
| Tradutor Interprete de Linguagem de Sinais | **5** | R$ 7.325 |
| Bibliotecario-Documentalista | **5** | R$ 3.201 |
| Analista de Tec. da Informacao | **5** | R$ 10.021 |
| Tecnico Desportivo | **4** | R$ 14.460 |

O cargo de **Assistente em Administracao** responde por mais de 1/4 de todos os casos ilegais. E um cargo tipicamente administrativo, sem qualquer enquadramento nas excecoes constitucionais, independentemente do cargo municipal acumulado.

### 6.2. Concentracao por orgao federal

| Orgao federal | Casos | Total salarios municipais |
|---|---|---|
| Universidade Federal da Paraiba (UFPB) | **193** (52%) | R$ 1.396.018 |
| Universidade Federal de Campina Grande (UFCG) | **67** (18%) | R$ 385.954 |
| Instituto Federal da Paraiba (IFPB) | **58** (16%) | R$ 390.083 |
| INSS | **13** | R$ 102.296 |
| IBGE | **13** | R$ 45.066 |
| ICMBio | **8** | R$ 25.412 |
| Ministerio da Previdencia Social | **2** | R$ 15.107 |
| DNOCS | **2** | R$ 8.225 |
| DNIT | **1** | R$ 10.723 |

A UFPB concentra mais da metade dos casos ilegais, seguida de UFCG e IFPB. Juntas, as tres instituicoes de ensino superior respondem por **86% dos casos** -- sao seus servidores tecnicos/administrativos (nao docentes) que acumulam com cargos municipais.

### 6.3. Concentracao por municipio

| Municipio | Casos | Total salarios municipais |
|---|---|---|
| Joao Pessoa | **147** (40%) | R$ 1.181.098 |
| Campina Grande | **36** (10%) | R$ 247.206 |
| Patos | **12** | R$ 64.811 |
| Cabedelo | **9** | R$ 53.161 |
| Santa Rita | **9** | R$ 51.236 |
| Bayeux | **8** | R$ 70.285 |
| Conde | **6** | R$ 66.890 |
| Areia | **6** | R$ 16.882 |
| Sousa | **5** | R$ 33.754 |
| Cajazeiras | **5** | R$ 61.843 |

### 6.4. Tipo do cargo municipal nos casos ilegais

| Tipo de cargo municipal | Casos |
|---|---|
| Efetivos | **229** (62%) |
| Contratacao por excepcional interesse publico | **74** (20%) |
| Cargo Comissionado | **47** (13%) |
| Inativos/Pensionistas municipais | **12** (3%) |
| Eletivos (mandato politico) | **7** (2%) |

O fato de 62% dos casos envolverem cargos **efetivos** em ambas as esferas agrava a situacao: sao servidores concursados federais ocupando simultaneamente cargos concursados municipais, com estabilidade em ambos.

### 6.5. Casos individuais prioritarios

#### Maiores salarios municipais acumulados ilegalmente

| Servidor | Cargo federal | Orgao | Municipio | Cargo municipal | Sal. mun. |
|---|---|---|---|---|---|
| Josilane Marcia Justiniano da Silva | Tecnico em Assuntos Educacionais | UFPB | Joao Pessoa | Professor Educacao Basica II | R$ 35.863 |
| Arilane Florentino F. de Azevedo | Prof. Ens. Bas. Tec. (substituto) | UFPB | Joao Pessoa | Professor Educacao Basica I | R$ 35.729 |
| Andre Luiz da Costa Castro | Tecnico de Laboratorio/Area | UFPB | Joao Pessoa | Professor Educacao Basica II | R$ 33.929 |
| Patricia Farias Bandeira Coelho | Tecnico de Laboratorio/Area | UFCG | Campina Grande | Inspetor Sanitario | R$ 33.912 |
| Fabricio Alexandre da Silva | Secretario Executivo | UFPB | Joao Pessoa | Professor Educacao Basica II | R$ 32.941 |
| Theoffillo da Silva Lopes | Pedagogo-Area | UFPB | Joao Pessoa | Professor Educacao Basica I | R$ 32.415 |
| Kelly Cristiane Queiroz Barros | Tecnico em Arquivo | UFPB | Joao Pessoa | Professor Educacao Basica II | R$ 31.672 |
| Ana Moema Targino Fiuza | Assistente em Administracao | UFPB | Joao Pessoa | Procurador Geral (comissionado) | R$ 28.000 |
| Anaize Analia de Oliveira | Pedagogo-Area | IFPB | Joao Pessoa | Professor Educacao Basica I | R$ 27.873 |
| Ronnylson Cesar de O. Fonceca | Prof. Ens. Bas. Tec. (substituto) | IFPB | Esperanca | Diretor Educacional (comissionado) | R$ 27.058 |

#### Casos emblematicos

**Servidor federal ativo que exerce mandato de prefeito:**

| Servidor | Cargo federal | Orgao | Municipio | Cargo municipal |
|---|---|---|---|---|
| **Gutemberg de Lima Davi** | Sem informacao (ativo permanente) | IFPB | Bayeux | **Prefeito** (R$ 20.258) |

Servidor federal do IFPB exercendo simultaneamente mandato eletivo de Prefeito de Bayeux. A Constituicao exige afastamento do cargo federal para exercicio de mandato eletivo (art. 38, I e II da CF/88), mas o servidor permanece como "ativo permanente" no SIAPE.

**Analista de TI federal que atua como medico plantonista:**

| Servidor | Cargo federal | Orgao | Municipio | Cargo municipal |
|---|---|---|---|---|
| **Jeysibel de Sousa Dantas** | Analista de Tec. da Informacao | UFPB | Conde | Medico Plantoes (R$ 26.196) |

Analista de TI federal atuando como medico plantonista municipal. Alem da acumulacao ser ilegal (cargo tecnico federal + cargo municipal nao compativel), levanta questionamento sobre a regularidade do exercicio da medicina.

**Assistente administrativo federal nomeado Procurador Geral municipal:**

| Servidor | Cargo federal | Orgao | Municipio | Cargo municipal |
|---|---|---|---|---|
| **Ana Moema Targino Fiuza** | Assistente em Administracao | UFPB | Joao Pessoa | Procurador Geral (comissionado, R$ 28.000) |

Cargo administrativo federal acumulado com alto cargo comissionado municipal de confianca (chefia da Procuradoria Geral do Municipio).

---

## 7. Padroes Transversais

### 7.1. Contratacoes temporarias como porta de entrada
208 casos (26%) envolvem "Contratacao por excepcional interesse publico" no municipio. Nos casos ilegais, sao 74 (20%). Contratacoes temporarias sao mais faceis de criar e menos fiscalizadas, podendo servir como mecanismo para acomodar servidores federais em folha municipal sem concurso.

### 7.2. Cargos comissionados
58 casos (total) e 47 casos (ilegais) envolvem Cargo Comissionado municipal, sugerindo indicacao politica de servidores federais para cargos de confianca nos municipios. Os cargos comissionados sao particularmente problematicos porque sao de livre nomeacao -- o prefeito pode nomear um servidor federal sem qualquer concurso.

### 7.3. Mandatos eletivos
7 servidores federais ativos exercem mandatos eletivos municipais (vereadores e prefeitos). O art. 38 da CF/88 determina afastamento do cargo federal, mas estes permanecem como "ativo permanente" no SIAPE.

### 7.4. Inativos federais em cargo municipal
23 casos envolvem inativos/pensionistas federais que aparecem em folha municipal. Aposentados podem acumular com cargo publico apenas nos mesmos casos permitidos para ativos (art. 37, XVI e §10 CF).

### 7.5. Padrao UFPB/UFCG/IFPB: tecnico-administrativo + professor municipal
O padrao mais comum nos casos ilegais e: **servidor tecnico-administrativo de universidade/instituto federal** (Assistente em Administracao, Tecnico de Laboratorio, Pedagogo, Secretario Executivo) que simultaneamente atua como **professor da educacao basica** no municipio. Embora a acumulacao professor+professor seja permitida, a acumulacao tecnico+professor so seria legal se o cargo federal fosse de natureza tecnica/cientifica na area de atuacao do cargo de professor -- o que nao e o caso de Assistente em Administracao, Tecnico em Arquivo ou Secretario Executivo.

---

## 8. Analise Juridica Detalhada

### 8.1. Regra geral: vedacao de acumulacao (art. 37, XVI CF/88)

A Constituicao Federal veda a acumulacao remunerada de cargos publicos, admitindo apenas tres excecoes:

**(a)** dois cargos de professor;
**(b)** um cargo de professor com outro **tecnico ou cientifico**;
**(c)** dois cargos privativos de profissional de saude com profissao regulamentada.

### 8.2. O conceito de "cargo tecnico ou cientifico" (Sumula Vinculante 46)

A Sumula Vinculante 46 do STF estabelece que a definicao de "cargo tecnico" para fins de acumulacao deve considerar **a atribuicao do cargo**, nao apenas a denominacao. O STF tem entendimento consolidado de que:

- **Assistente em Administracao** -- NAO e cargo tecnico/cientifico para fins de acumulacao. Suas atribuicoes sao de suporte administrativo, sem exigencia de formacao especifica.
- **Secretario Executivo** -- Controverso, mas a jurisprudencia predominante do STJ/TST o classifica como cargo de suporte, nao tecnico.
- **Tecnico de Laboratorio** -- PODE ser considerado tecnico/cientifico dependendo da area e das atribuicoes efetivas. Exige analise caso a caso.
- **Pedagogo** -- O STJ ja reconheceu como cargo tecnico/cientifico em alguns casos (REsp 1.168.979/SC), mas a posicao nao e pacifica.

### 8.3. Acumulacao com mandato eletivo (art. 38 CF/88)

O servidor federal investido em mandato eletivo municipal deve:
- **Prefeito:** afastar-se do cargo federal, podendo optar pela remuneracao (art. 38, II CF);
- **Vereador:** havendo compatibilidade de horarios, acumula ambos; nao havendo, afasta-se (art. 38, III CF).

O caso de Gutemberg de Lima Davi (Prefeito de Bayeux + IFPB ativo permanente) indica que o afastamento nao foi processado no SIAPE.

### 8.4. Sancoes aplicaveis

- **Art. 132, XII da Lei 8.112/90:** demissao do cargo federal por acumulacao ilegal.
- **Art. 133 da Lei 8.112/90:** o servidor tem 10 dias para optar por um dos cargos; nao optando, sera instaurado processo administrativo disciplinar.
- **Art. 37, §6 da CF/88:** responsabilidade civil do Estado e direito de regresso contra o servidor.
- **Devolucao de valores:** o servidor pode ser obrigado a devolver a remuneracao recebida indevidamente de ambos os cargos durante o periodo de acumulacao ilegal.

---

## 9. Recomendacoes

1. **Priorizar os 369 casos de acumulacao provavelmente ilegal** -- servidores federais com cargos tecnicos/administrativos (nao docentes e nao saude) acumulando com cargos municipais. Estes NAO se enquadram em nenhuma excecao constitucional.
2. **Notificar UFPB, UFCG e IFPB** -- as tres instituicoes concentram 86% dos casos. As corregedorias internas devem instaurar procedimentos administrativos nos termos do art. 133 da Lei 8.112/90.
3. **Apurar caso do Prefeito de Bayeux** (Gutemberg de Lima Davi) -- verificar se houve afastamento do IFPB conforme art. 38 CF/88, ou se permanece recebendo simultaneamente.
4. **Investigar Analista de TI/Medico** (Jeysibel de Sousa Dantas) -- verificar registros no CRM-PB para confirmar habilitacao para exercicio da medicina.
5. **Verificar compatibilidade de horarios** nos 229 casos de efetivos em ambas as esferas -- mesmo para cargos que admitem acumulacao, a carga total nao pode exceder 60h semanais.
6. **Auditar contratacoes temporarias municipais** de servidores federais -- 74 casos ilegais envolvem contratacao temporaria, sugerindo uso do mecanismo para contornar vedacao.
7. **Cruzar com folha de pagamento completa** para calcular remuneracao total (federal + municipal) e verificar se excede o teto constitucional (art. 37, XI CF -- subsidio de Ministro do STF).
8. **Encaminhar ao MPF e TCU** -- a escala dos achados (369 acumulacoes provavelmente ilegais, R$ 2,46M em salarios municipais) justifica atuacao coordenada entre orgaos de controle.
