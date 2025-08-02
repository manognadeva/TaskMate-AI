import streamlit as st
from task_parser import parse_tasks
from smart_scheduler import schedule_tasks
from aws_s3 import load_user_profile
from datetime import datetime, timedelta

# Configure Streamlit app
st.set_page_config(page_title="TaskMate AI", layout="centered")

# Ask for user details
user_id = st.text_input("Enter your username (for loading preferences)", value="default_user")
username = st.text_input("Enter your name for display", value="Friend")

# Load user profile
user_profile = load_user_profile(user_id)

# Welcome Message
st.markdown(f"## Welcome, {username} 👋")
st.markdown("### What’s on your plate today?")
st.markdown("Just list everything — we’ll organize and schedule it for you.")

# ✅ Ask schedule type BEFORE task input
schedule_type = st.radio(
    "What type of schedule is this?",
    ["Work-related", "Personal (after hours)"],
    index=0,
    horizontal=False
)

# Task Input
user_input = st.text_area(" ", height=150, placeholder="Finish project, go for a walk, eat lunch, call mom, prep dinner")

# On Submit
if st.button("🧠 Sort my day") and user_input.strip():
    with st.spinner("Parsing your tasks and building a smart schedule..."):
        # 1. Parse with LLM
        parsed_tasks = parse_tasks(user_input)

        # 2. Schedule based on selected type
        schedule = schedule_tasks(
            parsed_tasks,
            user_profile,
            schedule_type=schedule_type.lower()
        )

        # 3. Show output
        if not schedule:
            st.warning("⚠️ No tasks could be scheduled. Please check your input.")
        else:
            st.success("✅ Your smart schedule is ready!")
            for task in schedule:
                st.markdown(
                    f"- **{task['time']}**: {task['description']} ({task['duration']} min, energy: {task['energy']}, urgency: {task['urgency']})"
                )
