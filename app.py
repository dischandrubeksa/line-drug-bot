from flask import Flask, request, abort
from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    TextMessage, MessageAction, CarouselColumn, CarouselTemplate, TemplateMessage, ReplyMessageRequest
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
import re
import math
import random
import logging

DRUG_DATABASE = {
    "Amoxicillin": {
        "concentration_mg_per_ml": 250 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "Pharyngitis": {"dose_mg_per_kg_per_day": 50, "frequency": 2, "duration_days": 10, "max_mg_per_day": 2000},
            "Otitis Media": {"dose_mg_per_kg_per_day": 90, "frequency": 2, "duration_days": 10, "max_mg_per_day": 4000},
            "Pneumonia": {"dose_mg_per_kg_per_day": 90, "frequency": 2, "duration_days": 7, "max_mg_per_day": 4000},
            "Anthrax": {"dose_mg_per_kg_per_day": 75, "frequency": 3, "duration_days": 60, "max_mg_per_day": 1000},
            "H. pylori": {"dose_mg_per_kg_per_day": 62.5, "frequency": 2, "duration_days": 14, "max_mg_per_day": 2000},
            "UTI": {"dose_mg_per_kg_per_day": 75, "frequency": 3, "duration_days": 7, "max_mg_per_day": 500},
            "Sinusitis": {"dose_mg_per_kg_per_day": 90, "frequency": 2, "duration_days": 10, "max_mg_per_day": 2000},
            "Endocarditis": {"dose_mg_per_kg_per_day": 50, "frequency": 1, "duration_days": 1, "max_mg_per_day": 2000},
            "Lyme Disease": {"dose_mg_per_kg_per_day": 50, "frequency": 3, "duration_days": 14, "max_mg_per_day": 500},
            "Osteoarticular": {"dose_mg_per_kg_per_day": 100, "frequency": 3, "duration_days": 14, "max_mg_per_day": 4000}
        }
    },
    "Cephalexin": {
        "concentration_mg_per_ml": 125 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "SSTI": {"dose_mg_per_kg_per_day": 50, "frequency": 4, "duration_days": 7, "max_mg_per_day": None},
            "Pharyngitis": {"dose_mg_per_kg_per_day": 50, "frequency": 2, "duration_days": 10, "max_mg_per_day": None},
            "UTI": {"dose_mg_per_kg_per_day": 100, "frequency": 4, "duration_days": 7, "max_mg_per_day": None}
        }
    },
    "Cefdinir": {
        "concentration_mg_per_ml": 125 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "Otitis Media": {"dose_mg_per_kg_per_day": 14, "frequency": 2, "duration_days": 10, "max_mg_per_day": 600},
            "Pharyngitis": {"dose_mg_per_kg_per_day": 14, "frequency": 2, "duration_days": 10, "max_mg_per_day": 600},
            "Rhinosinusitis": {"dose_mg_per_kg_per_day": 14, "frequency": 2, "duration_days": 10, "max_mg_per_day": 600}
        }
    },
    "Cefixime": {
        "concentration_mg_per_ml": 100 / 5,
        "bottle_size_ml": 50,
        "indications": {
            "Febrile Neutropenia": {"dose_mg_per_kg_per_day": 8, "frequency": 1, "duration_days": 7, "max_mg_per_day": 400},
            "Otitis Media": {"dose_mg_per_kg_per_day": 8, "frequency": 1, "duration_days": 7, "max_mg_per_day": 400},
            "Rhinosinusitis": {"dose_mg_per_kg_per_day": 8, "frequency": 1, "duration_days": 7, "max_mg_per_day": 400},
            "Strep Pharyngitis": {"dose_mg_per_kg_per_day": 8, "frequency": 1, "duration_days": 10, "max_mg_per_day": 400},
            "Typhoid Fever": {"dose_mg_per_kg_per_day": 17.5, "frequency": 2, "duration_days": 10, "max_mg_per_day": None},
            "UTI": {"dose_mg_per_kg_per_day": 8, "frequency": 2, "duration_days": 7, "max_mg_per_day": 400}
        }
    },
    "Augmentin": {
        "concentration_mg_per_ml": 400 / 5,
        "bottle_size_ml": 70,
        "indications": {
            "Impetigo": {"dose_mg_per_kg_per_day": 35, "frequency": 2, "duration_days": 7, "max_mg_per_day": 500},
            "Osteoarticular Infection": {  "dose_mg_per_kg_per_day": 120,"frequency": 3, "duration_days": 21,"max_mg_per_day": 1000 },
            "Otitis Media": {"dose_mg_per_kg_per_day": 85,"frequency": 2, "duration_days": 10, "max_mg_per_day": 2000 },
            "Pneumonia": { "dose_mg_per_kg_per_day": 90,"frequency": 2, "duration_days": 7, "max_mg_per_day": 2000 },
            "Rhinosinusitis": {"dose_mg_per_kg_per_day": 90,"frequency": 2,"duration_days": 10,"max_mg_per_day": 2000 },
            "Strep Carriage": { "dose_mg_per_kg_per_day": 40, "frequency": 3, "duration_days": 10,"max_mg_per_day": 2000 },
            "UTI": { "dose_mg_per_kg_per_day": 35, "frequency": 2, "duration_days": 7, "max_mg_per_day": 1750 }
        }
    },
    "Azithromycin": {
        "concentration_mg_per_ml": 200 / 5,
        "bottle_size_ml": 15,
        "indications": {
            "Pertussis": [
                {"day_range": "Day 1", "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 1, "max_mg_per_day": 500},
                {"day_range": "Day 2–5", "dose_mg_per_kg_per_day": 5, "frequency": 1, "duration_days": 4, "max_mg_per_day": 250}
            ],
            "Pneumonia (Atypical)": [
                {"day_range": "Day 1", "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 1, "max_mg_per_day": 500},
                {"day_range": "Day 2–5", "dose_mg_per_kg_per_day": 5, "frequency": 1, "duration_days": 4, "max_mg_per_day": 250}
            ],
            "Strep Pharyngitis": {
                "dose_mg_per_kg_per_day": 12, "frequency": 1, "duration_days": 5, "max_mg_per_dose": 500
            },
            "Typhoid Fever": {
                "dose_mg_per_kg_per_day": 15, "frequency": 1, "duration_days": 7, "max_mg_per_dose": 1000
            },
            "UTI (Off-label)": {
                "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 3, "max_mg_per_dose": 500
            },
            "Rhinosinusitis": {
                "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 3, "max_mg_per_dose": 500
            },
            "Chlamydia": {
                "dose_mg_per_kg_per_day": 20, "frequency": 1, "duration_days": 1, "max_mg_per_dose": 1000
            },
            "Diarrhea (Campylobacter)": {
                "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 3, "max_mg_per_dose": 500
            },
            "Diarrhea (Shigella)": [
                {"day_range": "Day 1", "dose_mg_per_kg_per_day": 12, "frequency": 1, "duration_days": 1, "max_mg_per_day": 500},
                {"day_range": "Day 2–5", "dose_mg_per_kg_per_day": 5, "frequency": 1, "duration_days": 4, "max_mg_per_day": 250}
            ],
            "Cholera": {
                "dose_mg_per_kg_per_day": 20, "frequency": 1, "duration_days": 1, "max_mg_per_dose": 1000
            },
            "Babesiosis": [
                {"day_range": "Day 1", "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 1, "max_mg_per_day": 500},
                {"day_range": "Day 2–5", "dose_mg_per_kg_per_day": 5, "frequency": 1, "duration_days": 4, "max_mg_per_day": 250}
            ],
            "Cat Scratch Disease": [
                {"day_range": "Day 1", "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 1, "max_mg_per_day": 500},
                {"day_range": "Day 2–5", "dose_mg_per_kg_per_day": 5, "frequency": 1, "duration_days": 4, "max_mg_per_day": 250}
            ],
            "MAC (Mycobacterium avium, prophylaxis)": {
                "dose_mg_per_kg_per_day": 20, "frequency": 1, "duration_days": 7, "max_mg_per_dose": 1200
            },
            "NTM Pulmonary Infection": {
                "dose_mg_per_kg_per_day": 10, "frequency": 1, "duration_days": 14, "max_mg_per_dose": 500
            },
            "Cystic Fibrosis (maintenance)": {
                "dose_mg_per_kg_per_day": 10, "frequency": 3, "duration_days": 14, "max_mg_per_dose": 500
            },
            "Asthma (Adjunct)": {
                "dose_mg_per_kg_per_day": 10, "frequency": 3, "duration_days": 14, "max_mg_per_dose": 500
            },
            "Other": "INDICATION_OTHERS"
        },
        "common_indications": ["Pneumonia (Atypical)", "Strep Pharyngitis","Rhinosinusitis","Chlamydia" ]
    }
}


logging.basicConfig(
    level=logging.INFO,  # เปลี่ยนเป็น DEBUG ถ้าต้องการ log ละเอียด
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # พิมพ์ log ไปยัง stdout (เช่น Render, Cloud Run จะเห็น)
    ]
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_drug_selection = {}
user_sessions = {}

@app.route('/')
def home():
    return 'LINE Bot is running!'

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        logging.info(f"❌ Exception occurred: {e}")
        abort(400)
    return 'OK'

def send_drug_selection(event):
    carousel1 = CarouselTemplate(columns=[
        CarouselColumn(title='Amoxicillin', text='250 mg/5 ml', actions=[MessageAction(label='เลือก Amoxicillin', text='เลือกยา: Amoxicillin')]),
        CarouselColumn(title='Cephalexin', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cephalexin', text='เลือกยา: Cephalexin')]),
        CarouselColumn(title='Cefdinir', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cefdinir', text='เลือกยา: Cefdinir')]),
        CarouselColumn(title='Cefixime', text='100 mg/5 ml', actions=[MessageAction(label='เลือก Cefixime', text='เลือกยา: Cefixime')]),
        CarouselColumn(title='Augmentin', text='600 mg/5 ml', actions=[MessageAction(label='เลือก Augmentin', text='เลือกยา: Augmentin')]),
    ])
    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title='Azithromycin', text='200 mg/5 ml', actions=[MessageAction(label='เลือก Azithromycin', text='เลือกยา: Azithromycin')]),
        CarouselColumn(title='Paracetamol', text='10–15 mg/kg/dose', actions=[MessageAction(label='เลือก Paracetamol', text='เลือกยา: Paracetamol')]),
        CarouselColumn(title='Cetirizine', text='0.25 mg/kg/day', actions=[MessageAction(label='เลือก Cetirizine', text='เลือกยา: Cetirizine')]),
        CarouselColumn(title='Hydroxyzine', text='10 mg/5 ml', actions=[MessageAction(label='เลือก Hydroxyzine', text='เลือกยา: Hydroxyzine')]),
        CarouselColumn(title='Ferrous drop', text='15 mg/0.6 ml', actions=[MessageAction(label='เลือก Ferrous drop', text='เลือกยา: Ferrous drop')])
    ])
    messaging_api.reply_message(
    ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[
            TemplateMessage(alt_text="เลือกยากลุ่มแรก", template=carousel1),
            TemplateMessage(alt_text="เลือกยากลุ่มเพิ่มเติม", template=carousel2)
        ]
    ))

def send_indication_carousel(event, drug_name, show_all=False):
    drug_info = DRUG_DATABASE.get(drug_name)
    if not drug_info or "indications" not in drug_info:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"ไม่พบข้อมูลสำหรับยา {drug_name}")]
            )
        )
        return

    indications = drug_info["indications"]
    all_names = list(indications.keys())
    common = drug_info.get("common_indications", [])
    if not show_all and common:
        names_to_show = common + ["Indication อื่นๆ"]
    else:
        names_to_show = [name for name in all_names if name != "Other"]

    columns = []
    for name in names_to_show:
        label = "เลือก"
        # ✅ title ใช้ชื่อเต็ม แสดงบน carousel
        title = name[:40] if len(name) > 40 else name

        actions = [MessageAction(label=label, text=f"Indication: {name}")]
        try:
            # ✅ ดึงค่า dose_mg_per_kg_per_day
            indication_info = indications[name]
            if isinstance(indication_info, list):
                dose_preview = f"{indication_info[0]['dose_mg_per_kg_per_day']} mg/kg/day"
            else:
                dose_preview = f"{indication_info['dose_mg_per_kg_per_day']} mg/kg/day"

            columns.append(CarouselColumn(title=title, text=dose_preview, actions=actions))
        except Exception as e:
            logging.info(f"⚠️ ผิดพลาดตอนสร้าง CarouselColumn สำหรับ {name}: {e}")
        
    carousel = CarouselTemplate(columns=columns[:5])
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TemplateMessage(alt_text=f"ข้อบ่งใช้ {drug_name}", template=carousel)]
        )
    )

    # แบ่งออกเป็นชุดละ 5
    carousel_chunks = [columns[i:i + 5] for i in range(0, len(columns), 5)]
    messages = []

    for chunk in carousel_chunks:
        try:
            messages.append(
                TemplateMessage(
                    alt_text=f"ข้อบ่งใช้ {drug_name}",
                    template=CarouselTemplate(columns=chunk)
                )
            )
        except Exception as e:
            logging.info(f"⚠️ ผิดพลาดตอนสร้าง TemplateMessage: {e}")

    # ✅ จำกัดจำนวน messages ไม่เกิน 5
    if len(messages) > 5:
        logging.info(f"⚠️ จำนวน carousel ({len(messages)}) เกิน 5 — ตัดให้เหลือ 5")
        messages = messages[:5]

    
    logging.info(f"📤 ส่ง carousel ทั้งหมด: {len(messages)} ชุด")
    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )
    except Exception as e:
        logging.info(f"❌ ผิดพลาดตอนส่งข้อความ: {e}")

def calculate_warfarin(inr, twd, bleeding):
    if bleeding == "yes":
        return "🚨 มี major bleeding → หยุด Warfarin, ให้ Vitamin K1"
    if inr < 1.5:
        return f"🔹 INR < 1.5 → เพิ่มขนาดยา 10–20%\nขนาดยาใหม่: {twd * 1.1:.1f} – {twd * 1.2:.1f} mg/สัปดาห์"
    elif 1.5 <= inr <= 1.9:
        return f"🔹 INR 1.5–1.9 → เพิ่มขนาดยา 5–10%\nขนาดยาใหม่: {twd * 1.05:.1f} – {twd * 1.10:.1f} mg/สัปดาห์"
    elif 2.0 <= inr <= 3.0:
        return "✅ INR 2.0–3.0 → คงขนาดยาเดิม"
    elif 4.0 <= inr <= 4.9:
        return f"⚠️ INR 4.0–4.9 → หยุดยา 1 วัน และลดขนาดยา 10%\nขนาดยาใหม่: {twd * 0.9:.1f} mg/สัปดาห์"
    else:
        return "🚨 INR ≥ 5.0 → หยุดยา และพิจารณาให้ Vitamin K"

def calculate_dose(drug, indication, weight):
    drug_info = DRUG_DATABASE.get(drug)
    if not drug_info:
        return f"❌ ไม่พบข้อมูลยา {drug}"

    indication_info = drug_info["indications"].get(indication)
    if not indication_info:
        return f"❌ ไม่พบ indication {indication} ใน {drug}"

    conc = drug_info["concentration_mg_per_ml"]
    bottle_size = drug_info["bottle_size_ml"]
    total_ml = 0
    reply_lines = [f"{drug} - {indication} (น้ำหนัก {weight} kg):"]

    # ✅ รองรับหลายช่วงวัน (list)
    if isinstance(indication_info, list):
        for phase in indication_info:
            dose_per_kg = phase["dose_mg_per_kg_per_day"]
            freq = phase["frequency"]
            days = phase["duration_days"]
            max_mg_day = phase.get("max_mg_per_day")

            total_mg_day = weight * dose_per_kg
            if max_mg_day:
                total_mg_day = min(total_mg_day, max_mg_day)

            ml_per_day = total_mg_day / conc
            ml_per_dose = ml_per_day / freq
            ml_phase = ml_per_day * days
            total_ml += ml_phase

            reply_lines.append(
                f"📆 {phase['day_range']}: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
            )
    else:
        dose_per_kg = indication_info["dose_mg_per_kg_per_day"]
        freq = indication_info["frequency"]
        days = indication_info["duration_days"]
        max_mg_day = indication_info.get("max_mg_per_day")

        total_mg_day = weight * dose_per_kg
        if max_mg_day:
            total_mg_day = min(total_mg_day, max_mg_day)

        ml_per_day = total_mg_day / conc
        ml_per_dose = ml_per_day / freq
        total_ml = ml_per_day * days

        reply_lines.append(
            f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
        )

    bottles = math.ceil(total_ml / bottle_size)
    reply_lines.append(f"\nรวมทั้งหมด {total_ml:.1f} ml → จ่าย {bottles} ขวด ({bottle_size} ml)")
    return "\n".join(reply_lines)

@handler.add(MessageEvent)
def handle_message(event: MessageEvent):
# ✅ ตรวจสอบว่าเป็นข้อความข้อความก่อน
    if not isinstance(event.message, TextMessageContent):
        return
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()
    
    if text_lower in ['คำนวณยา warfarin']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_sessions[user_id] = {"flow": "warfarin", "step": "ask_inr"}
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="🧪 กรุณาใส่ค่า INR (เช่น 2.5)")]
            )
        )
        return

    elif text_lower in ['คำนวณขนาดยาเด็ก', 'คำนวณยาเด็ก']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        send_drug_selection(event)
        return

    # ดำเนิน Warfarin flow
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if session.get("flow") == "warfarin":
            step = session.get("step")
            if step == "ask_inr":
                try:
                    session["inr"] = float(text)
                    session["step"] = "ask_twd"
                    reply = "📈 ใส่ Total Weekly Dose (TWD) เช่น 28"
                except:
                    reply = "❌ กรุณาใส่ค่า INR เป็นตัวเลข เช่น 2.5"
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
                return
            elif step == "ask_twd":
                try:
                    session["twd"] = float(text)
                    session["step"] = "ask_bleeding"
                    reply = "🩸 มี major bleeding หรือไม่? (yes/no)"
                except:
                    reply = "❌ กรุณาใส่ค่า TWD เป็นตัวเลข เช่น 28"
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
                return
            elif step == "ask_bleeding":
                if text.lower() not in ["yes", "no"]:
                    reply = "❌ ตอบว่า yes หรือ no เท่านั้น"
                else:
                    result = calculate_warfarin(session["inr"], session["twd"], text.lower())
                    user_sessions.pop(user_id, None)  # จบ session
                    reply = result
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
                return

    if text == "เลือกยาใหม่":
        user_drug_selection.pop(user_id, None)
        send_drug_selection(event)
        return
    # กดปุ่ม "Indication อื่นๆ"
    if text.startswith("MoreIndication:"):
        drug_name = text.replace("MoreIndication:", "").strip()
        send_indication_carousel(event, drug_name, show_all=True)
        return

    if text.startswith("เลือกยา:"):
        drug_name = text.replace("เลือกยา:", "").strip()
        user_drug_selection[user_id] = {"drug": drug_name}

        if drug_name in DRUG_DATABASE:
            send_indication_carousel(event, drug_name)
        else:
            example_weight = round(random.uniform(5.0, 20.0), 1)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"คุณเลือก {drug_name} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น {example_weight}")]
                )
            )
        return

    if text.startswith("Indication:"):
        indication = text.replace("Indication:", "").strip()
        if user_id in user_drug_selection:
            user_drug_selection[user_id]["indication"] = indication
            example_weight = round(random.uniform(5.0, 20.0), 1)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"เลือกข้อบ่งใช้ {indication} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น {example_weight}")]
                )
            )
        return

    if user_id in user_drug_selection:
    # 🌟 ทำความสะอาดข้อความก่อนจับน้ำหนัก
        cleaned_text = text.lower()
        cleaned_text = cleaned_text.replace("กก", "")
        cleaned_text = cleaned_text.replace("kg", "")
        cleaned_text = cleaned_text.replace("น้ำหนัก", "")
        cleaned_text = cleaned_text.replace("หนัก", "")
        cleaned_text = cleaned_text.replace(" ", "")

        match = re.search(r"(\d+(\.\d+)?)", cleaned_text)
        if match:
            weight = float(match.group(1))
            entry = user_drug_selection[user_id]
            drug = entry.get("drug")
            indication = entry.get("indication")

            try:
                reply = calculate_dose(drug, indication, weight)
            except Exception as e:
                logging.info(f"❌ คำนวณผิดพลาด: {e}")
                reply = "เกิดข้อผิดพลาดในการคำนวณ"
        else:
            reply = "กรุณาพิมพ์น้ำหนัก เช่น 20 กก"

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

    if user_id not in user_sessions and user_id not in user_drug_selection:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text="❓ พิมพ์ 'คำนวณยา warfarin' หรือ 'คำนวณยาเด็ก' เพื่อเริ่มต้นใช้งาน")
                ]
            )
        )
        

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='