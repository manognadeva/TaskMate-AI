from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import re

# Keep LLM reordering optional. If you don’t want it, remove these imports and the try/except that calls them.
from schedule_tasks_with_llm import build_prompt, call_llm_for_schedule, parse_llm_output

# --- Configuration ---
GRID_MINUTES = (0, 15, 30, 45)   # quarter-hour grid
FORCED_BREAK_MIN = 5             # fixed break after every task
PERSONAL_WINDOW_HOURS = 6        # cap for personal schedules

# --- Regex fallback (if parser didn't set 'deadline') ---
_DEADLINE_RE = re.compile(
    r'\b(?:before|by)\s*'
    r'(?P<hour>\d{1,2})'
    r'(?:\s*:\s*(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)\b',
    flags=re.IGNORECASE
)

# ---------- utilities ----------
def _fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")

def _time_to_dt(base_day: datetime, hhmm: str) -> datetime:
    return datetime.combine(base_day.date(), datetime.strptime(hhmm, "%H:%M").time())

def _round_up_to_grid(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    m = dt.minute
    for k in GRID_MINUTES:
        if m <= k:
            return dt.replace(minute=k)
    return (dt + timedelta(hours=1)).replace(minute=GRID_MINUTES[0])

def _round_down_to_grid(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    m = dt.minute
    downs = [k for k in GRID_MINUTES if k <= m]
    if downs:
        return dt.replace(minute=max(downs))
    return (dt - timedelta(hours=1)).replace(minute=max(GRID_MINUTES))

def _duration_minutes(task: Dict[str, Any]) -> int:
    """Accept int minutes or labels short/medium/long; clamp to 5..240."""
    val = task.get("duration", 30)
    if isinstance(val, int):
        minutes = val
    else:
        s = str(val).strip().lower()
        if s == "short":
            minutes = 15
        elif s == "medium":
            minutes = 30
        elif s == "long":
            minutes = 60
        else:
            try:
                minutes = int(s)
            except Exception:
                minutes = 30
    return max(5, min(minutes, 240))

def _parse_deadline_from_text(text: str, now: datetime) -> Optional[datetime]:
    m = _DEADLINE_RE.search(text or "")
    if not m:
        return None
    hour = int(m.group("hour"))
    minute = int(m.group("minute") or 0)
    ampm = m.group("ampm").lower()
    if hour == 12:
        hour = 0
    if ampm == "pm":
        hour += 12
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

# ---------- packing helpers ----------
def _fits(start: datetime, end: datetime, occupied: List[Tuple[datetime, datetime]],
          day_start: datetime, day_end: datetime) -> bool:
    if start < day_start or end > day_end or start >= end:
        return False
    for s, e in occupied:
        if not (end <= s or start >= e):
            return False
    return True

def _add_with_break(occupied: List[Tuple[datetime, datetime]], start: datetime, end: datetime) -> None:
    occupied.append((start, end))
    br_s, br_e = end, end + timedelta(minutes=FORCED_BREAK_MIN)
    occupied.append((br_s, br_e))

def _merge(occupied: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not occupied:
        return []
    occ = sorted(occupied, key=lambda x: x[0])
    out = [occ[0]]
    for s, e in occ[1:]:
        ls, le = out[-1]
        if s <= le:
            out[-1] = (ls, max(le, e))
        else:
            out.append((s, e))
    return out

def _find_backward_slot(deadline: datetime, duration_min: int,
                        occupied: List[Tuple[datetime, datetime]],
                        day_start: datetime) -> Optional[Tuple[datetime, datetime]]:
    """Find a slot that ENDS by deadline, scanning backward on the grid."""
    dur = timedelta(minutes=duration_min)
    end_candidate = _round_down_to_grid(deadline)
    for _ in range(12 * 4 + 1):
        start_candidate = end_candidate - dur
        start_candidate = _round_up_to_grid(start_candidate)
        end_candidate = start_candidate + dur
        if _fits(start_candidate, end_candidate, occupied, day_start, deadline):
            return (start_candidate, end_candidate)
        end_candidate = end_candidate - timedelta(minutes=15)
        if end_candidate <= day_start:
            break
    return None

def _find_forward_slot(cursor: datetime, duration_min: int,
                       occupied: List[Tuple[datetime, datetime]],
                       day_start: datetime, day_end: datetime) -> Optional[Tuple[datetime, datetime]]:
    dur = timedelta(minutes=duration_min)
    start_candidate = _round_up_to_grid(max(cursor, day_start))
    for _ in range(12 * 4 + 1):
        end_candidate = start_candidate + dur
        if _fits(start_candidate, end_candidate, occupied, day_start, day_end):
            return (start_candidate, end_candidate)
        start_candidate += timedelta(minutes=15)
        if start_candidate + dur > day_end:
            break
    return None

# ---------- core ----------
def schedule_tasks(parsed_tasks: List[Dict[str, Any]],
                   profile: Dict[str, Any],
                   schedule_type: str = "personal") -> List[Dict[str, Any]]:
    """
    - Start 'now' (snapped to next :00/:15/:30/:45).
    - 5-minute break after every task.
    - Tasks with 'deadline' (HH:MM) must FINISH by that time (scheduled backward first).
    - If parser didn't provide 'deadline', we also detect 'before/by <time>' in description.
    - Remaining tasks fill forward from 'now'.
    - Windows:
        * work-related: end at today's profile['work_hours']['end']
        * personal: end at (now + PERSONAL_WINDOW_HOURS)
    """
    if not parsed_tasks:
        return []

    now = datetime.now()
    start_from = _round_up_to_grid(now)

    # End window
    if schedule_type == "work-related":
        work_end = profile.get("work_hours", {}).get("end", "17:00")
        day_end = _time_to_dt(now, work_end)
        if day_end <= start_from:
            return []
    else:
        day_end = start_from + timedelta(hours=PERSONAL_WINDOW_HOURS)

    # Optional LLM refinement of order
    try:
        prompt = build_prompt(parsed_tasks, profile, schedule_type)
        refined_raw = call_llm_for_schedule(prompt)
        tasks = parse_llm_output(refined_raw, parsed_tasks)
    except Exception:
        tasks = parsed_tasks

    # Split tasks by presence of deadline
    deadline_tasks: List[Tuple[datetime, Dict[str, Any]]] = []
    normal_tasks: List[Dict[str, Any]] = []

    for t in tasks:
        desc = str(t.get("description", "")).strip()
        if not desc:
            continue

        # Prefer explicit 'deadline' field
        deadline_str = t.get("deadline")
        dl_dt: Optional[datetime] = None
        if isinstance(deadline_str, str) and re.match(r"^\d{2}:\d{2}$", deadline_str):
            dl_dt = _time_to_dt(now, deadline_str)

        # Fallback: parse from description
        if dl_dt is None:
            dl_dt = _parse_deadline_from_text(desc, now)

        if dl_dt is not None:
            # Cap at day_end
            dl_dt = min(dl_dt, day_end)
            deadline_tasks.append((dl_dt, t))
        else:
            normal_tasks.append(t)

    # Order deadline tasks by earliest finish time
    deadline_tasks.sort(key=lambda x: x[0])

    occupied: List[Tuple[datetime, datetime]] = []
    placed: List[Dict[str, Any]] = []

    # Place deadline tasks BACKWARD
    for dl, t in deadline_tasks:
        dur_min = _duration_minutes(t)
        slot = _find_backward_slot(dl, dur_min, _merge(occupied), start_from)
        if not slot:
            # If we cannot meet the deadline given remaining time, skip it
            # (Option: log or collect for warnings in UI)
            continue
        s_dt, e_dt = slot
        _add_with_break(occupied, s_dt, e_dt)
        placed.append({
            "description": str(t.get("description", "")).strip(),
            "start_time": _fmt(s_dt),
            "end_time": _fmt(e_dt),
        })

    # Place non-deadline tasks FORWARD from 'start_from'
    cursor = start_from
    occupied = _merge(occupied)
    for s, e in occupied:
        if s <= cursor < e:
            cursor = e

    for t in normal_tasks:
        dur_min = _duration_minutes(t)
        slot = _find_forward_slot(cursor, dur_min, occupied, start_from, day_end)
        if not slot:
            break
        s_dt, e_dt = slot
        _add_with_break(occupied, s_dt, e_dt)
        occupied = _merge(occupied)
        placed.append({
            "description": str(t.get("description", "")).strip(),
            "start_time": _fmt(s_dt),
            "end_time": _fmt(e_dt),
        })
        cursor = e_dt + timedelta(minutes=FORCED_BREAK_MIN)
        if cursor >= day_end:
            break

    # Chronological display
    placed.sort(key=lambda x: datetime.strptime(x["start_time"], "%I:%M %p"))
    return placed
