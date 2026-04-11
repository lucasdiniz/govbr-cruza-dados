# Relatorio de Investigacao: Porta Giratoria -- Servidor Municipal Socio de Fornecedor na Paraiba

**Data de Geracao:** 11 de abril de 2026
**Base de Dados:** Query Q308 -- `tce_pb_servidor` x `socio` (RFB) x `tce_pb_despesa`
**Metodologia:** cruzamento de servidores municipais PB com quadro societario de empresas (RFB) por 6 digitos centrais do CPF + nome normalizado, filtrado por empresas que recebem pagamentos municipais via TCE-PB.

> **Disclaimer:** Este relatorio apresenta cruzamentos automatizados de dados publicos. A condicao de socio de empresa por si so nao configura irregularidade. Porem, quando o servidor publico e simultaneamente socio de empresa fornecedora do proprio municipio onde atua, ha conflito de interesses que pode violar a Lei de Improbidade Administrativa (Lei 8.429/92) e o art. 9 da Lei de Licitacoes (Lei 14.133/21). A presenca nesta lista indica necessidade de investigacao aprofundada.

---

## 1. Resumo Executivo

A Query Q308 identificou **4.616 servidores municipais da Paraiba** que sao simultaneamente socios de empresas que fornecem bens ou servicos a municipios do estado.

| Metrica | Valor |
|---|---|
| Total de servidores-socios | **4.616** |
| Empresas fornecedoras distintas | **3.694** |
| Municipios com ocorrencias | **225** de 223 |
| Valor total recebido pelas empresas | **> R$ 1 bilhao** |

---

## 2. Concentracao por Municipio

| Municipio | Casos |
|---|---|
| Joao Pessoa | **691** (15%) |
| Campina Grande | **435** (9%) |
| Patos | **190** |
| Cabedelo | **106** |
| Sape | **83** |
| Bayeux | **82** |
| Santa Rita | **79** |
| Sousa | **74** |
| Cajazeiras | **66** |
| Queimadas | **63** |
| Guarabira | **58** |
| Monteiro | **48** |
| Esperanca | **46** |
| Conde | **41** |
| Pombal | **41** |

---

## 3. Perfil por Tipo de Cargo

| Tipo de cargo | Casos |
|---|---|
| Outros (administrativo, tecnico, etc.) | **1.911** (41%) |
| Medico | **1.535** (33%) |
| Assessor | **369** (8%) |
| Professor | **284** (6%) |
| Secretario | **199** (4%) |
| Enfermeiro/Tec. Enfermagem | **123** (3%) |
| Coordenador | **94** (2%) |
| Comissionado | **76** (2%) |
| Aposentado/Inativo | **26** (1%) |

O padrao dominante e de **medicos municipais socios de empresas de saude** que prestam servico aos mesmos municipios. Medicos representam 33% dos casos, refletindo a pejotizacao comum no setor de saude publica.

---

## 4. Caso Emblematico: I2 Servicos Saude Ltda

A empresa **I2 SERVICOS SAUDE LTDA** (CNPJ basico 35996035) concentra o maior numero de servidores-socios na amostra:

| Metrica | Valor |
|---|---|
| Servidores municipais que sao socios | **40+** |
| Municipios atendidos pela empresa | **16** |
| Total recebido de municipios PB | **R$ 67.743.819** |
| Cargo predominante dos servidores | Medico (plantonista, PSF, clinico) |

A empresa atua em 16 municipios simultaneamente e tem dezenas de medicos municipais como socios. A maioria das entradas no quadro societario ocorreu em **2024-2025**, com datas de entrada futuras (ex: 2025-12-12), sugerindo inclusao retroativa ou pre-datada no quadro societario da RFB.

### Municipios atendidos pela I2

Joao Pessoa, Campina Grande, Santa Rita, Bayeux, Inga, Alagoa Grande, Mari, Tapero, Caldas Brandao, Nova Olinda, Bonito de Santa Fe, Soledade, Monteiro, Rio Tinto, Curral de Cima, Araagi, entre outros.

---

## 5. Casos Prioritarios (excluindo I2 e CAGEPA)

### 5.1. Maiores valores recebidos

| Servidor | Municipio | Cargo | Empresa | Entrada sociedade | Total recebido | Mun. atendidos |
|---|---|---|---|---|---|---|
| Aliete de Souza Costa | Campina Grande | Aposentado | A Costa Comercio Atacadista Prod. Farmaceuticos | 1999-02-17 | R$ 141,6M | 146 |
| Soraya Formiga Mariz Dantas | Joao Pessoa | Supervisor Escolar | Construdantas Construcao e Incorporacao | 2000-09-04 | R$ 50,1M | 9 |
| Edwirges T. S. S. Andrade | Joao Pessoa | Professor de Portugues | Moura e Andrade Construtora | 2013-05-16 | R$ 47,3M | 28 |
| Bruno Fialho Carneiro Braga | Joao Pessoa | Medico | Hospital Sao Luiz | 2014-07-29 | R$ 41,9M | 59 |
| Mariana Carvalho P. Loudal | Joao Pessoa | Chefe Gabinete Procurador | ECOMAQ Empresa Construcao e Maquinas | 2013-10-16 | R$ 41,9M | 6 |

### 5.2. Prefeito socio de fornecedor do proprio municipio

| Servidor | Municipio | Cargo | Empresa | Total recebido | Mun. atendidos |
|---|---|---|---|---|---|
| **Antonio Jose Ferreira** | **Mogeiro** | **Prefeito** | Centro de Formacao e Capacitacao de Profissionais em Educacao Ltda | **R$ 41,8M** | 62 |

O prefeito de Mogeiro e socio (desde 2018) de empresa que recebeu R$ 41,8M de 62 municipios paraibanos. Outro servidor do mesmo municipio (Tiago de Oliveira Felix, Controlador Geral) tambem e socio da mesma empresa. Isto configura potencial conflito de interesses direto: o chefe do Executivo municipal e o responsavel pelo controle interno sao ambos socios de fornecedor do municipio.

### 5.3. Vereador socio de construtora fornecedora

| Servidor | Municipio | Cargo | Empresa | Total recebido |
|---|---|---|---|---|
| Alex Silva Oliveira | Barra de Santa Rosa | Vereador | Matrix Construtora Ltda | R$ 29,6M |

Vereador que e socio de construtora com R$ 29,6M em contratos com 30 municipios PB.

### 5.4. Secretarios e assessores com empresas fornecedoras

| Servidor | Municipio | Cargo | Empresa | Total recebido |
|---|---|---|---|---|
| Fabricio Cabral de Araujo | Juarez Tavora | Sec. de Cultura | Distribuidora FF Alimentos | R$ 30,5M |
| Victor Hugo M. D. e Silva | Joao Pessoa | Assessor Juridico | Paraguay Ribeiro Coutinho Advogados | R$ 26,3M |
| Felipe Gomes da Fonseca | Cacimba de Dentro | Sec. Relacoes Institucionais | B & F Edificare Engenharia | R$ 21,9M |
| Leticia Anna da S. Abrantes | Uirauna | Gerente Contratos e Convenios | Solida Pre Moldados | R$ 18,8M |

O caso de **Leticia Anna** e particularmente grave: como Gerente Municipal de Contratos e Convenios, ela tem acesso direto aos processos de contratacao e e socia de empresa fornecedora (desde jan/2023, admitida no cargo em mai/2023).

---

## 6. Padroes Transversais

### 6.1. Construtoras e engenharia dominam os maiores valores

Dos top 25 casos por valor, construtoras e empresas de engenharia representam mais da metade: Construdantas, Moura e Andrade, ECOMAQ, Torre Construcao, Matrix Construtora, AG Construtora, Del Engenharia, D2R3 Construcao, B&F Edificare, Solida Pre Moldados. Obras publicas sao particularmente vulneraveis a conflitos de interesse.

### 6.2. Setor farmaceutico

A Costa Comercio Atacadista de Produtos Farmaceuticos (R$ 141,6M, 146 municipios) tem como socia uma servidora aposentada de Campina Grande. A empresa atende quase 2/3 dos municipios do estado.

### 6.3. Engenheiros e fiscais de obras como socios de construtoras

Damiao Epaminondas T. Bezerra (Engenheiro Civil contratado, Manaira) e socio da Torre Construcao e Consultoria em Engenharia (R$ 32,9M). Wendeyson Gomes Ferreira (Fiscal de Obras, Itaporanga) e socio da Del Engenharia (R$ 22,2M). Estes cargos tem poder de fiscalizacao direta sobre as obras que as proprias empresas executam.

---

## 7. Fundamentacao Juridica

- **Art. 9, III da Lei 14.133/21** (nova Lei de Licitacoes): veda participacao em licitacao de pessoa que mantenha relacao de natureza tecnica, comercial, economica ou financeira com o ente licitante.
- **Art. 9, caput da Lei 8.429/92** (Improbidade Administrativa): constitui ato de improbidade auferir qualquer tipo de vantagem patrimonial indevida em razao do exercicio de cargo, mandato, funcao, emprego ou atividade publica.
- **Art. 37 da CF/88**: a administracao publica obedecera aos principios de legalidade, impessoalidade, moralidade, publicidade e eficiencia.
- **Art. 29, III da Lei Organica Municipal (tipica)**: conflito de interesses entre funcao publica e atividade empresarial.
- **Decreto 7.203/2010**: veda nepotismo e conflito de interesses na administracao publica federal (analogia para municipios).

---

## 8. Recomendacoes

1. **Investigar prioritariamente agentes politicos** (prefeitos, vereadores, secretarios) socios de fornecedores do proprio municipio -- conflito de interesses direto e insanavel.
2. **Verificar processos licitatorios** das empresas identificadas nos municipios onde seus socios sao servidores -- checar se houve dispensa indevida, direcionamento ou fracionamento.
3. **Cruzar datas de admissao no cargo vs entrada na sociedade** -- servidores que viraram socios apos tomar posse sugerem uso do cargo para acesso a contratos.
4. **Auditar a I2 Servicos Saude** -- 40+ medicos municipais de 16 municipios como socios de uma unica empresa sugere esquema organizado de pejotizacao e conflito de interesses.
5. **Verificar fiscal de obras que e socio de construtora** -- caso extremo de conflito, onde o agente que deveria fiscalizar a obra e beneficiario direto do contrato.
