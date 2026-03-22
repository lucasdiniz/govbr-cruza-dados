# Relatório de Auditoria: Falsos Positivos e Limitações Algorítmicas na Detecção de Cartéis

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q02_empresas_com_socios_em_comum...`)
**Foco da Análise:** Validação de Alertas de Alto Vulto e Identificação de Falsos Positivos na Paraíba.

---

## 1. Resumo Executivo
A execução do algoritmo de detecção de conluio e cartel (Query 02) apontou dois esquemas aparentemente bilionários no estado da Paraíba, somando mais de **R$ 117 milhões** em contratos suspeitos. A hipótese inicial sugeria graves casos de autocontratação e conflito de interesses envolvendo a alta cúpula de estatais e fundações públicas. 

Contudo, a auditoria investigativa profunda (OSINT cruzada com queries SQL diretas no PNCP) revelou que ambos os casos são, na verdade, **Falsos Positivos Algorítmicos**. O sistema detectou perfeitamente os vínculos societários, mas falhou ao não possuir contexto semântico sobre "Monopólios Estatais" e "Serviços Essenciais". Este relatório documenta a anatomia desse erro para fins de aprimoramento do modelo de dados.

## 2. A Mecânica do Falso Positivo (A Falha do Algoritmo `q02`)
A regra matemática da query `q02` é projetada para identificar "Bid Rigging" (Simulação de Concorrência):
> *Se a Empresa A e a Empresa B possuem o mesmo sócio (CPF em comum) e ambas recebem pagamentos/contratos do mesmo Órgão Público C, gere um alerta de fraude.*

O problema ocorre quando a **Empresa A é um monopólio de serviço essencial** (como água ou energia elétrica) e a **Empresa B é uma empresa privada comum**.

---

## 3. Estudo de Caso 1: O Falso Escândalo da CAGEPA (R$ 44,5 Milhões)

O banco de dados gerou um alerta vermelho de R$ 44.599.943,82 conectando a `COMPANHIA DE AGUA E ESGOTOS DA PARAIBA (CAGEPA)` à clínica `MEDPATOS SERVICOS MEDICOS LTDA`.

### A Ilusão Algorítmica:
* O sistema identificou o Sr. **Victor Castro Doria de Almeida** (CPF ***.151.594-**) como o elo. A pesquisa OSINT confirmou que ele é Conselheiro de Administração da CAGEPA e sócio da Medpatos.
* O algoritmo detectou que órgãos federais (como o Comando do Exército e a Advocacia Geral da União) eram clientes de *ambas* as empresas.

### A Realidade dos Fatos:
A CAGEPA detém o monopólio do fornecimento de água na Paraíba. É obrigatório que o Exército (ou qualquer órgão público) pague sua conta de água para a CAGEPA, o que a torna uma "fornecedora" no PNCP. Se esse mesmo batalhão do Exército licitar a clínica Medpatos para realizar exames admissionais em seus soldados, o algoritmo cruzará os dois contratos (água + saúde) sob o mesmo pagador e o mesmo CPF do conselheiro, gerando um falso alerta de cartel e somando o valor de todas as contas de água do Estado como "fraude".

---

## 4. Estudo de Caso 2: A Fundação PaqTcPB (R$ 72,8 Milhões)

O sistema gerou um segundo alerta colossal conectando a `FUNDACAO PARQUE TECNOLOGICO DA PARAIBA (PaqTcPB)` à clínica `ROC RADIOLOGIA CONCEITO LTDA`.

### A Ilusão Algorítmica:
* A Sra. **Nadja Maria da Silva Oliveira** (CPF ***.828.064-**) é Diretora Técnica do PaqTcPB e sócia da clínica de radiologia. 
* O algoritmo encontrou órgãos (como o Ministério da Ciência, Tecnologia e Inovações - MCTI e o Tribunal de Justiça da Paraíba - TJPB) transferindo recursos para ambas as entidades.

### A Realidade dos Fatos:
A Fundação PaqTcPB é um braço de execução de projetos tecnológicos governamentais e universitários (UEPB/UFCG). Ela atua captando milhões em convênios (como os repasses de R$ 1 milhão do MCTI identificados na auditoria) para fomento à pesquisa. Se o Tribunal de Justiça ou o Governo do Estado enviarem fundos para o PaqTcPB realizar um projeto de software, e paralelamente contratarem a ROC Radiologia para exames de saúde de seus servidores, o robô novamente une orçamentos bilionários de setores completamente distintos, criando a ilusão de um megaesquema de corrupção conduzido pela diretora.

## 5. Conclusão e Recomendações de Engenharia de Dados
Os achados não desmerecem a eficácia do banco de dados, mas expõem uma limitação inerente a cruzamentos estritamente relacionais sem análise de linguagem natural (NLP) ou clusterização de mercado (CNAE).

**Para as próximas atualizações de ETL do projeto `govbr-cruza-dados`, recomenda-se:**
1. **Filtro de "White-List" por CNAE:** Excluir da lógica de "sócios em comum" (Query 02) todas as empresas cujo CNAE principal pertença a monopólios de utilidade pública (Geração/Distribuição de Energia, Tratamento de Água/Esgoto e Gás). Isso eliminaria imediatamente os ruídos da CAGEPA, PBGÁS e ENERGISA vistos no log original.
2. **Filtro de Natureza Jurídica:** Criar exceções para Fundações de Apoio a Instituições de Ensino Superior (Fundações de Direito Privado com fins públicos), pois seus diretores frequentemente possuem atuação privada paralela que não constitui cartel de empreiteiras.

## Fontes e Refer?ncias
1. **Receita Federal:** Consulta de Natureza Jur?dica CAGEPA. [Comprovante CNPJ CAGEPA](https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj=09123654000187)
2. **Receita Federal:** Consulta de Natureza Jur?dica PaqTcPB. [Comprovante CNPJ PaqTcPB](https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj=09261843000116)
3. **Arquivos do Projeto:** 
esultados\q02_empresas_com_socios_em_comum...csv