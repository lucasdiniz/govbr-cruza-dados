# Relatório de Investigação: Esquema de "Pejotização" de Médicos e Dispensas Emergenciais em Campina Grande/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Dados Abertos do Governo Federal, Receita Federal e PNCP)
**Município Alvo:** Campina Grande - PB

---

## 1. Resumo Executivo
A análise de dados estruturada a partir de cruzamentos automatizados (ETL) sobre contratações públicas revelou um padrão sistêmico e altamente anômalo na Secretaria de Saúde de Campina Grande/PB. 

A detecção foi inicialmente realizada através da análise de empresas recém-criadas que, quase imediatamente após a obtenção do CNPJ, venceram contratos milionários. O aprofundamento investigativo validou que este padrão de dados reflete um escândalo real e em andamento, atualmente sob investigação do Ministério Público da Paraíba (MPPB) e do Tribunal de Contas do Estado (TCE-PB), envolvendo a substituição de vínculos empregatícios (concursos) por contratos através de Pessoas Jurídicas ("Pejotização") e contratos emergenciais com indícios de direcionamento.

## 2. Metodologia e Origem dos Dados (Data Mining)
Os indícios foram localizados primariamente através do arquivo de resultados extraído do banco de dados do projeto:

* **Arquivo Base de Evidências:** `C:\Users\lucas\govbr-cruza-dados\resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`
* **Lógica do Cruzamento (Query Q03):** O algoritmo cruza a data de abertura da empresa (`dt_inicio_atividade` na Receita Federal) com a data de assinatura do contrato no Portal Nacional de Contratações Públicas (`dt_assinatura`). A anomalia é gerada quando uma empresa fecha contratos de alto valor num intervalo muito curto (menos de 180 dias) após sua criação.

## 3. Achados de Dados: A "Fábrica" de CNPJs Médicos

A varredura no arquivo `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv` retornou dezenas de linhas referentes a Campina Grande, demonstrando uma linha de montagem de contratos:

### O Padrão Identificado:
1. **Nomenclatura:** Empresas registradas predominantemente com nomes próprios seguidos de "SERVICOS MEDICOS LTDA" (ex: *MIQUERINO SERVICOS MEDICOS LTDA*, *AMORIM E TARGINO SERVICOS MEDICOS LTDA*, *CARNEIRO E GRANJA SERVICOS MEDICOS LTDA*).
2. **Tempo de Existência:** Criação de CNPJs no final de 2024 e início de 2025, com assinaturas de contrato ocorrendo semanas (ou até dias) depois.
3. **Padronização Financeira:** A esmagadora maioria desses "credenciamentos" apresenta o **valor exato e tabelado de R$ 288.000,00**.
4. **Objeto do Contrato Idêntico:** Todos possuem a mesma descrição de objeto no PNCP: *"Credenciamento de serviços na área de saúde pública para atendimento de urgência e emergência, de forma complementar, em regime de atendimentos ambulatoriais, cirurgias, pareceres médicos..."*

## 4. Corroboração no Mundo Real: Investigações do MPPB e TCE-PB

A anomalia puramente matemática encontrada pelo algoritmo corrobora diretamente com as recentes ações dos órgãos de controle na Paraíba. Uma pesquisa em fontes públicas e notícias recentes confirmou o esquema:

### 4.1. Ação do Ministério Público (MPPB)
Conforme veiculado, a 15ª Promotoria de Justiça de Campina Grande instaurou procedimentos (novembro/2024 e 2025) focado expressamente na apuração desta "pejotização" por parte do Fundo Municipal de Saúde.

**Irregularidades apontadas pelo MP:**
* **Burlar o Teto Remuneratório e Regras Trabalhistas:** Médicos são pagos como "Serviços de Terceiros" (CNPJ) em vez de "Folha de Pagamento" (CPF). O limite de R$ 288.000,00 anualizado encontrado nos nossos dados equivale a **R$ 24.000,00 mensais**. 
* **Valores Exorbitantes:** O MP identificou pagamentos a profissionais que ultrapassavam os R$ 40 mil mensais, superando tetos constitucionais e limites razoáveis de carga horária. Somente um pequeno grupo desses PJs faturava mais de R$ 2,1 milhões mensais dos cofres públicos.
* **Precarização e "Quarteirização":** Suspeita-se que donos dos CNPJs credenciados subcontratam estudantes ou recém-formados por valores menores para realizar os plantões em hospitais (Pedro I, ISEA, UPAs).

### 4.2. O Caso "Lavamedi": A Fraude Emergencial Confirmada pelo Algoritmo
Durante o escrutínio do arquivo `q03`, o sistema identificou outra empresa recém-criada, fora do padrão médico, mas no mesmo município:

* **Linha 5029 do Arquivo `q03`:** `LAVAMEDI PRO SERVICOS, CONSULTORIA E ATENDIMENTO HOSPITALAR LTDA`. 
* **Data da Abertura:** 23/12/2024.
* **Data do Contrato:** 20/03/2025 (Menos de 90 dias depois).
* **Valor e Objeto:** Contrato de **R$ 1.273.140,00** para serviço completo de lavanderia na rede hospitalar municipal.

**A Ligação com o Mundo Real:**
As notícias e ações recentes do TCE-PB revelaram que a contratação da **Lavamedi** faz parte de um suposto esquema de favorecimento e nepotismo cruzado.
* **A Fraude Emergencial:** Investigações apontam que a Prefeitura deixava contratos antigos de serviços essenciais vencerem de propósito para justificar uma "Emergência Administrativa", o que permite a Dispensa de Licitação.
* **Nepotismo:** As investigações (baseadas em dados do Tribunal de Contas) ligam empresas deste esquema de serviços terceirizados, incluindo a Lavamedi (registrada em endereço suspeito/residencial), à esposa de um alto assessor do gabinete do prefeito de Campina Grande. Este esquema paralelo teria movimentado mais de R$ 12 milhões.

## 5. Conclusão

A eficácia do pipeline de dados `govbr-cruza-dados` está categoricamente demonstrada neste caso de uso. O cruzamento simples, porém eficiente, de "Idade do CNPJ" versus "Volume de Dinheiro em Contratos Recentes" (Query Q03) foi capaz de apontar com precisão cirúrgica o epicentro de dois grandes escândalos de desvio de conduta e potencial corrupção na Prefeitura de Campina Grande:
1. A burla sistêmica às leis trabalhistas e de teto de gastos via Pejotização em massa na Saúde.
2. O esquema de contratos milionários emergenciais direcionados a empresas "de fachada" ligadas a agentes políticos locais.

## Fontes e Referências (Open Source Intelligence)
1. **Polêmica Paraíba:** Reportagens sobre o esquema de mais de R$ 12 milhões envolvendo empresas ligadas a servidores do gabinete do prefeito e o uso de dispensas emergenciais (incluindo a empresa Lavamedi). [Leia na Polêmica Paraíba](https://www.polemicaparaiba.com.br/paraiba/campina-grande/bomba-documentos-revelam-que-esquema-ligado-a-gabinete-de-bruno-movimentou-mais-de-r-12-milhoes-sem-licitacao-em-campina-grande/)
2. **Paraíba Mix:** Notícias cobrindo a instauração do procedimento do MPPB pela 15ª Promotoria de Justiça contra os pagamentos milionários a médicos credenciados como Pessoa Jurídica (Pejotização). [Leia no Paraíba Mix](https://paraibamix.com.br/ministerio-publico-investiga-prefeitura-de-campina-grande-por-pejotizacao-e-pagamentos-que-chegam-a-r-40-mil-para-medicos/)
3. **Portal Correio / MPF:** Histórico de atuações do Ministério Público Federal e TCU envolvendo verbas do SUS e contratos irregulares na saúde do município. [Ação do MPF](https://www.mpf.mp.br/pb/sala-de-imprensa/noticias-pb/mpf-pede-condenacao-de-envolvidos-em-fraudes-no-hospital-de-clinicas-de-campina-grande-pb) | [Notícia Portal Correio](https://portalcorreio.com.br/ex-secretario-de-saude-de-campina-grande-e-denunciado-por-fraude-na-compra-de-insumos-na-pandemia/)
4. **Arquivos Locais de Extração:** 
   - `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`