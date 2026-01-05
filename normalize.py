"""Deterministic ticket normalization. No LLM calls happen in this module."""

import json
from pathlib import Path

TICKETS_PATH = Path("tickets.json")
OUTPUT_PATH = Path("normalized_tickets.json")


def build_text_for_model(subject: str, message: str) -> str:
    return f"Subject: {subject.strip()}\nMessage: {message.strip()}"


def normalize_ticket(ticket: dict) -> dict:
    subject = ticket["subject"]
    message = ticket["message"]
    text_for_model = build_text_for_model(subject, message)
    return {
        "ticket_id": ticket["ticket_id"],
        "subject": subject,
        "message": message,
        "channel": ticket["channel"],
        "created_at": ticket["created_at"],
        "text_for_model": text_for_model,
        "char_count": len(text_for_model),
    }


def main() -> list:
    tickets = json.loads(TICKETS_PATH.read_text(encoding="utf-8"))
    normalized = [normalize_ticket(t) for t in tickets]
    OUTPUT_PATH.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    print(f"[normalize] wrote {len(normalized)} tickets -> {OUTPUT_PATH}")
    return normalized


if __name__ == "__main__":
    main()
