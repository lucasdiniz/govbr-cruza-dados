# ADR-0008: AGENTS.md como fonte canônica de instruções para agentes de IA

## Status

Accepted

## Date

2026-05-17

## Context

O projeto já era escrito majoritariamente com auxílio de assistentes de IA
(GitHub Copilot, Claude Code, Codex — ver banner do
[`README.md`](../../README.md)) e o repositório está agora aberto para
contribuições externas. Com isso, novos contributors trazem **seus próprios
agentes**, cada um esperando arquivos de instruções em locais diferentes:

- **GitHub Copilot CLI** lê `.github/copilot-instructions.md`,
  `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` (raiz e `cwd`), e
  `.github/instructions/**/*.instructions.md`.
- **Claude Code** lê `CLAUDE.md` (e em versões recentes também `AGENTS.md`).
- **Cursor** lê `.cursorrules` (formato legacy) e `AGENTS.md` (formato novo).
- **Aider**, **Codex CLI**, **Continue.dev** e outros adotaram `AGENTS.md`
  como padrão a partir da spec [agents.md](https://agents.md).

Até esta decisão, o repositório só tinha
`.github/copilot-instructions.md` (~6.4 KB) e o conteúdo nele evoluiu junto
com a base. As alternativas consideradas para suportar os múltiplos
ecossistemas:

1. **Duplicar conteúdo em três (ou mais) arquivos.** Garantia máxima de que
   qualquer agente encontra o conteúdo, mas multiplica o esforço de
   manutenção — toda mudança de convenção precisa ser replicada em 3+
   lugares, com risco de drift entre cópias.
2. **Symlinks `CLAUDE.md → AGENTS.md` etc.** Bonito em Linux/macOS, frágil no
   Windows (que é onde o mantenedor trabalha — symlinks Git no Windows
   exigem permissões especiais e quebram em alguns clientes). Pior, o
   GitHub web UI não renderiza symlinks como o destino.
3. **Arquivo canônico único + arquivos-ponteiro curtos.** Mantém um arquivo
   com o conteúdo real; os outros são "stub" de 10-20 linhas explicando que
   o canônico está em `AGENTS.md` e listando o que é essencial saber. Agentes
   modernos leem todos os arquivos relevantes automaticamente, então enxergam
   o ponteiro **e** o canônico no contexto.

A discussão foi acelerada por uma observação concreta: a documentação oficial
do GitHub Copilot CLI lista explicitamente
[`AGENTS.md` entre os arquivos de instrução que o CLI respeita](https://docs.github.com/copilot/concepts/agents/about-copilot-cli),
em pé de igualdade com `CLAUDE.md` e
`.github/copilot-instructions.md`.

## Decision

**`AGENTS.md` na raiz do repositório é a fonte canônica de instruções para
agentes de IA.** Ele segue a spec [agents.md](https://agents.md) e contém:

- Visão geral do projeto e mapa de documentação
- Comandos de setup
- Arquitetura essencial (com pointers para `docs/`)
- Convenções (no-pandas, no-ORM, latin-1 do RFB, identificadores em PT-BR…)
- Quirks descobertos pelos agentes e mantenedor (Mermaid, MD3, MV layering,
  cache typing, deploy, …)
- Checklist obrigatório de PR (README / `docs/` / ADR / glossary / testes /
  audit scripts / trailer)

**`CLAUDE.md` e `.github/copilot-instructions.md` são arquivos-ponteiro
curtos** (~25 linhas) que:

- Apontam para `AGENTS.md`
- Listam um TL;DR com 4-5 itens críticos (idioma, no-pandas, no-ORM, trailer,
  PR checklist)
- Referenciam este ADR

Esse padrão preserva a descoberta automática (cada agente continua encontrando
o arquivo que ele espera), evita duplicação de conteúdo, e mantém o canônico
discoverable também para humanos navegando pelo repositório.

## Consequences

### Positive

- **Uma única fonte de verdade.** Convenções, quirks e checklist de PR estão
  num só lugar; mudanças não vazam de um arquivo para outro.
- **Manutenção 1×** em vez de 3×.
- **Cobertura ampla de agentes**: a spec `AGENTS.md` é o ponto de
  convergência da indústria em 2025-2026; quase todos os agentes modernos
  já leem.
- **Discoverable também para humanos.** `AGENTS.md` na raiz aparece no
  preview do GitHub e ajuda contributors sem agente a entender as
  convenções do projeto.
- **Pointer files explicam o padrão**, então mesmo agentes que só leem
  `CLAUDE.md` ou `copilot-instructions.md` recebem um redirecionamento
  legível.

### Negative / Trade-offs

- **Agentes muito antigos** que ignoram `AGENTS.md` e leem só seu arquivo
  específico verão apenas o ponteiro + TL;DR — não o conteúdo completo.
  Mitigação: o TL;DR cobre os ~5 itens mais críticos e o ponteiro instrui
  explicitamente a abrir `AGENTS.md`.
- **Risco de duplicar contexto.** Agentes que leem múltiplos arquivos
  (Copilot CLI, Claude Code recente) podem carregar pointer + canônico
  no mesmo prompt. O custo de tokens é baixo (pointer < 1 KB cada),
  aceitável.
- **Convenção precisa ser ensinada aos contributors humanos.** O
  `CONTRIBUTING.md` agora referencia `AGENTS.md` explicitamente para que
  contributors saibam onde editar.

### Mitigations

- TL;DR nos pointer files cobre o mínimo crítico para um agente legacy
  fazer trabalho útil mesmo sem ler `AGENTS.md`.
- `CONTRIBUTING.md` e `README.md` referenciam `AGENTS.md` como ponto de
  partida para contributors usando agentes.
- Se um novo agente popular surgir com formato próprio, adicionar um
  novo pointer file segue o mesmo padrão (3 ou 4 arquivos pointer não
  muda a economia da decisão).

## Related

- Code:
  - [`AGENTS.md`](../../AGENTS.md) — canônico
  - [`CLAUDE.md`](../../CLAUDE.md) — pointer
  - [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — pointer
- Other ADRs: nenhum diretamente, mas o conteúdo de `AGENTS.md` referencia
  todos os outros ADRs como contexto arquitetural.
- External:
  - [agents.md spec](https://agents.md)
  - [GitHub Copilot CLI — files respected](https://docs.github.com/copilot/concepts/agents/about-copilot-cli)
  - [Anthropic Claude Code — CLAUDE.md docs](https://docs.anthropic.com/claude-code)
