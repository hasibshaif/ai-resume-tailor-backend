import os
import re
import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, request, jsonify, send_from_directory
from app.utils.file_utils import save_file
from app.utils.nlp_utils import generate_tailored_resume_with_chunking
from app.utils.s3_utils import upload_to_s3, delete_from_s3

api = Blueprint("api", __name__)


@api.route("/upload-resume", methods=["POST"])
def upload_resume():
    user_id = request.headers.get("userId")
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    file = request.files.get("resume")
    if not file or file.filename.split(".")[-1].lower() != "docx":
        return (
            jsonify({"error": "Invalid file format. Only .docx files are allowed."}),
            400,
        )

    original_filename = file.filename
    s3_key = f"{user_id}/master_resume/{original_filename}"
    local_file_path = os.path.join("static/uploads", original_filename)

    try:
        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_S3_REGION"),
        )

        # Delete any existing files in the master_resume folder
        existing_files = s3_client.list_objects_v2(
            Bucket=os.getenv("AWS_S3_BUCKET"), Prefix=f"{user_id}/master_resume/"
        )
        for obj in existing_files.get("Contents", []):
            s3_client.delete_object(Bucket=os.getenv("AWS_S3_BUCKET"), Key=obj["Key"])

        # Save the new file locally
        file.save(local_file_path)

        # Upload the new file to S3
        s3_url = upload_to_s3(local_file_path, os.getenv("AWS_S3_BUCKET"), s3_key)
        if not s3_url:
            return jsonify({"error": "Failed to upload to S3"}), 500
        os.remove(local_file_path)

        return (
            jsonify(
                {
                    "message": "Resume uploaded successfully",
                    "resumeUrl": s3_url,
                    "fileName": original_filename,
                }
            ),
            200,
        )
    except Exception as e:
        print(f"Error uploading resume: {e}")
        return jsonify({"error": "Failed to upload resume"}), 500


@api.route("/static/uploads/<filename>", methods=["GET"])
def serve_uploaded_file(filename):
    """
    Serve files from the static/uploads directory.
    """
    upload_folder = "static/uploads"
    if os.path.exists(os.path.join(upload_folder, filename)):
        return send_from_directory(upload_folder, filename)
    else:
        return jsonify({"error": "File not found"}), 404


@api.route("/get-master-resume", methods=["GET"])
def get_master_resume():
    user_id = request.headers.get("userId")
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_S3_REGION"),
        )
        response = s3_client.list_objects_v2(
            Bucket=os.getenv("AWS_S3_BUCKET"), Prefix=f"{user_id}/master_resume/"
        )
        if "Contents" not in response:
            return jsonify({"error": "No master resume found"}), 404

        master_resumes = response["Contents"]
        if not master_resumes:
            return jsonify({"error": "No master resume found"}), 404

        # Assume there's only one file in master_resume directory
        master_file = master_resumes[0]["Key"]
        pre_signed_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.getenv("AWS_S3_BUCKET"), "Key": master_file},
            ExpiresIn=3600,  # Valid for 1 hour
        )
        return (
            jsonify(
                {"resumeUrl": pre_signed_url, "fileName": master_file.split("/")[-1]}
            ),
            200,
        )
    except ClientError as e:
        print(f"Error accessing S3: {e}")
        return jsonify({"error": "Failed to access S3"}), 500

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@api.route("/generate-resume", methods=["POST"])
def generate_resume():
    user_id = request.headers.get("userId")
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    job_title = data.get("jobTitle")
    job_description = data.get("jobDescription")
    if not job_title or not job_description:
        return jsonify({"error": "Job title and description are required"}), 400

    sanitized_job_title = re.sub(r"[^\w\s-]", "", job_title).replace(" ", "_")
    tailored_file_name = f"{sanitized_job_title}_Tailored_Resume.docx"
    s3_key_tailored = f"{user_id}/{tailored_file_name}"
    local_file_path = os.path.join("static/uploads", tailored_file_name)

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_S3_REGION"),
        )

        # Find the master resume in the master_resume folder
        response = s3_client.list_objects_v2(
            Bucket=os.getenv("AWS_S3_BUCKET"), Prefix=f"{user_id}/master_resume/"
        )
        if "Contents" not in response or not response["Contents"]:
            return jsonify({"error": "No master resume found"}), 404

        # Get the first file in the master_resume folder
        master_file_key = response["Contents"][0]["Key"]
        pre_signed_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.getenv("AWS_S3_BUCKET"), "Key": master_file_key},
            ExpiresIn=3600,  # Valid for 1 hour
        )

        # Generate the tailored resume
        generate_tailored_resume_with_chunking(
            pre_signed_url, job_title, job_description, local_file_path
        )

        # Upload the tailored resume back to S3
        s3_url = upload_to_s3(
            local_file_path, os.getenv("AWS_S3_BUCKET"), s3_key_tailored
        )
        os.remove(local_file_path)

        # Generate a pre-signed URL for the tailored resume
        tailored_resume_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.getenv("AWS_S3_BUCKET"), "Key": s3_key_tailored},
            ExpiresIn=3600,  # Valid for 1 hour
        )

        return (
            jsonify(
                {
                    "message": "Resume tailored successfully",
                    "resumeUrl": tailored_resume_url,
                }
            ),
            200,
        )
    except Exception as e:
        print(f"Error generating tailored resume: {e}")
        return jsonify({"error": "Failed to generate tailored resume"}), 500


@api.route("/get-tailored-resumes", methods=["GET"])
def get_tailored_resumes():
    user_id = request.headers.get("userId")
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_S3_REGION"),
        )
        response = s3_client.list_objects_v2(
            Bucket=os.getenv("AWS_S3_BUCKET"),
            Prefix=f"{user_id}/",
        )
        tailored_resumes = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if "master_resume" not in key:  # Exclude the master resume
                file_name = key.split("/")[-1]
                pre_signed_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": os.getenv("AWS_S3_BUCKET"), "Key": key},
                    ExpiresIn=3600,
                )
                tailored_resumes.append(
                    {"title": file_name, "downloadUrl": pre_signed_url}
                )

        return jsonify({"resumes": tailored_resumes}), 200
    except Exception as e:
        print(f"Error fetching tailored resumes: {e}")
        return jsonify({"error": "Failed to fetch tailored resumes"}), 500
    

@api.route("/delete-tailored-resume", methods=["DELETE"])
def delete_tailored_resume():
    user_id = request.headers.get("userId")
    key = request.args.get("key")

    if not user_id or not key:
        return jsonify({"error": "User ID and resume key are required"}), 400

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_S3_REGION"),
    )

    try:
        # Delete the object
        s3_client.delete_object(
            Bucket=os.getenv("AWS_S3_BUCKET"), Key=f"{user_id}/{key}"
        )

        # Verify deletion by listing objects again
        response = s3_client.list_objects_v2(
            Bucket=os.getenv("AWS_S3_BUCKET"), Prefix=f"{user_id}/"
        )
        if "Contents" in response:
            remaining_files = [obj["Key"] for obj in response["Contents"]]
            print(f"Remaining files: {remaining_files}")  # Debugging
            if f"{user_id}/{key}" in remaining_files:
                raise Exception("File deletion failed.")

        return jsonify({"message": "Resume deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting tailored resume: {e}")
        return jsonify({"error": "Failed to delete tailored resume"}), 500
