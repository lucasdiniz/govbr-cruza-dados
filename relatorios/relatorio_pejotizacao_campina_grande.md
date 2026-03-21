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

* **Arquivo Base de Evidências:** `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`
* **Lógica do Cruzamento (Query Q03):** O algoritmo cruza a data de abertura da empresa (`dt_inicio_atividade` na Receita Federal) com a data de assinatura do contrato no Portal Nacional de Contratações Públicas (`dt_assinatura`).

## 3. Achados de Dados: A "Fábrica" de CNPJs Médicos

A varredura no arquivo `q03` retornou dezenas de linhas referentes a Campina Grande, demonstrando uma linha de montagem de contratos:
1. **Nomenclatura:** Empresas registradas predominantemente com nomes próprios seguidos de "SERVICOS MEDICOS LTDA".
2. **Tempo de Existência:** Criação de CNPJs no final de 2024 e início de 2025.
3. **Padronização Financeira:** A esmagadora maioria desses "credenciamentos" apresenta o **valor exato e tabelado de R$ 288,00,00** ou **R$ 360,00,00** ou **R$ 450,00,00**.

### Lista Completa de CNPJs Suspeitos Encontrados nos Dados (Campina Grande):
* MIQUERINO SERVICOS MEDICOS LTDA (CNPJ: 57446568000158)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-09-2024
  - Data do Contrato: 25-10-2024
* AMORIM E TARGINO SERVICOS MEDICOS LTDA (CNPJ: 57441841000151)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-09-2024
  - Data do Contrato: 25-10-2024
* ANDREZZA OURIQUES - CONSULTORIO MEDICO E ATENDIMENTOS LTDA (CNPJ: 57232276000112)
  - Valor: R$ 288.000,00
  - Data de Abertura: 10-09-2024
  - Data do Contrato: 10-10-2024
* AMORIM E TARGINO SERVICOS MEDICOS LTDA (CNPJ: 57441841000151)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-09-2024
  - Data do Contrato: 25-10-2024
* CARNEIRO E GRANJA SERVICOS MEDICOS LTDA (CNPJ: 57891406000129)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-10-2024
  - Data do Contrato: 29-11-2024
* CARNEIRO E GRANJA SERVICOS MEDICOS LTDA (CNPJ: 57891406000129)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-10-2024
  - Data do Contrato: 29-11-2024
* FERREIRA E CHAVES SERVICOS MEDICOS LTDA (CNPJ: 58221384000152)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-11-2024
  - Data do Contrato: 26-12-2024
* FERREIRA E CHAVES SERVICOS MEDICOS LTDA (CNPJ: 58221384000152)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-11-2024
  - Data do Contrato: 26-12-2024
* R L B MARINHO (CNPJ: 58208191000161)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-11-2024
  - Data do Contrato: 26-12-2024
* R L B MARINHO (CNPJ: 58208191000161)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-11-2024
  - Data do Contrato: 26-12-2024
* P K C A MANGUEIRA (CNPJ: 57622368000109)
  - Valor: R$ 288.000,00
  - Data de Abertura: 09-10-2024
  - Data do Contrato: 14-11-2024
* P K C A MANGUEIRA (CNPJ: 57622368000109)
  - Valor: R$ 288.000,00
  - Data de Abertura: 09-10-2024
  - Data do Contrato: 14-11-2024
* YASMIN DANTAS PEREIRA (CNPJ: 58085636000163)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-11-2024
  - Data do Contrato: 20-12-2024
* YASMIN DANTAS PEREIRA (CNPJ: 58085636000163)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-11-2024
  - Data do Contrato: 20-12-2024
* MARTINS TEIXEIRA SERVICOS MEDICOS LTDA (CNPJ: 57546353000109)
  - Valor: R$ 288.000,00
  - Data de Abertura: 03-10-2024
  - Data do Contrato: 12-11-2024
* MARIA CLARA VIEIRA MORAIS (CNPJ: 58030282000150)
  - Valor: R$ 288.000,00
  - Data de Abertura: 08-11-2024
  - Data do Contrato: 18-12-2024
* MARIA CLARA VIEIRA MORAIS (CNPJ: 58030282000150)
  - Valor: R$ 288.000,00
  - Data de Abertura: 08-11-2024
  - Data do Contrato: 18-12-2024
* MARTINS TEIXEIRA SERVICOS MEDICOS LTDA (CNPJ: 57546353000109)
  - Valor: R$ 288.000,00
  - Data de Abertura: 03-10-2024
  - Data do Contrato: 12-11-2024
* RONALDO GADELHA SERVICOS MEDICOS LTDA (CNPJ: 60364793000150)
  - Valor: R$ 288.000,00
  - Data de Abertura: 11-04-2025
  - Data do Contrato: 22-05-2025
* FABIO A DA S REZENDE (CNPJ: 57835718000115)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-10-2024
  - Data do Contrato: 05-12-2024
* ANNA&ROBERTA HELTH LTDA (CNPJ: 57554017000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 03-10-2024
  - Data do Contrato: 14-11-2024
* FELIX E XAVIER SERVICOS MEDICOS LTDA (CNPJ: 57794628000123)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-10-2024
  - Data do Contrato: 06-12-2024
* LUIS GUSTAVO VIEIRA DE ARAUJO (CNPJ: 57781485000115)
  - Valor: R$ 288.000,00
  - Data de Abertura: 21-10-2024
  - Data do Contrato: 05-12-2024
* ANA LUISA NOBREGA RODRIGUES (CNPJ: 57822339000190)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-10-2024
  - Data do Contrato: 10-12-2024
* ANA LUISA NOBREGA RODRIGUES (CNPJ: 57822339000190)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-10-2024
  - Data do Contrato: 10-12-2024
* HUGO COSTA GUEDES ALVES (CNPJ: 57756077000103)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-10-2024
  - Data do Contrato: 05-12-2024
* D NOBRE VASCONCELLOS (CNPJ: 56927853000128)
  - Valor: R$ 288.000,00
  - Data de Abertura: 20-08-2024
  - Data do Contrato: 10-10-2024
* MANUELLA WANDERLEY TENORIO DE ALBUQUERQUE (CNPJ: 56941745000100)
  - Valor: R$ 288.000,00
  - Data de Abertura: 21-08-2024
  - Data do Contrato: 11-10-2024
* CCGA SERVICOS MEDICOS LTDA (CNPJ: 59542251000140)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-02-2025
  - Data do Contrato: 11-04-2025
* CCGA SERVICOS MEDICOS LTDA (CNPJ: 59542251000140)
  - Valor: R$ 360.000,00
  - Data de Abertura: 19-02-2025
  - Data do Contrato: 11-04-2025
* L E B SANTOS (CNPJ: 56603979000147)
  - Valor: R$ 288.000,00
  - Data de Abertura: 12-08-2024
  - Data do Contrato: 03-10-2024
* L E B SANTOS (CNPJ: 56603979000147)
  - Valor: R$ 288.000,00
  - Data de Abertura: 12-08-2024
  - Data do Contrato: 03-10-2024
* LAYSE M LIMA AMORIM (CNPJ: 59945747000165)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-03-2025
  - Data do Contrato: 09-05-2025
* IAGO BASILIO DE SOUSA (CNPJ: 57804069000195)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-10-2024
  - Data do Contrato: 18-12-2024
* IAGO BASILIO DE SOUSA (CNPJ: 57804069000195)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-10-2024
  - Data do Contrato: 18-12-2024
* TIMOTEO CAVALCANTI SERVICOS MEDICOS LTDA (CNPJ: 60280847000107)
  - Valor: R$ 288.000,00
  - Data de Abertura: 07-04-2025
  - Data do Contrato: 02-06-2025
* OLIVEIRA E IRINEU SERVICOS MEDICOS LTDA (CNPJ: 55525671000168)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-06-2024
  - Data do Contrato: 08-08-2024
* JIMR SERVICOS MEDICOS LTDA (CNPJ: 57094194000159)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-08-2024
  - Data do Contrato: 25-10-2024
* VILAR RODRIGUES SERVICOS MEDICOS LTDA (CNPJ: 60094111000136)
  - Valor: R$ 360.000,00
  - Data de Abertura: 26-03-2025
  - Data do Contrato: 22-05-2025
* VILAR RODRIGUES SERVICOS MEDICOS LTDA (CNPJ: 60094111000136)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-03-2025
  - Data do Contrato: 22-05-2025
* MACEDO & DIAS SERVICOS MEDICOS LTDA (CNPJ: 60085439000196)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-03-2025
  - Data do Contrato: 21-05-2025
* ADRIO PESSOA BEZERRA (CNPJ: 55585886000174)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-06-2024
  - Data do Contrato: 16-08-2024
* GEOVANA NASCIMENTO DE VASCONCELOS & CIA LTDA (CNPJ: 55531780000198)
  - Valor: R$ 288.000,00
  - Data de Abertura: 14-06-2024
  - Data do Contrato: 12-08-2024
* ITALO PEREIRA SALVIANO (CNPJ: 55564545000112)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-06-2024
  - Data do Contrato: 15-08-2024
* HERK SERVICOS MEDICOS LTDA (CNPJ: 57493377000147)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-09-2024
  - Data do Contrato: 29-11-2024
* RAISSA RIBEIRO BARBOZA ALBUQUERQUE (CNPJ: 55580306000156)
  - Valor: R$ 288.000,00
  - Data de Abertura: 18-06-2024
  - Data do Contrato: 17-08-2024
* NOBREGA SOUZA SERVICOS MEDICOS LTDA (CNPJ: 59948198000182)
  - Valor: R$ 288.000,00
  - Data de Abertura: 18-03-2025
  - Data do Contrato: 20-05-2025
* NOBREGA SOUZA SERVICOS MEDICOS LTDA (CNPJ: 59948198000182)
  - Valor: R$ 360.000,00
  - Data de Abertura: 18-03-2025
  - Data do Contrato: 20-05-2025
* JOAO GABRIEL LEMOS DE MENESES (CNPJ: 55445297000190)
  - Valor: R$ 288.000,00
  - Data de Abertura: 07-06-2024
  - Data do Contrato: 09-08-2024
* A A N MOUTA (CNPJ: 59944770000135)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-03-2025
  - Data do Contrato: 21-05-2025
* CABRAL SERVICOS MEDICOS LTDA (CNPJ: 54362052000137)
  - Valor: R$ 450.000,00
  - Data de Abertura: 18-03-2024
  - Data do Contrato: 23-05-2024
* CAMILA POWELL LTDA (CNPJ: 55535890000128)
  - Valor: R$ 288.000,00
  - Data de Abertura: 14-06-2024
  - Data do Contrato: 19-08-2024
* MARCOS JOSE FIRMINO DA SILVA FILHO (CNPJ: 56201897000176)
  - Valor: R$ 288.000,00
  - Data de Abertura: 01-08-2024
  - Data do Contrato: 08-10-2024
* RILDO CAVALCANTI FERNANDES NETO (CNPJ: 55412095000142)
  - Valor: R$ 288.000,00
  - Data de Abertura: 05-06-2024
  - Data do Contrato: 13-08-2024
* LAILA MARIA ALVES DUARTE (CNPJ: 54412778000137)
  - Valor: R$ 450.000,00
  - Data de Abertura: 20-03-2024
  - Data do Contrato: 29-05-2024
* DIPED - MEDICINA E DESENVOLVIMENTO INFANTIL LTDA (CNPJ: 55161476000104)
  - Valor: R$ 288.000,00
  - Data de Abertura: 16-05-2024
  - Data do Contrato: 25-07-2024
* KAUE KEMIAC SANTOS (CNPJ: 55334535000190)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-05-2024
  - Data do Contrato: 07-08-2024
* KAUE KEMIAC SANTOS (CNPJ: 55334535000190)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-05-2024
  - Data do Contrato: 07-08-2024
* RENATA O VALE (CNPJ: 59644535000148)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-02-2025
  - Data do Contrato: 07-05-2025
* LYLIAN ALVES GOMES LTDA (CNPJ: 55146011000176)
  - Valor: R$ 288.000,00
  - Data de Abertura: 15-05-2024
  - Data do Contrato: 25-07-2024
* A CARVALHO SERVICOS DE GESTAO EM SAUDE LTDA (CNPJ: 60426820000171)
  - Valor: R$ 1.200.000,00
  - Data de Abertura: 16-04-2025
  - Data do Contrato: 27-06-2025
* A CARVALHO SERVICOS DE GESTAO EM SAUDE LTDA (CNPJ: 60426820000171)
  - Valor: R$ 800.000,00
  - Data de Abertura: 16-04-2025
  - Data do Contrato: 27-06-2025
* GABRIELLY DO N L DE A RODRIGUES (CNPJ: 59604338000103)
  - Valor: R$ 288.000,00
  - Data de Abertura: 21-02-2025
  - Data do Contrato: 07-05-2025
* BISPO SERVICOS MEDICOS LTDA (CNPJ: 55371945000101)
  - Valor: R$ 288.000,00
  - Data de Abertura: 03-06-2024
  - Data do Contrato: 19-08-2024
* ANA PAULA ARAUJO RIBEIRO DA COSTA (CNPJ: 55255162000162)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-05-2024
  - Data do Contrato: 08-08-2024
* ANA PAULA ARAUJO RIBEIRO DA COSTA (CNPJ: 55255162000162)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-05-2024
  - Data do Contrato: 08-08-2024
* L R SERVICOS MEDICOS E HOSPITALARES LTDA (CNPJ: 60164289000106)
  - Valor: R$ 288.000,00
  - Data de Abertura: 31-03-2025
  - Data do Contrato: 17-06-2025
* MARIA I M FERNANDES SERVICOS MEDICOS LTDA (CNPJ: 57486088000110)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-09-2024
  - Data do Contrato: 18-12-2024
* MARIA I M FERNANDES SERVICOS MEDICOS LTDA (CNPJ: 57486088000110)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-09-2024
  - Data do Contrato: 18-12-2024
* RAYAN DE FREITAS SOUZA SERVICOS MEDICOS LTDA (CNPJ: 57487819000142)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-09-2024
  - Data do Contrato: 20-12-2024
* RAYAN DE FREITAS SOUZA SERVICOS MEDICOS LTDA (CNPJ: 57487819000142)
  - Valor: R$ 288.000,00
  - Data de Abertura: 30-09-2024
  - Data do Contrato: 20-12-2024
* NOBREGA E MATIAS SERVICOS MEDICOS LTDA (CNPJ: 55165007000155)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-05-2024
  - Data do Contrato: 08-08-2024
* ESTER SOARES DE ALMEIDA (CNPJ: 54991522000121)
  - Valor: R$ 450.000,00
  - Data de Abertura: 03-05-2024
  - Data do Contrato: 25-07-2024
* ARTHUR FRANCA M MEDEIROS (CNPJ: 59681504000167)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-02-2025
  - Data do Contrato: 20-05-2025
* NOBREGA E MATIAS SERVICOS MEDICOS LTDA (CNPJ: 55165007000155)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-05-2024
  - Data do Contrato: 08-08-2024
* CAMILA R DANTAS SERVICOS MEDICOS LTDA (CNPJ: 57453153000101)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-09-2024
  - Data do Contrato: 19-12-2024
* V S THEOTONIO DE CARVALHO (CNPJ: 59660259000101)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-02-2025
  - Data do Contrato: 20-05-2025
* CAMILA R DANTAS SERVICOS MEDICOS LTDA (CNPJ: 57453153000101)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-09-2024
  - Data do Contrato: 19-12-2024
* WILLGNEY P GENUINO (CNPJ: 55113132000111)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-05-2024
  - Data do Contrato: 08-08-2024
* **LAVAMEDI PRO SERVICOS, CONSULTORIA E ATENDIMENTO HOSPITALAR LTDA (CNPJ: 58541682000120) - Valor: R$ 1.273.140,00 - Abertura: 23-12-2024 - Contrato: 20-03-2025 (Alvo TCE)**
* ALBERTO DA SILVA FARIAS  LTDA (CNPJ: 56979667000132)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-08-2024
  - Data do Contrato: 18-11-2024
* WILLGNEY P GENUINO (CNPJ: 55113132000111)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-05-2024
  - Data do Contrato: 08-08-2024
* ANDER VIANA SERVICOS MEDICOS LTDA (CNPJ: 59355911000184)
  - Valor: R$ 288.000,00
  - Data de Abertura: 07-02-2025
  - Data do Contrato: 09-05-2025
* TORRES BARROS SERVICOS MEDICOS LTDA (CNPJ: 57441882000148)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-09-2024
  - Data do Contrato: 26-12-2024
* TORRES BARROS SERVICOS MEDICOS LTDA (CNPJ: 57441882000148)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-09-2024
  - Data do Contrato: 26-12-2024
* LORENZO DINIZ DE CARVALHO (CNPJ: 54842454000139)
  - Valor: R$ 288.000,00
  - Data de Abertura: 23-04-2024
  - Data do Contrato: 25-07-2024
* ADRIANA FERREIRA LOPES (CNPJ: 55977897000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-07-2024
  - Data do Contrato: 25-10-2024
* ADRIANA FERREIRA LOPES (CNPJ: 55977897000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-07-2024
  - Data do Contrato: 25-10-2024
* RAFAELA MANGUEIRA CUNHA LTDA (CNPJ: 57322637000111)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-09-2024
  - Data do Contrato: 26-12-2024
* A C B C DO AMARAL (CNPJ: 58144958000136)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-11-2024
  - Data do Contrato: 28-02-2025
* L V A DE QUEIROZ (CNPJ: 58144961000150)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-11-2024
  - Data do Contrato: 28-02-2025
* ANNE KAROLYNE SERVICOS MEDICOS LTDA (CNPJ: 54922874000125)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-04-2024
  - Data do Contrato: 08-08-2024
* L B RODRIGUES (CNPJ: 58144956000147)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-11-2024
  - Data do Contrato: 28-02-2025
* CINTIA S OLIVEIRA (CNPJ: 59332331000171)
  - Valor: R$ 288.000,00
  - Data de Abertura: 06-02-2025
  - Data do Contrato: 21-05-2025
* KRISCIA PINTO TAVARES  LTDA (CNPJ: 54697424000186)
  - Valor: R$ 288.000,00
  - Data de Abertura: 11-04-2024
  - Data do Contrato: 25-07-2024
* JCR SERVICOS MEDICOS LTDA (CNPJ: 53902518000187)
  - Valor: R$ 450.000,00
  - Data de Abertura: 14-02-2024
  - Data do Contrato: 29-05-2024
* GUSMAO SERVICOS MEDICOS LTDA (CNPJ: 54932936000180)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-04-2024
  - Data do Contrato: 12-08-2024
* LIZANDRA L. A. P. SERVICOS MEDICOS LTDA (CNPJ: 54731422000166)
  - Valor: R$ 288.000,00
  - Data de Abertura: 15-04-2024
  - Data do Contrato: 29-07-2024
* GUSMAO SERVICOS MEDICOS LTDA (CNPJ: 54932936000180)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-04-2024
  - Data do Contrato: 12-08-2024
* RICARDO WAGNER GOMES DA SILVA NETO (CNPJ: 59660231000174)
  - Valor: R$ 288.000,00
  - Data de Abertura: 25-02-2025
  - Data do Contrato: 11-06-2025
* NYCOLAS EULLEN DUTRA DE SOUZA (CNPJ: 54826432000185)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-04-2024
  - Data do Contrato: 08-08-2024
* NYCOLAS EULLEN DUTRA DE SOUZA (CNPJ: 54826432000185)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-04-2024
  - Data do Contrato: 08-08-2024
* RODRIGO J B FREIRE (CNPJ: 55942764000198)
  - Valor: R$ 288.000,00
  - Data de Abertura: 16-07-2024
  - Data do Contrato: 04-11-2024
* NORONHA SERVICOS MEDICOS LTDA (CNPJ: 55951423000189)
  - Valor: R$ 288.000,00
  - Data de Abertura: 16-07-2024
  - Data do Contrato: 04-11-2024
* FERNANDA MIRANDA PINHEIRO NOBREGA (CNPJ: 54725232000136)
  - Valor: R$ 288.000,00
  - Data de Abertura: 15-04-2024
  - Data do Contrato: 07-08-2024
* ISABELE ARAUJO DO EGITO  LTDA (CNPJ: 54747230000148)
  - Valor: R$ 288.000,00
  - Data de Abertura: 16-04-2024
  - Data do Contrato: 08-08-2024
* DR ALEXANDRE RIBEIRO PELA SAUDE MENTAL LTDA (CNPJ: 59485645000104)
  - Valor: R$ 288.000,00
  - Data de Abertura: 15-02-2025
  - Data do Contrato: 11-06-2025
* CENTRO DE ATENDIMENTO PEDIATRICO DR KLERISTON SILVA MAURICIO LTDA (CNPJ: 53919323000140)
  - Valor: R$ 450.000,00
  - Data de Abertura: 15-02-2024
  - Data do Contrato: 13-06-2024
* I SOUZA ARAUJO SERVICOS MEDICOS LTDA (CNPJ: 58995702000132)
  - Valor: R$ 288.000,00
  - Data de Abertura: 20-01-2025
  - Data do Contrato: 19-05-2025
* K M SABOIA MOREIRA (CNPJ: 59402962000110)
  - Valor: R$ 288.000,00
  - Data de Abertura: 11-02-2025
  - Data do Contrato: 11-06-2025
* RICARDO DINIZ DOS SANTOS FILHO SERVICOS MEDICOS LTDA (CNPJ: 53808310000101)
  - Valor: R$ 450.000,00
  - Data de Abertura: 05-02-2024
  - Data do Contrato: 04-06-2024
* JULIA MARQUES DE FREITAS SERVICOS MEDICOS LTDA (CNPJ: 58148094000120)
  - Valor: R$ 288.000,00
  - Data de Abertura: 19-11-2024
  - Data do Contrato: 19-03-2025
* NAYANE SAMPAIO BEZERRA  LTDA (CNPJ: 54648388000160)
  - Valor: R$ 288.000,00
  - Data de Abertura: 09-04-2024
  - Data do Contrato: 07-08-2024
* JUSCELINO MONTEIRO DA SILVA  LTDA (CNPJ: 54912789000186)
  - Valor: R$ 671.512,50
  - Data de Abertura: 26-04-2024
  - Data do Contrato: 29-08-2024
* MATHEUS RODRIGUES DA SILVA DE OLIVEIRA (CNPJ: 57881672000170)
  - Valor: R$ 288.000,00
  - Data de Abertura: 29-10-2024
  - Data do Contrato: 06-03-2025
* TIAGO T DE S PIMENTEL (CNPJ: 58656304000191)
  - Valor: R$ 288.000,00
  - Data de Abertura: 06-01-2025
  - Data do Contrato: 18-05-2025
* B S SILVA BRUNO SOARES SERVICOS MEDICOS (CNPJ: 58240469000188)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-11-2024
  - Data do Contrato: 07-04-2025
* CYNTHIA BEATRIZ DE ARAUJO MACHADO (CNPJ: 57834984000123)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-10-2024
  - Data do Contrato: 06-03-2025
* AMAF MED LTDA (CNPJ: 58194005000182)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-11-2024
  - Data do Contrato: 07-04-2025
* VGM.JS SERVICOS MEDICOS LTDA (CNPJ: 58239528000106)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-11-2024
  - Data do Contrato: 11-04-2025
* LML SERVICOS MEDICOS LTDA (CNPJ: 53568054000114)
  - Valor: R$ 450.000,00
  - Data de Abertura: 19-01-2024
  - Data do Contrato: 04-06-2024
* M DE PONTES MEDEIROS (CNPJ: 59092506000110)
  - Valor: R$ 288.000,00
  - Data de Abertura: 24-01-2025
  - Data do Contrato: 11-06-2025
* A.P.M SERVICOS MEDICOS (CNPJ: 54972157000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 02-05-2024
  - Data do Contrato: 19-09-2024
* A.P.M SERVICOS MEDICOS (CNPJ: 54972157000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 02-05-2024
  - Data do Contrato: 19-09-2024
* JULIANA SANTOS FURTADO LTDA (CNPJ: 57777238000145)
  - Valor: R$ 288.000,00
  - Data de Abertura: 09-10-2024
  - Data do Contrato: 27-02-2025
* M. S. SERVICOS EM SAUDE LTDA (CNPJ: 55399218000152)
  - Valor: R$ 288.000,00
  - Data de Abertura: 05-06-2024
  - Data do Contrato: 25-10-2024
* MARIALICE PINTO VIANA CORREIA  LTDA (CNPJ: 58450848000100)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-12-2024
  - Data do Contrato: 08-05-2025
* BSI SERVICO EM ANESTESIA LTDA (CNPJ: 5957768000153)
  - Valor: R$ 288.000,00
  - Data de Abertura: 20-02-2025
  - Data do Contrato: 16-07-2025
* MATHEUS ARAUJO SILVA LTDA (CNPJ: 57731728000100)
  - Valor: R$ 288.000,00
  - Data de Abertura: 17-10-2024
  - Data do Contrato: 14-03-2025
* DIVANY REINALDO RAMOS CAVALCANTE (CNPJ: 53308294000180)
  - Valor: R$ 450.000,00
  - Data de Abertura: 27-12-2023
  - Data do Contrato: 23-05-2024
* ANA LUISA IZIDRO NORONHA LTDA (CNPJ: 5798127000148)
  - Valor: R$ 360.000,00
  - Data de Abertura: 05-11-2024
  - Data do Contrato: 07-04-2025
* ANA LUISA IZIDRO NORONHA LTDA (CNPJ: 5798127000148)
  - Valor: R$ 288.000,00
  - Data de Abertura: 05-11-2024
  - Data do Contrato: 07-04-2025
* SAMPAIO SERVICOS MEDICOS S/S UNIPESSOAL (CNPJ: 61488701000106)
  - Valor: R$ 288.000,00
  - Data de Abertura: 10-06-2025
  - Data do Contrato: 10-11-2025
* MARIA TEREZA SAEGER - SAUDE E DESENVOLVIMENTO DA CRIANCA LTDA (CNPJ: 59001489000169)
  - Valor: R$ 288.000,00
  - Data de Abertura: 21-01-2025
  - Data do Contrato: 25-06-2025
* LUIS FERNANDO BRITO FERREIRA LTDA (CNPJ: 53116209000181)
  - Valor: R$ 450.000,00
  - Data de Abertura: 06-12-2023
  - Data do Contrato: 10-05-2024
* GG LIMA SERVICOS MEDICOS LTDA (CNPJ: 58277136000123)
  - Valor: R$ 288.000,00
  - Data de Abertura: 28-11-2024
  - Data do Contrato: 09-05-2025
* H F DE SOUSA SERVICOS MEDICOS (CNPJ: 53261102000127)
  - Valor: R$ 450.000,00
  - Data de Abertura: 19-12-2023
  - Data do Contrato: 30-05-2024
* AMILTON ALBUQUERQUE SERVICOS MEDICOS LTDA (CNPJ: 58368187000160)
  - Valor: R$ 288.000,00
  - Data de Abertura: 06-12-2024
  - Data do Contrato: 20-05-2025
* GUSTAVO ARLEN DE FREITAS VIANA SERVICOS MEDICOS LTDA (CNPJ: 55226956000106)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-05-2024
  - Data do Contrato: 04-11-2024
* A MEDEIROS SERVICOS MEDICOS LTDA (CNPJ: 58229289000103)
  - Valor: R$ 288.000,00
  - Data de Abertura: 26-11-2024
  - Data do Contrato: 12-05-2025
* GMR SERVICOS MEDICOS LTDA (CNPJ: 55377140000175)
  - Valor: R$ 288.000,00
  - Data de Abertura: 03-06-2024
  - Data do Contrato: 18-11-2024
* ALEXIA ARAUJO SERVICOS MEDICOS LTDA (CNPJ: 58833881000101)
  - Valor: R$ 288.000,00
  - Data de Abertura: 13-01-2025
  - Data do Contrato: 30-06-2025
* ANA CLARA DAMASCENO VALGUEIRO (CNPJ: 53169189000107)
  - Valor: R$ 450.000,00
  - Data de Abertura: 12-12-2023
  - Data do Contrato: 29-05-2024
* AXIAL MEDICAL SERVICOS MEDICOS LTDA (CNPJ: 58305551000143)
  - Valor: R$ 288.000,00
  - Data de Abertura: 02-12-2024
  - Data do Contrato: 20-05-2025
* JOYCE FERNANDA ROCHA FERREIRA (CNPJ: 53172248000104)
  - Valor: R$ 450.000,00
  - Data de Abertura: 12-12-2023
  - Data do Contrato: 05-06-2024
* GABRIEL MONTEIRO MARQUES MORAIS  LTDA (CNPJ: 58315892000108)
  - Valor: R$ 288.000,00
  - Data de Abertura: 02-12-2024
  - Data do Contrato: 28-05-2025
* SIMOES LIMEIRA ATIVIDADES MEDICAS LTDA (CNPJ: 58312060000120)
  - Valor: R$ 288.000,00
  - Data de Abertura: 02-12-2024
  - Data do Contrato: 29-05-2025
* MAMS SERVICOS MEDICOS LTDA (CNPJ: 58185482000181)
  - Valor: R$ 288.000,00
  - Data de Abertura: 22-11-2024
  - Data do Contrato: 19-05-2025
* IVNA PAOLA ARRUDA CAMARA VIRGOLINO SERVICOS MEDICOS LTDA (CNPJ: 57741652000102)
  - Valor: R$ 288.000,00
  - Data de Abertura: 18-10-2024
  - Data do Contrato: 14-04-2025

## 4. Corroboração no Mundo Real: Investigações do MPPB e TCE-PB
A anomalia puramente matemática encontrada pelo algoritmo corrobora diretamente com as recentes ações dos órgãos de controle na Paraíba (MPPB), que instaurou procedimento focado expressamente na apuração desta "pejotização". Médicos são pagos como "Serviços de Terceiros" (CNPJ) para burlar a Folha de Pagamento, com pagamentos a profissionais que ultrapassavam os R$ 40 mil mensais.

## Fontes e Referências (Open Source Intelligence)
1. **Polêmica Paraíba:** Reportagens sobre o esquema de mais de R$ 12 milhões (Lavamedi). [Leia na Polêmica Paraíba](https://www.polemicaparaiba.com.br/paraiba/campina-grande/bomba-documentos-revelam-que-esquema-ligado-a-gabinete-de-bruno-movimentou-mais-de-r-12-milhoes-sem-licitacao-em-campina-grande/)
2. **Paraíba Mix:** Notícias cobrindo a instauração do procedimento do MPPB. [Leia no Paraíba Mix](https://paraibamix.com.br/ministerio-publico-investiga-prefeitura-de-campina-grande-por-pejotizacao-e-pagamentos-que-chegam-a-r-40-mil-para-medicos/)
3. **Portal Correio / MPF:** Histórico de atuações do Ministério Público Federal. [Notícia Portal Correio](https://portalcorreio.com.br/ex-secretario-de-saude-de-campina-grande-e-denunciado-por-fraude-na-compra-de-insumos-na-pandemia/)
4. **Arquivos Locais de Extração:** 
   - `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`