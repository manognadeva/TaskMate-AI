import boto3
import json
from botocore.exceptions import ClientError
from datetime import datetime

bucket_name = "taskmate-user-data"
s3 = boto3.client("s3")

class ProfileNotFoundError(Exception):
    pass

def load_user_profile(user_id):
    """
    Loads a user profile from S3.
    Raises ProfileNotFoundError if the user doesn't exist.
    """
    try:
        response = s3.get_object(Bucket=bucket_name, Key=f"{user_id}/profile.json")
        profile = json.loads(response["Body"].read())
        print(f"✅ Loaded profile for {user_id}")
        return profile
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"🆕 No profile found for {user_id}")
            raise ProfileNotFoundError(f"No profile found for {user_id}")
        else:
            raise

def upload_user_profile(user_id, profile_data):
    """
    Uploads the user's preferences to S3.
    """
    s3.put_object(
        Bucket=bucket_name,
        Key=f"{user_id}/profile.json",
        Body=json.dumps(profile_data),
        ContentType='application/json'
    )
    print(f"✅ Uploaded profile for {user_id} to S3")

def upload_task_snapshot(user_id, task_data):
    """
    Uploads the user's task snapshot to S3.
    """
    now = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    s3.put_object(
        Bucket=bucket_name,
        Key=f"{user_id}/snapshots/{now}.json",
        Body=json.dumps(task_data),
        ContentType='application/json'
    )
    print(f"📤 Uploaded daily snapshot for {user_id} to S3")
