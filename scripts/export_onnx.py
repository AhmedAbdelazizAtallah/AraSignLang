"""
One-time helper: export your YOLOv26s .pt weights to ONNX at 416x416.

Run LOCALLY (where torch + ultralytics are installed), then deploy with only
onnxruntime — no torch — which keeps memory low on Render.

Usage:
    pip install ultralytics
    python scripts/export_onnx.py --weights backend/models/yolov26s.pt
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export YOLO .pt → ONNX (416).")
    parser.add_argument("--weights", default="backend/models/yolov26s.pt")
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--opset", type=int, default=12)
    args = parser.parse_args()

    from ultralytics import YOLO

    weights = Path(args.weights)
    if not weights.exists():
        raise SystemExit(f"Weights not found: {weights}")

    print(f"▶ Loading {weights} …")
    model = YOLO(str(weights))
    print(f"▶ Exporting to ONNX (imgsz={args.imgsz}, opset={args.opset}) …")
    out = model.export(format="onnx", imgsz=args.imgsz, opset=args.opset, simplify=True, dynamic=False)
    print(f"✅ Exported ONNX model → {out}")
    print("   Keep it at backend/models/yolov26s.onnx and set MODEL_BACKEND=onnx.")


if __name__ == "__main__":
    main()
