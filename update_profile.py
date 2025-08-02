from aws_s3 import load_user_profile, upload_user_profile
from groq import Groq
import json
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
api_key = os.getenv("OPENAI_API_KEY")  

print("Loaded API Key:", api_key[:10], "...")  

client = Groq(api_key=api_key)  

def update_profile_with_instruction(instruction: str):
    profile = load_user_profile()

    prompt = f"""
You are an assistant that helps update a user profile dictionary based on instructions.

Here is the current profile:
{json.dumps(profile, indent=2)}

Instruction:
{instruction}

Return only the updated profile as a raw JSON object. No explanation, no code blocks.
"""

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        content = response.choices[0].message.content

        try:
            updated_profile = json.loads(content)
            upload_user_profile(updated_profile)
            print("✅ Profile updated and uploaded to S3")
            print(updated_profile)
        except Exception as e:
            print("❌ JSON parse error:", e)
            print("Raw output:\n", content)

    except Exception as e:
        print("❌ API Error:", str(e))


instruction = input("Enter your instruction to update the profile: ")
update_profile_with_instruction(instruction)
