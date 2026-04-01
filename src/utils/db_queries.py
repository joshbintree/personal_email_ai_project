from utils.db_connections import get_db_connection, get_cursor
from utils.embed_text import embed_db_query
def _strip_nul(value):
    """Remove null bytes from strings — Postgres TEXT columns reject them."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_strip_nul(v) for v in value]
    return value

def insert_chunks(chunks: list[dict]):
    connection = get_db_connection()
    cur = get_cursor(connection)
    rows = [
        (
            _strip_nul(chunk["message_id"]),
            _strip_nul(chunk["content"]),
            chunk["embedding"],
            _strip_nul(chunk["sender_name"]),
            _strip_nul(chunk["sender_email"]),
            chunk["received_at"],
            chunk["has_attachment"],
            _strip_nul(chunk["attachments"]),
            _strip_nul(chunk["gmail_labels"]),
        )
        for chunk in chunks
    ]
    cur.executemany(
        """
        INSERT INTO emails
            (message_id, content, embedding, sender_name, sender_email,
             received_at, has_attachment, attachments, gmail_labels)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows
    )
    connection.commit()
    cur.close()
    connection.close()
    print(f"Inserted {len(rows)} rows.")

# main search query to get relevant emails
def search_emails(query: str, top_k: int = 10):
    connection = get_db_connection()
    cur = get_cursor(connection)

    query_embedding = embed_db_query(query)
    cur.execute(
        """
        SELECT content, sender_name, sender_email, received_at, has_attachment, gmail_labels,
               embedding <=> %s::vector AS distance
        FROM emails
        ORDER BY distance
        LIMIT %s
        """,
        (query_embedding, top_k)
    )
    results = cur.fetchall()
    cur.close()
    connection.close()
    return results


def search_emails_by_date(query_embedding: list[float], after: str = None, before: str = None, top_k: int = 20):
    conn = get_db_connection()
    cur = get_cursor(conn)
    cur.execute(
        """
        SELECT content, sender_name, sender_email, received_at, has_attachment, gmail_labels,
               embedding <=> %s::vector AS distance
        FROM emails
        WHERE received_at > %s
          AND (%s IS NULL OR received_at < %s)
        ORDER BY distance
        LIMIT %s
        """,
        (query_embedding, after, before, before, top_k)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def search_emails_by_sender(query_embedding: list[float], sender_email: str, limit: int = 5):
    conn = get_db_connection()
    cur = get_cursor(conn)
    cur.execute(
        """
        SELECT content, sender_name, sender_email, received_at, has_attachment, gmail_labels,
               embedding <=> %s::vector AS distance
        FROM emails
        WHERE sender_email ILIKE %s
        ORDER BY distance
        LIMIT %s
        """,
        (query_embedding, f"%{sender_email}%", limit)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results
def search_emails_with_attachments(
    query_embedding: list[float],
    limit: int = 5,
    after: str = None,
    before: str = None,
    year: int = None,
):
    conn = get_db_connection()
    cur = get_cursor(conn)
    cur.execute(
        """
        SELECT content, sender_name, sender_email, received_at, has_attachment, gmail_labels,
               embedding <=> %s::vector AS distance
        FROM emails
        WHERE has_attachment = TRUE
          AND (%s IS NULL OR received_at > %s)
          AND (%s IS NULL OR received_at < %s)
          AND (%s IS NULL OR EXTRACT(YEAR FROM received_at) = %s)
        ORDER BY distance
        LIMIT %s
        """,
        (query_embedding, after, after, before, before, year, year, limit)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def count_emails(
    after: str = None,
    before: str = None,
    year: int = None,
    sender_email: str = None,
) -> int:
    conn = get_db_connection()
    cur = get_cursor(conn)
    cur.execute(
        """
        SELECT COUNT(DISTINCT message_id)
        FROM emails
        WHERE (%s IS NULL OR received_at > %s)
          AND (%s IS NULL OR received_at < %s)
          AND (%s IS NULL OR EXTRACT(YEAR FROM received_at) = %s)
          AND (%s IS NULL OR sender_email ILIKE %s)
        """,
        (after, after, before, before, year, year, sender_email, f"%{sender_email}%" if sender_email else None)
    )
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return result

def get_top_senders(limit: int = 10, year: int = None):
    conn = get_db_connection()
    cur = get_cursor(conn)
    cur.execute(
        """
        SELECT sender_email, sender_name, COUNT(DISTINCT message_id) AS email_count
        FROM emails
        WHERE (%s IS NULL OR EXTRACT(YEAR FROM received_at) = %s)
        GROUP BY sender_email, sender_name
        ORDER BY email_count DESC
        LIMIT %s
        """,
        (year, year, limit)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

