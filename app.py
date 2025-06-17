from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import re
import math

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='

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

    print("📩 Received body:", body)
    print("🧾 Signature:", signature)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid Signature — กรุณาตรวจสอบ LINE_CHANNEL_SECRET")
        abort(400)
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        abort(400)
    return 'OK'

def send_drug_selection(event):
    user_id = event.source.user_id

    carousel1 = CarouselTemplate(columns=[
        CarouselColumn(title='Paracetamol', text='10–15 mg/kg/dose', actions=[MessageAction(label='เลือก Paracetamol', text='เลือกยา: Paracetamol')]),
        CarouselColumn(title='Cetirizine', text='0.25 mg/kg/day', actions=[MessageAction(label='เลือก Cetirizine', text='เลือกยา: Cetirizine')]),
        CarouselColumn(title='Amoxicillin', text='250 mg/5 ml', actions=[MessageAction(label='เลือก Amoxicillin', text='เลือกยา: Amoxicillin')]),
        CarouselColumn(title='Cephalexin', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cephalexin', text='เลือกยา: Cephalexin')]),
        CarouselColumn(title='Cefdinir', text='125 mg/5 ml', actions=[MessageAction(label='เลือก Cefdinir', text='เลือกยา: Cefdinir')]),
        CarouselColumn(title='Cefixime', text='100 mg/5 ml', actions=[MessageAction(label='เลือก Cefixime', text='เลือกยา: Cefixime')]),
        CarouselColumn(title='Augmentin', text='600 mg/5 ml', actions=[MessageAction(label='เลือก Augmentin', text='เลือกยา: Augmentin')]),
        CarouselColumn(title='Azithromycin', text='200 mg/5 ml', actions=[MessageAction(label='เลือก Azithromycin', text='เลือกยา: Azithromycin')]),
        CarouselColumn(title='Hydroxyzine', text='10 mg/5 ml', actions=[MessageAction(label='เลือก Hydroxyzine', text='เลือกยา: Hydroxyzine')]),
        CarouselColumn(title='Ferrous drop', text='15 mg/0.6 ml', actions=[MessageAction(label='เลือก Ferrous drop', text='เลือกยา: Ferrous drop')])
    ])

    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title='Salbutamol', text='2 mg/5 ml', actions=[MessageAction(label='เลือก Salbutamol', text='เลือกยา: Salbutamol')]),
        CarouselColumn(title='Chlorpheniramine', text='2 mg/5 ml', actions=[MessageAction(label='เลือก Chlorpheniramine', text='เลือกยา: Chlorpheniramine')]),
        CarouselColumn(title='Domperidone', text='1 mg/ml', actions=[MessageAction(label='เลือก Domperidone', text='เลือกยา: Domperidone')])
    ])

    line_bot_api.reply_message(
        event.reply_token,
        TemplateSendMessage(alt_text="เลือกยากลุ่มแรก", template=carousel1)
    )

    line_bot_api.push_message(
        user_id,
        TemplateSendMessage(alt_text="เลือกยากลุ่มเพิ่มเติม", template=carousel2)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.lower() in ['คำนวณยา', 'dose', 'เริ่ม']:
        send_drug_selection(event)
        return

    if text == "เลือกยาใหม่":
        if user_id in user_drug_selection:
            del user_drug_selection[user_id]
        send_drug_selection(event)
        return

    if text.startswith("เลือกยา:"):
        drug_name = text.replace("เลือกยา:", "").strip()
        user_drug_selection[user_id] = drug_name
        reply = f"คุณเลือก {drug_name} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_id in user_drug_selection:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            weight = float(match.group(1))
            drug = user_drug_selection[user_id]

            try:
                if drug == "Paracetamol":
                    dose_min = weight * 10
                    dose_max = weight * 15
                    reply = f"Paracetamol ขนาดที่แนะนำ: {dose_min:.2f} - {dose_max:.2f} mg ต่อครั้ง"

                elif drug == "Cetirizine":
                    dose = weight * 0.25
                    reply = f"Cetirizine ขนาดที่แนะนำ: {dose:.2f} mg ต่อวัน"

                elif drug == "Domperidone":
                    dose = weight * 0.25
                    reply = f"Domperidone ขนาดที่แนะนำ: {dose:.2f} mg (1 mg/ml) ≈ {dose:.2f} ml ต่อครั้ง"

                elif drug == "Hydroxyzine":
                    dose = weight * 0.5
                    volume = dose / (10 / 5)
                    reply = f"Hydroxyzine: {dose:.2f} mg ≈ {volume:.2f} ml ต่อครั้ง"

                elif drug == "Ferrous drop":
                    dose = weight * 3
                    volume = dose / (15 / 0.6)
                    reply = f"Ferrous fumarate: {dose:.2f} mg ≈ {volume:.2f} ml ต่อวัน"

                elif drug == "Salbutamol":
                    dose = weight * 0.15
                    volume = dose / (2 / 5)
                    reply = f"Salbutamol: {dose:.2f} mg ≈ {volume:.2f} ml ต่อครั้ง"

                elif drug == "Chlorpheniramine":
                    dose = weight * 0.35
                    volume = dose / (2 / 5)
                    reply = f"Chlorpheniramine: {dose:.2f} mg/day ≈ {volume:.2f} ml/day (แบ่งให้ทุก 8 ชม.)"

                elif drug in ["Amoxicillin", "Cephalexin", "Cefdinir", "Cefixime", "Augmentin", "Azithromycin"]:
                    settings = {
                        "Amoxicillin":   {"dose": 50, "conc": 250 / 5, "bottle": 60, "days": 7},
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
                        f"ขนาด: {total_mg_day:.0f} mg/วัน ≈ {ml_per_day:.1f} ml/วัน\n"
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
                TextMessage(text="กรุณาพิมพ์น้ำหนัก เช่น 20")
            )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='