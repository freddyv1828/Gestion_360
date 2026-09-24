# backend/utils.py
import os
import boto3

R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "tu-bucket")

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=boto3.session.Config(signature_version='s3v4')
    )