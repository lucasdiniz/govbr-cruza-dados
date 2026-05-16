# Política de privacidade e tratamento de dados pessoais

**Última atualização:** 2026-05-16  
**Commit de referência:** `4982af7`

Esta política explica como o **govbr-cruza-dados** e o portal
[transparenciapb.org](https://transparenciapb.org) tratam dados pessoais de
visitantes, contributors, jornalistas e pessoas citadas em cruzamentos públicos.
Ela expande a nota curta em [`../DATA-LICENSE.md`](../DATA-LICENSE.md), sem
substituir os termos de cada fonte oficial. Não é parecer jurídico.

## Quem somos

O projeto é mantido por **Lucas Diniz**, pessoa física. Até existir estrutura
pública formal, o mantenedor é referido como **owner**. O projeto não é entidade
jurídica, órgão público nem jornalismo profissional; é uma iniciativa pessoal de
transparência, controle social e pesquisa aplicada com dados públicos.

## Quais dados coletamos

### Diretamente do visitante

| Origem | Dados | Uso |
|---|---|---|
| Formulário `/contato` | nome, e-mail, assunto e mensagem | responder contatos, correções e pedidos LGPD |
| Logs do `/contato` | IP e User-Agent por mensagem | anti-abuse, rate limit e auditoria |
| Umami self-hosted | visitas, paths, browser, OS e eventos | métricas de uso sem tracking cross-site |
| Logs técnicos | IP, User-Agent, path, horário e status HTTP | segurança, diagnóstico e fail2ban |

As mensagens são salvas em `contato_messages` no PostgreSQL. Quando a integração
está ativa, a mensagem também é enviada via Resend para a caixa do projeto.
Umami roda no mesmo domínio e não usa Google Analytics, Facebook Pixel ou rede de
anúncios. GoAccess é usado para observabilidade operacional; a política pública
é manter IP anonimizado em estatísticas históricas quando compatível com a
investigação de abuso. Logs brutos podem conter IP completo e ficam restritos ao
owner/operadores.

### De fontes públicas

O projeto integra 18+ fontes públicas brasileiras, em geral publicadas sob a Lei
de Acesso à Informação  **Lei 12.527/2011 (LAI)**. Podem aparecer: CPFs
parciais ou completos conforme a fonte, vínculos servidor-município, remuneração
e cargo, valores de Bolsa Família no contexto de vínculo público, candidatos e
dados TSE, sócios RFB, sanções CEIS/CNEP/CEAF, fornecedores, empenhos,
pagamentos, contratos, licitações, emendas, PGFN, CPGF, SIAPE, BNDES, PNCP e
ComprasNet.

## Bases legais consideradas

- **LGPD art. 7º, III**  tratamento pela administração pública para execução de
  políticas públicas; aplica-se à coleta/divulgação pela fonte original.
- **LGPD art. 7º, IV**  estudos com anonimização quando possível; o projeto
  aplica minimização, especialmente CPF parcial.
- **LGPD art. 26**  uso compartilhado pelo Poder Público, regime sob o qual as
  fontes divulgam muitos datasets.
- **Interesse público/transparência**  servidores públicos, fornecedores do
  Estado, candidatos, sancionados e pessoas ligadas a recursos públicos têm
  contexto de publicidade ampliado, observados necessidade e proporcionalidade.

## Como tratamos os dados

- **Armazenamento:** PostgreSQL 16 em VM Azure única, sem replicação geográfica
  estruturada. Ver [`architecture.md`](architecture.md).
- **Mascaramento:** CPFs em relatórios markdown versionados usam
  `***.NNN.NNN-**`. O script `scripts/audit_report_identifiers.py --strict`
  falha se encontrar CPF completo formatado (`NNN.NNN.NNN-NN`).
- **Normalização:** joins técnicos usam `cpf_digitos`, `cpf_digitos_6` e
  `cpf_cnpj_norm`; a UI evita expor identificador completo quando o parcial
  basta. CNPJs completos podem aparecer por serem dados cadastrais públicos.
- **Bolsa Família:** o portal mostra valores apenas durante período de vínculo
  ativo do servidor público, mitigando exposição fora do contexto investigativo.
- **Logs:** retenção operacional recomendada de 90 dias para access logs usados
  por fail2ban/anti-abuse e até 6 meses para `journalctl`, sujeitos à rotação do
  servidor.
- **Backups:** ainda não há rotina estruturada de backup/restore; é um gap
  operacional documentado em `ops.md`/runbooks de operação.

## Direitos do titular (LGPD art. 18)

Você pode solicitar: confirmação de tratamento; acesso; correção; anonimização,
bloqueio ou eliminação; portabilidade quando aplicável; eliminação de dados
tratados com consentimento; informação sobre compartilhamento; informação sobre
não fornecer consentimento; e revogação de consentimento. Em dados públicos de
interesse público, sanções obrigatórias e vínculos funcionais, alguns direitos
podem ter limites legais.

## Como exercer direitos

Envie e-mail para
[`contato@transparenciapb.org`](mailto:contato@transparenciapb.org) com assunto
**`[LGPD]`**. Inclua, se possível: nome, CPF ou CPF mascarado, URL exata, fonte
pública de origem e pedido específico. O objetivo é responder em até **15 dias
úteis**. O pedido cobre dados pessoais identificados pelo solicitante que
apareçam no portal ou repositório; não substitui solicitação às fontes oficiais.

## Takedown

Pedidos de remoção/anonimização podem ser aceitos quando: a fonte oficial removeu
ou retificou o dado; a divulgação causar dano desproporcional; houver ordem
judicial, decisão administrativa ou orientação aplicável da ANPD/STF; ou houver
erro de matching por CPF parcial, homônimo ou inconsistência. Envie e-mail com
assunto **`[LGPD] Takedown`**, URL, identificação do dado e base legal específica.

## Limitações

- Não controlamos as fontes originais; remover daqui não remove do Portal da
  Transparência, TCE, CGU, Receita Federal ou outros portais.
- CEIS, CNEP e CEAF têm publicidade obrigatória, com limites mais estreitos para
  remoção.
- Servidores públicos e fornecedores pagos com recurso público têm interesse
  público relevante (LGPD art. 23), mitigando expectativa de sigilo sobre atos
  funcionais, remuneração pública, contratos e sanções.
- O projeto pode ocultar a apresentação pública sem alterar registros oficiais de
  origem.

## Cookies e armazenamento local

| Item | Função |
|---|---|
| Sessão | estado técnico de navegação ou autenticação administrativa, quando necessário |
| CSRF | proteção de formulários contra submissões forjadas, quando necessário |
| Umami | analytics self-hosted, sem tracking cross-site e com respeito a Do Not Track |
| `localStorage` Umami | marcação opcional de navegador de operador para depuração |

Não usamos cookies de publicidade comportamental, retargeting, Google Analytics
ou Facebook Pixel.

## Compartilhamento com terceiros

| Terceiro | Dados | Finalidade |
|---|---|---|
| Resend | dados inseridos no `/contato` e metadados mínimos | envio de e-mail ao owner |
| Microsoft Azure | aplicação, banco, logs e arquivos hospedados | infraestrutura/hosting |
| Fontes oficiais | não recebem dados do portal por padrão | são a origem dos datasets |

Não vendemos dados pessoais nem compartilhamos listas de visitantes com
anunciantes.

## Crianças

O portal não é destinado a menores de 12 anos e não coleta ativamente dados de
crianças. Bases públicas podem conter dados de menores em situações específicas;
nesses casos, a exposição deve ser minimizada e avaliada com cuidado.

## Contato DPO

Não há DPO formal; este é um gap operacional. O owner atua como ponto de contato
LGPD. Use [`contato@transparenciapb.org`](mailto:contato@transparenciapb.org)
com assunto **`[LGPD] descrição curta`**.

## Histórico de modificações

| Data | Mudança | Commit |
|---|---|---|
| 2026-05-16 | Primeira versão pública da política LGPD, expandindo `DATA-LICENSE.md`. | `4982af7` |
