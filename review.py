"""Human review checkpoint. Interactive; overrides genuinely affect final output."""

import json
import sys
from pathlib import Path

PREDICTIONS_PATH = Path("triage_predictions.json")
ESCALATIONS_PATH = Path("escalations.json")
CONFIG_PATH = Path("triage_config.json")
OVERRIDES_PATH = Path("review_overrides.json")


def display_predictions(predictions: list, escalated_ids: set) -> None:
    print("\n--- Predicted Triage (review before final queue is generated) ---")
    for p in predictions:
        flag = "  [ESCALATED]" if p["ticket_id"] in escalated_ids else ""
        print(f"{p['ticket_id']}: category={p['category']}, priority={p['priority']}{flag}")
    print("-------------------------------------------------------------\n")


def parse_override_line(line: str, config: dict) -> dict | None:
    parts = [x.strip() for x in line.split(",")]
    if len(parts) != 3:
        print(f"  Ignored (expected 'ticket_id,category,priority'): {line!r}")
        return None
    ticket_id, category, priority = parts
    if category not in config["allowed_categories"]:
        print(f"  Ignored ({category!r} is not an allowed category): {line!r}")
        return None
    if priority not in config["allowed_priorities"]:
        print(f"  Ignored ({priority!r} is not an allowed priority): {line!r}")
        return None
    return {"ticket_id": ticket_id, "category": category, "priority": priority}


def collect_overrides(config: dict, input_stream=sys.stdin) -> list:
    print("Enter any overrides as: ticket_id,category,priority")
    print("Press Enter on an empty line when done.")
    overrides = []
    for line in input_stream:
        line = line.rstrip("\n")
        if line.strip() == "":
            break
        parsed = parse_override_line(line, config)
        if parsed is not None:
            overrides.append(parsed)
    return overrides


def apply_overrides(predictions: list, raw_overrides: list) -> list:
    by_id = {p["ticket_id"]: p for p in predictions}
    records = []
    for o in raw_overrides:
        ticket_id = o["ticket_id"]
        original = by_id.get(ticket_id)
        if original is None:
            print(f"  Ignored (unknown ticket_id): {ticket_id}")
            continue
        records.append({
            "ticket_id": ticket_id,
            "old_category": original["category"],
            "new_category": o["category"],
            "old_priority": original["priority"],
            "new_priority": o["priority"],
        })
    return records


def main(input_stream=sys.stdin) -> list:
    predictions = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    escalations = json.loads(ESCALATIONS_PATH.read_text(encoding="utf-8")) if ESCALATIONS_PATH.exists() else []
    escalated_ids = {e["ticket_id"] for e in escalations}

    display_predictions(predictions, escalated_ids)
    raw_overrides = collect_overrides(config, input_stream)
    overrides = apply_overrides(predictions, raw_overrides)

    OVERRIDES_PATH.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    print(f"[review] recorded {len(overrides)} override(s) -> {OVERRIDES_PATH}")
    return overrides


if __name__ == "__main__":
    main()
