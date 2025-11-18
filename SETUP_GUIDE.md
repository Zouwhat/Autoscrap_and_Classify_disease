# Thai News Extraction Pipeline v2.0 - Setup Guide

## 📋 ระบบใหม่ที่สร้าง

ระบบ extraction pipeline แบบใหม่ที่ใช้ **config.json** ในการกำหนดค่าทั้งหมด:

```
Epic1_3/
├── config.json                  ✨ NEW - ไฟล์ config หลัก
├── config_loader.py             ✨ NEW - โหลดและ validate config
├── llm_client.py                ✨ NEW - Unified LLM client (Typhoon + Ollama)
├── extraction_engine.py         ✨ NEW - Core extraction engine
├── pipeline_runner.py           🔄 UPDATED - Entry point (เรียบง่ายขึ้น)
└── SETUP_GUIDE.md              📖 ไฟล์นี้
```

---

## 🚀 วิธีใช้งาน (Quick Start)

### 1. เตรียม Environment

```bash
# ติดตั้ง dependencies (ถ้ายังไม่มี)
pip install pandas requests python-dotenv

# ตั้งค่า API key สำหรับ Typhoon (ถ้าใช้ Typhoon)
export TYPHOON_API_KEY="your-api-key-here"

# หรือสร้างไฟล์ .env
echo "TYPHOON_API_KEY=your-api-key-here" > .env
```

### 2. ติดตั้ง Ollama (ถ้าใช้ Ollama)

```bash
# ดาวน์โหลดและติดตั้ง Ollama
# https://ollama.com/download

# Pull Qwen model
ollama pull qwen2.5:3b

# ทดสอบว่า Ollama รันอยู่
ollama list
```

### 3. แก้ไข config.json

เปิดไฟล์ `config.json` และแก้ไขส่วนบนสุด:

```json
{
  "llm_provider": "typhoon",  // เปลี่ยนเป็น "ollama" ถ้าใช้ Ollama

  "data_paths": {
    "input_file": "E:\\SS5_internship\\...\\prepare_data.csv",
    "base_file": "E:\\SS5_internship\\...\\base_heat_map.csv",
    "output_filled_file": "E:\\SS5_internship\\...\\prepare_data_filled.csv",
    "output_heat_data_file": "E:\\SS5_internship\\...\\heat_data.csv"
  }
}
```

### 4. รัน Pipeline

```bash
# รันแบบ default
python pipeline_runner.py

# รันพร้อมดู config (dry run)
python pipeline_runner.py --dry-run

# รันพร้อม verbose logging
python pipeline_runner.py --verbose
```

---

## ⚙️ การ Config ระบบ

### เปลี่ยน LLM Provider

แก้ไขใน `config.json`:

```json
{
  "llm_provider": "typhoon"  // หรือ "ollama"
}
```

### ปรับ Temperature, Max Tokens

```json
{
  "llm_settings": {
    "typhoon": {
      "temperature": 0.1,      // ปรับตามต้องการ (0.0 - 1.0)
      "max_tokens": 500,       // จำนวน tokens สูงสุด
      "timeout_seconds": 45
    }
  }
}
```

### เปิด/ปิด Columns

#### วิธีที่ 1: เปิด/ปิดทั้งกลุ่ม

```json
{
  "columns": {
    "bulk_operations": {
      "enable_all_location": true,      // เปิด columns เกี่ยวกับสถานที่
      "enable_all_medical": true,       // เปิด columns เกี่ยวกับโรค
      "enable_all_temperature": false,  // ปิด columns อุณหภูมิ
      "enable_all_datetime": true,      // เปิด columns วันเวลา
      "enable_all_basic_info": true     // เปิด columns ข้อมูลพื้นฐาน
    }
  }
}
```

#### วิธีที่ 2: เปิด/ปิดแต่ละ column

```json
{
  "columns": {
    "schema": [
      {
        "name": "จังหวัดที่เกิดเหตุ",
        "enabled": true,      // เปลี่ยนเป็น false เพื่อปิด
        "data_type": "multiclass",
        "extraction_hint": "จังหวัดที่เกิดเหตุ: ..."
      }
    ]
  }
}
```

### เพิ่ม Column ใหม่

เพิ่มใน `columns.schema`:

```json
{
  "name": "สาเหตุการเสียชีวิต",
  "enabled": true,
  "data_type": "text",
  "extraction_hint": "สาเหตุการเสียชีวิต: สาเหตุหลักของการเสียชีวิต"
}
```

### เปลี่ยน Processing Mode

```json
{
  "processing": {
    "mode": "incremental",            // หรือ "full"
    "skip_processed_records": true,   // ข้าม records ที่ extract แล้ว
    "batch_size": 20                  // จำนวน records ต่อ batch
  }
}
```

---

## 📊 วิธีทำงานของระบบ

### 1. Incremental Processing

```
prepare_data.csv (100 records)
         ↓
   Deduplication กับ base_heat_map.csv
         ↓
   New records (80 records) → Process
   Existing records (20 records) → Skip
```

### 2. Classification & Extraction

```
New records (80)
         ↓
   Classification (LLM)
         ↓
   Relevant (50) → Extract
   Irrelevant (30) → Skip
         ↓
   Extraction (LLM)
         ↓
   Success (45)
   Failed (5)
```

### 3. Output

```
prepare_data_filled.csv   ← All processed (80 records)
heat_data.csv             ← Only relevant (50 records)
base_heat_map.csv         ← Updated (10,000 + 80 = 10,080 records)
```

---

## 🔧 Troubleshooting

### ปัญหา: Ollama ไม่ทำงาน

```bash
# เช็คว่า Ollama รันอยู่หรือไม่
curl http://localhost:11434/api/tags

# ถ้าไม่รัน ให้รัน Ollama
ollama serve

# หรือเปิด Ollama app (Windows/Mac)
```

### ปัญหา: Typhoon API key ไม่ทำงาน

```bash
# เช็คว่า API key ถูกตั้งไว้หรือไม่
echo $TYPHOON_API_KEY

# ตั้งค่าใหม่
export TYPHOON_API_KEY="your-api-key-here"
```

### ปัญหา: ไฟล์ input ไม่พบ

- เช็ค path ใน `config.json` → `data_paths.input_file`
- ตรวจสอบว่าไฟล์มีอยู่จริง
- ตรวจสอบ encoding (ควรเป็น UTF-8)

### ปัญหา: Column ไม่ถูก extract

- เช็คว่า column ถูกเปิดใช้งาน (`enabled: true`)
- เช็ค `extraction_hint` ว่าชัดเจนหรือไม่
- ลอง verbose mode: `python pipeline_runner.py --verbose`

---

## 📖 ตัวอย่างการใช้งาน

### ตัวอย่างที่ 1: ใช้ Typhoon extract ข้อมูลพื้นฐาน

```json
{
  "llm_provider": "typhoon",
  "columns": {
    "bulk_operations": {
      "enable_all_location": true,
      "enable_all_medical": false,
      "enable_all_temperature": false,
      "enable_all_datetime": true,
      "enable_all_basic_info": true
    }
  }
}
```

```bash
python pipeline_runner.py
```

### ตัวอย่างที่ 2: ใช้ Ollama extract ทุกอย่าง

```json
{
  "llm_provider": "ollama",
  "columns": {
    "bulk_operations": {
      "enable_all_location": true,
      "enable_all_medical": true,
      "enable_all_temperature": true,
      "enable_all_datetime": true,
      "enable_all_basic_info": true
    }
  }
}
```

```bash
python pipeline_runner.py
```

### ตัวอย่างที่ 3: Full reprocess (ไม่ใช้ base)

```json
{
  "processing": {
    "mode": "full",
    "skip_processed_records": false
  }
}
```

```bash
python pipeline_runner.py
```

---

## 📝 Tips & Best Practices

1. **ทดสอบก่อน** - ใช้ `--dry-run` เพื่อเช็ค config ก่อนรัน
2. **Backup ก่อน** - ระบบจะ backup `base_heat_map.csv` อัตโนมัติ
3. **เริ่มจากน้อย** - ทดสอบกับ input ไฟล์เล็กๆ ก่อน
4. **ใช้ batch size เล็ก** - ถ้า API มี rate limit
5. **เช็ค logs** - ดูไฟล์ `logs/pipeline.log` เมื่อมีปัญหา

---

## 🎯 Next Steps

1. ทดสอบระบบด้วย input ไฟล์ตัวอย่าง
2. ปรับ prompt ใน `config.json` ตามความต้องการ
3. เพิ่ม/ลด columns ตามที่ต้องการ
4. ทดลองใช้ทั้ง Typhoon และ Ollama เพื่อเปรียบเทียบ
5. ตรวจสอบ output files และปรับแต่ง validation rules

---

**พร้อมใช้งานแล้ว! 🚀**

หากมีคำถามหรือปัญหา กรุณาเช็ค logs หรือใช้ `--verbose` mode
