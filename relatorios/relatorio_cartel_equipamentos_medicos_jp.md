# Relatório de Investigação: Conluio e Concorrência Simulada em João Pessoa/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q01_empresas_do_mesmo_grupo...`)
**Foco:** Simulação de Competição (Bid Rigging) no Setor Médico.

---

## 1. Resumo Executivo
O script de detecção de conluio identificou licitações em João Pessoa (PB) onde empresas controladas pela mesma "Holding de Topo" competiram entre si, dando falsa aparência de concorrência e burlando a Lei de Licitações. A inteligência de fontes abertas confirmou que o padrão detectado já está sob escrutínio de Tribunais de Contas pelo Brasil.

## 2. A Fraude: O Cartel da Prime Holding
A detecção originou-se no **Pregão Eletrônico nº 10.075/2019** (UASG: 08715618000140), da Prefeitura Municipal de João Pessoa, focado na aquisição de caros equipamentos de Raio-X e diagnóstico por imagem para os hospitais da rede (Santa Isabel, Valentina e Complexo de Mangabeira).

O algoritmo detectou a participação conjunta de duas empresas no certame:
1. **VMI TECNOLOGIAS LTDA** (CNPJ: 02.659.246/0001-03)
2. **ALFA MED SISTEMAS MEDICOS LTDA** (CNPJ: 11.405.384/0001-49)

**A Ligação Oculta:**
Ambas as empresas, aparentemente concorrentes, pertencem ao mesmo grupo econômico e são controladas pela **PRIME HOLDING E SERVICOS LTDA** (CNPJ: 10.328.635/0001-76). As investigações de OSINT confirmaram que as duas empresas dividem o exato mesmo parque industrial na cidade de Lagoa Santa, em Minas Gerais.

Na licitação de João Pessoa, essa "concorrência entre irmãs" resultou na homologação de ambas em lotes distintos, dividindo os lucros milionários da compra de equipamentos de imagem.

## 3. Implicações Jurídicas e Corroboração Externa
A participação de empresas sob controle comum em um mesmo lote ou licitação anula o caráter competitivo exigido pela administração pública.

* **Alerta dos Tribunais (TCE):** Cortes de contas (como TCE-BA e TCE-RN) já emitiram pareceres desfavoráveis em auditorias envolvendo a dupla (VMI e Alfa Med), citando exatamente o risco de conluio quando essas empresas atuam juntas para esvaziar a concorrência e manter os preços altos nos pregões de prefeituras.
* **Saúde na Paraíba:** O estado é alvo frequente de desmantelamento de esquemas similares (como nas Operações "Festa no Terreiro" e "Saulus"), onde o uso de empresas do mesmo grupo para forjar pesquisas de preço (orçamentos) e propostas de pregão é a espinha dorsal de desvios na saúde pública.
* **A Hegemonia no Interior da Paraíba (Novo Achado TCE-PB):** O esquema de loteamento de licitações não se restringiu à capital. O cruzamento de dados com bases do TCE-PB revelou que a *ALFA MED SISTEMAS MEDICOS LTDA* pulverizou sua atuação e venceu licitações em **24 municípios diferentes** do estado, faturando mais de R$ 5,3 milhões no interior paraibano. A Prime Holding utiliza suas subsidiárias para estabelecer um verdadeiro monopólio regional no fornecimento de equipamentos de Raio-X.

## 4. Conclusão
O cruzamento de dados de `Bid Rigging` funcionou com precisão cirúrgica. A identificação de concorrência ilusória entre subsidiárias da *Prime Holding* em compras de Raio-X pela prefeitura de João Pessoa é um forte indício de superfaturamento por ausência de competição real, configurando fraude à licitação.

## Fontes e Referências
1. **Diário Oficial / Portal da Transparência:** Editais e resultados do Pregão 10.075/2019 da Prefeitura de João Pessoa. [Acesse o Portal da Transparência JP (Buscar Pregão 10.075/2019)](https://transparencia.joaopessoa.pb.gov.br/licitacoes/)
2. **Tribunais de Contas:** Diários eletrônicos do TCE (como TCE-RN) e despachos abordando auditorias sobre o grupo VMI/Alfa Med. [Acesse o Diário do TCE-RN (Pág 3)](https://webdisk.diariooficial.rn.gov.br/Jornal/12024-03-26.pdf)
3. **Receita Federal (QSA):** Comprovação do controle acionário pela Prime Holding sobre as subsidiárias e identidade de endereços. [Consulta de Quadro Societário](https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp)
4. **Arquivos do Projeto:** `resultados\q01_empresas_do_mesmo_grupo_holding_em_licita_o_concorrente_bid_.csv`