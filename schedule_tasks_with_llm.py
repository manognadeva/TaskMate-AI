import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from groq import Groq

DEFAULT_SCHEDULER_MODEL = os.getenv("GROQ_MODEL_SCHEDULER", "llama-3.3-70b-versatile")
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

def _get_groq_client() -> Groq:
    load_dotenv()
    key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not key or not key.startswith("gsk_"):
        raise RuntimeError(
            "Missing or invalid Groq API key. "
            "Set GROQ_API_KEY (preferred) or OPENAI_API_KEY with a gsk_… token."
        )
    return Groq(api_key=key)

def _chat_complete(client: Groq, model: str, messages: list, **kwargs):
    """
    Try the requested model; if it is decommissioned or invalid,
    fall back to a known-good model automatically.
    """
    try:
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    except Exception as e:
        # try fallbacks
        for fb in FALLBACK_MODELS:
            if fb == model:
                continue
            try:
                return client.chat.completions.create(model=fb, messages=messages, **kwargs)
            except Exception:
                continue
        raise e

def build_prompt(parsed_tasks: List[Dict[str, Any]],
                 profile: Dict[str, Any],
                 schedule_type: str) -> str:
    """
    Build a compact JSON prompt for the LLM to refine ordering.
    """
    payload = {
        "schedule_type": schedule_type,
        "profile": {
            "work_hours": profile.get("work_hours", {}),
            "break_duration_min": profile.get("break_duration_min", 10),
            "energy_levels": profile.get("energy_levels", {}),
        },
        "tasks": parsed_tasks
    }
    instructions = (
        "Reorder tasks to maximize productivity, respecting durations where reasonable. "
        "Prefer high-energy tasks during the user's higher energy periods. "
        "Return ONLY a JSON array of tasks with the SAME schema "
        "(description, priority, energy, duration)."
    )
    return instructions + "\n\n" + json.dumps(payload, ensure_ascii=False)

def call_llm_for_schedule(prompt: str) -> List[Dict[str, Any]]:
    """
    Sends the scheduling prompt to Groq and returns a refined list of tasks.
    """
    client = _get_groq_client()
    messages = [
        {"role": "system", "content": "You are an expert day planner."},
        {"role": "user", "content": prompt},
    ]
    resp = _chat_complete(
        client,
        model=DEFAULT_SCHEDULER_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=1200,
    )
    content = resp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []  # caller will skip refinement

def parse_llm_output(llm_tasks: List[Dict[str, Any]],
                     fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate the refined tasks; if invalid, return the fallback.
    """
    if not llm_tasks:
        return fallback
    out = []
    for item in llm_tasks:
        try:
            desc = str(item.get("description", "")).strip()
            if not desc:
                continue
            pr = str(item.get("priority", "medium")).lower()
            if pr not in {"low", "medium", "high"}:
                pr = "medium"
            en = str(item.get("energy", "medium")).lower()
            if en not in {"low", "medium", "high"}:
                en = "medium"
            dur = int(item.get("duration", 30))
            dur = max(5, min(dur, 240))
            out.append({"description": desc, "priority": pr, "energy": en, "duration": dur})
        except Exception:
            continue
    return out if out else fallback
