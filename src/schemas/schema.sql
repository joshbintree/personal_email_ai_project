CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS emails (
    id              SERIAL PRIMARY KEY,
    content         TEXT,
    embedding       VECTOR(384),
    message_id      TEXT,
    sender_name     TEXT,
    sender_email    TEXT,
    received_at     TIMESTAMPTZ,
    has_attachment  BOOLEAN DEFAULT FALSE,
    attachments     TEXT[],
    gmail_labels    TEXT[]
);