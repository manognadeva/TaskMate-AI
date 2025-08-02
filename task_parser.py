import os
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
from groq import Groq

DEFAULT_PARSER_MODEL = os.getenv("GROQ_MODEL_PARSER", "llama-3.3-70b-versatile")
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

def _safe_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'(\[.*\]|\{.*\})', text, flags=re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Failed to parse JSON from LLM output.")

def _chat_complete(client: Groq, model: str, messages: list, **kwargs):
    try:
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    except Exception as e:
        for fb in FALLBACK_MODELS:
            if fb == model:
                continue
            try:
                return client.chat.completions.create(model=fb, messages=messages, **kwargs)
            except Exception:
                continue
        raise e

def parse_tasks(user_input: str) -> List[Dict[str, Any]]:
    """
    Uses Groq LLM to parse natural language task input into structured tasks.
    RETURN SCHEMA for each task:
      - description: string (keep original constraint words if present)
      - priority: "low" | "medium" | "high"
      - energy: "low" | "medium" | "high"
      - duration: integer minutes
      - deadline: "HH:MM" 24-hour time string if a phrase like 'before/by <time>' is present, else null
    """
    client = _get_groq_client()

    system = (
        "You convert messy task lists into a STRICT JSON array. "
        "You MUST preserve any temporal constraints such as 'before 9 pm' or 'by 8:30 pm'. "
        "For each task include keys: description, priority (low|medium|high), energy (low|medium|high), "
        "duration (integer minutes), and deadline. "
        "deadline MUST be null or a 24-hour time string 'HH:MM' that the task must FINISH BY. "
        "Output ONLY valid JSON. No extra words."
    )

    user = (
        "Tasks:\n"
        f"{user_input}\n\n"
        "Return ONLY a JSON array like:\n"
        '[{"description":"Dinner before 9 pm","priority":"medium","energy":"low","duration":30,"deadline":"21:00"},'
        ' {"description":"Finish project","priority":"high","energy":"high","duration":120,"deadline":null}]'
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]

    resp = _chat_complete(
        client,
        model=DEFAULT_PARSER_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=800,
    )
    content = resp.choices[0].message.content
    data = _safe_json(content)

    # Normalize + basic validation/defaults
    normalized: List[Dict[str, Any]] = []
    for item in data:
        desc = str(item.get("description", "")).strip()
        if not desc:
            continue

        priority = str(item.get("priority", "medium")).lower()
        if priority not in {"low", "medium", "high"}:
            priority = "medium"

        energy = str(item.get("energy", "medium")).lower()
        if energy not in {"low", "medium", "high"}:
            energy = "medium"

        # duration
        val = item.get("duration", 30)
        try:
            duration = int(val)
        except Exception:
            # allow labels
            s = str(val).strip().lower()
            duration = 15 if s == "short" else 30 if s == "medium" else 60 if s == "long" else 30
        duration = max(5, min(duration, 240))

        # deadline as "HH:MM" 24h or None
        deadline = item.get("deadline", None)
        if isinstance(deadline, str):
            deadline = deadline.strip()
            if deadline == "":
                deadline = None
        if deadline is not None:
            # basic format guard HH:MM
            if not re.match(r"^\d{2}:\d{2}$", deadline):
                deadline = None

        normalized.append({
            "description": desc,
            "priority": priority,
            "energy": energy,
            "duration": duration,
            "deadline": deadline,
        })
    return normalized
