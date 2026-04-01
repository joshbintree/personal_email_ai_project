import json
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, Literal
import os
from dotenv import load_dotenv
from utils.embed_text import embed_db_query
import gradio as gr
import instructor
from rag_prompts import ask
from utils.db_queries import (
    search_emails,
    search_emails_by_date,
    search_emails_by_sender,
    search_emails_with_attachments,
    get_top_senders,
    count_emails,
)

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = instructor.from_openai(openai_client)

class EmailQuery(BaseModel):
    intents: list[Literal[
        "search_emails",
        "search_emails_by_date",
        "search_emails_by_sender",
        "search_emails_with_attachments",
        "get_top_senders",
        "count_emails",
    ]]
    after:        Optional[str] = None   # YYYY-MM-DD
    before:       Optional[str] = None   # YYYY-MM-DD
    sender_email: Optional[str] = None
    year:         Optional[int] = None   # e.g. 2024


def route_query(question: str) -> dict:
    query: EmailQuery = client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=EmailQuery,
        messages=[
            {
                "role": "system",
                "content": (
                    "Today's date is 2026-03-29. You are a query router for a personal email assistant. "
                    "A question may have multiple intents — list all that apply. "
                    "Extract all relevant parameters (dates, sender, year, email, labels, attachments, etc.)."
                )
            },
            {"role": "user", "content": question}
        ]
    )

    query_embedding = embed_db_query(question)
    responses = []

    for intent in query.intents:
        match intent:
            case "search_emails_by_date":
                if query.after:
                    responses.append({
                        "type": "emails",
                        "results": search_emails_by_date(query_embedding, after=query.after, before=query.before)
                    })
            case "search_emails_by_sender":
                if query.sender_email:
                    responses.append({
                        "type": "emails",
                        "results": search_emails_by_sender(query_embedding, sender_email=query.sender_email)
                    })
            case "search_emails_with_attachments":
                responses.append({
                    "type": "emails",
                    "results": search_emails_with_attachments(
                        query_embedding,
                        after=query.after,
                        before=query.before,
                        year=query.year,
                    )
                })
            case "get_top_senders":
                responses.append({
                    "type": "top_senders",
                    "results": get_top_senders(year=query.year)
                })
            case "count_emails":
                responses.append({
                    "type": "count",
                    "results": count_emails(
                        after=query.after,
                        before=query.before,
                        year=query.year,
                        sender_email=query.sender_email,
                    ),
                    "filters": {
                        "after": query.after,
                        "before": query.before,
                        "year": query.year,
                        "sender_email": query.sender_email,
                    }
                })
            case _:
                responses.append({
                    "type": "emails",
                    "results": search_emails(question)
                })

    if not responses:
        return {"type": "emails", "results": search_emails(question)}

    return responses[0] if len(responses) == 1 else {"type": "multi", "responses": responses}


def format_response(routed: dict, question: str) -> str:
    if routed["type"] == "count":
        count = routed["results"]
        filters = routed.get("filters", {})
        parts = []
        if filters.get("sender_email"):
            parts.append(f"from **{filters['sender_email']}**")
        if filters.get("year"):
            parts.append(f"in **{filters['year']}**")
        elif filters.get("after") or filters.get("before"):
            if filters.get("after"):
                parts.append(f"after {filters['after']}")
            if filters.get("before"):
                parts.append(f"before {filters['before']}")
        qualifier = " " + " ".join(parts) if parts else ""
        return f"There are **{count:,}** emails{qualifier} in your archive."

    if routed["type"] == "top_senders":
        results = routed["results"]
        if not results:
            return "No sender data found."
        lines = [f"{i+1}. {name or email} ({email}) — {count} emails"
                 for i, (email, name, count) in enumerate(results)]
        return "Your top senders:\n" + "\n".join(lines)

    if routed["type"] == "emails":
        results = routed["results"]
        if not results:
            return "No relevant emails found."
        return ask(question, results)

    return "No results found."


def answer_question(question: str) -> str:
    routed = route_query(question)

    if routed["type"] == "multi":
        parts = [format_response(r, question) for r in routed["responses"]]
        return "\n\n---\n\n".join(parts)

    return format_response(routed, question)

def translate_response(answer: str, target_language: str) -> str:
    if not answer or not target_language:
        return ""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"Translate the following text to {target_language}. Preserve formatting like numbered lists and bold text."
            },
            {"role": "user", "content": answer}
        ]
    )
    return response.choices[0].message.content


def search_and_translate(question: str, target_language: str):
    answer = answer_question(question)
    if target_language:
        translation = translate_response(answer, target_language)
        return answer, gr.update(value=translation, visible=True)
    return answer, gr.update(value="", visible=False)


with gr.Blocks(title="Personal Email Assistant") as demo:
    gr.Markdown("# Personal Email Search Assistant")

    with gr.Row():
        with gr.Column():
            query_input = gr.Textbox(
                label="Search Query",
                placeholder="Enter your search query here...",
                lines=2
            )
            language_input = gr.Dropdown(
                label="Translate response to",
                choices=["", "Korean", "Spanish", "French", "Japanese", "Chinese", "German", "Portuguese"],
                value="",
                allow_custom_value=True,
            )
            search_button = gr.Button("Search", variant="primary")

        with gr.Column():
            results_output = gr.Markdown(label="Results")
            translation_output = gr.Markdown(label="Translation", visible=False)

    search_button.click(
        fn=search_and_translate,
        inputs=[query_input, language_input],
        outputs=[results_output, translation_output]
    )

    query_input.submit(
        fn=search_and_translate,
        inputs=[query_input, language_input],
        outputs=[results_output, translation_output]
    )
if __name__ == "__main__":
    demo.launch()