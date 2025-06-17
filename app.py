from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import re
import math

# ✅ ควรวาง DRUG_DATABASE ที่นี่ ก่อน app = Flask(...)
DRUG_DATABASE = {
    "Amoxicillin": {
        "Pharyngitis": (50, 10, 2),
        "Otitis Media": (90, 10, 2),
        "Pneumonia": (90, 7, 2),
        "Anthrax": (75, 60, 3),
        "H. pylori": (62.5, 14, 2),
        "UTI": (75, 7, 3),
        "Sinusitis": (90, 10, 2),
        "Endocarditis": (50, 1, 1),
        "Lyme Disease": (50, 14, 3),
        "Osteoarticular": (100, 14, 3)
    },
    "Cephalexin": {
        "SSTI": (50, 7, 4),
        "Pharyngitis": (50, 10, 2),
        "UTI": (100, 7, 4)
    },
    "Cefdinir": {
        "Otitis Media": (14, 10, 2),
        "Pharyngitis": (14, 10, 2),
        "Rhinosinusitis": (14, 10, 2)
    }
}

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

def send_indication_carousel(event, drug_name):
    indications = DRUG_DATABASE.get(drug_name, {})
    if not indications:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"ยังไม่มีข้อบ่งใช้สำหรับ {drug_name}")
        )
        return

    columns = []
    for name in indications:
        actions = [MessageAction(label=f"เลือก {name}", text=f"Indication: {name}")]
        columns.append(CarouselColumn(title=name[:40], text=f"{drug_name} indication", actions=actions))

    carousels = [columns[i:i+5] for i in range(0, len(columns), 5)]
    messages = [TemplateSendMessage(
        alt_text=f"ข้อบ่งใช้ {drug_name}",
        template=CarouselTemplate(columns=chunk)
    ) for chunk in carousels]

    line_bot_api.reply_message(event.reply_token, messages)

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

        if drug_name in DRUG_DATABASE:
            send_indication_carousel(event, drug_name)
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
                if drug in DRUG_DATABASE:
                    indication = entry.get("indication")
                    dose_info = DRUG_DATABASE[drug].get(indication)
                    
                    if not dose_info:
                      reply = f"ยังไม่มีข้อมูลการคำนวณสำหรับ {drug} - {indication}"
                    else:
                        dose_per_kg, days, freq = dose_info
                        # ใช้ค่าเฉพาะของยา (mg/ml)
                        if drug == "Amoxicillin":
                            conc = 250 / 5  # 50 mg/ml
                        elif drug == "Cephalexin":
                            conc = 125 / 5  # 25 mg/ml
                        elif drug == "Cefdinir":
                            conc = 125 / 5  # 25 mg/ml
                        else:
                            conc = 250 / 5  # default fallback
                        
                        bottle_size = 60  # ml

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