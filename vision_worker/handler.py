"""RunPod Serverless GPU worker: bovine detection + within-video tracking.

Uses the COCO-pretrained YOLO26 nano model. COCO's cow class supports a first
functional bovine detector, but not breed recognition or permanent animal identity.
"""
import os
import math
import tempfile
from pathlib import Path

import boto3
import cv2
import runpod
import torch
from ultralytics import YOLO

MODEL = os.getenv("DOTS_VISION_MODEL", "yolo26n.pt")
MAX_BYTES = 100 * 1024 * 1024
MAX_SECONDS = 120
SAMPLE_EVERY = 3
CONFIDENCE = 0.25
_model = None


def model():
    global _model
    if _model is None:
        _model = YOLO(MODEL)
    return _model


def download_video(key: str, target: str):
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    bucket = os.environ["R2_BUCKET"]
    head = client.head_object(Bucket=bucket, Key=key)
    size = int(head.get("ContentLength") or 0)
    if size <= 0 or size > MAX_BYTES:
        raise ValueError("El video está vacío o supera 100 MB.")
    client.download_file(bucket, key, target)


def handler(job):
    inp = job.get("input") or {}
    key = str(inp.get("object_key") or "")
    if not key.startswith("vision/uploads/") or not key.endswith(".mp4") or ".." in key:
        return {"status": "error", "error": "object_key inválido"}
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        download_video(key, path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError("No se pudo abrir el video.")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = total / fps if fps > 0 else 0
        if duration > MAX_SECONDS:
            cap.release()
            raise ValueError("El video supera los 120 segundos permitidos.")
        detector = model()
        if not torch.cuda.is_available():
            raise RuntimeError("El worker no tiene GPU CUDA disponible; configurá una GPU en el endpoint RunPod.")
        device = 0
        stride = max(1, math.ceil(total / 240)) if total else SAMPLE_EVERY
        frame_no = 0
        sampled = 0
        frames = []
        unique_tracks = set()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_no % stride == 0 and sampled < 240:
                result = detector.track(
                    source=frame, persist=True, tracker="botsort.yaml",
                    classes=[19], conf=CONFIDENCE, imgsz=960,
                    device=device, verbose=False,
                )[0]
                animals = []
                boxes = result.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        coords = [round(float(v), 1) for v in boxes.xyxy[i].tolist()]
                        confidence = round(float(boxes.conf[i].item()), 4)
                        track_id = None
                        if boxes.id is not None:
                            track_id = int(boxes.id[i].item())
                            unique_tracks.add(track_id)
                        animals.append({"track_id": track_id, "confidence": confidence, "xyxy": coords})
                frames.append({"frame": frame_no, "time_seconds": round(frame_no / fps, 2),
                               "cattle_count": len(animals), "animals": animals})
                sampled += 1
            frame_no += 1
        cap.release()
        return {
            "status": "completed",
            "model": MODEL,
            "model_scope": "COCO-pretrained general object detector, class cow",
            "device": "cuda" if device == 0 else "cpu",
            "video_duration_seconds": round(duration, 2),
            "video_frames": total,
            "sampled_frames": sampled,
            "sampling": f"1 de cada {stride} fotogramas, distribuidos a lo largo del video",
            "cattle_detections": sum(f["cattle_count"] for f in frames),
            "max_cattle_in_frame": max((f["cattle_count"] for f in frames), default=0),
            "unique_temporary_track_ids": len(unique_tracks),
            "frames": frames,
            "permanent_identity": False,
            "limitations": [
                "Los IDs BoT-SORT son temporales dentro de este video.",
                "No identifica permanentemente cada vaca ni reemplaza caravanas RFID.",
                "La precisión bovina debe validarse con videos y anotaciones de rodeos argentinos.",
                "La oclusión, distancia, barro, iluminación y ángulo de cámara afectan el resultado.",
            ],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:500]}
    finally:
        if path and os.path.exists(path):
            os.remove(path)
        # El video original se borra de R2 al terminar, también si falla la inferencia.
        try:
            if key.startswith("vision/uploads/"):
                client = boto3.client(
                    "s3",
                    endpoint_url=f"https://${os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                    region_name="auto",
                )
                client.delete_object(Bucket=os.environ["R2_BUCKET"], Key=key)
        except Exception:
            pass


runpod.serverless.start({"handler": handler})
