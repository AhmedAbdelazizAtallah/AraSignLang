<div align="center">

# 🖐️ Arabic Sign Language AI

### Production-ready real-time Arabic Sign Language recognition
**FastAPI · WebSockets · OpenCV · ONNX Runtime (YOLOv26s) · Glassmorphism UI**

</div>

---

A commercial-grade web app that recognises **Arabic sign language letters** in
real time and turns them into **words and full sentences**. Supports **live
webcam**, **video upload** and **image upload** through one unified inference
pipeline, with a polished futuristic UI, analytics, exportable reports and a
learning mode.

> ⚡ Uses **ONNX Runtime** (no torch) → deploys on free hosts like Render (512 MB).
> See **[DEPLOY.md](DEPLOY.md)**.

---

## ✨ Features
- **3 input modes:** 📷 live camera · 🎥 video · 🖼 image — animated tabs, each keeps its own state.
- **Unified pipeline:** LetterBox → **416×416** (aspect preserved) → async inference → stabilizer.
- **Real-time overlays:** confidence-coloured box, Arabic label `حرف : ب`, live FPS/latency/device.
- **Smart guide + quality LED**, **stable typing** (majority vote + smoothing + cooldown).
- **Arabic language AI:** dictionary autocomplete, spell-correction, AI sentence suggestions.
- **Sentence builder** (space/delete/undo/redo/copy/**speak**), analytics dashboard, session history,
  export TXT/CSV/JSON/PDF, learning mode.

## 🧠 Model
- **28 Arabic letters** (0=ا … 27=ي), matching your `data.yaml`.
- Exported **end-to-end** (NMS embedded): output `[1, 300, 6]` = `[x1,y1,x2,y2,score,class_id]`.
- The ONNX backend auto-detects this format (and raw YOLO heads too).
- **No demo/mock mode** — a real model is required; otherwise inference is rejected clearly.

## 🚀 Quick start (local, ONNX)
```bash
pip install ultralytics
python scripts/export_onnx.py --weights backend/models/yolov26s.pt   # → yolov26s.onnx
bash run.sh                                                          # http://localhost:8000
```
Open **/** · API docs **/docs** · model status **/health**.

### Diagnose the model output
```bash
python scripts/inspect_onnx.py --model backend/models/yolov26s.onnx --image hand.jpg
```

## ☁️ Free deployment (GitHub + Render)
Full guide in **[DEPLOY.md](DEPLOY.md)**. Includes `render.yaml`, `Procfile`,
`start`/`run` scripts, `Dockerfile` (all bind to `$PORT`) and `/health`.

## 📁 Structure
```
backend/   api · websocket · inference (onnx_backend, detector, stabilizer) · services · utils · config
frontend/  css · js · animations · assets · fonts
templates/index.html · scripts/(export_onnx, inspect_onnx)
render.yaml · Procfile · Dockerfile · docker-compose.yml
requirements.txt (onnx) · requirements-torch.txt (optional) · .env · DEPLOY.md
```

## 🔌 API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness + model diagnostics |
| WS  | `/ws/live` | Real-time frame → prediction |
| POST| `/api/detect/image` | Image → annotated PNG |
| POST| `/api/detect/video` | Video → overlaid MP4 + timeline |
| POST| `/api/language/suggest` | Word autocomplete |
| POST| `/api/language/sentences` | Sentence suggestions |
| GET | `/api/sessions/history` | Archived sessions |
| POST| `/api/sessions/export` | Export TXT/CSV/JSON/PDF |

<div align="center"><sub>Built with ❤️ for the Arabic deaf & hard-of-hearing community.</sub></div>
