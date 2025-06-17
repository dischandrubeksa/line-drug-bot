from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient, ReplyMessageRequest, TextMessage, TemplateMessage, CarouselTemplate, CarouselColumn, MessageAction
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
import re
import math

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("Missing LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)

user_drug_selection = {}  # user_id: drug
user_indication_selection = {}  # user_id: indication (for Amoxicillin)

@app.route('/')
def home():
    return 'LINE Bot is running!'

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        events = parser.parse(body, signature)
    except Exception as e:
        abort(400)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_message(event)

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

    messaging_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[
            TemplateMessage(alt_text="เลือกยากลุ่มแรก", template=carousel1),
            TemplateMessage(alt_text="เลือกยากลุ่มเพิ่มเติม", template=carousel2)
        ]
    ))

def send_amoxicillin_indications(event):
# รายชื่อ indication และ label ที่จะใช้แสดง
    indications = [
("Pharyngitis / Tonsillitis", "Pharyngitis"),
("Otitis media (AOM)", "Otitis media"),
("Pneumonia (CAP)", "Pneumonia"),
("Anthrax", "Anthrax"),
("H. pylori", "H. pylori"),
("Urinary tract infection", "UTI"),
("Rhinosinusitis", "Rhinosinusitis"),
("Endocarditis prophylaxis", "Endocarditis"),
("Lyme disease", "Lyme disease"),
("Osteoarticular infection", "Osteoarticular")
]

    columns = []
    for i in range(0, len(indications), 3):
        group = indications[i:i+3]
        col = CarouselColumn(
            title='เลือก indication',
            text='เลือกข้อบ่งใช้ของ Amoxicillin',
            actions=[MessageAction(label=ind, text=f"indication: {ind}") for ind in group]
        )
        columns.append(col)

    carousel = CarouselTemplate(columns=columns)
    messaging_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TemplateMessage(alt_text="เลือก indication", template=carousel)]
    ))

def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.lower() in ['คำนวณยา', 'dose', 'เริ่ม']:
        send_drug_selection(event)
        return

    if text == "เลือกยาใหม่":
        user_drug_selection.pop(user_id, None)
        user_indication_selection.pop(user_id, None)
        send_drug_selection(event)
        return

    if text.startswith("เลือกยา:"):
        drug_name = text.replace("เลือกยา:", "").strip()
        user_drug_selection[user_id] = drug_name

        if drug_name == "Amoxicillin":
            send_amoxicillin_indications(event)
        else:
            reply = f"คุณเลือก {drug_name} แล้ว กรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20"
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            ))
        return

    if text.startswith("indication:"):
        indication = text.replace("indication:", "").strip()
        user_indication_selection[user_id] = indication
        reply = f"เลือก indication: {indication}\nกรุณาพิมพ์น้ำหนักเป็นกิโลกรัม เช่น 20"
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply)]
        ))
        return

    if user_id in user_drug_selection:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            weight = float(match.group(1))
            drug = user_drug_selection[user_id]

            try:
                if drug == "Amoxicillin" and user_id in user_indication_selection:
                    ind = user_indication_selection[user_id]
                    dose_map = {
                        "Pharyngitis": (50, 10),
                        "Otitis media": (90, 10),
                        "Pneumonia": (90, 7),
                        "Anthrax": (75, 60),
                        "Helicobacter pylori": (62.5, 14),
                        "UTI": (75, 7),
                        "Rhinosinusitis": (90, 10),
                        "Endocarditis prophylaxis": (50, 1),
                        "Lyme disease": (50, 14),
                        "Osteoarticular infection": (100, 14)
                    }
                    max_dose = {
                        "Pneumonia": 4000,
                        "Anthrax": 1000,
                        "UTI": 500,
                        "Rhinosinusitis": 2000,
                        "Endocarditis prophylaxis": 2000,
                        "Lyme disease": 500,
                        "Osteoarticular infection": 4000
                    }

                    dose_per_kg, days = dose_map.get(ind, (50, 7))
                    total_mg = weight * dose_per_kg
                    max_mg = max_dose.get(ind)
                    if max_mg:
                        dose_info = f"{min(total_mg, max_mg):.0f} mg/day (สูงสุด {max_mg} mg)"
                    else:
                        dose_info = f"{total_mg:.0f} mg/day"

                    reply = (
                        f"{drug} - {ind}:\n"
                        f"ขนาด: {dose_info}\nระยะเวลา: {days} วัน"
                    )
                else:
                    reply = f"ยังไม่รองรับยา {drug} หรือไม่พบ indication"

                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                ))
            except Exception as e:
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการคำนวณ")]
                ))
        else:
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="กรุณาพิมพ์น้ำหนัก เช่น 20")]
            ))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

LINE_CHANNEL_ACCESS_TOKEN = 'f9aa6b49ac00dfb359098504cffe6eab'
LINE_CHANNEL_SECRET = 'kzXIG0cO1xDAPMJaQ0NrEiufMINBbst7Z5ndou3YkPp21dJKvr3ZHIL4eeePNM2q4JPFmy+ttnGunjBPaEZ3Vl1yG3gVR8sISp/DVpy7SibXB+xoed0JZd2MmbU9qnhKkf2Eu5teI7DiM/v0DMkV7AdB04t89/1O/w1cDnyilFU='