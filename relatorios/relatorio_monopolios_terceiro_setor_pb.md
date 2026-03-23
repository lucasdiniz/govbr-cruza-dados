# Relatório de Investigação: Hegemonia do Terceiro Setor e Conflito de Interesses na Paraíba

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivos `q59` e `q60` - Bases do TCE-PB e DadosPB)
**Foco:** O monopólio de Organizações Sociais (OS) e entidades filantrópicas como duto de repasses municipais sem licitação.

---

## 1. Resumo Executivo
O cruzamento de dados focados nas bases estaduais (Tribunal de Contas do Estado da Paraíba - Sagres) identificou um gargalo sistêmico de terceirização na administração pública paraibana. O **Instituto Walfredo Guedes Pereira** consolidou-se como um monopólio de prestação de serviços de saúde e assistência, recebendo repasses vultosos de praticamente todos os municípios do estado. A gravidade do caso aumenta ao cruzar o quadro diretivo/societário da instituição com a folha de pagamento de servidores públicos (inativos) na capital.

## 2. A "Metástase" Financeira: Presente em 158 Cidades
O algoritmo de fornecedores seriais (`q60_fornecedor_recebendo_pagamentos_sem_licitacao`) flagrou uma dependência extrema do poder público estadual em relação a esta única entidade filantrópica.
* **O Volume:** O Instituto Walfredo Guedes Pereira (CNPJ 09.124.165/0001-40) recebeu incríveis **R$ 183.126.188,89** (Cento e oitenta e três milhões de reais).
* **A Capilaridade:** A entidade recebeu repasses (geralmente sob a rubrica de subvenções, convênios ou inexigibilidade) de **158 dos 223 municípios da Paraíba**. Isso representa um monopólio de prestação de serviços em mais de 70% do território do estado.

## 3. O Conflito de Interesses: O Fator "Servidor Municipal"
Embora repasses para hospitais filantrópicos sejam comuns (o Instituto administra complexos como o Hospital São Vicente de Paulo), o arquivo `q59` alertou para um severo conflito de governança.

* **O Elo na Prefeitura de João Pessoa:** A ferramenta identificou a Sra. **Maria Gerlane Carneiro Cavalcanti** no quadro de qualificação societária/diretiva do Instituto. 
* **A Irregularidade:** O cruzamento com a folha de pagamento (DadosPB/TCE) provou que ela é uma **Servidora Municipal Inativa** (Técnico de Comunicação Social) da Prefeitura de João Pessoa. 
* **Análise de Risco:** A presença de servidores (ativos ou inativos) do próprio município nas diretorias de entidades que recebem milhões em subvenções e repasses da prefeitura fere o princípio da impessoalidade. É uma brecha clássica usada para a "terceirização" de mão de obra (burlando concursos públicos) ou para o uso político da estrutura filantrópica por grupos estabelecidos na capital.

## 4. Conclusão
O terceiro setor na Paraíba (OSs e fundações privadas) opera como uma administração paralela que movimenta centenas de milhões de reais com regras de contratação muito mais afrouxadas que a Lei de Licitações (Lei 14.133/21). O domínio do Instituto Walfredo Guedes sobre 158 cidades, atrelado a membros ligados à prefeitura da capital, exige auditoria imediata sobre a efetiva prestação dos serviços conveniados no interior e a folha de pagamento "oculta" do instituto.

## Fontes e Referências
1. **Dados Cadastrais do Terceiro Setor (OSINT):** Quadro de Sócios e Administradores do Instituto Walfredo Guedes Pereira. [Acesse os Dados Abertos (CNPJ Biz)](https://cnpj.biz/09124165000140)
2. **Tribunal de Contas do Estado (TCE-PB):** Portal Sagres (Módulo de Subvenções e Repasses a Terceiro Setor). [Acesse a Base de Dados Abertos do Sagres-PB](https://sagres.tce.pb.gov.br/dados_abertos.php)
3. **Arquivos Locais de Extração:** `resultados\q59_servidor_municipal_que_socio_de_empresa...csv` e `resultados\q60_fornecedor_recebendo_pagamentos_sem_licitacao...csv`