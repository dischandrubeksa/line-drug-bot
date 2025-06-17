from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import re

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 🧠 บันทึกการเลือกยา (session ชั่วคราวต่อ user)
user_drug_selection = {}

@app.route('/')
def home():
    return 'LINE Bot is running!'

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ✅ Rich Message: ให้เลือกยา
def send_drug_selection(event):
    carousel = TemplateSendMessage(
        alt_text='กรุณาเลือกตัวยาที่ต้องการคำนวณ',
        template=CarouselTemplate(columns=[
            CarouselColumn(
                title='Paracetamol',
                text='10–15 mg/kg/dose',
                actions=[MessageAction(label='เลือก Paracetamol', text='เลือกยา: Paracetamol')]
            ),
            CarouselColumn(
                title='Cetirizine',
                text='0.25 mg/kg/day',
                actions=[MessageAction(label='เลือก Cetirizine', text='เลือกยา: Cetirizine')]
            )
        ])
    )
    line_bot_api.reply_message(event.reply_token, carousel)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ✅ เริ่มต้นด้วยคำว่า "คำนวณยา"
    if text.lower() in ['คำนวณยา', 'dose', 'เริ่ม']:
        send_drug_selection(event)
        return

    # ✅ เปลี่ยนตัวยาใหม่
    if text == "เลือกยาใหม่":
        if user_id in user_drug_selection:
            del user_drug_selection[user_id]
        send_drug_selection(event)
        return

    # ✅ เลือกยา
    if text.startswith("เลือกยา:"):
        drug_name = text.replace("เลือกยา:", "").strip()
        user_drug_selection[user_id] = drug_name
        reply = f"คุณเลือก {drug_name} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ✅ ถ้ามีการเลือกยาไว้ → คำนวณจากน้ำหนัก
    if user_id in user_drug_selection:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            weight = float(match.group(1))
            drug = user_drug_selection[user_id]

            # ✅ คำนวณขนาดยา
            if drug == "Paracetamol":
                dose_min = weight * 10
                dose_max = weight * 15
                reply = (
                    f"{drug} ขนาดที่แนะนำ: {dose_min:.2f} - {dose_max:.2f} mg ต่อครั้ง\n\n"
                    f"พิมพ์น้ำหนักใหม่เพื่อคำนวณอีกครั้ง หรือพิมพ์ 'เลือกยาใหม่' เพื่อเปลี่ยนตัวยา"
                )
            elif drug == "Cetirizine":
                dose = weight * 0.25
                reply = (
                    f"{drug} ขนาดที่แนะนำ: {dose:.2f} mg ต่อวัน\n\n"
                    f"พิมพ์น้ำหนักใหม่เพื่อคำนวณอีกครั้ง หรือพิมพ์ 'เลือกยาใหม่' เพื่อเปลี่ยนตัวยา"
                )
            else:
                reply = "ขออภัย ยังไม่รองรับตัวยานี้ครับ"

            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="กรุณาระบุน้ำหนักเป็นตัวเลข เช่น 20"))
        return

    # ✅ ข้อความอื่น
    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text="พิมพ์ว่า 'คำนวณยา' เพื่อเริ่ม หรือ 'เลือกยาใหม่' เพื่อเปลี่ยนตัวยา"
    ))

# ✅ รันแอป
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # สำหรับ Render/Heroku
    app.run(host="0.0.0.0", port=port)
       
LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='