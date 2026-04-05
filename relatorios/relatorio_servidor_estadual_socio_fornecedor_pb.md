# Relatório Exploratório: Servidores Estaduais com Vínculo Societário em Fornecedores do Estado da Paraíba

**Data de Geração:** 5 de abril de 2026  
**Base de Dados:** Query Q109 — `pb_diaria` × `socio` × `empresa` × `pb_empenho`  
**Metodologia:** match por `nome_upper` entre credores de diárias estaduais e sócios de empresas que também aparecem em empenhos estaduais.

> **Disclaimer metodológico forte:** Este relatório tem risco de falso positivo maior que os demais porque o vínculo inicial entre servidor e sócio é feito por nome, sem CPF completo. Os casos abaixo devem ser tratados como fila de triagem, não como prova de conflito de interesses. A confirmação exige checagem individual no quadro societário, CPF, cargo, lotação e eventual coincidência nominal.

---

## 1. Resumo Executivo

A Q109 encontrou **577 grupos** em que um credor de diária estadual também coincide nominalmente com sócio de empresa fornecedora do estado. O sinal é útil para triagem, mas ainda é exploratório. O valor do cruzamento está em revelar nomes que circulam simultaneamente:
- como pessoa física em pagamentos de diárias;
- como sócio em empresas ativas;
- e como parte de empresas que recebem empenhos estaduais relevantes.

---

## 2. Casos Mais Fortes da Amostra

### 2.1. Companhia de Água e Esgotos da Paraíba — CAGEPA
- **CNPJ básico:** 09123654
- **Total empenhado da empresa:** R$ 842,7 milhões
- **Quantidade de empenhos:** 4.535
- **Nomes que apareceram no cruzamento:** Deusdete Queiroga Filho, Lúcio Landim Batista da Costa, Tatiana Ribeiro Rocha, Washington Luis Soares Ramalho

**Leitura investigativa:** a presença repetida de nomes associados a uma estatal de grande porte sugere que parte dos matches pode refletir coincidência nominal, estrutura societária histórica ou vínculos indiretos. Ainda assim, o volume da empresa justifica checagem amostral.

### 2.2. EMPAER
- **CNPJ básico:** 33820785
- **Total empenhado da empresa:** R$ 674,8 milhões
- **Quantidade de empenhos:** 177
- **Nomes da amostra:** Aderval Monteiro Valença Dias, Aristeu Chaves Sousa

**Leitura investigativa:** caso semelhante ao da CAGEPA. O principal valor aqui é identificar se são de fato sócios relevantes, sócios antigos ou homônimos.

---

## 3. Como Usar Este Relatório

Este relatório não deve ser publicado como peça conclusiva sem validação adicional. O uso correto é:

1. Selecionar os 20 nomes com maior volume associado de empresa.
2. Confirmar CPF e qualificação societária diretamente no QSA da Receita Federal.
3. Verificar se o servidor atua no mesmo órgão, área ou cadeia de despesa relacionada à empresa.
4. Eliminar homônimos, sócios retirados e participações irrelevantes.

---

## 4. Próximo Endurecimento Recomendado

Para transformar a Q109 em relatório final de alto valor, o ideal é acrescentar pelo menos um dos filtros abaixo:

1. CPF parcial ou completo quando disponível.
2. Recorte por empresa privada, excluindo estatais e entidades onde o match nominal tende a ser mais ruidoso.
3. Qualificação societária mais sensível, como administrador ou sócio com participação relevante.
4. Coincidência temporal entre a diária, a participação societária e o período de empenho da empresa.

## 5. Corroboração Externa

Nesta primeira rodada de pesquisa externa, **não localizei notícia ou investigação pública específica** que validasse diretamente os nomes destacados pela Q109. Isso reforça o caráter exploratório deste relatório: ele é útil para triagem interna e para geração de pautas de auditoria, mas ainda não deve ser tratado como peça conclusiva sem validação nominal e documental adicional.

## Fontes
1. Query Q109 — `queries/fraude_dados_pb_novos.sql`
2. Tabelas `pb_diaria`, `socio`, `empresa`, `pb_empenho`
