from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
# สร้างแอป Flask
app = Flask(__name__)

# 🔒 ใส่ Token และ Secret ที่คุณได้จาก LINE Developers
LINE_CHANNEL_ACCESS_TOKEN = 'ใส่ access token ของคุณที่นี่'
LINE_CHANNEL_SECRET = 'ใส่ channel secret ของคุณที่นี่'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 📮 ตั้งค่า Webhook route
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except:
        abort(400)

    return 'OK'

# 📥 ฟังก์ชันรับข้อความจากผู้ใช้
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip().lower()  # รับข้อความแล้วแปลงให้เล็กหมด
    reply = ""  # ข้อความที่จะตอบกลับ

    # 👨‍⚕️ ตัวอย่างคำสั่ง: น้ำหนัก 20
    if msg.startswith("น้ำหนัก"):
        try:
            kg = float(msg.split()[1])     # ดึงตัวเลขน้ำหนัก
            dose = kg * 10                 # สมมุติสูตร 10 mg/kg
            reply = f"ขนาดยาที่แนะนำ: {dose:.2f} mg"
        except:
            reply = "กรุณาพิมพ์ว่า: น้ำหนัก [ตัวเลข] เช่น น้ำหนัก 20"
    else:
        reply = "พิมพ์ว่า: น้ำหนัก [ตัวเลข] เช่น น้ำหนัก 20"

    # 📨 ส่งข้อความตอบกลับ
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# 🟢 สั่งให้ Flask รันเมื่อเปิดไฟล์นี้โดยตรง
if __name__ == "__main__":
    app.run()