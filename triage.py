"""LLM triage prediction stage: one batched Gemini call for all tickets."""

import json
import logging
from pathlib import Path

from llm_client import generate_json

NORMALIZED_PATH = Path("normalized_tickets.json")
CONFIG_PATH = Path("triage_config.json")
PREDICTIONS_PATH = Path("triage_predictions.json")
ESCALATIONS_PATH = Path("escalations.json")
LOG_PATH = Path("pipeline.log")

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(message)s")


def build_response_schema(config: dict) -> dict:
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "ticket_id": {"type": "STRING"},
                "category": {"type": "STRING", "enum": config["allowed_categories"]},
                "priority": {"type": "STRING", "enum": config["allowed_priorities"]},
                "reason": {"type": "STRING"},
                "suggested_reply": {"type": "STRING"},
                "confidence": {"type": "NUMBER"},
            },
            "required": ["ticket_id", "category", "priority", "reason", "suggested_reply", "confidence"],
        },
    }


def build_prompt(normalized_tickets: list, config: dict) -> str:
    return f"""You are a support-ticket triage assistant for a financial services company.

Classify each ticket below using ONLY the allowed values from this config:
{json.dumps(config, indent=2)}

For each ticket, return an object with:
- ticket_id: copied exactly from the input
- category: one of allowed_categories
- priority: one of allowed_priorities, based on urgency implied by the message
- reason: a short one-sentence justification
- suggested_reply: a reply to the customer in the configured tone, at most {config['reply_style']['max_words']} words
- confidence: your confidence in this classification, from 0.0 to 1.0

Do not invent categories, priorities, or routing destinations outside the config.

Tickets:
{json.dumps(normalized_tickets, indent=2)}

Return a JSON array with exactly one object per ticket, in any order.
"""


def _fallback_record(ticket_id: str, config: dict, reason: str) -> dict:
    logging.warning("Fallback triage for %s: %s", ticket_id, reason)
    categories = config["allowed_categories"]
    priorities = config["allowed_priorities"]
    category = "other" if "other" in categories else categories[-1]
    priority = priorities[-1]
    reply = _enforce_word_limit(
        "Thanks for reaching out. Your request has been routed to our team for manual review, and we'll follow up shortly.",
        config["reply_style"]["max_words"],
    )
    return {
        "ticket_id": ticket_id,
        "category": category,
        "priority": priority,
        "reason": f"Fallback classification: {reason}",
        "suggested_reply": reply,
        "route_to": config["routing_rules"].get(category, next(iter(config["routing_rules"].values()))),
        "confidence": 0.0,
    }


def _enforce_word_limit(reply: str, max_words: int) -> str:
    words = reply.split()
    if len(words) <= max_words:
        return reply
    logging.warning("Truncating reply from %d to %d words", len(words), max_words)
    return " ".join(words[:max_words]) + "..."


def validate_and_repair(raw_predictions, normalized_tickets: list, config: dict) -> list:
    expected_ids = [t["ticket_id"] for t in normalized_tickets]
    by_id = {}
    if isinstance(raw_predictions, list):
        for entry in raw_predictions:
            if isinstance(entry, dict) and "ticket_id" in entry:
                by_id[entry["ticket_id"]] = entry

    allowed_categories = set(config["allowed_categories"])
    allowed_priorities = set(config["allowed_priorities"])
    max_words = config["reply_style"]["max_words"]

    results = []
    for ticket_id in expected_ids:
        entry = by_id.get(ticket_id)
        if entry is None:
            results.append(_fallback_record(ticket_id, config, "missing from model response"))
            continue

        category = entry.get("category")
        priority = entry.get("priority")
        if category not in allowed_categories or priority not in allowed_priorities:
            results.append(_fallback_record(ticket_id, config, "invalid category/priority in model response"))
            continue

        reply = _enforce_word_limit(str(entry.get("suggested_reply", "")).strip(), max_words)
        try:
            confidence = float(entry.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        results.append({
            "ticket_id": ticket_id,
            "category": category,
            "priority": priority,
            "reason": str(entry.get("reason", "")).strip(),
            "suggested_reply": reply,
            "route_to": config["routing_rules"][category],  # always derived from config, never trusted from model
            "confidence": confidence,
        })

    return results


def compute_escalations(predictions: list) -> list:
    escalations = []
    for p in predictions:
        if p["category"] == "other" or p["confidence"] < 0.60:
            escalations.append({
                "ticket_id": p["ticket_id"],
                "category": p["category"],
                "confidence": p["confidence"],
                "reason": "category is 'other'" if p["category"] == "other" else "confidence below 0.60",
            })
    return escalations


def main() -> list:
    normalized_tickets = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    prompt = build_prompt(normalized_tickets, config)
    schema = build_response_schema(config)

    raw_predictions = generate_json(
        stage="TRIAGE_PREDICTED",
        prompt=prompt,
        response_schema=schema,
        input_artifacts=[str(NORMALIZED_PATH), str(CONFIG_PATH)],
        output_artifact=str(PREDICTIONS_PATH),
    )

    predictions = validate_and_repair(raw_predictions, normalized_tickets, config)
    PREDICTIONS_PATH.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    print(f"[triage] wrote {len(predictions)} predictions -> {PREDICTIONS_PATH}")

    escalations = compute_escalations(predictions)
    ESCALATIONS_PATH.write_text(json.dumps(escalations, indent=2), encoding="utf-8")
    print(f"[triage] flagged {len(escalations)} escalations -> {ESCALATIONS_PATH}")

    return predictions


if __name__ == "__main__":
    main()
