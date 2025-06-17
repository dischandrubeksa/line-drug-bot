from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import re
import math

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_drug_selection = {}

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
        print(f"❌ Exception occurred: {e}")
        abort(400)
    return 'OK'

def send_drug_selection(event):
    carousel1 = CarouselTemplate(columns=[
        CarouselColumn(title='Paracetamol', text='10–15 mg/kg/dose', actions=[MessageAction(label='เลือก Paracetamol', text='เลือกยา: Paracetamol')]),
        CarouselColumn(title='Cetirizine', text='0.25 mg/kg/day', actions=[MessageAction(label='เลือก Cetirizine', text='เลือกยา: Cetirizine')]),
        CarouselColumn(title='Amoxicillin', text='250 mg/5 ml', actions=[MessageAction(label='เลือก Amoxicillin', text='เลือกยา: Amoxicillin')]),
        CarouselColumn(title='Cephalexin', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cephalexin', text='เลือกยา: Cephalexin')]),
        CarouselColumn(title='Cefdinir', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cefdinir', text='เลือกยา: Cefdinir')])
    ])
    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title='Cefixime', text='100 mg/5 ml', actions=[MessageAction(label='เลือก Cefixime', text='เลือกยา: Cefixime')]),
        CarouselColumn(title='Augmentin', text='600 mg/5 ml', actions=[MessageAction(label='เลือก Augmentin', text='เลือกยา: Augmentin')]),
        CarouselColumn(title='Azithromycin', text='200 mg/5 ml', actions=[MessageAction(label='เลือก Azithromycin', text='เลือกยา: Azithromycin')]),
        CarouselColumn(title='Hydroxyzine', text='10 mg/5 ml', actions=[MessageAction(label='เลือก Hydroxyzine', text='เลือกยา: Hydroxyzine')]),
        CarouselColumn(title='Ferrous drop', text='15 mg/0.6 ml', actions=[MessageAction(label='เลือก Ferrous drop', text='เลือกยา: Ferrous drop')])
    ])
    line_bot_api.reply_message(
        event.reply_token,
        [
            TemplateSendMessage(alt_text="เลือกยากลุ่มแรก", template=carousel1),
            TemplateSendMessage(alt_text="เลือกยากลุ่มเพิ่มเติม", template=carousel2)
        ]
    )

def send_amoxicillin_indications(event):
    carousel1 = CarouselTemplate(columns=[
        CarouselColumn(title="Pharyngitis", text="25–50 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Pharyngitis", text="Indication: Pharyngitis")
        ]),
        CarouselColumn(title="Otitis Media", text="80–90 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Otitis Media", text="Indication: Otitis Media")
        ]),
        CarouselColumn(title="Pneumonia", text="90 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Pneumonia", text="Indication: Pneumonia")
        ]),
        CarouselColumn(title="Anthrax", text="75 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก Anthrax", text="Indication: Anthrax")
        ]),
        CarouselColumn(title="H. pylori", text="50 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก H. pylori", text="Indication: H. pylori")
        ]),
    ])

    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title="UTI", text="50–100 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก UTI", text="Indication: UTI")
        ]),
        CarouselColumn(title="Sinusitis", text="45–90 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Sinusitis", text="Indication: Sinusitis")
        ]),
        CarouselColumn(title="Endocarditis", text="50 mg/kg once", actions=[
            MessageAction(label="เลือก Endocarditis", text="Indication: Endocarditis")
        ]),
        CarouselColumn(title="Lyme Disease", text="50 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก Lyme Disease", text="Indication: Lyme Disease")
        ]),
        CarouselColumn(title="Osteoarticular", text="80–120 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก Osteoarticular", text="Indication: Osteoarticular")
        ]),
    ])

    line_bot_api.reply_message(
        event.reply_token,
        [
            TemplateSendMessage(alt_text="เลือกข้อบ่งใช้ของ Amoxicillin", template=carousel1),
            TemplateSendMessage(alt_text="เลือกข้อบ่งใช้อื่นๆ", template=carousel2)
        ]
    )

def send_cephalexin_indications(event):
    carousel = CarouselTemplate(columns=[
        CarouselColumn(title="Skin/Skin Structure", text="25–50 mg/kg/day ÷ 4", actions=[
            MessageAction(label="เลือก SSTI", text="Indication: Cephalexin-SSTI")
        ]),
        CarouselColumn(title="Pharyngitis", text="25–50 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Pharyngitis", text="Indication: Cephalexin-Pharyngitis")
        ]),
        CarouselColumn(title="UTI", text="50–100 mg/kg/day ÷ 4", actions=[
            MessageAction(label="เลือก UTI", text="Indication: Cephalexin-UTI")
        ])
    ])

    line_bot_api.reply_message(
        event.reply_token,
        [TemplateSendMessage(alt_text="เลือกข้อบ่งใช้ของ Cephalexin", template=carousel)]
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.lower() in ['คำนวณยา', 'dose', 'เริ่ม']:
        send_drug_selection(event)
        return

    if text == "เลือกยาใหม่":
        user_drug_selection.pop(user_id, None)
        send_drug_selection(event)
        return

    if text.startswith("เลือกยา:"):
        drug_name = text.replace("เลือกยา:", "").strip()
        user_drug_selection[user_id] = {"drug": drug_name}

    if drug_name == "Amoxicillin":
        send_amoxicillin_indications(event)
    elif drug_name == "Cephalexin":
        send_cephalexin_indications(event)
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"คุณเลือก {drug_name} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20")
        )
    return


    if text.startswith("Indication:"):
        indication = text.replace("Indication:", "").strip()
        if user_id in user_drug_selection:
            user_drug_selection[user_id]["indication"] = indication
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"เลือกข้อบ่งใช้ {indication} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20")
            )
        return

    if user_id in user_drug_selection:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            weight = float(match.group(1))
            entry = user_drug_selection[user_id]
            drug = entry.get("drug")

            try:
                if drug == "Amoxicillin":
                    indication = entry.get("indication", "ทั่วไป")
                    dose_map = {
                        "Pharyngitis": (50, 10),
                        "Otitis Media": (90, 10),
                        "Pneumonia": (90, 7),
                        "Anthrax": (75, 60),
                        "H. pylori": (62.5, 14),
                        "UTI": (75, 7),
                        "Sinusitis": (90, 10),
                        "Endocarditis": (50, 1),
                        "Lyme Disease": (50, 14),
                        "Osteoarticular": (100, 14)
                    }
                    max_dose = {
                        "Pneumonia": 4000,
                        "Anthrax": 1000,
                        "UTI": 500,
                        "Sinusitis": 2000,
                        "Endocarditis": 2000,
                        "Lyme Disease": 500,
                        "Osteoarticular": 4000
                    }

                    dose_per_kg, days = dose_map.get(indication, (50, 7))
                    conc = 250 / 5  # 50 mg/ml
                    bottle_size = 60  # ml

                    total_mg_day = weight * dose_per_kg
                    if indication in max_dose:
                        total_mg_day = min(total_mg_day, max_dose[indication])
                    ml_per_day = total_mg_day / conc
                    ml_per_dose = ml_per_day / 2
                    total_ml = ml_per_day * days
                    bottles = math.ceil(total_ml / bottle_size)

                    reply = (
                        f"{drug} - {indication} (น้ำหนัก {weight} kg):"
                        f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/วัน"
                        f"≈ {ml_per_day:.1f} ml/วัน, ครั้งละ ~{ml_per_dose:.1f} ml วันละ 2 ครั้ง"
                        f"ใช้ {days} วัน รวม {total_ml:.1f} ml → จ่าย {bottles} ขวด ({bottle_size} ml)"
                    )
                elif drug == "Cephalexin":
                    indication = entry.get("indication", "ทั่วไป")
                    dose_map = {
                        "Cephalexin-SSTI": (50, 7, 4),
                        "Cephalexin-Pharyngitis": (50, 10, 2),
                        "Cephalexin-UTI": (100, 7, 4)
                    }
                    conc = 125 / 5  # 25 mg/ml
                    bottle_size = 60

                    dose_info = dose_map.get(indication)
                    if not dose_info:
                        reply = f"ยังไม่มีข้อมูลการคำนวณสำหรับ {indication}"
                    else:
                        dose_per_kg, days, freq = dose_info
                        total_mg_day = weight * dose_per_kg
                        ml_per_day = total_mg_day / conc
                        ml_per_dose = ml_per_day / freq
                        total_ml = ml_per_day * days
                        bottles = math.ceil(total_ml / bottle_size)

                        reply = (
                            f"{drug} - {indication} (น้ำหนัก {weight} kg):\n"
                            f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/วัน\n"
                            f"≈ {ml_per_day:.1f} ml/วัน, ครั้งละ ~{ml_per_dose:.1f} ml วันละ {freq} ครั้ง\n"
                            f"ใช้ {days} วัน รวม {total_ml:.1f} ml → จ่าย {bottles} ขวด ({bottle_size} ml)"
                        )
                else:
                    reply = f"ยังไม่รองรับยา {drug}"

                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

            except Exception as e:
                print(f"❌ Error in calculation: {e}")
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="เกิดข้อผิดพลาดในการคำนวณ"))
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="กรุณาพิมพ์น้ำหนัก เช่น 20")
            )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='