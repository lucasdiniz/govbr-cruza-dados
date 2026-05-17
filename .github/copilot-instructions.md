# Copilot instructions

> Canonical instructions for AI coding agents — including GitHub Copilot CLI —
> live in [`AGENTS.md`](../AGENTS.md) at the repository root.
>
> The Copilot CLI reads **both** this file and `AGENTS.md` automatically. This
> file exists only to make the entry point obvious; all content is maintained
> in `AGENTS.md` ([ADR-0008](../docs/adr/0008-agents-md-canonical.md)).

**TL;DR:**

- Working language: **Portuguese (BR)** — identifiers, comments, commits, PRs.
- No pandas in ETL; streaming + `COPY FROM STDIN` ([ADR-0001](../docs/adr/0001-no-pandas.md)).
- No ORM in web; raw SQL via psycopg2 ([ADR-0005](../docs/adr/0005-no-orm-web.md)).
- Every commit ends with
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Every PR checks **README / `docs/` / ADR** for matching updates — see the
  checklist in `AGENTS.md`.

See [`AGENTS.md`](../AGENTS.md) for the full setup, architecture, conventions,
discovered quirks (Mermaid parser, MD3 upgrade gate, MV layering, cache type
coercion, deploy quirks, …) and PR checklist.
