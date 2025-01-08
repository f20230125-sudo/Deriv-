# Support-Triage Pipeline

A replayable pipeline that reads customer support tickets, classifies them with Gemini against a controlled label set, runs a human review checkpoint, and produces a final agent queue.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY
```

## Run

Full pipeline, end to end (interactive review checkpoint included):

```bash
python pipeline.py
```

Stages enforced in order:

```
INIT -> INPUTS_LOADED -> TICKETS_NORMALIZED -> TRIAGE_PREDICTED
     -> HUMAN_REVIEW_COMPLETE -> FINAL_QUEUE_GENERATED
     -> VALIDATION_COMPLETE -> RESULTS_FINALISED
```

Individual stages can also be run directly against their on-disk inputs (useful for replaying a single stage, e.g. after editing `normalized_tickets.json`):

```bash
python normalize.py
python triage.py
python review.py
python finalize.py
```

## Validate

```bash
python validate.py
```

Checks required artifacts exist and are valid JSON, that normalization precedes any LLM call, that every ticket has exactly one prediction, that categories/priorities/routes are config-compliant, that review overrides are reflected in the final queue, and that replies respect `reply_style.max_words`.

## Artifacts produced

`normalized_tickets.json`, `triage_predictions.json`, `escalations.json`, `llm_calls.jsonl`, `review_overrides.json`, `final_queue.json`, `queue_summary.md`, `pipeline.log`.

## Configuration

`tickets.json` and `triage_config.json` may be replaced with equivalent fixtures; nothing in the pipeline depends on their exact contents beyond the documented schema.
