# دليل تشغيل منصة Botify Demo على سيرفر الـ EC2 المباشر

تم تجهيز هذا المشروع بالكامل ليعمل فوراً ومباشرة عند رفعه على سيرفر الـ **AWS EC2** بدون تعقيدات!

---

## 🚀 طريقة التشغيل في 3 خطوات بسيطة:

### الخطوة 1: رفع المشروع إلى سيرفر EC2
قم بنقل المجلد بالكامل إلى سيرفرك عبر الـ SSH/SCP أو عن طريق زيب:
```bash
scp -i /path/to/your-key.pem -r "demo al rajhi" ec2-user@<YOUR-EC2-IP>:~/botify-demo
```

### الخطوة 2: تشغيل سكريبت الإعداد التلقائي
انتقل إلى مجلد المشروع وشغل السكريبت:
```bash
cd ~/botify-demo
chmod +x deploy_ec2.sh
./deploy_ec2.sh
```

أو تشغيله بـ Python مباشرة:
```bash
pip install -r requirements.txt
python3 run.py
```

### الخطوة 3: فتح الواجهة والتجربة
افتح المتصفح من جهازك واذهب إلى:
`http://<YOUR-EC2-PUBLIC-IP>:8000`

---

## 📊 كيف يقرأ Splunk و Dynatrace البيانات فوراً بدون Tokens؟

### 1️⃣ تجربة Dynatrace (الأداء والبنية التحتية):
* عند ضغط زر **`Run Scenario`** على أي سيكناريو أداء (مثل **CPU Spike** أو **Memory Stress**)، سيقوم الكود بجهد حقيقي لموارد الـ EC2.
* **Dynatrace OneAgent** الموجود على سيرفرك يلتقط هذا الارتفاع فترتفع المؤشرات في واجهة Dynatrace ويتولد تنبيه مشكلة **Problem Alert** فوراً.

### 2️⃣ تجربة Splunk (اللوجز والأحداث الأمنية):
* عند تشغيل أي سيناريو أمني أو تطبيقي (مثل **Brute-Force** أو **HTTP 500**)، يكتب البرنامج اللوجز مباشرة في ملفين:
  1. `./data/logs/splunk_events.log`
  2. `/var/log/botify_demo/app.log`
* لربطه بـ **Splunk** الذي يعمل على السيرفر:
  * افتح **Splunk Web** $\rightarrow$ `Settings` $\rightarrow$ `Data Inputs` $\rightarrow$ `Files & Directories`.
  * اضغط **Add New** واختر المسار: `/var/log/botify_demo/app.log` أو المسار الخاص بالمرشح `.log`.
  * اختر `Sourcetype`: `botify:demo:json` أو `_json`.
  * **النتيجة**: كلما ضغطت على زر سيناريو في منصتنا، ستظهر اللوجز فوراً في Splunk Search!

---

## ⚡ خيار التشغيل في الخلفية (Daemon / Systemd):
إذا أردت تشغيل المنصة لتظل تعمل دائماً في الخلفية حتى بعد إغلاق الـ SSH Terminal:
```bash
nohup python3 run.py > demo.log 2>&1 &
```
