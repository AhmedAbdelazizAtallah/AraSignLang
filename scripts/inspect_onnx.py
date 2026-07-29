"""
🔬 أداة تشخيص موديل ONNX — شغّلها لمعرفة الشكل الحقيقي لمخرجات موديلك.

تطبع: أسماء وأشكال المدخلات/المخرجات، عدد الكلاسات المُستنتج، نطاق القيم
(min/max) لكل جزء، وهل الصناديق normalized (0..1) أم بالبكسل، وأعلى تنبؤ على
صورة اختبار. انسخ الناتج كامل وابعته لي لأظبط لك الكود بدقة.

التشغيل:
    python scripts/inspect_onnx.py --model backend/models/yolov26s.onnx
    # اختياري: على صورة حقيقية
    python scripts/inspect_onnx.py --model backend/models/yolov26s.onnx --image test.jpg
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="backend/models/yolov26s.onnx")
    ap.add_argument("--image", default=None)
    ap.add_argument("--imgsz", type=int, default=416)
    args = ap.parse_args()

    import onnxruntime as ort
    import cv2

    if not Path(args.model).exists():
        raise SystemExit(f"❌ الموديل غير موجود: {args.model}")

    sess = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])

    print("=" * 60)
    print("📥 المدخلات (inputs):")
    for i in sess.get_inputs():
        print(f"   name={i.name}  shape={i.shape}  type={i.type}")
    print("📤 المخرجات (outputs):")
    for o in sess.get_outputs():
        print(f"   name={o.name}  shape={o.shape}  type={o.type}")
    print("=" * 60)

    # جهّز صورة إدخال (حقيقية أو عشوائية)
    if args.image and Path(args.image).exists():
        img = cv2.imread(args.image)
        img = cv2.resize(img, (args.imgsz, args.imgsz))
        print(f"🖼  باستخدام صورة: {args.image}")
    else:
        img = (np.random.rand(args.imgsz, args.imgsz, 3) * 255).astype("uint8")
        print("🖼  باستخدام صورة عشوائية (مرّر --image لصورة حقيقية)")

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    tensor = rgb.transpose(2, 0, 1).astype("float32")[None] / 255.0

    out = sess.run(None, {sess.get_inputs()[0].name: tensor})[0]
    print(f"\n🔢 شكل المخرج الخام: {out.shape}")

    p = np.squeeze(out, 0) if out.ndim == 3 else out
    print(f"   بعد إزالة batch: {p.shape}")

    # وجّه لـ (N, F): الأغلب إن العدد الأكبر = عدد الصناديق
    if p.ndim == 2 and p.shape[0] < p.shape[1]:
        p = p.transpose()
        print(f"   تم عمل transpose → (N, F) = {p.shape}")
    F = p.shape[1]
    print(f"\n   عدد الخصائص لكل صندوق (F) = {F}")
    print(f"   → لو الصيغة (4+nc): عدد الكلاسات = {F - 4}")
    print(f"   → لو الصيغة (5+nc): عدد الكلاسات = {F - 5}")

    # حلّل نطاق القيم
    boxes = p[:, :4]
    rest = p[:, 4:]
    print("\n📊 نطاق القيم:")
    print(f"   الصناديق (أول 4): min={boxes.min():.3f}  max={boxes.max():.3f}")
    print(f"      → {'يبدو normalized (0..1)' if boxes.max() <= 1.5 else 'يبدو بالبكسل'}")
    print(f"   باقي القيم (scores): min={rest.min():.3f}  max={rest.max():.3f}")
    raw = rest.max() > 1.0
    print(f"      → {'logits خام (محتاج sigmoid)' if raw else 'احتمالات 0..1 جاهزة'}")

    # أعلى تنبؤ (نجرب كلا الصيغتين)
    print("\n🎯 أعلى تنبؤ (تجريبي):")
    for label, cls in (("صيغة 4+nc", rest), ("صيغة 5+nc", p[:, 5:])):
        if cls.shape[1] <= 0:
            continue
        s = _sigmoid(cls) if raw else cls
        conf = s.max(axis=1)
        cid = s.argmax(axis=1)
        best = conf.argmax()
        # توزيع الكلاسات الفائزة عبر كل الصناديق
        uniq, counts = np.unique(cid[conf >= 0.25], return_counts=True)
        print(f"   [{label}] أعلى ثقة={conf[best]:.3f} class_id={cid[best]}")
        print(f"      أكثر class_id تكراراً فوق 0.25: {dict(zip(uniq.tolist(), counts.tolist()))}")

    print("\n" + "=" * 60)
    print("✅ انسخ كل الناتج ده وابعته لي لأظبط الكود على موديلك بالضبط.")
    print("=" * 60)


if __name__ == "__main__":
    main()
