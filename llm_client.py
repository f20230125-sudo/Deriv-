"""Thin Gemini wrapper: one schema-constrained call + append-only call logging.

Only this module talks to the network. Deterministic stages (normalize.py)
never import it, so normalization-before-LLM ordering is structural, not
just a convention.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

LOG_PATH = Path("llm_calls.jsonl")


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or export GEMINI_API_KEY in your shell before running the pipeline."
        )
    return genai.Client(api_key=api_key)


def _log_call(stage: str, model: str, prompt: str, input_artifacts: list, output_artifact: str) -> None:
    record = {
        "stage": stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "gemini",
        "model": model,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "input_artifacts": input_artifacts,
        "output_artifact": output_artifact,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def generate_json(
    *,
    stage: str,
    prompt: str,
    response_schema: dict,
    input_artifacts: list,
    output_artifact: str,
):
    """Make one schema-constrained Gemini call and return the parsed JSON payload."""
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    client = _client()

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )

    _log_call(stage, model, prompt, input_artifacts, output_artifact)

    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
