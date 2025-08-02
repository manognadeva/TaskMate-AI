import os
from dotenv import load_dotenv
import streamlit as st
from datetime import datetime

# Local modules
from aws_s3 import load_user_profile, upload_user_profile, upload_task_snapshot
from task_parser import parse_tasks
from smart_scheduler import schedule_tasks  # rule-based scheduler that uses LLM helpers

# ===== Load environment =====
load_dotenv()

# ===== CSS Styling (White Theme + Clean UI + Rounded Buttons) =====
st.markdown("""
<style>
html, body, .stApp {
    background-color: #ffffff;
    color: #111111;
    font-family: 'Segoe UI', sans-serif;
}
.stButton > button {
    background-color: #a855f7;
    color: white;
    font-weight: 600;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    margin: 0.2rem;
}
.stButton > button:hover {
    background-color: #9333ea;
}
h1, h2, h3 { color: #111111; }
</style>
""", unsafe_allow_html=True)

# ===== Session State Setup =====
if 'page' not in st.session_state:
    st.session_state.page = "login"
if 'profile' not in st.session_state:
    st.session_state.profile = None

# ===== Login Page =====
if st.session_state.page == "login":
    st.title("TaskMate AI")
    st.markdown("#### Let’s get you started in seconds")

    user_name  = st.text_input("What's your name?")
    user_email = st.text_input("Email (used to personalize your experience)")

    if user_name and user_email:
        profile = load_user_profile(user_email)
        st.session_state.user_name = user_name
        st.session_state.user_id   = user_email

        if profile:
            st.session_state.profile = profile
            st.session_state.page    = "confirm_profile"
            st.rerun()
        else:
            st.session_state.new_user = True
            st.session_state.page     = "setup_profile"
            st.rerun()

# ===== Confirm Existing Profile =====
elif st.session_state.page == "confirm_profile":
    st.title(f"👋 Welcome back, {st.session_state.user_name}!")
    st.subheader("Here’s your current setup:")

    p = st.session_state.profile
    st.write(f"**Work Hours:** {p['work_hours']['start']} - {p['work_hours']['end']}")
    st.write(f"**Break Duration:** {p['break_duration_min']} minutes")
    st.write("**Energy Levels:**")
    st.write(f"- Morning: {p['energy_levels']['morning']}")
    st.write(f"- Afternoon: {p['energy_levels']['afternoon']}")
    st.write(f"- Evening: {p['energy_levels']['evening']}")

    c1, c2 = st.columns(2)
    if c1.button("✅ It is up to date"):
        st.session_state.page = "scheduler"
        st.rerun()
    if c2.button("🔁 Update my preferences"):
        st.session_state.page = "setup_profile"
        st.rerun()

# ===== Profile Setup Page =====
elif st.session_state.page == "setup_profile":
    st.title("🛠️ Setup Your Preferences")
    st.markdown("Let’s personalize TaskMate for you:")

    work_start = st.time_input("Workday Starts At", value=datetime.strptime("09:00", "%H:%M").time())
    work_end   = st.time_input("Workday Ends At",   value=datetime.strptime("17:00", "%H:%M").time())
    break_min  = st.slider("Preferred Break Duration", 5, 60, 15)
    em = st.selectbox("Morning Energy",   ["high","medium","low"], index=0)
    ea = st.selectbox("Afternoon Energy", ["high","medium","low"], index=1)
    ee = st.selectbox("Evening Energy",   ["high","medium","low"], index=2)

    if st.button("🎯 Save and Continue"):
        profile = {
            "work_hours": {"start": work_start.strftime("%H:%M"), "end": work_end.strftime("%H:%M")},
            "break_duration_min": break_min,
            "energy_levels": {"morning": em, "afternoon": ea, "evening": ee}
        }
        upload_user_profile(st.session_state.user_id, profile)
        st.session_state.profile = profile
        st.session_state.page    = "scheduler"
        st.success("✅ Your preferences have been saved.")
        st.rerun()

# ===== Scheduler Page =====
elif st.session_state.page == "scheduler":
    st.title(f"Welcome, {st.session_state.user_name} 👋")
    st.subheader("What’s on your plate today?")

    schedule_type = st.radio(
        "Type of tasks:",
        ["Work-related","Personal (after hours)"],
        horizontal=True,
        index=1
    )

    task_input = st.text_area(
        " ",
        placeholder="Finish my project, workout for 1 hour, shower, dinner...",
        height=150,
        label_visibility="collapsed"
    )

    if st.button("🧠 Sort my day"):
        if not task_input.strip():
            st.warning("Add at least one task to begin.")
        else:
            with st.spinner("Thinking through your day..."):
                try:
                    parsed    = parse_tasks(task_input)  # Groq-powered parser
                    sched_key = "work-related" if schedule_type == "Work-related" else "personal"
                    scheduled = schedule_tasks(parsed, st.session_state.profile, schedule_type=sched_key)

                    if not scheduled:
                        st.warning("⚠️ No tasks could be scheduled. Please check your input.")
                    else:
                        st.session_state.today_tasks = scheduled
                        upload_task_snapshot(st.session_state.user_id, scheduled)
                        st.success("✅ Your schedule is ready!")

                        st.markdown("---")
                        st.subheader("📅 Here's your schedule:")

                        for idx, task in enumerate(scheduled):
                            s = str(task['start_time'])
                            e = str(task['end_time'])
                            st.markdown(f"**{s} → {e}** — {task['description']}")

                            cd, cs = st.columns(2)
                            with cd:
                                if st.button("✅ Done", key=f"done_{idx}"):
                                    st.success(f"Marked done: {task['description']}")
                            with cs:
                                if st.button("❌ Skip", key=f"skip_{idx}"):
                                    st.info(f"Skipped: {task['description']}")

                except Exception as e:
                    st.error(f"Oops! Something went wrong: {e}")

    st.markdown("---")
    st.caption("TaskMate AI - Adding clarity to life")
