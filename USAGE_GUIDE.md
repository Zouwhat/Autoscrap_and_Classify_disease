# Thai News Processing Pipeline - คู่มือการใช้งาน

คู่มือการใช้งานระบบประมวลผลข่าวภาษาไทยด้วย LLM แบบครบวงจร

---

## 📋 สารบัญ

1. [Quick Start (ใช้งานแบบเร็ว)](#quick-start)
2. [วิธีการใช้งานแบบ Auto](#วิธีการใช้งานแบบ-auto)
3. [วิธีการใช้งานแบบ Manual](#วิธีการใช้งานแบบ-manual)
4. [การตั้งค่า Config](#การตั้งค่า-config)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### ติดตั้งและตั้งค่า

```bash
# 1. ติดตั้ง dependencies
pip install -r requirements.txt

# 2. ตั้งค่า API Key (ถ้าใช้ Typhoon)
# สร้างไฟล์ .env
echo TYPHOON_API_KEY=your-api-key-here > .env

# 3. รัน pipeline ทั้งหมด
python full_pipeline.py
```

---

## 🤖 วิธีการใช้งานแบบ Auto

### รันทั้งระบบอัตโนมัติ (3 ขั้นตอน)

```bash
# รันทั้งหมด: Google Alert → Scraping → Extraction
python full_pipeline.py
```

**ขั้นตอนที่ทำงานอัตโนมัติ:**
1. ✅ ดึง URLs จาก Google Alerts (Gmail)
2. ✅ Scrape เนื้อหาข่าวจาก URLs
3. ✅ จำแนกและสกัดข้อมูลด้วย LLM

### ตัวเลือกการรัน

```bash
# ข้าม Google Alert (ใช้ input_df.csv ที่มีอยู่)
python full_pipeline.py --skip-alert

# ข้าม Scraping (ใช้ prepare_data.csv ที่มีอยู่)
python full_pipeline.py --skip-scraping

# รันเฉพาะ LLM Extraction
python full_pipeline.py --skip-alert --skip-scraping

# แสดง log แบบละเอียด
python full_pipeline.py --verbose

# ดูคำสั่งทั้งหมด
python full_pipeline.py --help
```

### Output Files

```
full_pipeline.py
    ↓
1. input_df.csv           # URLs from Google Alerts
    ↓
2. prepare_data.csv       # URLs + scraped content
    ↓
3. heat_data.csv          # Final extracted data
```

---

## 🔧 วิธีการใช้งานแบบ Manual

### Step 1: Google Alert Collection (ดึง URLs)

```bash
python google_alert_from_email.py
```

**Input:**
- Gmail credentials (ใน `google_pass.gitignore`)

**Output:**
- `input_df.csv` - รายการ URLs จาก Google Alerts

**Config:**
```python
# แก้ไขใน google_alert_from_email.py
LOOKBACK_DAYS = 60        # ย้อนหลังกี่วัน
MAILBOX = "INBOX"         # mailbox ที่ใช้
```

---

### Step 2: Smart Web Scraping (ดึงเนื้อหา)

```bash
python smart_scraper.py --input input_df.csv
```

**Input:**
- `input_df.csv` - URLs ที่ต้องการ scrape

**Output:**
- `prepare_data.csv` - URLs + เนื้อหาข่าว

**Features:**
- ✅ Incremental scraping (ข้าม URLs ที่มี content แล้ว)
- ✅ Retry mechanism
- ✅ Error handling

**Advanced Options:**
```bash
# กำหนด output file
python smart_scraper.py --input input_df.csv --output custom_output.csv

# Force scrape ทั้งหมด (ไม่ skip)
python smart_scraper.py --input input_df.csv --force
```

---

### Step 3: LLM Extraction Pipeline (สกัดข้อมูล)

```bash
python pipeline_runner.py
```

**Input:**
- `prepare_data.csv` - ข่าวที่มีเนื้อหาแล้ว
- `config.json` - การตั้งค่า

**Output:**
- `prepare_data_filled.csv` - ข้อมูลทั้งหมด (relevant + irrelevant)
- `heat_data.csv` - ข้อมูลที่เกี่ยวข้องเท่านั้น
- `base_heat_map.csv` - ฐานข้อมูลสะสม (incremental mode)

**ขั้นตอนที่ทำงาน:**
1. Deduplication (ตรวจสอบ URL ซ้ำ)
2. Classification (จำแนกว่าข่าวเกี่ยวข้องหรือไม่)
3. Extraction (สกัดข้อมูลจากข่าวที่เกี่ยวข้อง)
4. Validation (ตรวจสอบ data type)
5. Output (บันทึกผลลัพธ์)

**Mode Options:**
```bash
# ตรวจสอบ config
python pipeline_runner.py --dry-run

# ใช้ config file อื่น
python pipeline_runner.py --config custom_config.json

# แสดง log แบบละเอียด
python pipeline_runner.py --verbose
```

---

## ⚙️ การตั้งค่า Config

### เปลี่ยน LLM Provider

แก้ไขใน `config.json`:

```json
{
  "llm_provider": "typhoon",  // "typhoon" หรือ "ollama"

  "llm_settings": {
    "typhoon": {
      "model": "typhoon-v2.1-12b-instruct",
      "temperature": 0.1,
      "max_tokens": 5000
    },
    "ollama": {
      "model": "qwen3:8b",
      "base_url": "http://localhost:11434"
    }
  }
}
```

**Typhoon (Cloud API):**
- ต้องมี API key
- เสียค่าใช้จ่าย
- ความแม่นยำสูง

**Ollama (Local):**
- รันบนเครื่องเอง
- ฟรี ไม่เสียค่า API
- ต้องติดตั้ง Ollama + Model

### เปิด/ปิด Columns

```json
{
  "columns": {
    "bulk_operations": {
      "enable_all_location": true,      // เปิดข้อมูลสถานที่
      "enable_all_medical": true,       // เปิดข้อมูลทางการแพทย์
      "enable_all_temperature": false,  // ปิดข้อมูลอุณหภูมิ
      "enable_all_datetime": true,      // เปิดข้อมูลวันเวลา
      "enable_all_basic_info": true     // เปิดข้อมูลพื้นฐาน
    }
  }
}
```

### เปลี่ยน Processing Mode

```json
{
  "processing": {
    "mode": "incremental",        // "incremental" หรือ "full"
    "batch_size": 20,             // จำนวน records ต่อ batch
    "skip_processed_records": true // ข้าม records ที่ประมวลผลแล้ว
  }
}
```

**Incremental Mode:**
- ข้าม URLs ที่ extract แล้ว (ตรวจจาก base_heat_map.csv)
- เร็วกว่า ประหยัดค่า API
- เหมาะกับการรันประจำ

**Full Mode:**
- ประมวลผลทุก record ใหม่
- ช้ากว่า เสียค่า API มากกว่า
- เหมาะกับการ re-process

---

## 📁 File Structure

```
Epic1_3/
├── full_pipeline.py              # 🚀 Auto pipeline (3 steps)
│
├── google_alert_from_email.py    # Step 1: Google Alert
├── smart_scraper.py              # Step 2: Scraping
├── pipeline_runner.py            # Step 3: Extraction
│
├── config.json                   # ⚙️ Configuration
├── .env                          # 🔑 API Keys
├── google_pass.gitignore         # 📧 Gmail credentials
│
├── input_df.csv                  # Output Step 1
├── prepare_data.csv              # Output Step 2
├── heat_data.csv                 # 📊 Final Output
├── base_heat_map.csv             # 💾 Incremental database
│
├── config_loader.py              # Core: Config
├── extraction_engine.py          # Core: Extraction
├── llm_client.py                 # Core: LLM
│
├── logs/                         # 📝 Log files
├── backups/                      # 💾 Backups
│
└── USAGE_GUIDE.md               # 📖 This file
```

---

## 🔍 Troubleshooting

### ปัญหา: ไม่มี API Key

```bash
# ตรวจสอบ API key
echo %TYPHOON_API_KEY%

# ตั้งค่า API key
# Windows
set TYPHOON_API_KEY=your-key-here

# Linux/Mac
export TYPHOON_API_KEY=your-key-here

# หรือสร้างไฟล์ .env
echo TYPHOON_API_KEY=your-key-here > .env
```

### ปัญหา: No new records to process

**สาเหตุ:** ทุก URLs ประมวลผลไปแล้ว (incremental mode)

**แก้ไข:**
```bash
# วิธีที่ 1: ลบ base database (process ใหม่ทั้งหมด)
del base_heat_map.csv
python pipeline_runner.py

# วิธีที่ 2: เปลี่ยนเป็น full mode
# แก้ config.json: "mode": "full"
python pipeline_runner.py
```

### ปัญหา: Input file not found

**ตรวจสอบ path ใน config.json:**
```json
{
  "data_paths": {
    "input_file": "E:\\SS5_internship\\pj_vibe\\src\\Epic1_3\\prepare_data.csv"
  }
}
```

ตรวจสอบว่าไฟล์มีอยู่จริงและ path ถูกต้อง

### ปัญหา: Ollama ไม่ทำงาน

```bash
# ติดตั้ง Ollama
# Download: https://ollama.com

# Pull model
ollama pull qwen3:8b

# ตรวจสอบ
ollama list

# รัน Ollama server
ollama serve
```

### ปัญหา: Gmail Authentication Failed

1. ตรวจสอบ `google_pass.gitignore` มี email และ app password ถูกต้อง
2. ต้องใช้ **App Password** ไม่ใช่ password ปกติ
3. เปิด 2-Step Verification ใน Google Account
4. สร้าง App Password: https://myaccount.google.com/apppasswords

---

## 🎯 Use Cases

### Use Case 1: รันประจำวัน (Daily)

```bash
# เช้าวันละครั้ง - ดึงข่าวใหม่และประมวลผล
python full_pipeline.py
```

### Use Case 2: Re-process ข้อมูลเดิม

```bash
# ลบ base และ process ใหม่
del base_heat_map.csv
python pipeline_runner.py
```

### Use Case 3: ทดสอบด้วยข้อมูลใหม่

```bash
# 1. เพิ่ม URLs ใหม่ใน input_df.csv (manual)
# 2. Scrape เฉพาะ URLs ใหม่
python smart_scraper.py --input input_df.csv

# 3. Extract
python pipeline_runner.py
```

### Use Case 4: เปลี่ยน Columns

```bash
# 1. แก้ config.json (เปิด/ปิด columns)
# 2. ลบ base_heat_map.csv
del base_heat_map.csv

# 3. Process ใหม่
python pipeline_runner.py
```

---

## 📊 Performance

### Typhoon API
- **Classification:** ~2-3 วินาที/record
- **Extraction:** ~3-5 วินาที/record
- **Total:** ~5-8 วินาที/record
- **30 records:** ~3-4 นาที

### Ollama Local (qwen3:8b)
- **Classification:** ~1-2 วินาที/record
- **Extraction:** ~2-3 วินาที/record
- **Total:** ~3-5 วินาที/record
- **30 records:** ~2-3 นาที

### Smart Scraping
- **Speed:** ~1-2 วินาที/URL
- **30 URLs:** ~1 นาที
- **Incremental:** ข้าม URLs ที่มี content (fast)

---

## 📝 Best Practices

1. ✅ **ใช้ Incremental Mode** สำหรับการรันประจำ
2. ✅ **Backup base_heat_map.csv** ก่อน re-process
3. ✅ **ตรวจสอบ config** ด้วย `--dry-run` ก่อนรัน
4. ✅ **Monitor logs** ที่ `logs/pipeline.log`
5. ✅ **Test กับข้อมูลน้อยๆ** ก่อนรัน production

---

## 🆘 Support

- **Documentation:** README.md, SETUP_GUIDE.md
- **Config Reference:** config.json (มี comments อธิบาย)
- **Log Files:** logs/pipeline.log
- **Examples:** COMMANDS.txt

---

**พร้อมใช้งาน! 🚀**

เริ่มต้นด้วยคำสั่ง:
```bash
python full_pipeline.py
```
