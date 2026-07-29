# 🚀 دليل النشر على GitHub + Render (مجاني بالكامل)

نسخة **ONNX** خفيفة تدخل في خطة Render المجانية (512MB).

## قبل ما تبدأ — جهّز الموديل ONNX
```bash
pip install ultralytics
python scripts/export_onnx.py --weights backend/models/yolov26s.pt
# → backend/models/yolov26s.onnx
```

## 1️⃣ ارفع على GitHub
```bash
cd Arabic-Sign-Language-AI
git lfs install                 # لو الموديل > 100 ميجا
git init
git add .
git commit -m "Arabic Sign Language AI — ONNX build"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```
> ملف `.gitattributes` مظبوط مسبقاً لتتبّع `*.onnx` و`*.pt` عبر Git LFS.

## 2️⃣ انشر على Render (الأسهل: Blueprint)
1. ادخل https://render.com وسجّل بحساب GitHub (مجاناً).
2. **New → Blueprint** واختر الريبو.
3. Render يقرأ `render.yaml` تلقائياً → اضغط **Apply**.
4. انتظر الـ build وستحصل على رابط:
   `https://arabic-sign-language-ai.onrender.com`

## 3️⃣ افتح تطبيقك 🎉
- `/`        ← التطبيق (HTTPS تلقائي — ضروري للكاميرا)
- `/health`  ← حالة الموديل (`loaded: true` يعني تمام)
- `/docs`    ← توثيق الـ API

## ⚠️ ملاحظات الخطة المجانية
- **النوم:** بعد 15 دقيقة خمول (يصحى في ~30-50 ثانية). امنعه بـ UptimeRobot ping على `/health`.
- **الرام:** 512 ميجا — لهذا نستخدم ONNX.
- **القرص مؤقت:** الملفات المرفوعة تُمسح عند إعادة التشغيل (طبيعي).

## 🔧 حل المشكلات
- **"Model not loaded":** تأكد أن `yolov26s.onnx` موجود (رُفع عبر LFS).
- **الكاميرا لا تعمل:** لازم `https://` (Render يوفّره) + إذن الكاميرا.
- **الحرف غلط:** راجع ترتيب `backend/config/labels.py` مع `data.yaml`.
