import mailbox
from email.utils import parsedate_to_datetime
from email.header import decode_header, make_header
from email.utils import parseaddr
import html2text 
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import timezone

splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    model_name="text-embedding-3-small",
    chunk_size=1024,
    chunk_overlap=50,
)

def parse_date(raw_date: str):
    if not raw_date:
        return None
    try:
        dt = parsedate_to_datetime(raw_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None

def decode_subject(raw):
    return str(make_header(decode_header(raw))) if raw else ""

def safe_decode(payload: bytes, charset: str) -> str:
    encodings = [
        charset,
        # Universal
        "utf-8",
        # Japanese
        "iso-2022-jp",
        "shift_jis",
        "euc-jp",
        # Chinese (Simplified)
        "gb2312",
        "gbk",
        "gb18030",
        # Chinese (Traditional)
        "big5",
        # Korean
        "euc-kr",
        "iso-2022-kr",
        # Fallbacks
        "latin-1",
        "ascii",
    ]
    seen = set()
    for enc in encodings:
        if enc in seen:
            continue
        seen.add(enc)
        try:
            return payload.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("latin-1", errors="replace")

def has_attachment(message) -> bool:
    for part in message.walk():
        cd = str(part.get("Content-Disposition", ""))
        if "attachment" in cd:
            return True
        # some attachments omit Content-Disposition but have a filename
        if part.get_filename() is not None:
            return True
    return False

def get_attachment_names(message) -> list[str]:
    names = []
    if not has_attachment(message):
        return []
    for part in message.walk():
        filename = part.get_filename()
        if filename:
            # decode encoded filenames (e.g. =?utf-8?...)
            decoded = str(make_header(decode_header(filename)))
            names.append(decoded)
    return names

def get_body(message):
    """Prefer text/plain; fall back to stripping text/html."""
    plain, html = None, None
    for part in message.walk():
        ct = part.get_content_type()
        cd = str(part.get("Content-Disposition", ""))
        if "attachment" in cd:
            continue

        payload = part.get_payload(decode=True)
        if payload is None:  # skip multipart containers
            continue

        charset = clean_charset(part.get_content_charset())

        if ct == "text/plain" and plain is None:
            plain = safe_decode(payload, charset)
        elif ct == "text/html" and html is None:
            raw_html = safe_decode(payload, charset)
            html = html2text.html2text(raw_html)

    return plain or html or ""
def clean_charset(charset: str) -> str:
    if not charset:
        return "utf-8"
    # take only the first word, strip quotes and whitespace
    return charset.split()[0].strip().strip('"').strip("'")
def get_emails_from_mbox():
    seen_ids = set()
    records = []
    mbox = mailbox.mbox('./All_mail_Including_Spam_and_Trash.mbox')
    for msg in mbox:
        msg_id = msg.get('Message-ID').strip()
        if msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)
        raw_sender = msg.get('From', "")
        decoded_sender = str(make_header(decode_header(raw_sender)))
        sender_name, sender_email = parseaddr(decoded_sender)
        msg_subject = decode_subject(msg.get('Subject'))
        msg_received_at = parse_date(msg.get('Date'))
        msg_body = get_body(msg)
        msg_has_attachment = has_attachment(msg)
        msg_attachments = get_attachment_names(msg)
        labels_raw = msg.get('X-Gmail-Labels', '')
        gmail_labels = [l.strip() for l in labels_raw.split(',') if l.strip()]


        records.append({
            'message_id': msg_id,
            'subject': msg_subject,
            'sender_name': sender_name,
            'sender_email': sender_email,
            'received_at': msg_received_at,
            'body': msg_body,
            'has_attachment': msg_has_attachment,
            'attachments': msg_attachments,
            'gmail_labels': gmail_labels,
        })
    return records

SKIP_LABELS = {"Spam", "Promotions"}

def chunk_records(records: list[dict]) -> list[dict]:
    chunks = []
    for record in records:
        if SKIP_LABELS.intersection(record.get("gmail_labels", [])):
            continue
        display_sender = record["sender_name"] or record["sender_email"]
        full_text = (
            f"Subject: {record['subject']}\n"
            f"From: {display_sender}\n\n"
            f"{record['body']}"
        )
        texts = splitter.split_text(full_text)
        for text in texts:
            chunks.append({
                "message_id":     record["message_id"],
                "content":        text,
                "sender_name":    record["sender_name"],
                "sender_email":   record["sender_email"],
                "received_at":    record["received_at"],
                "has_attachment": record["has_attachment"],
                "attachments":    record["attachments"],
                "gmail_labels":   record["gmail_labels"],
            })
    return chunks
