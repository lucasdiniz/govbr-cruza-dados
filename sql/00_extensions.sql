-- Extensões necessárias para o sistema
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Conversão segura de texto para data (retorna NULL em vez de erro)
CREATE OR REPLACE FUNCTION safe_to_date(val TEXT, fmt TEXT)
RETURNS DATE AS $$
BEGIN
  IF val IS NULL OR TRIM(val) = '' OR TRIM(val) = '00000000' THEN
    RETURN NULL;
  END IF;
  -- Se tem timestamp (YYYY-MM-DD HH:MM:SS...), pegar so a data
  IF LENGTH(TRIM(val)) > 10 AND TRIM(val) ~ '^\d{4}-\d{2}-\d{2}' THEN
    RETURN TO_DATE(LEFT(TRIM(val), 10), 'YYYY-MM-DD');
  END IF;
  RETURN TO_DATE(TRIM(val), fmt);
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Função imutável para normalizar nomes (usável em índices funcionais)
CREATE OR REPLACE FUNCTION normalize_name(input TEXT)
RETURNS TEXT AS $$
  SELECT UPPER(TRIM(regexp_replace(unaccent(input), '\s+', ' ', 'g')));
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;
