# Architecture Decision Records (ADRs)

Este diretório registra as decisões arquiteturais relevantes do `govbr-cruza-dados`.

## O que é um ADR?

Um Architecture Decision Record documenta **uma decisão técnica importante**, o
**contexto** em que ela foi tomada, e suas **consequências** (positivas, negativas e
mitigações). ADRs não são tutoriais nem especificações — são a memória institucional
do projeto.

Os ADRs aqui foram, em sua maioria, escritos **retroativamente**: documentam decisões
já tomadas e em produção. Isso é intencional — registrar a justificativa atrás de um
"por que está assim?" é mais valioso do que não registrar nada.

Para o panorama arquitetural geral (que referencia estes ADRs nos pontos críticos),
veja [`docs/architecture.md`](../architecture.md).

## Índice

| ID       | Título                                                 | Status   | Data       |
| -------- | ------------------------------------------------------ | -------- | ---------- |
| ADR-0001 | [No pandas — streaming + COPY FROM STDIN](0001-no-pandas.md) | Accepted | 2024-06-15 |
| ADR-0002 | [Materialized Views em camadas L1 → L2 → views planas](0002-mv-layered.md) | Accepted | 2024-09-10 |
| ADR-0003 | [Shadow rewarm com `__pending` swap atômico](0003-shadow-rewarm.md) | Accepted | 2025-01-20 |
| ADR-0004 | [Framework ETL incremental dedicado](0004-etl-incremental-framework.md) | Accepted | 2025-03-05 |
| ADR-0005 | [Sem ORM no web — raw SQL via psycopg2](0005-no-orm-web.md) | Accepted | 2024-08-01 |
| ADR-0006 | [Atomic swap de Materialized Views (zero-downtime updates)](0006-mv-atomic-swap.md) | Accepted | 2026-05-16 |
| ADR-0007 | [ETL-level fix para contaminação de cnpj_basico + REFRESH CONCURRENTLY](0007-etl-normalize-fix.md) | Accepted | 2026-05-16 |
| ADR-0008 | [AGENTS.md como fonte canônica de instruções para agentes de IA](0008-agents-md-canonical.md) | Accepted | 2026-05-17 |
| ADR-0009 | [Cleanup de entries órfãs em `web_cache` pós-MV refresh](0009-orphan-empresa-cache-cleanup.md) | Accepted | 2026-05-17 |

## Convenções

### Numeração

ADRs são numerados sequencialmente com 4 dígitos zero-padded: `0001`, `0002`, ...
O nome do arquivo segue o padrão `NNNN-titulo-curto-kebab-case.md`.

### Imutabilidade

**Uma vez `Accepted`, um ADR é imutável.** Correções tipográficas e links são OK.
Mudança de decisão = **novo ADR** com:

- `Status: Accepted`
- Campo `Supersedes ADR-XXXX` no header
- O ADR antigo atualizado para `Status: Superseded by ADR-YYYY`

Isso preserva o histórico de raciocínio. Quem ler o repositório daqui a 2 anos vai
querer entender *por que* a decisão mudou, não só que mudou.

### Status

- **Accepted** — em vigor, implementada
- **Superseded by ADR-XXXX** — substituída por outra decisão
- **Deprecated** — não está mais em uso, mas não foi formalmente substituída

### Quando escrever um ADR?

Escreva um ADR quando a decisão:

- Afeta múltiplos módulos ou subsistemas
- Tem trade-offs não-óbvios (alguém razoável poderia ter escolhido diferente)
- Vai ser questionada depois ("por que não usamos X?")
- Estabelece um padrão que outros contributors precisam seguir

Decisões locais, idiomáticas ou facilmente reversíveis **não** precisam de ADR —
um comentário no código basta.

## Template

```markdown
# ADR-NNNN: <título curto>

## Status

[Accepted | Superseded by ADR-XXXX | Deprecated]

## Date

YYYY-MM-DD

## Context

(O problema que motivou a decisão. Por que essa escolha precisou ser feita.
 Quais alternativas existiam.)

## Decision

(A escolha feita, em linguagem direta.)

## Consequences

### Positive

- ...

### Negative / Trade-offs

- ...

### Mitigations

- ...

## Related

- Code: link para arquivos/funções
- Other ADRs: ADR-XXXX
- External: links para docs/posts/papers
```

## Referências externas

- Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) (2011) — origem do formato
- [adr.github.io](https://adr.github.io/) — coletânea de templates e exemplos
