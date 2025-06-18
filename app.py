ทำให้ยา prn ไม่ใส่ระยะเวลา ใช้กี่ขวด จัดการคำที่ชอบขึ้นมาพร้อม autoresponse


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
user_ages = {}


SPECIAL_DRUGS = {
    "Paracetamol": {
    "concentration_mg_per_ml": 160 / 5,
    "bottle_size_ml": 60,
    "indications": {
        "Fever": [
            {
                "min_age_years": 0,
                "max_age_years": 6,
                "dose_mg_per_kg_per_day": 60,
                "frequency": 4,
                "duration_days": 3,
                "max_mg_per_dose": 250
            },
            {
                "min_age_years": 6,
                "max_age_years": 18,
                "dose_mg_per_kg_per_day": 60,
                "frequency": 4,
                "duration_days": 3,
                "max_mg_per_dose": 500
            }
        ]
    },
    "common_indications": ["Fever"]
    },
    "Cetirizine": {
    "concentration_mg_per_ml": 1 / 1,
    "bottle_size_ml": 60,
    "indications": {
      "Allergic rhinitis, perennial": {
        "6_to_11_months": {
          "dose_mg": 2.5,
          "frequency": 1,
          "max_mg_per_day": 2.5
        },
        "12_to_23_months": {
          "initial_dose_mg": 2.5,
          "frequency": 1,
          "max_frequency": 2,
          "max_mg_per_day": 5
        }
      },
      "Allergic symptoms, hay fever": {
        "2_to_5_years": {
          "initial_dose_mg": 2.5,
          "frequency": 1,
          "options": [
            {"dose_mg": 2.5, "frequency": 2},
            {"dose_mg": 5, "frequency": 1}
          ],
          "max_mg_per_day": 5
        },
        "above_or_equal_6": {
          "dose_mg_range": [5, 10],
          "frequency": 1,
          "max_mg_per_day": 10
        }
      },
      "Anaphylaxis (adjunctive only)": {
        "6_to_23_months": {
          "dose_mg": 2.5,
          "frequency": 1,
          "max_mg_per_day": 2.5
        },
        "2_to_5_years": {
          "dose_range_mg": [2.5, 5],
          "frequency": 1,
          "max_mg_per_day": 5
        },
        "above_5": {
          "dose_range_mg": [5, 10],
          "frequency": 1,
          "max_mg_per_day": 10
        }
      },
      "Urticaria, acute": {
        "6_to_23_months": {
          "dose_mg": 2.5,
          "frequency": 1
        },
        "2_to_5_years": {
          "dose_range_mg": [2.5, 5],
          "frequency": 1
        },
        "above_5": {
          "dose_range_mg": [5, 10],
          "frequency": 1
        }
      },
      "Urticaria, chronic spontaneous": {
        "6_to_11_months": {
          "dose_mg": 2.5,
          "frequency": 1
        },
        "12_to_23_months": {
          "initial_dose_mg": 2.5,
          "frequency": 1,
          "max_frequency": 2,
          "max_mg_per_day": 5
        },
        "2_to_5_years": {
          "initial_dose_mg": 2.5,
          "frequency": 1,
          "options": [
            {"dose_mg": 2.5, "frequency": 2},
            {"dose_mg": 5, "frequency": 1}
          ],
          "max_mg_per_day": 5
        },
        "6_to_11_years": {
          "dose_mg": 5,
          "frequency_options": [1, 2]
        },
        "above_or_equal_12": {
          "dose_mg": 10,
          "frequency": 1
        }
      }
    },
    "common_indications": [
      "Allergic rhinitis, perennial",
      "Allergic symptoms, hay fever",
      "Anaphylaxis (adjunctive only)",
      "Urticaria, acute",
      "Urticaria, chronic spontaneous"
    ]
    },
    "Hydroxyzine": {
        "concentration_mg_per_ml": 10 / 5 ,
        "bottle_size_ml": 60,
        "indications": {
        "Anxiety": {
            "under_6": {
            "dose_mg": 12.5,
            "frequency": 4,
            "max_mg_per_dose": 12.5
            },
            "above_or_equal_6": {
            "dose_mg_range": [12.5, 25],
            "frequency": 4,
            "max_mg_per_dose": 25
            }
        },
        "Pruritus (age-based)": {
            "under_6": {
            "dose_mg": 12.5,
            "frequency": [3, 4],
            "max_mg_per_dose": 12.5
            },
            "above_or_equal_6": {
            "dose_mg_range": [12.5, 25],
            "frequency": [3, 4],
            "max_mg_per_dose": 25
            }
        },
        "Pruritus (weight_based)": {
            "≤40kg": {
                "dose_mg_per_kg_per_day": 2,
                "frequency": [6, 8],
                "max_mg_per_dose": 25
            },
            ">40kg": {
                "dose_mg_range": [25, 50],
                "frequency": [1, 2],
                "max_mg_per_dose": 50
            }
        },
        "Pruritus from opioid": {
            "all_ages": {
            "dose_mg_per_kg_per_dose": 0.5,
            "frequency": 6,
            "max_mg_per_dose": 50
            }
        },
        "Sedation": {
            "all_ages": {
            "dose_mg_per_kg": 0.6,
            "max_mg_per_dose": 100
            }
        }
        },
        "common_indications": [
        "Anxiety",
        "Pruritus (age-based)",
        "Pruritus (weight_based)",
        "Pruritus from opioid",
        "Sedation"
        ]
    },
    "Ferrous drop": {
        "concentration_mg_per_ml": 15 / 0.6 ,
        "bottle_size_ml": 60,
        "indications": {
        "Iron deficiency, treatment": {
            "all_ages": {
            "initial_dose_mg_per_kg_per_day": 3,
            "max_dose_range_mg_per_day": [60, 120],
            "usual_max_mg_per_day": 150,
            "absolute_max_mg_per_day": 200,
            "frequency": [1, 3],
            "note": "ให้ครั้งเดียว หรือแบ่งวันละ 1–3 ครั้งได้; การให้วันเว้นวันอาจช่วยดูดซึมดีขึ้น"
            }
        }
        },
        "common_indications": [
        "Iron deficiency, treatment"
        ]
    }
    }

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
    return

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
    common = drug_info.get("common_indications", [])

    if not show_all and common:
        names_to_show = common + ["Indication อื่นๆ"]
    else:
        names_to_show = [name for name in indications.keys() if name not in common and name != "Other"]

    columns = []

    for name in names_to_show:
        label = "เลือก"
        title = name[:40] if len(name) > 40 else name

        if name != "Indication อื่นๆ":
            indication_info = indications[name]
            if isinstance(indication_info, list):
                text = f"{indication_info[0]['dose_mg_per_kg_per_day']} mg/kg/day"
            else:
                text = f"{indication_info['dose_mg_per_kg_per_day']} mg/kg/day"
            action_text = f"Indication: {name}"
        else:
            text = "ดูข้อบ่งใช้อื่นทั้งหมด"
            action_text = f"MoreIndication: {drug_name}"

        actions = [MessageAction(label=label, text=action_text)]
        columns.append(CarouselColumn(title=title, text=text, actions=actions))

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

    logging.info(f"📤 ส่ง carousel ทั้งหมด: {len(messages)} ชุด")
    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )
        return
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
            if "max_mg_per_dose" in phase:
                ml_per_dose = min(ml_per_dose, phase["max_mg_per_dose"] / conc)
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
        if "max_mg_per_dose" in indication_info:
            ml_per_dose = min(ml_per_dose, indication_info["max_mg_per_dose"] / conc)
        total_ml = ml_per_day * days

        reply_lines.append(
            f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
        )

    bottles = math.ceil(total_ml / bottle_size)
    reply_lines.append(f"\nรวมทั้งหมด {total_ml:.1f} ml → จ่าย {bottles} ขวด ({bottle_size} ml)")
    return "\n".join(reply_lines)

def calculate_special_drug(user_id, drug, weight, age):
    info = SPECIAL_DRUGS[drug]
    indication = user_drug_selection.get(user_id, {}).get("indication")

    if drug == "Hydroxyzine" and indication == "Pruritus (weight_based)":
        data = info["indications"][indication]
        if weight <= 40:
            profile = data["\u226440kg"]  # ≤ = less than or equal to
            dose_per_kg = profile["dose_mg_per_kg_per_day"]
            freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
            max_dose = profile["max_mg_per_dose"]

            total_mg_day = weight * dose_per_kg
            reply_lines = [f"{drug} - {indication} (\u226440kg):"]
            for freq in freqs:
                dose_per_time = min(total_mg_day / freq, max_dose)
                reply_lines.append(f"💊 {total_mg_day:.1f} mg/day → {freq} ครั้ง/วัน → ครั้งละ ~{dose_per_time:.1f} mg")
            return "\n".join(reply_lines)

        else:
            profile = data[">40kg"]
            dose_range = profile["dose_mg_range"]
            freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
            max_dose = profile["max_mg_per_dose"]

            reply_lines = [f"{drug} - {indication} (>40kg):"]
            for freq in freqs:
                for dose in dose_range:
                    dose_per_time = min(dose, max_dose)
                    reply_lines.append(f"💊 {dose_per_time:.1f} mg × {freq} ครั้ง/วัน")
            return "\n".join(reply_lines)
    
    if drug == "Cetirizine":
        indication_info = info["indications"].get(indication)
        if not indication_info:
            return f"❌ ไม่พบข้อบ่งใช้ {indication}"

        age_group = None
        if age < 1:
            age_group = "6_to_11_months"
        elif 1 <= age < 2:
            age_group = "12_to_23_months"
        elif 2 <= age <= 5:
            age_group = "2_to_5_years"
        elif 6 <= age <= 11:
            age_group = "6_to_11_years"
        elif age >= 12:
            age_group = "above_or_equal_12"
        elif age > 5:
            age_group = "above_5"

        group_data = indication_info.get(age_group)
        if not group_data:
            return f"❌ ไม่พบข้อมูลกลุ่มอายุ {age_group}"

        lines = [f"{drug} - {indication} (อายุ {age} ปี):"]
        if "dose_mg" in group_data:
            lines.append(f"💊 ขนาดยา: {group_data['dose_mg']} mg × {group_data['frequency']} ครั้ง/วัน")
        elif "initial_dose_mg" in group_data:
            options = group_data.get("options", [])
            lines.append(f"💊 เริ่มต้น {group_data['initial_dose_mg']} mg × {group_data['frequency']} ครั้ง/วัน")
            for opt in options:
                lines.append(f"หรือ: {opt['dose_mg']} mg × {opt['frequency']} ครั้ง/วัน")
        elif "dose_range_mg" in group_data:
            for dose in group_data["dose_range_mg"]:
                lines.append(f"💊 ขนาดยา: {dose} mg × {group_data['frequency']} ครั้ง/วัน")
        elif "dose_mg_range" in group_data:
            for dose in group_data["dose_mg_range"]:
                lines.append(f"💊 ขนาดยา: {dose} mg × {group_data['frequency']} ครั้ง/วัน")
        elif "dose_mg" in group_data and "frequency_options" in group_data:
            for freq in group_data["frequency_options"]:
                lines.append(f"💊 ขนาดยา: {group_data['dose_mg']} mg × {freq} ครั้ง/วัน")

        return "\n".join(lines)
    
    if drug == "Ferrous drop":
        indication_info = info["indications"][indication]["all_ages"]
        dose_per_kg = indication_info["initial_dose_mg_per_kg_per_day"]
        freqs = indication_info["frequency"]
        max_range = indication_info["max_dose_range_mg_per_day"]
        usual_max = indication_info.get("usual_max_mg_per_day")
        absolute_max = indication_info.get("absolute_max_mg_per_day")

        total_mg_day = weight * dose_per_kg
        total_mg_day = min(max(total_mg_day, max_range[0]), max_range[1])
        if absolute_max:
            total_mg_day = min(total_mg_day, absolute_max)

        reply_lines = [f"{drug} - {indication} (น้ำหนัก {weight} kg):"]
        reply_lines.append(f"💊 {dose_per_kg} mg/kg/day → {total_mg_day:.1f} mg/day")

        for freq in freqs:
            reply_lines.append(f"→ {freq} ครั้ง/วัน → ครั้งละ ~{(total_mg_day / freq):.1f} mg")

        if "note" in indication_info:
            reply_lines.append(f"\n📌 หมายเหตุ: {indication_info['note']}")

        return "\n".join(reply_lines)

    # กรณีพิเศษอื่น ๆ เช่น Paracetamol (ใช้แบบเดิม)
    indication_info = next(iter(info["indications"].values()))
    for entry in indication_info:
        if entry["min_age_years"] <= age < entry["max_age_years"]:
            dose_per_kg = entry["dose_mg_per_kg_per_day"]
            freq = entry["frequency"]
            duration = entry["duration_days"]
            max_dose = entry["max_mg_per_dose"]

            total_mg_day = weight * dose_per_kg
            dose_per_time = min(total_mg_day / freq, max_dose)

            return (
                f"{drug} (อายุ {age} ปี, น้ำหนัก {weight} kg):\n"
                f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.1f} mg/day\n"
                f"แบ่ง {freq} ครั้ง/วัน → ครั้งละ ~{dose_per_time:.1f} mg เป็นเวลา {duration} วัน"
            )

    return f"❌ ไม่พบขนาดยาที่เหมาะสมสำหรับอายุ {age} ปีใน {drug}"


def send_special_indication_carousel(event, drug_name):
    drug_info = SPECIAL_DRUGS.get(drug_name)
    if not drug_info or "indications" not in drug_info:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"ไม่พบข้อบ่งใช้ของ {drug_name}")]
            )
        )
        return

    indications = drug_info["indications"]
    common = drug_info.get("common_indications", [])

    names_to_show = common
    columns = []

    for name in names_to_show:
        title = name[:40]
        indication_info = indications[name]

        try:
            if isinstance(indication_info, list):
                dose = indication_info[0].get("dose_mg_per_kg_per_day") or "?"
            elif isinstance(indication_info, dict):
                # หา dose แบบยืดหยุ่น
                sample_group = next(iter(indication_info.values()))
                if isinstance(sample_group, dict):
                    dose = sample_group.get("dose_mg") or sample_group.get("initial_dose_mg") \
                        or sample_group.get("dose_mg_range", ["?"])[0] \
                        or sample_group.get("dose_range_mg", ["?"])[0]
                else:
                    dose = "?"
            else:
                dose = "?"
        except Exception as e:
            dose = "?"

        columns.append(CarouselColumn(
            title=title,
            text=f"{dose} mg",
            actions=[MessageAction(label="เลือก", text=f"Indication: {name}")]
        ))


    carousel_template = CarouselTemplate(columns=columns)
    messages = [TemplateMessage(
        alt_text=f"ข้อบ่งใช้ {drug_name}",
        template=carousel_template
    )]

    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=messages
        )
    )
    return


@handler.add(MessageEvent)
def handle_message(event: MessageEvent):
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
        user_ages.pop(user_id, None)
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
        user_ages.pop(user_id, None)
        send_drug_selection(event)
        return

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
            send_special_indication_carousel(event, drug_name)
        return

    if text.startswith("Indication:") and user_id in user_drug_selection:
        indication = text.replace("Indication:", "").strip()
        user_drug_selection[user_id]["indication"] = indication
        drug = user_drug_selection[user_id].get("drug")

        if user_id in user_ages:
            user_ages.pop(user_id)

        if drug in SPECIAL_DRUGS:
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="📆 กรุณาพิมพ์อายุของเด็ก เช่น 5 ปี")]
                )
            )
        else:
            example_weight = round(random.uniform(5.0, 20.0), 1)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"เลือกข้อบ่งใช้ {indication} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น {example_weight}")]
                )
            )
        return
    
    if user_id in user_drug_selection:

        # 🛠 แก้การจับอายุ: ใช้ .group(0) และใส่ try-except
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["อายุ", "ปี", "y", "ขวบ", "เดือน", "mo"]):
            try:
                # ตรวจจับปีและเดือน
                years = 0
                months = 0

                year_match = re.search(r"(\d+(?:\.\d+)?)\s*(ปี|y|ขวบ)", text_lower)
                if year_match:
                    years = float(year_match.group(1))

                month_match = re.search(r"(\d+(?:\.\d+)?)\s*(เดือน|mo)", text_lower)
                if month_match:
                    months = float(month_match.group(1))

                if not year_match and not month_match:
                    raise ValueError("ไม่พบปีหรือเดือน")

                age_years = round(years + months / 12, 2)

                if 0 <= age_years <= 18:
                    user_ages[user_id] = age_years
                    example_weight = round(random.uniform(5.0, 20.0), 1)
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"🎯 อายุ {age_years:.2f} ปีแล้ว กรุณาใส่น้ำหนัก เช่น {example_weight} กก")]
                        )
                    )
                else:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ กรุณาใส่อายุระหว่าง 0–18 ปี (หรือเป็นเดือนก็ได้)")]
                        )
                    )
                return

            except:
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ กรุณาพิมพ์อายุให้ถูกต้อง เช่น 6 เดือน หรือ 1 ปี 6 เดือน หรือ 2 ขวบ")]
                    )
                )
                return

        if any(kw in text_lower for kw in ["น้ำหนัก", "กก", "kg"]) or text.replace(".", "", 1).isdigit():
            weight_match = re.search(r"(\d+(\.\d+)?)", text)
            if weight_match:
                try:
                    weight = float(weight_match.group(1))
                except ValueError:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ กรุณาพิมพ์น้ำหนักให้ถูกต้อง เช่น 20 กก")]
                        )
                    )

                entry = user_drug_selection[user_id]
                drug = entry.get("drug")

                if drug in SPECIAL_DRUGS:
                    age = user_ages.get(user_id)
                    if age is None:
                        # แจ้งให้ใส่อายุก่อน แล้วค่อยพิมพ์น้ำหนักอีกครั้ง
                        messaging_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="📆 กรุณาพิมพ์อายุของเด็กก่อน เช่น 5 ปี\nจากนั้นพิมพ์น้ำหนักอีกครั้ง")]
                            )
                        )
                        return  # หยุดการทำงานที่นี่เลย
                    else:
                        try:
                            reply = calculate_special_drug(user_id, drug, weight, age)
                        except Exception as e:
                            logging.info(f"❌ คำนวณผิดพลาดใน SPECIAL_DRUG: {e}")
                            reply = "เกิดข้อผิดพลาดในการคำนวณยา"
                else:
                    if "indication" not in entry:
                        reply = "❗️ กรุณาเลือกข้อบ่งใช้ก่อน เช่น 'Indication: Fever'"
                    else:
                        indication = entry["indication"]
                        try:
                            reply = calculate_dose(drug, indication, weight)
                        except Exception as e:
                            logging.info(f"❌ คำนวณผิดพลาดใน DRUG_DATABASE: {e}")
                            reply = "เกิดข้อผิดพลาดในการคำนวณยา"

                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
                return

        else:
            # ถ้าไม่มีคำว่า "อายุ" หรือ "น้ำหนัก" ให้แจ้งเตือน
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❗️ กรุณาพิมพ์อายุ เช่น '5 ปี' หรือ น้ำหนัก เช่น '18 กก'")]
                )
            )
            return

    if user_id not in user_sessions and user_id not in user_drug_selection:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text="❓ พิมพ์ 'คำนวณยา warfarin' หรือ 'คำนวณยาเด็ก' เพื่อเริ่มต้นใช้งาน")
                ]
            )
        )
        return
        

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='