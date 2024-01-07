"""Explicit pipeline state machine.

Stages must advance strictly in order. Any attempt to skip a stage
(e.g. generating the final queue before human review is complete)
raises immediately instead of silently proceeding.
"""

from enum import Enum


class PipelineState(Enum):
    INIT = 0
    INPUTS_LOADED = 1
    TICKETS_NORMALIZED = 2
    TRIAGE_PREDICTED = 3
    HUMAN_REVIEW_COMPLETE = 4
    FINAL_QUEUE_GENERATED = 5
    VALIDATION_COMPLETE = 6
    RESULTS_FINALISED = 7


class StageOrderError(RuntimeError):
    pass


class StateMachine:
    def __init__(self):
        self.state = PipelineState.INIT

    def advance_to(self, target: PipelineState) -> None:
        expected = PipelineState(self.state.value + 1)
        if target != expected:
            raise StageOrderError(
                f"Cannot advance to {target.name} from {self.state.name}; "
                f"expected next stage is {expected.name}."
            )
        self.state = target
        print(f"[pipeline] -> {self.state.name}")
