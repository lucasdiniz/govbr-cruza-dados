# Relatório de Investigação: Sobreposição de Diárias Estaduais e Viagens Federais na Paraíba

**Data de Geração:** 11 de abril de 2026  
**Base de Dados:** Query Q106 — `pb_diaria` × `viagem` (Portal da Transparência federal)  
**Metodologia:** identificação de pessoas que receberam diária estadual (PB) e viagem federal no mesmo período, por correspondência exata de nome (case-insensitive).

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. O match é feito por nome completo, o que pode gerar falsos positivos (homônimos). Além disso, viagens federais com período anual (01/jan a 31/dez) representam registros administrativos de lotação/convênio, não necessariamente deslocamento contínuo. A irregularidade não é presumida pelo cruzamento.

---

## 1. Resumo Executivo

A Query Q106 identificou **2.774 sobreposições** envolvendo **508 pessoas distintas** que receberam diárias do governo estadual da Paraíba enquanto tinham viagens federais registradas no mesmo período. O total envolvido em diárias estaduais nessas sobreposições atinge valores significativos.

Os achados dividem-se em duas categorias:
- **Casos de sobreposição real** — servidor em viagem estadual e federal no mesmo período curto;
- **Casos de viagem federal anual** — registro federal cobre o ano inteiro (01/jan a 31/dez), gerando sobreposição mecânica com qualquer diária estadual.

**Conclusão metodológica importante:** a maioria dos resultados cai na segunda categoria. O Ministério da Justiça e Segurança Pública registra viagens anuais (01/jan a 31/dez) com valores acima de R$ 120 mil, que cruzam mecanicamente com qualquer diária estadual do mesmo ano. Isso reduz o valor investigativo bruto, mas os casos com sobreposição em períodos curtos permanecem relevantes.

---

## 2. Casos por Categoria

### 2.1. Categoria A: Viagem federal anual (menor valor investigativo)

Os dois nomes mais recorrentes nos resultados ilustram o problema:

**DANIEL OLIVEIRA DOS SANTOS** — 17 sobreposições
- **Diárias estaduais:** múltiplas viagens de fiscalização da taxa FSDS (Fundo de Segurança e Defesa Social) para cidades do interior da PB (Mamanguape, Itabaiana, Guarabira, Campina Grande etc.)
- **Viagem federal:** Ministério da Justiça, período 01/jan a 31/dez/2025, valor R$ 123 mil, destinos Brasília/DF
- **Análise:** a viagem federal cobre o ano inteiro — sobreposição é mecânica, não real. As diárias estaduais são de fiscalização tributária no interior da PB, sem conflito com o registro federal.

**FLAVIO SOARES DA SILVA** — 2 sobreposições
- **Diárias estaduais:** atividades do ENEM/PPL (segurança de provas em presídios)
- **Viagem federal:** Ministério da Justiça, período 01/jan a 31/dez/2025, valor R$ 122 mil
- **Análise:** mesma situação — viagem federal anual, sobreposição mecânica.

### 2.2. Categoria B: Sobreposição por homônimo (investigar caso a caso)

**JOAO BARBOSA DA SILVA** — 9 sobreposições
- **Diárias estaduais:** reforço policial em festas municipais (Alhandra, Pitimbu, Campina Grande, Lucena, Itabaiana) — valores de R$ 92 a R$ 185
- **Viagem federal:** Ministério da Justiça, período 01/jan a 31/dez/2025, valor R$ 120 mil, destinos no PA/RR/AM/MS
- **Análise:** os destinos federais (São Félix do Xingu/PA, Boa Vista/RR, Altamira/PA) são incompatíveis com o perfil de policial militar do interior da PB. Provável **homônimo** — o João Barbosa da Silva federal atua na fronteira amazônica, enquanto o estadual é PM fazendo policiamento em festas locais.

---

## 3. Limitações Metodológicas

### 3.1. Match por nome gera falsos positivos
A Q106 cruza por nome completo, sem CPF. Nomes comuns como "João Barbosa da Silva" ou "Daniel Oliveira dos Santos" podem ter múltiplas pessoas nos registros estadual e federal.

### 3.2. Viagens federais anuais inflam os resultados
O Ministério da Justiça registra viagens com período 01/jan a 31/dez, abrangendo o ano todo. Isso cruza mecanicamente com qualquer diária estadual, gerando milhares de sobreposições sem significado investigativo real.

### 3.3. Recomendação de refinamento
Para aumentar a precisão da Q106, sugerimos:
- **Filtrar viagens federais com duração > 90 dias**, que provavelmente são registros administrativos;
- **Priorizar sobreposições onde ambos os períodos são curtos** (< 15 dias);
- **Cruzar por CPF quando disponível**, em vez de nome.

---

## 4. Casos que Merecem Investigação Adicional

Apesar das limitações, a análise identifica um padrão investigável:

1. **Servidores que recebem diárias estaduais para segurança do ENEM/PPL** — esses são potencialmente servidores de segurança pública que também estão em convênio com o Ministério da Justiça. A duplicidade de diária estadual + viagem federal no mesmo período pode configurar acúmulo irregular de remuneração.

2. **Policiais militares em reforço de festas municipais** — se o mesmo policial consta em viagem federal, pode haver acúmulo de diárias de duas fontes para o mesmo período.

---

## 5. Fundamentação Jurídica

- **Art. 37, XVI da CF/88:** proibição de acumulação remunerada de cargos públicos (salvo exceções).
- **Art. 58-59 da Lei 8.112/90:** diárias para deslocamento a serviço são inacumuláveis quando o servidor já está em viagem por outra fonte.
- **Art. 10, XII da Lei 8.429/92 (LIA):** permitir ou facilitar enriquecimento ilícito de servidor constitui ato de improbidade.

---

## 6. Recomendações

1. **Não considerar os 2.774 resultados brutos como achados investigativos** — a maioria é sobreposição mecânica com viagens anuais federais.
2. **Refinar a query Q106** excluindo viagens com duração > 90 dias e priorizando sobreposições curtas.
3. **Investigar os casos de servidores de segurança pública com convênio ENEM/PPL** para verificar se há duplicidade real de diárias.
4. **Quando o CPF completo estiver disponível**, substituir o match por nome por match por CPF.
