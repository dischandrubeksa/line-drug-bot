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
        CarouselColumn(title="Anthrax", text="60 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก Anthrax", text="Indication: Anthrax")
        ]),
        CarouselColumn(title="H. pylori", text="50 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก H. pylori", text="Indication: H. pylori")
        ]),
    ])
    
    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title="UTI", text="25–50 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก UTI", text="Indication: UTI")
        ]),
        CarouselColumn(title="Sinusitis", text="45 mg/kg/day ÷ 2", actions=[
            MessageAction(label="เลือก Sinusitis", text="Indication: Sinusitis")
        ]),
        CarouselColumn(title="Endocarditis Prophylaxis", text="50 mg/kg once", actions=[
            MessageAction(label="เลือก Endocarditis", text="Indication: Endocarditis")
        ]),
        CarouselColumn(title="Lyme Disease", text="50 mg/kg/day ÷ 3", actions=[
            MessageAction(label="เลือก Lyme Disease", text="Indication: Lyme Disease")
        ]),
        CarouselColumn(title="Osteoarticular Infection", text="90 mg/kg/day ÷ 2", actions=[
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
                if drug == "Paracetamol":
                    dose_min = weight * 10
                    dose_max = weight * 15
                    reply = f"Paracetamol: {dose_min:.2f} – {dose_max:.2f} mg ต่อครั้ง"

                elif drug == "Cetirizine":
                    dose = weight * 0.25
                    reply = f"Cetirizine: {dose:.2f} mg ต่อวัน"

                elif drug == "Domperidone":
                    dose = weight * 0.25
                    reply = f"Domperidone: {dose:.2f} mg ≈ {dose:.2f} ml ต่อครั้ง"

                elif drug == "Hydroxyzine":
                    dose = weight * 0.5
                    volume = dose / (10 / 5)
                    reply = f"Hydroxyzine: {dose:.2f} mg ≈ {volume:.2f} ml ต่อครั้ง"

                elif drug == "Ferrous drop":
                    dose = weight * 3
                    volume = dose / (15 / 0.6)
                    reply = f"Ferrous fumarate: {dose:.2f} mg ≈ {volume:.2f} ml ต่อวัน"

                elif drug == "Amoxicillin":
                    indication = entry.get("indication")
                    if indication == "Pharyngitis":
                        dose_min = weight * 25
                        dose_max = weight * 50
                        reply = f"Amoxicillin (Pharyngitis): {dose_min:.0f}–{dose_max:.0f} mg/วัน ÷ 2 ครั้ง"
                    elif indication == "Otitis Media":
                        dose = weight * 90
                        reply = f"Amoxicillin (Otitis Media): {dose:.0f} mg/วัน ÷ 2 ครั้ง"
                    elif indication == "Sinusitis":
                        dose = weight * 45
                        reply = f"Amoxicillin (Sinusitis): {dose:.0f} mg/วัน ÷ 2 ครั้ง"
                    elif indication == "Pneumonia":
                        dose = weight * 90
                        reply = f"Amoxicillin (Pneumonia): {dose:.0f} mg/วัน ÷ 2 ครั้ง"   
                    elif indication == "Anthrax":
                        dose = weight * 60
                        reply = f"Amoxicillin (Anthrax): {dose:.0f} mg/วัน ÷ 3 ครั้ง"
                    elif indication == "H. pylori":
                        dose = weight * 50
                        reply = f"Amoxicillin (H. pylori): {dose:.0f} mg/วัน ÷ 2 ครั้ง"
                    elif indication == "UTI":
                        dose_min = weight * 25
                        dose_max = weight * 50
                        reply = f"Amoxicillin (UTI): {dose_min:.0f}–{dose_max:.0f} mg/วัน ÷ 2 ครั้ง"
                    elif indication == "Endocarditis":
                        dose = weight * 50
                        reply = f"Amoxicillin (Endocarditis): {dose:.0f} mg once"
                    elif indication == "Lyme Disease":
                        dose = weight * 50
                        reply = f"Amoxicillin (Lyme Disease): {dose:.0f} mg/วัน ÷ 3 ครั้ง"
                    elif indication == "Osteoarticular":
                        dose = weight * 90
                        reply = f"Amoxicillin (Osteoarticular): {dose:.0f} mg/วัน ÷ 2 ครั้ง"
                    else:
                        reply = "กรุณาเลือกข้อบ่งใช้ของ Amoxicillin ก่อนครับ"

                elif drug in ["Cephalexin", "Cefdinir", "Cefixime", "Augmentin", "Azithromycin"]:
                    settings = {
                        "Cephalexin":    {"dose": 50, "conc": 125 / 5, "bottle": 60, "days": 7},
                        "Cefdinir":      {"dose": 14, "conc": 125 / 5, "bottle": 30, "days": 5},
                        "Cefixime":      {"dose": 8,  "conc": 100 / 5, "bottle": 30, "days": 5},
                        "Augmentin":     {"dose": 90, "conc": 600 / 5, "bottle": 70, "days": 10},
                        "Azithromycin":  {"dose": 10, "conc": 200 / 5, "bottle": 15, "days": 3}
                    }

                    cfg = settings[drug]
                    total_mg_day = weight * cfg["dose"]
                    ml_per_day = total_mg_day / cfg["conc"]
                    total_ml = ml_per_day * cfg["days"]
                    bottles = math.ceil(total_ml / cfg["bottle"])

                    reply = (
                        f"{drug}:\n"
                        f"{total_mg_day:.0f} mg/วัน ≈ {ml_per_day:.1f} ml/วัน\n"
                        f"ใช้ {cfg['days']} วัน รวม {total_ml:.1f} ml → จ่าย {bottles} ขวด ({cfg['bottle']} ml)"
                    )
                else:
                    reply = "ขออภัย ยังไม่รองรับตัวยานี้ครับ"

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