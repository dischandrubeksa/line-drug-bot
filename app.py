from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

# ดึง Token และ Secret จาก Environment
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

# ตรวจสอบว่า Token และ Secret ถูกกำหนด
if LINE_CHANNEL_ACCESS_TOKEN is None or LINE_CHANNEL_SECRET is None:
    raise ValueError("Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ✅ สำหรับตรวจว่าเว็บออนไลน์
@app.route('/')
def index():
    return "OK"

# ✅ Webhook สำหรับรับข้อความจาก LINE
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ✅ ฟังก์ชันตอบกลับข้อความจากผู้ใช้
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text

    # ตัวอย่าง: ตรวจคำว่า "น้ำหนัก" แล้วคำนวณขนาดยา
    if user_text.startswith("น้ำหนัก"):
        try:
            weight = float(user_text.replace("น้ำหนัก", "").strip())
            dose = weight * 10
            reply = f"ขนาดยาที่แนะนำ: {dose:.2f} mg"
        except:
            reply = "กรุณาระบุน้ำหนักเป็นตัวเลข เช่น: น้ำหนัก 20"
    else:
        reply = "พิมพ์ว่า 'น้ำหนัก [ตัวเลข]' เพื่อคำนวณขนาดยา"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ✅ รัน Flask ด้วย host/port ที่ Render ต้องการ
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # อ่านจาก Render
    app.run(host='0.0.0.0', port=port)
    
LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='