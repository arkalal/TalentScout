"""Central configuration: paths, model settings and the LLM factory."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# quieter local model loading
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

RESUME_DIR = Path(os.getenv("TALENTSCOUT_RESUME_DIR", ROOT / "data" / "resumes"))
JD_DIR = ROOT / "data" / "jds"
VECTOR_DIR = ROOT / "vector_store"
REPORT_DIR = ROOT / "reports"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = os.getenv("TALENTSCOUT_MODEL", "openai/gpt-4.1-mini")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Multi-round screening sizes
ROUND1_SHORTLIST = 10  # 100 -> 10
# Score weights (Round 1) and blend with Round 2 deep fit
ROUND1_WEIGHTS = {"must_have": 0.45, "nice_to_have": 0.15, "experience": 0.20, "semantic": 0.20}
FINAL_BLEND = {"round1": 0.4, "deep_fit": 0.6}
# Round 3 decision thresholds on the final score (LLM may move a candidate one band with justification)
HIRE_THRESHOLD = 75
BORDERLINE_THRESHOLD = 60


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.0):
    """ChatOpenAI pointed at OpenRouter (same pattern as the course notebooks)."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key.")
    return ChatOpenAI(
        model=MODEL_NAME,
        temperature=temperature,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=90,
        max_retries=2,
        default_headers={"X-Title": "TalentScout Matching Agent"},
    )
