-- sql/40_contato_messages.sql
--
-- Tabela de mensagens recebidas pela página /contato.
-- Audit trail completo: salva sempre que alguém submete o form, mesmo
-- quando o envio do email falha ou quando o honeypot é triggered.
--
-- Phase no run_all: nao roda (tabela operacional do frontend, não ETL).
-- Aplicar manualmente ou via deploy: psql -d $POSTGRES_DB -f sql/40_contato_messages.sql

CREATE TABLE IF NOT EXISTS contato_messages (
    id              BIGSERIAL PRIMARY KEY,
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_remetente    INET,
    user_agent      TEXT,
    -- email_remetente eh OBRIGATORIO no form, mas mantido nullable no DB
    -- pra defesa contra schemas mudando.
    email_remetente TEXT,
    nome_remetente  TEXT,
    titulo          TEXT NOT NULL,
    mensagem        TEXT NOT NULL,
    -- Status do envio via provider (Resend). NULL = ainda nao tentado.
    email_enviado_em TIMESTAMPTZ,
    email_erro      TEXT,
    -- Honeypot trigger: campo invisivel que bots preenchem. Salvamos pra
    -- estatistica e pra responder 200-fake (nao revela ao bot).
    honeypot_triggered BOOLEAN NOT NULL DEFAULT FALSE
);

-- Indice pra listagem cronologica (admin futuramente).
CREATE INDEX IF NOT EXISTS idx_contato_messages_criada_em
    ON contato_messages (criada_em DESC);

-- Indice parcial pra encontrar emails que falharam o envio.
CREATE INDEX IF NOT EXISTS idx_contato_messages_email_falha
    ON contato_messages (criada_em DESC)
    WHERE email_erro IS NOT NULL;

-- Indice parcial pra detectar mensagens pendentes (salvas mas nao
-- enviadas — pode acontecer se o processo reiniciou no meio do
-- background task). Operadores podem listar com:
--   SELECT * FROM contato_messages
--   WHERE honeypot_triggered = FALSE
--     AND email_enviado_em IS NULL AND email_erro IS NULL
--     AND criada_em < NOW() - INTERVAL '2 minutes';
CREATE INDEX IF NOT EXISTS idx_contato_messages_pendente
    ON contato_messages (criada_em)
    WHERE honeypot_triggered = FALSE
      AND email_enviado_em IS NULL
      AND email_erro IS NULL;

-- Indice usado pelo throttle app-level (web/contato.py:is_throttled)
-- pra checar quantas mensagens recentes tem por IP/email.
CREATE INDEX IF NOT EXISTS idx_contato_messages_throttle_ip
    ON contato_messages (ip_remetente, criada_em DESC)
    WHERE honeypot_triggered = FALSE;
CREATE INDEX IF NOT EXISTS idx_contato_messages_throttle_email
    ON contato_messages (email_remetente, criada_em DESC)
    WHERE honeypot_triggered = FALSE;

COMMENT ON TABLE contato_messages IS
    'Mensagens recebidas via /contato. Audit trail: salva sempre que o form é submetido, mesmo se honeypot ou se Resend falhar. Ver web/contato.py.';
