TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "General semantic search across all emails. Use when no date, sender, or attachment filter is needed.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails_by_date",
            "description": "Search emails within a specific date range. Use when the question mentions a time period, month, year, or words like 'last week', 'recently', 'in March'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after":  {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                    "before": {"type": "string", "description": "End date in YYYY-MM-DD format (optional)"}
                },
                "required": ["after"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails_by_sender",
            "description": "Search emails from a specific person. Use when the question mentions a name or email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sender_email": {"type": "string", "description": "Email address of the sender"}
                },
                "required": ["sender_email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails_with_attachments",
            "description": "Search emails that have attachments. Use when the question mentions files, documents, PDFs, invoices, or attachments.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_senders",
            "description": "Return the people who email you most. Use for questions like 'who emails me most?' or 'who are my top contacts?'",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

    tool_call = response.choices[0].message.tool_calls[0]
    fn_name = tool_call.function.name
    params = json.loads(tool_call.function.arguments)