# Relatório de Investigação: Megafraudes Estruturais no Sertão da Paraíba

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivos `q03` e `q18`)
**Foco:** Contratos superiores a R$ 11 Milhões envolvendo Laranjas e Direcionamento de Licitação no Alto Sertão.

---

## 1. Resumo Executivo
A busca por anomalias de "Empresas Recém-Criadas" e "Faixas Etárias Extremas" identificou duas fraudes de altíssimo impacto (acima de R$ 11 milhões cada) em prefeituras do sertão paraibano. Os casos envolvem a emancipação de um adolescente para atuar como testa de ferro do pai em Cajazeiras e a abertura de um consórcio 72 horas antes de ganhar a licitação de uma represa em São João do Rio do Peixe.

## 2. Cajazeiras/PB: O Laranja Adolescente (R$ 11,1 Milhões)
O algoritmo de Laranjas (q18) identificou um contrato de **R$ 11.163.973,50** para gêneros alimentícios e limpeza.
* **A Empresa:** GOMES E COSTA LTDA (CNPJ 44.409.367/0001-39).
* **A Fraude:** O dono da empresa é **Damião Gomes Sarmento Neto**, que no ato de fundação da empresa tinha apenas **15/16 anos de idade** (nascido em 2006). Ele foi emancipado judicialmente apenas para assinar pela empresa.
* **O Verdadeiro Operador:** A pesquisa OSINT revelou que a empresa é uma fachada jurídica para a família de *Jucélio Costa de Araújo*, dono do "Supermercado Félix", um fornecedor histórico de prefeitos da região. 
* **O Cerco do MPPB:** A manobra de usar o filho para monopolizar licitações ruiu quando o Ministério Público da Paraíba flagrou a empresa do adolescente em *conluio* (acordo de divisão de lucros) com outra empresa local (Melo e Martins) em um mega-pregão de **R$ 23 milhões** na cidade.

## 3. São João do Rio do Peixe/PB: A Obra do Açude e o TCU (R$ 11,1 Milhões)
O algoritmo de empresas recém-criadas (q03) pescou um absurdo matemático na área de infraestrutura.
* **O Contrato:** Implantação do Açude de Cacimba Nova (R$ 11.182.196,24).
* **A Empresa:** CONSÓRCIO CACIMBA NOVA (CNPJ 63.946.566/0001-20), liderado pela Vexa Engenharia Ltda.
* **A Fraude Numérica:** O consórcio assinou o contrato milionário no dia **08/12/2025**. Porém, o seu CNPJ foi aberto na Receita Federal no dia **05/12/2025**. A empresa passou a existir apenas 3 dias antes de abocanhar a verba.
* **A Suspensão Federal:** A investigação OSINT revelou que o roubo foi interceptado. O Plenário do TCU proferiu o **Acórdão 26/2026** (Relator Benjamin Zymler) determinando uma Medida Cautelar paralisando a obra. O TCU constatou que o prefeito municipal havia desclassificado ilegalmente todas as grandes construtoras concorrentes (mesmo com preços menores) com exigências absurdas, apenas para garantir que o consórcio recém-nascido ganhasse a licitação.

## 4. Conclusão
As fraudes no sertão paraibano demonstram grande ousadia (uso de manobras de emancipação de menores e inabilitações em massa de concorrentes). No entanto, o cruzamento básico de dados (Idade x Valor) e (Data de Abertura x Data de Contrato) provou-se altamente eficaz para desmontar esquemas que tentavam dar aparência de legalidade a licitações marcadas.

## Fontes e Referências
1. **Tribunal de Contas da União:** Acórdão 26/2026-Plenário (Suspensão da obra do Açude de Cacimba Nova).
2. **Ministério Público da Paraíba (MPPB):** Investigação de conluio no Pregão Eletrônico 90021/2024 em Cajazeiras.
3. **Cartórios e JUCEP:** Registros de emancipação do sócio menor de idade e constituição do grupo societário da CGN Participações.

## 5. A Hegemonia Regional do Laranja Adolescente
Os dados estaduais do TCE-PB revelaram que o esquema n?o se limitava aos cofres de Cajazeiras. A empresa de fachada do adolescente (Gomes e Costa Ltda) espalhou seus tent?culos e recebeu pagamentos frequentes de **"Dispensas de Licita??o" em 5 munic?pios vizinhos** (Cachoeira dos ?ndios, Cajazeiras, Nazarezinho, Santa Cruz e Vieir?polis). O cl? utiliza o mesmo Laranja para sangrar os cofres de prefeitos aliados em toda a regi?o do Alto Sert?o.

## Fontes e Refer?ncias
1. **Tribunal de Contas da Uni?o:** Ac?rd?o 26/2026-Plen?rio (Suspens?o da obra do A?ude de Cacimba Nova). [Acesse o Ac?rd?o do TCU na ?ntegra](https://pesquisa.apps.tcu.gov.br/#/doc/acordao-completo/26/2026/Plen?rio)
2. **Minist?rio P?blico da Para?ba (MPPB):** Investiga??o de conluio no Preg?o Eletr?nico em Cajazeiras. [Consulta P?blica de Inqu?ritos MPPB](https://www.mppb.mp.br/index.php/pt/transparencia/consultas-publicas)
3. **Cart?rios e JUCEP:** Registros de emancipa??o do s?cio menor de idade. [Portal da REDESIM-PB](https://www.redesim.pb.gov.br/)
4. **Arquivos do Projeto:** 
esultados\q03...csv e 
esultados\q18...csv