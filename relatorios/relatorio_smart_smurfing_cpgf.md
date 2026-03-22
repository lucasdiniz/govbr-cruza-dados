# Relatório de Investigação: "Smart Smurfing" e Fracionamento de Despesas no Cartão Corporativo (CPGF)

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q19_fracionamento_de_despesa_valores_logo_abaixo_de_limites_lega.csv`)
**Foco da Análise:** Uso de precisão matemática para burla de limites da Nova Lei de Licitações (14.133/21).

---

## 1. Resumo Executivo
A análise aprimorada do algoritmo de detecção de fracionamento de despesas (popularmente conhecido em lavagem de dinheiro como *"Smurfing"*) revelou uma adaptação imediata dos fraudadores e servidores públicos à **Nova Lei de Licitações (Lei 14.133/21)**. 

Com a elevação drástica dos tetos legais para "Pronto Pagamento" (uso de Cartão Corporativo), o perfil da fraude abandonou o antigo "fatiamento de baixo clero" (passar o cartão repetidas vezes em R$ 800,00) para abraçar o **"Smart Smurfing"**. O sistema provou que servidores das Forças Armadas e órgãos federais estão esvaziando o cartão corporativo passando notas fiscais na casa dos **R$ 11.950,00** — cravando os gastos poucos reais abaixo do limite do decreto federal correspondente àquele ano, a fim de não disparar alertas de auditoria ou necessidade de licitação.

## 2. A Metodologia de Detecção Dinâmica
Diferente das buscas tradicionais que procuram por anomalias fixas (ex: transações de R$ 799,00), o algoritmo foi atualizado para rastrear compras múltiplas na mesma loja/favorecido que atinjam entre **80% e 100% do teto legal exato estabelecido para o ano da transação**:
* **2020/2021 (Lei 8.666):** Teto de R$ 17.600,00 (Dispensa)
* **2024 (Lei 14.133):** Teto de R$ 11.981,20 (Pronto Pagamento / Cartão)
* **2025/2026 (Lei 14.133):** Tetos de R$ 12.545,11 e R$ 13.098,42 (Pronto Pagamento / Cartão)

---

## 3. Achados de Alto Vulto: A Elite do Fracionamento

O cruzamento dinâmico expôs casos onde a precisão matemática comprova a intenção de burlar o sistema (dolo):

### 3.1. O "Milagre" de R$ 20 do Grupamento de Apoio da FAB (Brasília)
O servidor **Leonardo Vasconcelos** (Grupamento de Apoio do Distrito Federal - Aeronáutica) protagonizou o caso mais cirúrgico da base de dados sob a nova lei.
* **Período:** 14 de Junho de **2024**
* **Transações no mesmo dia:** 4 passadas de cartão no mesmo favorecido.
* **Média por transação:** **R$ 11.958,91**
* **Teto da Lei no dia (Decreto 11.871/23):** **R$ 11.981,20**
* **A Fraude:** O servidor fatiou o pagamento de **R$ 47.835,64** passando o cartão corporativo quatro vezes com uma diferença cômica de apenas **R$ 22,29** para o limite legal, garantindo que o sistema bancário do Tesouro não bloqueasse a compra por exigência de licitação.

### 3.2. O Padrão nas Outras Forças Armadas
A tática se repete nas divisões logísticas das Forças Armadas nos anos de 2024 e 2025, sempre acompanhando a inflação do decreto presidencial:
* **Exército (9º Grupamento Logístico - 2024):** O servidor *Tarso Prado Paiva* pagou a empresa *Ricardo Claudino dos Santos* passando o cartão 3 vezes no valor médio de **R$ 11.826,67** (Lembrando que o teto era R$ 11.981,20). Total gasto no dia: R$ 35.480,00.
* **Marinha (Comando de Patrulha Naval - 2025):** O servidor *Igor Macharett Baptista* pagou a *J. J. D. Manutenções* passando o cartão 3 vezes com média de **R$ 10.333,33**. Neste ano, o teto já havia subido para **R$ 12.545,11**, o que permitiu fatiar mais de 30 mil reais sem acionar o TCU.

### 3.3. A Mega-Fraude Hospitalar (A Fraude Clássica da Lei 8.666)
O filtro de "Abaixo da Dispensa" pegou um caso histórico operando sob o teto da lei antiga no Rio de Janeiro:
* **Órgão:** Hospital Federal da Lagoa (RJ)
* **Favorecido:** BIG STORE COMÉRCIO E SERVIÇOS
* **Período:** Abril de 2020 (Auge da pandemia).
* **A Fraude:** O hospital fez 4 pagamentos para a empresa. A média cravou em **R$ 17.489,50**. O limite federal de dispensa no mês era de exatos **R$ 17.600,00**. Total transferido sem licitação: **R$ 69.958,00**.

---

### 3.4. A Elite do "Smurfing Industrial" (A Faixa de 60-80%)
Ao calibrar o algoritmo para buscar transa??es n?o apenas na margem de 99% do limite, mas ampliando a rede para a faixa de **60% a 100% do teto**, o volume de fraudes explodiu de 29 para **1.285 casos**. Isso revelou o verdadeiro "Smurfing Industrial": servidores que mant?m as transa??es em um patamar aparentemente "seguro" (em torno de 70% do limite) para n?o acionar os alertas autom?ticos de teto de gastos, mas o fazem dezenas de vezes no mesmo m?s.

Os maiores casos do Brasil operam dentro do Quartel General da Pol?cia Federal (Coordena??o Geral de Administra??o CGAD/DLOG):
* **O Recorde Nacional (Henrique Araujo Hohn - Setembro/2025):** Em um ?nico m?s, este servidor passou o cart?o corporativo **31 vezes**. A m?dia de cada transa??o foi de **R$ 8.805,15** (confortavelmente abaixo do limite de R$ 12.545,11 de 2025). O total faturado no cart?o em 30 dias? Impressionantes **R$ 272.959,56**.
* **O Vice-Campe?o (Thiago Pedrosa Cortes - Setembro/2024):** No mesmo ?rg?o, este servidor usou a mesma t?tica: **22 transa??es** no m?s. M?dia de **R$ 9.555,76** (limite da ?poca era R$ 11.981,20). Total fatiado: **R$ 210.226,71**.

Isso prova que a redu??o da "gan?ncia" por nota fiscal (evitando chegar a 99% do limite) ? compensada por um volume industrial de passadas de cart?o.


### 3.5. A M?scara Definitiva: Saques em Esp?cie (CNPJ -1)
A investiga??o aprofundada na raiz do banco de dados revelou como os maiores operadores do esquema (como Henrique Hohn e Thiago Cortes, citados acima) impedem o rastreio do dinheiro. 

Em praticamente todas as suas maiores transa??es fracionadas, o campo de CNPJ do favorecido foi preenchido como -1 e a Raz?o Social como SEM INFORMACAO. No contexto do Portal da Transpar?ncia, isso caracteriza **Saque em Esp?cie**. 

A engenharia da fraude opera em duas camadas de prote??o:
1. **Fuga Sist?mica:** Fatiam os valores na casa dos R$ 9.000 para n?o acionar as travas banc?rias autom?ticas da Nova Lei de Licita??es.
2. **Fuga de Auditoria:** Ao inv?s de passar o cart?o repetidas vezes em uma mesma loja (o que atrairia a Receita Federal e o TCU para investigar o fornecedor), eles sacam o valor em **dinheiro vivo** nas m?quinas de autoatendimento. Com montanhas de dinheiro f?sico em m?os (chegando a R$ 270.000 em um ?nico m?s), o rastro digital ? sumariamente destru?do, tornando a auditoria do destino final do recurso praticamente imposs?vel sem uma quebra de sigilo policial de ponta a ponta.

## 4. O Escudo do "Sigilo" (O Ranking de Volume)
Vale ressaltar que, ao remover o filtro nominal, as entidades que mais operam o "Smurfing" no Brasil permanecem blindadas pelo sigilo de segurança nacional. 

* A **Agência Brasileira de Inteligência (ABIN)** lidera o país, com 1.432 transações fracionadas intencionalmente para não acender os alertas de compras públicas, totalizando **R$ 1.174.324,57** fatiados.
* A **Secretaria de Administração da Presidência da República** (1.123 transações fatiadas, R$ 935 mil) e o **GSI** (532 transações, R$ 445 mil) vêm logo atrás, adotando a mesma postura de gastar quase um milhão de reais em "pedacinhos" de 800 reais.

## 5. Conclusão
O uso de um algoritmo dinâmico atrelado à vigência dos decretos de limite de gastos provou que o fracionamento de despesas não é um acidente contábil gerado por "esquecimentos" de servidores, mas sim uma **fraude de engenharia matemática**. Os portadores dos cartões de pagamento do governo federal monitoram ativamente a atualização do limite do "Pronto Pagamento" e repassam o cartão exatamente abaixo da linha de corte, rasgando o princípio constitucional da licitação.

## Fontes e Referências
1. **Legislação (Nova Lei):** Artigo 95, § 2º da Lei 14.133/21 (Estabelece o pronto pagamento em 20% do limite de dispensa).
2. **Atualização de Tetos:** Decretos 11.871/23 (Teto 2024), 12.343/24 (Teto 2025) e 12.807/25 (Teto 2026).
3. **Portaria Normativa:** Portaria Normativa MF nº 1.344/2023.
4. **Arquivos Locais:** `resultados\q19_fracionamento_de_despesa_valores_logo_abaixo_de_limites_lega.csv`

## Fontes e Refer?ncias
1. **Legisla??o (Nova Lei):** Artigo 95, ? 2? da Lei 14.133/21. [Acessar Lei 14.133 (Planalto)](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm)
2. **Portaria Normativa:** Portaria Normativa MF n? 1.344/2023. [Acessar Di?rio Oficial da Uni?o](https://www.in.gov.br/en/web/dou/-/portaria-normativa-mf-n-1.344-de-31-de-outubro-de-2023-520425000)
3. **Arquivos Locais:** 
esultados\q19_fracionamento_de_despesa_valores_logo_abaixo_de_limites_lega.csv