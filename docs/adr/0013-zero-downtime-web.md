# ADR-0013: Zero-downtime no web (deploys + VM resize)

## Status

Proposed

## Date

2026-05-19

## Context

O site [transparenciapb.org](https://transparenciapb.org) sofre 502 Bad Gateway
em duas janelas previsíveis:

1. **Durante deploys de código.** O step "Restart cruza-web (after warm)" em
   [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml#L1434)
   executa `sudo systemctl restart cruza-web`, que é stop+start hard de um
   `Type=simple` rodando uvicorn diretamente
   ([`deploy/cruza-web.service`](../../deploy/cruza-web.service)). O socket
   TCP `127.0.0.1:8000` fecha imediatamente; o novo master de uvicorn leva
   3-5s pra rebindar e spawnar workers. Como
   [`deploy/nginx-cruza.conf`](../../deploy/nginx-cruza.conf#L429) faz
   `proxy_pass http://127.0.0.1:8000` (sem bloco `upstream`, sem
   `proxy_next_upstream`, sem `error_page 502 503 504`), a janela inteira
   retorna 502 cru ao cliente.

2. **Durante resize da VM Azure.** O preflight/postflight do workflow
   ([`deploy.yml#L255-308`](../../.github/workflows/deploy.yml#L255) e
   [`#L2164-2201`](../../.github/workflows/deploy.yml#L2164)) faz
   `az vm deallocate → az vm resize → az vm start` pra alternar entre
   `Standard_B2as_v2` (web) e `Standard_B4as_v2` (ETL). O B-series
   (burstable) **exige** deallocate pra qualquer resize — não há live-resize
   pra essa família no Azure. A VM inteira fica fora ~30-60s, nginx incluso.
   Nada *na própria VM* pode mitigar isso, por definição.

A frequência é alta: todo deploy ETL/SQL/web dispara (1) e
quase todo deploy não-trivial dispara (2). Em janelas de baixa visibilidade
isso passa despercebido; em picos (acesso de imprensa, divulgação em redes)
os 502 viram reclamação concreta.

## Decision

Adotar **estratégia em duas faixas**, atacando cada causa raiz com a
ferramenta apropriada:

### Faixa 1 — Gunicorn master + `systemctl reload` (deploys)

Substituir o uvicorn standalone por **Gunicorn como master de processo + 
`UvicornWorker` como worker class**:

- `pyproject.toml`: adicionar `gunicorn>=21` em
  `[project.optional-dependencies].web`
- `deploy/cruza-web.service`:
  ```ini
  ExecStart=/home/govbr/govbr-project/venv/bin/gunicorn web.main:app \
    -k uvicorn.workers.UvicornWorker \
    -w 3 -b 127.0.0.1:8000 \
    --graceful-timeout 30 --timeout 90 --keep-alive 5
  ExecReload=/bin/kill -s HUP $MAINPID
  KillMode=mixed
  TimeoutStopSec=60
  ```
- `deploy.yml`: trocar `systemctl restart cruza-web` por
  `systemctl reload cruza-web` em todos os ~15 pontos. Adicionar lógica de
  fallback: se o **unit file** mudou (`systemctl show -p NeedDaemonReload`
  ou comparação de hash), forçar `restart` em vez de `reload` — porque
  mudanças em `ExecStart` só são aplicadas em restart.

Mecanismo: o master do Gunicorn mantém o socket TCP `8000` aberto
continuamente. `SIGHUP` faz rotação graceful — spawna novos workers com o
código atualizado, espera readiness, manda `SIGTERM` nos antigos (que
drenam requisições in-flight até `--graceful-timeout`). nginx nunca vê o
socket fechar.

Isso é o padrão production-grade default em Python (Gunicorn existe há 15+
anos exatamente pra isso). uvicorn standalone foi pensado pra dev/single
worker; pra produção multi-worker com hot restart, a doc oficial do uvicorn
recomenda o mesmo padrão.

### Faixa 2 — Cloudflare na frente, plano Free (VM resize + safety net)

Colocar **Cloudflare como CDN/proxy** entre internet e a VM Azure:

- Mudar nameservers DNS de `transparenciapb.org` pra CF
- Ativar **proxy mode (orange cloud)** — todo tráfego HTTPS passa por CF
- Cert SSL: modo **"Full (Strict)"** — CF valida o cert Let's Encrypt
  origem (já temos)
- Ativar **Always Online** — CF cacheia HTML das páginas crawleadas e serve
  quando origin retorna 5xx / timeout
- **Cache Rules** explícitas pra rotas anônimas cacheáveis (`/cidade/*`,
  `/empresa/*`, `/licitacao/*`, `/sobre`, `/glossario`); bypass em `/api/*`,
  `/_traffic/*`, `/sw.js`
- `deploy/nginx-cruza.conf`: adicionar `set_real_ip_from <CF ranges>` +
  `real_ip_header CF-Connecting-IP` pra preservar IP real do cliente no
  log do nginx (essencial pro `goaccess` em `/_traffic/raw` e pro
  `limit_req` continuarem funcionando)
- `iptables`: allowlist dos IP ranges da CF na porta 443 (mitiga exposição
  do IP origem via histórico DNS)

Cobertura por cenário:

| Cenário                            | CF cobre? | Como                       |
| ---------------------------------- | --------- | -------------------------- |
| Deploy 502 (3-5s, GETs cacheáveis) | ✅        | Always Online + cache TTL  |
| Deploy 502 (POSTs `/api/contato`)  | ❌        | Mitigado por Faixa 1       |
| VM resize (30-60s, GETs cacheados) | ✅        | Always Online              |
| VM resize (drilldowns ad-hoc)      | ❌        | Custom Error Page amigável |
| VM resize (POSTs raros)            | ❌        | Aceito; raro               |
| DDoS / scanners agressivos         | ✅        | Bonus do CF                |

Custo: **US$ 0/mês**. Reversível em 5 min (volta DNS pro IP direto).

## Alternativas consideradas

### Live-resize Azure dentro da mesma família ❌

Descartado: o B-series não suporta resize sem deallocate. Memory hot-add
do Azure é restrito a SKUs D/E-series específicas com Hyper-V Dynamic
Memory, predominantemente Windows. Trocar pra D-series (ex: `D2as_v4`)
custaria ~US$ 70/mês a mais — desproporcional pra um problema de minutos
por semana.

### 2 VMs atrás de Azure Load Balancer ❌ (por enquanto)

Custo proibitivo no setup atual onde web + DB coabitam:

- **Replicar tudo** (2× VM cheia): ~US$ 122/mês adicional + complexidade
  alta de PG streaming replication com dataset de 248GB
- **Separar web (small) de DB (big)**: ~US$ 43/mês adicional, mas requer
  refactor arquitetural significativo — extrair `web/*` pra B1s, manter
  PostgreSQL no host atual, configurar conexão remota, replicar static
  files pra ambos os hosts, ajustar deploy pra rollout 1-a-1

Pros do D.3: zero-downtime real **inclusive pra POSTs**.  
Cons: custo +40% e complexidade operacional 4-5x maior.

**Reavaliar SE**: Cloudflare não der conta dos POSTs e usuários começarem a
reclamar de formulário caindo, OU se houver consolidação de receita
suficiente pra absorver o custo, OU se chegar uma necessidade de HA real
(uptime SLO formal).

### Blue/green com 2 systemd instances + upstream nginx ❌

Sem dependência nova, mas:

- 2× memória residente (uvicorn × 6 workers em vez de × 3) — VM web é
  Standard_B2as_v2 com 8GB, apertado
- Refactor não trivial em `deploy.yml`: cada `systemctl restart cruza-web`
  vira sequência rollout (restart standby → health check → swap nginx
  upstream → restart primary)
- Não resolve VM resize — só Cloudflare ou D.3 resolvem

Gunicorn faz o mesmo (worker rotation graceful) sem essa complexidade,
porque o **mesmo processo master** já tem a lógica nativa. Blue/green
faria sentido se já tivéssemos cluster, não pra single-host.

### nginx `proxy_cache` + `proxy_cache_use_stale` ❌ (parcial)

Cobriria o cenário de 502 servindo HTML de cache local do nginx, sem CF.
Mas:

- Não cobre VM resize (nginx tá fora junto)
- Cria nova camada de cache concorrendo com `web_cache` (PG) — coerência
  difícil
- Mantém problema do IP origem público

Cloudflare faz isso e mais (Always Online, DDoS, IP masking) por US$ 0.

## Plano de implementação

Faseado pra reduzir risco — cada fase é independente e reversível:

**Fase 1 (PR independente):** Faixa 1 — Gunicorn + reload + 
`error_page 502 503 504 /503.html` no nginx com página estática amigável.
Resolve ~99% dos 502s de deploy. Risco: gunicorn vs uvicorn standalone tem
diferenças sutis em logging/signals; testar com canary deploy (`etl_phase=web`)
em janela de baixo tráfego antes de promover.

**Fase 2 (PR separado, depende de Fase 1):** Faixa 2 — Cloudflare proxy +
nginx `set_real_ip_from` + Cache Rules. Resolve VM resize pra GETs
cacheáveis. Risco: mudança de DNS é cheap-rollback (TTL baixo durante
migração); validar `_traffic/raw` mostra IP real depois da mudança.

**Fase 3 (futuro condicional):** Se reclamações de POST/drilldown durante
resize persistirem, reabrir avaliação de D.3 com proposta concreta de
separação web/DB.

## Consequences

### Positive

- Deploy 502s caem de ~3-5s/deploy pra <100ms (Gunicorn reload graceful)
- VM resize 502s caem de ~30-60s/resize pra **0** pra GETs cacheáveis 
  (~80% do tráfego pelo padrão de uso observado)
- Bonus Cloudflare: proteção DDoS, IP origem mascarado, analytics extra,
  TLS 1.3 universal sem config local
- Reduz superfície de ataque direto à VM Azure (pode `iptables` restringir
  443 só pros IPs CF)
- Padrão "Gunicorn como master de Uvicorn workers" alinha com prática
  estabelecida da comunidade Python — onboarding mais fácil pra
  contribuidores futuros

### Negative / Trade-offs

- Gunicorn é uma dependência nova no path de servir requisições — debugging
  de issues em produção precisa entender 2 camadas (Gunicorn master ↔
  UvicornWorker) em vez de só uma
- Cloudflare é trust boundary novo — eles veem todo tráfego HTTPS
  decrypted in-flight. Pra um site público brasileiro de dados abertos é
  aceitável; pra dados sensíveis seria show-stopper
- Logs de access do nginx ganham nova fonte de verdade pra IP do cliente
  (`CF-Connecting-IP`) — qualquer ferramenta que parsea logs (goaccess,
  scripts ad-hoc) precisa estar ciente
- Rate limiting (`limit_req`) pode reagir a IP errado durante a janela de
  config sem `set_real_ip_from` — pode bloquear tráfego legítimo ou deixar
  passar abuso. Deploy da Fase 2 precisa ser uma operação atômica: ativar
  CF + reload nginx com novo config no mesmo passo
- POSTs ainda perdem durante VM resize (~30-60s). Aceitável dado volume
  baixo de POSTs no app (`/api/contato`, alguns `/api/cache` admin)

### Mitigations

- **Fase 1 canary**: testar Gunicorn primeiro com `etl_phase=web` (zero
  ETL impact) em janela de baixo tráfego (madrugada BR). Se algo der
  errado, `systemctl restart` força fallback pro estado bom + rollback do
  service file via git revert
- **Fase 2 staged DNS**: começar com TTL baixo (60s) na mudança pra CF;
  monitorar `journalctl -u nginx -f` + `_traffic/raw` por 24h antes de
  subir TTL pra default. Se Cache Rules causarem stale incorreto, basta
  desabilitar a regra no dashboard CF (efeito em segundos)
- **iptables allowlist** pra CF IPs feito como step opcional (não
  obrigatório pra Fase 2 inicial), via cron job que pulla lista atualizada
  de [CF IP ranges](https://www.cloudflare.com/ips/) semanalmente
- **Documentar em [`docs/ops.md`](../ops.md)** o procedimento de "voltar
  pro estado anterior" pra cada fase, incluindo como purgar cache CF em
  emergência

## Related

- Code:
  - [`deploy/cruza-web.service`](../../deploy/cruza-web.service) (a editar
    em Fase 1)
  - [`deploy/nginx-cruza.conf`](../../deploy/nginx-cruza.conf) (Fase 1
    `error_page` + Fase 2 `set_real_ip_from`)
  - [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
    (~15 ocorrências de `systemctl restart cruza-web`)
  - [`pyproject.toml`](../../pyproject.toml) (Fase 1 dep nova)
- Other ADRs:
  - [ADR-0003](0003-shadow-rewarm.md) — outro padrão zero-downtime do
    projeto (cache rewarm via `__pending` swap atômico)
  - [ADR-0006](0006-mv-atomic-swap.md) — outro padrão zero-downtime (swap
    atômico de MVs)
- External:
  - [Uvicorn deployment docs](https://www.uvicorn.org/deployment/) —
    recomenda Gunicorn como process manager pra produção multi-worker
  - [Gunicorn signal handling](https://docs.gunicorn.org/en/stable/signals.html) —
    `SIGHUP` = reload graceful
  - [Cloudflare Always Online](https://developers.cloudflare.com/cache/about/always-online/)
  - [Azure VM resize matrix](https://learn.microsoft.com/en-us/azure/virtual-machines/resize-vm) —
    confirma necessidade de deallocate pra B-series
