"""Signed upload + RunPod Serverless job proxy for cattle video analysis.

Heavy inference never runs inside Vercel. The browser uploads directly to private
Cloudflare R2 using a short-lived presigned URL; this API only creates/checks jobs.
"""
import os
import re
import requests
from flask import Blueprint, jsonify, request
import boto3
from botocore.config import Config

vision_api = Blueprint("vision_api", __name__, url_prefix="/api/fuentes/vision")
KEY_RE = re.compile(r"^vision/uploads/[a-f0-9-]{36}\\.mp4$")


def _r2():
    account = os.getenv("R2_ACCOUNT_ID")
    bucket = os.getenv("R2_BUCKET")
    access = os.getenv("R2_ACCESS_KEY_ID")
    secret = os.getenv("R2_SECRET_ACCESS_KEY")
    if not all((account, bucket, access, secret)):
        raise RuntimeError("Faltan R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID o R2_SECRET_ACCESS_KEY")
    return boto3.client(
        "s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=access, aws_secret_access_key=secret,
        region_name="auto", config=Config(signature_version="s3v4"),
    ), bucket


def _job_url(action):
    endpoint = os.getenv("RUNPOD_ENDPOINT_ID")
    if not endpoint:
        raise RuntimeError("Falta RUNPOD_ENDPOINT_ID")
    return f"https://api.runpod.ai/v2/{endpoint}/{action}"


@vision_api.get("/status")
def vision_status():
    required = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY")
    missing = [key for key in required if not os.getenv(key)]
    return jsonify({
        "status": "ready" if not missing else "configuration_required",
        "provider": "RunPod Serverless + Cloudflare R2",
        "gpu_inference": "external",
        "missing_environment": missing,
        "model": "YOLO26n COCO (clase cow) + BoT-SORT",
        "identity_limit": "Los IDs son temporales por video; no identifican permanentemente cada bovino.",
    })


@vision_api.post("/upload-url")
def vision_upload_url():
    data = request.get_json(silent=True) or {}
    name = str(data.get("filename") or "").lower()
    size = data.get("size")
    if not name.endswith((".mp4", ".mov", ".m4v")):
        return jsonify({"error": "Formato no admitido. Usá MP4, MOV o M4V."}), 400
    try:
        size = int(size)
    except (TypeError, ValueError):
        return jsonify({"error": "Tamaño de archivo inválido."}), 400
    if size <= 0 or size > 100 * 1024 * 1024:
        return jsonify({"error": "El video debe pesar hasta 100 MB."}), 413
    try:
        s3, bucket = _r2()
        import uuid
        key = f"vision/uploads/{uuid.uuid4()}.mp4"
        content_type = "video/mp4"
        url = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=900,
        )
        return jsonify({"upload_url": url, "object_key": key, "content_type": content_type,
                        "expires_in": 900, "max_bytes": 100 * 1024 * 1024})
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "configuration_required"}), 503


@vision_api.post("/analyze")
def vision_analyze():
    data = request.get_json(silent=True) or {}
    key = str(data.get("object_key") or "")
    if not KEY_RE.fullmatch(key):
        return jsonify({"error": "Identificador de archivo inválido."}), 400
    try:
        s3, bucket = _r2()
        obj = s3.head_object(Bucket=bucket, Key=key)
        if int(obj.get("ContentLength") or 0) > 100 * 1024 * 1024:
            return jsonify({"error": "El video supera 100 MB."}), 413
        if int(obj.get("ContentLength") or 0) <= 0:
            return jsonify({"error": "El archivo está vacío."}), 400
        response = requests.post(
            _job_url("run"),
            headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}"},
            json={"input": {"object_key": key}},
            timeout=25,
        )
        response.raise_for_status()
        job = response.json()
        return jsonify({"status": job.get("status", "IN_QUEUE"), "job_id": job.get("id"),
                        "provider": "RunPod Serverless", "model": "YOLO26n + BoT-SORT",
                        "object_key": key}), 202
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "unavailable"}), 503


@vision_api.get("/jobs/<job_id>")
def vision_job_status(job_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", job_id):
        return jsonify({"error": "ID de trabajo inválido."}), 400
    try:
        response = requests.get(
            _job_url(f"status/{job_id}"),
            headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}"},
            timeout=15,
        )
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "unavailable"}), 503
