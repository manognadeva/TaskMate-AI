from aws_s3 import upload_user_profile, load_user_profile

# Try to load existing profile from S3
profile = load_user_profile()

# If not found, create default
if not profile:
    profile = {
        "work_hours": {"start": "09:00", "end": "17:00"},
        "peak_productivity": "morning",
        "default_priority": "medium",
        "task_preferences": ["work", "personal", "health"]
    }

# Upload profile to S3
upload_user_profile(profile)
