"""Validation script. Run standalone (`python validate.py`) or reused by pipeline.py."""

import json
import sys
from pathlib import Path

import normalize

REQUIRED_ARTIFACTS = [
    "tickets.json",
    "triage_config.json",
    "normalized_tickets.json",
    "triage_predictions.json",
    "review_overrides.json",
    "final_queue.json",
    "queue_summary.md",
]


def _load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_required_artifacts(report: list) -> bool:
    ok = True
    for name in REQUIRED_ARTIFACTS:
        if not Path(name).exists():
            report.append(f"FAIL: required artifact missing: {name}")
            ok = False
    if ok:
        report.append("PASS: all required artifacts present")
    return ok


def check_json_valid(report: list) -> bool:
    ok = True
    for name in REQUIRED_ARTIFACTS:
        if not name.endswith(".json") or not Path(name).exists():
            continue
        try:
            _load_json(name)
        except json.JSONDecodeError as e:
            report.append(f"FAIL: {name} is not valid JSON: {e}")
            ok = False
    if ok:
        report.append("PASS: all JSON artifacts parse correctly")
    return ok


def check_normalization_deterministic_and_from_disk(report: list) -> bool:
    tickets = _load_json("tickets.json")
    normalized = _load_json("normalized_tickets.json")
    expected = [normalize.normalize_ticket(t) for t in tickets]
    if normalized != expected:
        report.append("FAIL: normalized_tickets.json does not match deterministic normalization of tickets.json")
        return False
    report.append("PASS: normalized_tickets.json is a deterministic, reproducible function of tickets.json")
    return True


def check_normalization_before_llm(report: list) -> bool:
    normalized_path = Path("normalized_tickets.json")
    calls_path = Path("llm_calls.jsonl")
    if not calls_path.exists():
        report.append("PASS: no llm_calls.jsonl found (nothing to compare); normalization exists independently")
        return True
    lines = [l for l in calls_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        report.append("PASS: llm_calls.jsonl is empty")
        return True
    first_call = json.loads(lines[0])
    if str(normalized_path) not in first_call.get("input_artifacts", []):
        report.append("FAIL: first LLM call does not list normalized_tickets.json as an input artifact")
        return False
    report.append("PASS: normalization artifact precedes and feeds the first LLM call")
    return True


def check_one_prediction_per_ticket(report: list) -> bool:
    tickets = _load_json("tickets.json")
    predictions = _load_json("triage_predictions.json")
    ticket_ids = [t["ticket_id"] for t in tickets]
    prediction_ids = [p["ticket_id"] for p in predictions]
    ok = True
    if len(prediction_ids) != len(set(prediction_ids)):
        report.append("FAIL: triage_predictions.json contains duplicate ticket_id entries")
        ok = False
    if set(ticket_ids) != set(prediction_ids):
        report.append("FAIL: prediction ticket_ids do not match input ticket_ids exactly")
        ok = False
    if ok:
        report.append(f"PASS: exactly one prediction per ticket ({len(ticket_ids)} tickets)")
    return ok


def check_labels_and_routing(report: list) -> bool:
    config = _load_json("triage_config.json")
    predictions = _load_json("triage_predictions.json")
    allowed_categories = set(config["allowed_categories"])
    allowed_priorities = set(config["allowed_priorities"])
    routing_rules = config["routing_rules"]

    ok = True
    for p in predictions:
        if p["category"] not in allowed_categories:
            report.append(f"FAIL: {p['ticket_id']} has category {p['category']!r} not in allowed_categories")
            ok = False
        if p["priority"] not in allowed_priorities:
            report.append(f"FAIL: {p['ticket_id']} has priority {p['priority']!r} not in allowed_priorities")
            ok = False
        expected_route = routing_rules.get(p["category"])
        if p.get("route_to") != expected_route:
            report.append(
                f"FAIL: {p['ticket_id']} route_to {p.get('route_to')!r} != config mapping {expected_route!r}"
            )
            ok = False
    if ok:
        report.append("PASS: all predicted categories/priorities/routes are config-compliant")
    return ok


def check_overrides_applied(report: list) -> bool:
    overrides = _load_json("review_overrides.json")
    final_queue = _load_json("final_queue.json")
    config = _load_json("triage_config.json")
    final_by_id = {t["ticket_id"]: t for t in final_queue}

    ok = True
    for o in overrides:
        final = final_by_id.get(o["ticket_id"])
        if final is None:
            report.append(f"FAIL: overridden ticket {o['ticket_id']} missing from final_queue.json")
            ok = False
            continue
        if final["final_category"] != o["new_category"] or final["final_priority"] != o["new_priority"]:
            report.append(f"FAIL: override for {o['ticket_id']} not reflected in final_queue.json")
            ok = False
        if not final.get("was_overridden"):
            report.append(f"FAIL: {o['ticket_id']} was overridden but was_overridden is not true")
            ok = False
        expected_route = config["routing_rules"].get(final["final_category"])
        if final["final_route_to"] != expected_route:
            report.append(f"FAIL: {o['ticket_id']} final_route_to does not match config for its final_category")
            ok = False
    if ok:
        report.append(f"PASS: {len(overrides)} override(s) correctly applied in final_queue.json")
    return ok


def check_reply_word_limit(report: list) -> bool:
    config = _load_json("triage_config.json")
    max_words = config["reply_style"]["max_words"]
    final_queue = _load_json("final_queue.json")

    ok = True
    for t in final_queue:
        word_count = len(t["suggested_reply"].split())
        if word_count > max_words:
            report.append(f"FAIL: {t['ticket_id']} reply has {word_count} words, exceeds max_words={max_words}")
            ok = False
    if ok:
        report.append(f"PASS: all replies respect max_words={max_words}")
    return ok


def run_validation():
    report = []
    checks = [
        check_required_artifacts,
        check_json_valid,
        check_normalization_deterministic_and_from_disk,
        check_normalization_before_llm,
        check_one_prediction_per_ticket,
        check_labels_and_routing,
        check_overrides_applied,
        check_reply_word_limit,
    ]
    ok = True
    for check in checks:
        try:
            ok = check(report) and ok
        except Exception as e:
            report.append(f"FAIL: {check.__name__} raised an exception: {e}")
            ok = False
    return ok, report


def main() -> bool:
    ok, report = run_validation()
    print("\n".join(report))
    print("\nVALIDATION " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
