# Model weights

## For deployment (Render / free hosting) — use ONNX ✅
Place your exported ONNX model here:  `backend/models/yolov26s.onnx`
Default backend (`MODEL_BACKEND=onnx`) needs only onnxruntime — low RAM.

### Export the ONNX (one time, locally)
```bash
pip install ultralytics
python scripts/export_onnx.py --weights backend/models/yolov26s.pt
```

## Model output format
Your model is exported END-TO-END (NMS embedded): output shape [1, 300, 6],
each row = [x1, y1, x2, y2, score, class_id]. The ONNX backend auto-detects
this and also supports raw YOLO heads.

## Classes
28 Arabic letters (0=ا … 27=ي), matching your data.yaml. See
backend/config/labels.py.

## No model = no predictions (by design)
There is no demo/mock mode. If the model is missing, the UI loads but inference
is rejected with a clear error and /health reports "loaded": false.
