"""Constantes do frontend web."""
import os

# Connection pool
POOL_MIN = 2
# POOL_MAX bumpado pra suportar warmer paralelo (8 workers em
# WARM_CACHE_WORKERS_MUN). Em runtime web, FastAPI nao usa nem perto
# disso (poucos requests/segundo). 16 conns no PG ainda eh barato.
POOL_MAX = int(os.getenv("WEB_POOL_MAX", "16"))

# Timeouts (segundos) — usados como statement_timeout no PostgreSQL
TIMEOUT_PROFILE = 3
TIMEOUT_AUTOCOMPLETE = 2
TIMEOUT_COUNT = 10
TIMEOUT_QUERY_LIGHT = 15
TIMEOUT_QUERY_MEDIUM = 45
TIMEOUT_QUERY_HEAVY = 90

# Timeout do warmer compute_empresa_perfil_dict (web/warm_cache.py).
# Maior que TIMEOUT_PROFILE porque mega-empresas (BB cnpj_basico=00000000,
# Caixa 00360305, INSS 29979036) tem MILHOES de empenhos em tce_pb_despesa
# — GROUP BY municipio e GROUP BY elemento_despesa em prod podem demorar
# minutos. 600s = 10min eh teto generoso (warmer roda offline, paralelo,
# vale esperar). Empresa que demorar mais que isso fica de fora — provavelmente
# bug no plano de query ou estatisticas stale.
# Route nao chama compute (cache-only), entao TIMEOUT_PROFILE=3s do route
# nao eh afetado.
TIMEOUT_PROFILE_WARM = 600

# Limites de resultado
LIMIT_AUTOCOMPLETE = 20
LIMIT_QUERY = 500
LIMIT_TOP = 10

# Cache in-memory
CACHE_TTL = 3600  # 1 hora
