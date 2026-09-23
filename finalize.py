"""Final agent queue generation. Runs only after prediction + human review."""

import json
from collections import Counter
from pathlib import Path

PREDICTIONS_PATH = Path("triage_predictions.json")
OVERRIDES_PATH = Path("review_overrides.json")
CONFIG_PATH = Path("triage_config.json")
FINAL_QUEUE_PATH = Path("final_queue.json")
SUMMARY_PATH = Path("queue_summary.md")


def build_final_queue(predictions: list, overrides: list, config: dict) -> list:
    overrides_by_id = {o["ticket_id"]: o for o in overrides}
    routing_rules = config["routing_rules"]

    final_queue = []
    for p in predictions:
        override = overrides_by_id.get(p["ticket_id"])
        final_category = override["new_category"] if override else p["category"]
        final_priority = override["new_priority"] if override else p["priority"]
        final_queue.append({
            "ticket_id": p["ticket_id"],
            "final_category": final_category,
            "final_priority": final_priority,
            "final_route_to": routing_rules[final_category],
            "suggested_reply": p["suggested_reply"],
            "was_overridden": override is not None,
        })
    return final_queue


def build_summary(final_queue: list, overrides: list) -> str:
    total = len(final_queue)
    by_category = Counter(t["final_category"] for t in final_queue)
    by_priority = Counter(t["final_priority"] for t in final_queue)
    by_destination = Counter(t["final_route_to"] for t in final_queue)

    lines = ["# Queue Summary", "", f"Total tickets: {total}", "", "## By Category"]
    for category, count in sorted(by_category.items()):
        lines.append(f"- {category}: {count}")

    lines += ["", "## By Priority"]
    for priority, count in sorted(by_priority.items()):
        lines.append(f"- {priority}: {count}")

    lines += ["", "## By Destination Queue"]
    for destination, count in sorted(by_destination.items()):
        lines.append(f"- {destination}: {count}")

    lines += ["", "## Overridden Tickets"]
    if overrides:
        for o in overrides:
            lines.append(
                f"- {o['ticket_id']}: category {o['old_category']} -> {o['new_category']}, "
                f"priority {o['old_priority']} -> {o['new_priority']}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> list:
    predictions = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8")) if OVERRIDES_PATH.exists() else []
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    final_queue = build_final_queue(predictions, overrides, config)
    FINAL_QUEUE_PATH.write_text(json.dumps(final_queue, indent=2), encoding="utf-8")
    print(f"[finalize] wrote {len(final_queue)} tickets -> {FINAL_QUEUE_PATH}")

    summary = build_summary(final_queue, overrides)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    print(f"[finalize] wrote summary -> {SUMMARY_PATH}")

    return final_queue


if __name__ == "__main__":
    main()
