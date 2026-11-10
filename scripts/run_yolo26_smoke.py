"""CPU smoke test for YOLO26 + BoT-SORT.

This proves that the public pretrained model and tracker execute in CI.
It is NOT a cattle-accuracy validation; the public bus sample is only a runtime fixture.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from ultralytics import YOLO

OUT = Path("artifacts/yolo26-smoke")
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = "https://github.com/ultralytics/assets/releases/download/v0.0.0"
FIXTURES = {
    "image": f"{ASSETS}/bus.jpg",
    "video": f"{ASSETS}/bus.mp4",
}


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "DOTS-CI/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as out:
        out.write(response.read())
    if target.stat().st_size < 10_000:
        raise RuntimeError(f"Fixture download appears incomplete: {target}")


def main() -> None:
    image = OUT / "runtime-fixture.jpg"
    video = OUT / "runtime-fixture.mp4"
    download(FIXTURES["image"], image)
    download(FIXTURES["video"], video)

    model = YOLO("yolo26n.pt")
    prediction = model.predict(
        source=str(image),
        imgsz=640,
        conf=0.25,
        device="cpu",
        save=True,
        project=str(OUT),
        name="detection",
        exist_ok=True,
        verbose=False,
    )
    detections = []
    for result in prediction:
        for box in result.boxes:
            class_id = int(box.cls.item())
            detections.append({
                "class_id": class_id,
                "class_name": model.names[class_id],
                "confidence": round(float(box.conf.item()), 5),
                "xyxy": [round(float(v), 2) for v in box.xyxy[0].tolist()],
            })

    # Execute the BoT-SORT tracking pipeline on a public video fixture.
    # Track IDs are only sequence-local IDs, not permanent object identities.
    tracked_frames = 0
    track_ids = set()
    for result in model.track(
        source=str(video),
        tracker="botsort.yaml",
        imgsz=640,
        conf=0.25,
        device="cpu",
        stream=True,
        persist=True,
        verbose=False,
    ):
        tracked_frames += 1
        if result.boxes is not None and result.boxes.id is not None:
            track_ids.update(int(x) for x in result.boxes.id.cpu().tolist())

    report = {
        "status": "executed",
        "model": "yolo26n.pt",
        "device": "cpu",
        "fixture": "Ultralytics public bus image/video (runtime-only, not cattle)",
        "image_detection_count": len(detections),
        "detections": detections,
        "tracker": "BoT-SORT",
        "tracked_video_frames": tracked_frames,
        "unique_sequence_track_ids": sorted(track_ids),
        "cattle_validation": "NOT_PERFORMED",
        "note": "Runtime smoke test only. Cattle accuracy requires DOTS-authorized cattle footage and ground-truth annotations.",
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if tracked_frames == 0:
        raise RuntimeError("BoT-SORT did not process any video frames")


if __name__ == "__main__":
    main()
