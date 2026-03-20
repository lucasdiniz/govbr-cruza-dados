-- Extensões necessárias para o sistema
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Função imutável para normalizar nomes (usável em índices funcionais)
CREATE OR REPLACE FUNCTION normalize_name(input TEXT)
RETURNS TEXT AS $$
  SELECT UPPER(TRIM(regexp_replace(unaccent(input), '\s+', ' ', 'g')));
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;
