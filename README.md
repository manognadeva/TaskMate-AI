# TaskMate AI Scheduler 🧠🗓️

An **AI-powered taskbot** that turns messy brain-dumps into **clean, time-blocked schedules** with **LLMs + Personalization (AWS S3) + Smart Rules**.

---

## Brief Idea 💡

TaskMate lets you type natural language like:

- “morning: email recruiter, review PR#482, study dbt for 45m, gym if energy is high”  
- “finish project tonight, call mom, cook dinner”  
- “personal schedule only — keep work after 6 pm out”

What the system does is:
- Parses your input 
- Infers priority, duration, energy, and due dates
- Schedules tasks into a timeline with automatic **breaks, start & end times, and interactive Done/Skip controls**.  

It adapts to **your energy patterns**, your preferences to do stuff and **work vs personal windows**, stored in **AWS S3**.

---

## Key Features 🚀

- **Natural-Language Parsing** → structured tasks (priority, time, energy, due date).  
- **Smart Scheduling with LLMs** → respects work vs personal hours, adds 5–10 min breaks, avoids overlaps.  
- **Personalization** → user preferences & energy patterns saved in **AWS S3**.  
- **Interactive UI (Streamlit)** → **Done / Skip** buttons (side-by-side, round), instant feedback.  
- **Time-blocked Output** → every task shows **start & end time**.  
- **Login-like Flow** → new users create a profile; returning users review/keep/update preferences.  
- **Work vs Personal Mode** → plan **within work hours** or **outside** them based on your choice.  

---

## How It Works ⚙️

1. **Profile Setup** (`setup_profile.py`)  
   Collect preferences (work hours, personal hours, energy patterns) and store in **S3**.  

2. **Task Parsing** (`task_parser.py`)  
   Convert messy text into JSON tasks with priority/estimates/energy/due dates.  

3. **LLM Scheduling** (`schedule_tasks_with_llm.py` + `smart_scheduler.py`)  
   Build an ordered, **time-boxed** schedule with breaks and constraints.  

4. **Frontend** (`app.py`)  
   Streamlit UI for login/setup, input, schedule view, and **Done/Skip** actions.  

5. **Profile Updates** (`update_profile.py`)  
   Adjust preferences as your routine changes (saved back to **S3**).  

6. **S3 Utilities** (`aws_s3.py`)  
   Read/write user profiles and snapshots (persistence = **S3 only**).  

---

## Tech Stack 🧰

- **Python**, **Streamlit** (frontend)  
- **LLMs** (OpenAI-compatible) for parsing & scheduling  
- **AWS S3** for user profiles & snapshots (no DB)  

---

## Project Structure 📁
├── app.py                 # Streamlit UI entry

├── main.py                # Orchestration / bootstrap

├── setup_profile.py # New user onboarding & preference capture

├── update_profile.py # Modify existing preferences

├── task_parser.py # NL → structured task JSON

├── parsed_tasks.json # Sample parsed output

├── schedule_tasks_with_llm.py # LLM-assisted scheduling

├── smart_scheduler.py # Deterministic rules (breaks, windows, ordering)

├── aws_s3.py # S3 read/write helpers
