from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def build_context(results: list[tuple], max_content_chars: int = 300) -> str:
    """Format DB results into readable context for the LLM.
    Deduplicates chunks from the same email and truncates content previews.
    """
    seen = set()
    blocks = []
    for i, row in enumerate(results):
        content, sender_name, sender_email, received_at, has_attachment, gmail_labels, distance = row
        date_str = received_at.strftime('%Y-%m-%d') if received_at else 'unknown'

        dedup_key = (sender_email, date_str)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        labels = gmail_labels or []
        in_inbox = "Inbox" in labels
        preview = content[:max_content_chars].strip()
        if len(content) > max_content_chars:
            preview += "..."

        blocks.append(
            f"[Email {len(blocks)+1}]\n"
            f"From: {sender_name or sender_email} <{sender_email}>\n"
            f"Date: {date_str}\n"
            f"In inbox: {'Yes' if in_inbox else 'No'}\n"
            f"Has attachment: {'Yes' if has_attachment else 'No'}\n"
            f"Preview:\n{preview}"
        )
    return "\n\n---\n\n".join(blocks)

def ask(question: str, results: list[tuple]) -> str:
    context = build_context(results)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a personal email assistant. Answer the user's question "
                    "using only the email excerpts provided below. If the answer is not "
                    "in the emails, say so honestly.\n"
                    "When asked to 'show' or 'list' emails, present them as a concise numbered list "
                    "with sender, date, and a brief summary — do not reproduce the full content.\n\n"
                    f"Email context:\n{context}"
                )
            },
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content