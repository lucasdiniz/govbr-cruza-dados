"""Constantes do frontend web."""

# Connection pool
POOL_MIN = 2
POOL_MAX = 4

# Timeouts (segundos) — usados como statement_timeout no PostgreSQL
TIMEOUT_PROFILE = 3
TIMEOUT_AUTOCOMPLETE = 2
TIMEOUT_COUNT = 10
TIMEOUT_QUERY_LIGHT = 15
TIMEOUT_QUERY_MEDIUM = 45
TIMEOUT_QUERY_HEAVY = 90

# Limites de resultado
LIMIT_AUTOCOMPLETE = 20
LIMIT_QUERY = 500
LIMIT_TOP = 10

# Cache in-memory
CACHE_TTL = 3600  # 1 hora
