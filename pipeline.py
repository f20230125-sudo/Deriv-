"""Entry point. Drives every stage in strict order via the state machine."""

import sys
from pathlib import Path

import finalize
import normalize
import review
import triage
import validate
from state import PipelineState, StateMachine


def main() -> int:
    sm = StateMachine()

    if not Path("tickets.json").exists() or not Path("triage_config.json").exists():
        print("[pipeline] tickets.json and triage_config.json must exist in the working directory.")
        return 1
    sm.advance_to(PipelineState.INPUTS_LOADED)

    normalize.main()
    sm.advance_to(PipelineState.TICKETS_NORMALIZED)

    triage.main()
    sm.advance_to(PipelineState.TRIAGE_PREDICTED)

    review.main()
    sm.advance_to(PipelineState.HUMAN_REVIEW_COMPLETE)

    finalize.main()
    sm.advance_to(PipelineState.FINAL_QUEUE_GENERATED)

    ok, report = validate.run_validation()
    print("\n".join(report))
    sm.advance_to(PipelineState.VALIDATION_COMPLETE)
    if not ok:
        print("[pipeline] validation failed; see report above.")
        return 1

    sm.advance_to(PipelineState.RESULTS_FINALISED)
    print("\n" + Path("queue_summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
