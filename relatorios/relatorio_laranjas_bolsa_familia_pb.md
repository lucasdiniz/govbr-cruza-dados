# Relatório de Investigação: Laranjas do Bolsa Família em Empresas Milionárias na Paraíba

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivos `q39_socio_empresa_bolsa_familia.csv`)
**Foco:** Uso de vulnerabilidade social para blindagem patrimonial.

---

## 1. Resumo Executivo
O cruzamento automático entre a base do Auxílio Brasil/Bolsa Família e o quadro de Sócios e Administradores (QSA) da Receita Federal expôs uma tipologia grave de fraude na Paraíba: o uso de cidadãos em situação de pobreza extrema como "testas de ferro" (laranjas) para empresas com Capital Social na casa dos milhões. 

A inteligência de fontes abertas (OSINT) validou que empresas atreladas a esses CPFs possuem vasto histórico de condenações por corrupção e improbidade administrativa em obras públicas no estado.

## 2. O Estudo de Caso: Hidro Perfurações Ltda
O cruzamento apontou que a Sra. **Maria do Desterro Formiga Flavio** (Município de São José da Lagoa Tapada/PB) recebe o benefício social de **R$ 600,00**. Contudo, na Receita Federal, ela consta como dona da **HIDRO PERFURACOES LTDA** (CNPJ: 04.830.606/0001-05), que possui Capital Social de **R$ 5.000.000,00**.

**Corroboração (OSINT e TCE):**
Pesquisas confirmam que o nome da "sócia" é usado para blindar os verdadeiros donos de uma empresa com atuação suspeita em todo o estado:
* **Tribunal de Contas da União (TCU):** A Hidro Perfurações foi condenada no Acórdão 18200/2021 (TCE) junto a ex-prefeitos por inexecução e pagamentos fraudulentos na construção de escolas (Proinfância) em Quixabá/PB.
* **Governo do Estado (CAGEPA):** A empresa foi punida em 2019 com a suspensão e o impedimento de licitar com a administração estadual e com o próprio Ministério Público (MPPB) por dois anos devido a quebras de contrato.
* **Ministério Público Federal (MPF):** Foi alvo de ação do MPF em Guarabira por improbidade e dano moral coletivo em desvios de obras.

## 3. Outros Casos Alarmantes de "Miseráveis Milionários"
O padrão se repete em outros municípios, criando frentes prontas para investigação de lavagem de dinheiro:

* **João Pessoa/PB:** 
  * **Janailda Maria da Silva:** Recebe míseros **R$ 180,00** do Bolsa Família, mas é "dona" da **SUCATAS HOSPITALARES COMERCIO E RECICLAGEM LTDA** (CNPJ: 15.739.000/0001-76) com Capital Social de **R$ 1.500.000,00**. (O setor de descarte hospitalar é crítico e alvo de máfias ambientais).
  * **Aline Medeiros Correa de Oliveira:** Recebe **R$ 640,00**, mas figura como dona da construtora **OLHO DAGUA DO CAPIM SPE LTDA** (CNPJ: 50.839.309/0001-08) com Capital de **R$ 4.800.000,00**.

* **Juarez Távora/PB:**
  * **Severino Alves de Andrade:** Recebe **R$ 600,00**, dono da **ETHIC REPRESENTACOES COMERCIAIS LTDA** (CNPJ: 00.803.795/0001-00) com Capital de **R$ 2.500.000,00**.

* **O "Conglomerado" de Queimadas/PB:**
  * **Carlos Alberto de Luna Candido:** Recebe **R$ 600,00** do governo. No entanto, seu CPF foi usado para abrir rapidamente **cinco empresas** diferentes, cada uma com Capital de R$ 200.000,00, sugerindo uma base de notas frias: *LUNA PUBLICIDADES LTDA*, *LIVRARIA LUNA LTDA*, *ALBERTO LUNA ASSISTENCIA TECNICA LTDA*, *LUNA SOLUCOES DIGITAIS LTDA* e *ADEGA LUNA LTDA*.

## 4. Conclusão
A detecção de Laranjas do Bolsa Família não representa fraude contra o programa social em si, mas sim o crime de Fraude Societária (Falsidade Ideológica e Lavagem de Dinheiro) por parte dos verdadeiros operadores do esquema, que se escondem atrás da identidade de pessoas humildes para fraudar cofres públicos (como provado pelo caso da Hidro Perfurações) garantindo que seus bens pessoais não sejam bloqueados pela Justiça.

## Fontes e Referências
1. **Acórdão TCU (18200/2021):** Condenação da Hidro Perfurações por inexecução de obras. [Acesse o Acórdão do TCU](https://pesquisa.apps.tcu.gov.br/#/doc/acordao-completo/18200/2021/Primeira%20C%C3%A2mara)
2. **CGE-PB (Controladoria Geral do Estado):** Cadastro de Fornecedores Impedidos (Sanção CAGEPA 2019 contra a Hidro Perfurações). [Acesse o Diário do CAFIL/PB](https://cge.pb.gov.br/site/imagens/Gsc/Uploads/2019/07-Julho/cadastro%20cge%20-%20cafilpb%2026.07.2019.pdf)
3. **Ministério Público Federal:** Ações civis públicas em Guarabira/PB.
4. **Arquivos do Projeto:** `resultados\q39_socio_empresa_bolsa_familia.csv`