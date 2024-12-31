import boto3
import os
from botocore.exceptions import ClientError

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION"),
)


def upload_to_s3(file_path, bucket_name, s3_key):
    """
    Upload a file to S3.
    :param file_path: Path to the file on the local system.
    :param bucket_name: Name of the S3 bucket.
    :param s3_key: Key for the file in S3 (e.g., userId/resume.docx).
    :return: Public URL of the uploaded file.
    """
    try:
        s3_client.upload_file(file_path, bucket_name, s3_key)
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        return s3_url
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        return None


def delete_from_s3(bucket_name, s3_key):
    """
    Delete a file from S3.
    :param bucket_name: Name of the S3 bucket.
    :param s3_key: Key for the file in S3 (e.g., userId/resume.docx).
    :return: None
    """
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
    except ClientError as e:
        print(f"Error deleting from S3: {e}")
