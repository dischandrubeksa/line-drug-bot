from flask import Flask, request, abort
from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    TextMessage, MessageAction, CarouselColumn, CarouselTemplate, TemplateMessage, ReplyMessageRequest, FlexMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.models import QuickReplyButton, PostbackAction
from linebot.v3.messaging.models import FlexContainer
from datetime import datetime, timedelta
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
            "Pharyngitis/Tonsillitis": [
                {
                    "sub_indication": "Group A Streptococcus",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": [1, 2],
                    "duration_days": 10,
                    "max_mg_per_day": 1000,
                    "note": "📌 ใช้ได้ทั้งแบบวันละครั้งหรือแบ่งวันละ 2 ครั้ง × 10 วัน ตามความสะดวก"
                }
            ],
            "Acute Otitis Media (AOM)": [
                {
                    "label": "High-dose regimen",
                    "dose_mg_per_kg_per_day": [80, 90],
                    "frequency": 2,
                    "duration_days": 10,
                    "max_mg_per_day": 4000,
                    "note": "เหมาะในสหรัฐอเมริกา หรือเมื่อมี S. pneumoniae ดื้อเพนนิซิลลิน"
                },
                {
                    "label": "Standard-dose regimen",
                    "dose_mg_per_kg_per_day": [40, 50],
                    "frequency": 2,
                    "duration_days": 7,
                    "max_mg_per_day": 1500,
                    "note": "ใช้ได้เฉพาะในพื้นที่ที่เชื้อ S. pneumoniae ดื้อต่อ penicillin < 10% เท่านั้น"
                }
            ],
            "Pneumonia (community acquired)": [
                {
                    "label": "Empiric therapy (bacterial pneumonia)",
                    "dose_mg_per_kg_per_day": 90,
                    "frequency": 2,
                    "duration_days": 5,
                    "max_mg_per_day": 4000
                },
                {
                    "label": "Group A Streptococcus, mild",
                    "dose_mg_per_kg_per_day": [50, 75],
                    "frequency": 2,
                    "duration_days": 7,
                    "max_mg_per_day": 4000
                },
                {
                    "label": "H. influenzae, mild",
                    "dose_mg_per_kg_per_day": [75, 100],
                    "frequency": 3,
                    "duration_days": 7,
                    "max_mg_per_day": 4000
                },
                {
                    "label": "S. pneumoniae, MIC ≤2",
                    "dose_mg_per_kg_per_day": 90,
                    "frequency": [2, 3],
                    "duration_days": 7,
                    "max_mg_per_day": 4000,
                    "note": "เลือกความถี่ตาม MIC: 12 ชม หรือ 8 ชม"
                },
                {
                    "label": "S. pneumoniae, MIC = 2 mcg/mL",
                    "dose_mg_per_kg_per_day": [90, 100],
                    "frequency": 3,
                    "duration_days": 7,
                    "max_mg_per_day": 4000,
                    "note": "ใช้เพื่อให้ time > MIC ได้ตามเป้าหมาย"
                }
            ],
            "Anthrax": [
                {
                    "title": "Postexposure prophylaxis, exposure to aerosolized spores",
                    "dose_mg_per_kg_per_day": 75,
                    "frequency": 3,
                    "duration_days": 60,
                    "max_mg_per_dose": 1000
                },
                {
                    "title": "Cutaneous, without systemic involvement",
                    "dose_mg_per_kg_per_day": 75,
                    "frequency": 3,
                    "duration_days_range": [7, 10],
                    "max_mg_per_dose": 1000,
                    "note": "ใช้ในกรณี naturally acquired infection"
                },
                {
                    "title": "Systemic, oral step-down therapy",
                    "dose_mg_per_kg_per_day": 75,
                    "frequency": 3,
                    "duration_days": 60,
                    "max_mg_per_dose": 1000,
                    "note": "เป็นส่วนหนึ่งของ combination therapy เพื่อให้ครบ 60 วัน"
                }
            ],
            "H. pylori eradication": [
                {
                    "name": "Standard-dose (weight-based)",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 2,
                    "duration_days": 14,
                    "max_mg_per_dose": 1000,
                    "note": "ใช้ร่วมกับยาฆ่าเชื้อชนิดอื่นตาม guideline"
                },
                {
                    "name": "Standard-dose (fixed dosing)",
                    "fixed_dose_by_weight": [
                        {"min_weight": 15, "max_weight": 24.9, "dose_mg": 500},
                        {"min_weight": 25, "max_weight": 34.9, "dose_mg": 750},
                        {"min_weight": 35, "max_weight": 999, "dose_mg": 1000}
                    ],
                    "frequency": 2,
                    "duration_days": 14,
                    "note": "Fixed dosing ตามน้ำหนักช่วง (twice daily × 14 วัน)"
                },
                {
                    "name": "High-dose (fixed dosing)",
                    "fixed_dose_by_weight": [
                        {"min_weight": 15, "max_weight": 24.9, "dose_mg": 750},
                        {"min_weight": 25, "max_weight": 34.9, "dose_mg": 1000},
                        {"min_weight": 35, "max_weight": 999, "dose_mg": 1500}
                    ],
                    "frequency": 2,
                    "duration_days": 14,
                    "note": "ใช้กรณีดื้อ clarithromycin และ metronidazole"
                }
            ],
            "Lyme disease": [
                {
                    "name": "Erythema migrans / Borrelial lymphocytoma",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 14,
                    "max_mg_per_dose": 500,
                    "note": "รักษานาน 14 วัน"
                },
                {
                    "name": "Carditis",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 21,
                    "max_mg_per_dose": 500,
                    "note": "รักษานาน 14–21 วัน"
                },
                {
                    "name": "Arthritis (initial, recurrent, or refractory)",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 28,
                    "max_mg_per_dose": 500,
                    "note": "รักษานาน 28 วัน"
                },
                {
                    "name": "Acrodermatitis chronica atrophicans",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 28,
                    "max_mg_per_dose": 500,
                    "note": "รักษานาน 21–28 วัน"
                }
            ],
            "Urinary tract infection": [
                {
                    "sub_indication": "Infants",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 2,
                    "duration_days": 7,
                    "note": "📌 แนะนำใช้เฉพาะในกรณีที่เชื้อไวต่อ amoxicillin"
                },
                {
                    "sub_indication": "Infants (severe)",
                    "dose_mg_per_kg_per_day": 100,
                    "frequency": 2,
                    "duration_days": 10,
                    "note": "📌 อาจใช้ในกรณี moderate/severe infection"
                },
                {
                    "sub_indication": "Children and Adolescents",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 7,
                    "max_mg_per_dose": 500,
                    "note": "📌 แนะนำระยะเวลา 7–14 วัน หรือ 3–5 วันใน cystitis ที่ไม่ซับซ้อน (≥2 ปี)"
                },
                {
                    "sub_indication": "Children and Adolescents (high dose)",
                    "dose_mg_per_kg_per_day": 100,
                    "frequency": 3,
                    "duration_days": 10,
                    "max_mg_per_dose": 500,
                    "note": "📌 สำหรับ moderate/severe infection ที่ตอบสนองช้า"
                },
                {
                    "sub_indication": "Children (uncomplicated cystitis)",
                    "dose_mg_per_kg_per_day": 30,
                    "frequency": 3,
                    "duration_days": 3,
                    "note": "📌 ใช้ได้ในเด็ก ≥2 ปี ที่มี uncomplicated cystitis"
                }
            ],
            "Rhinosinusitis": [
                {
                    "sub_indication": "Standard-dose regimen (พื้นที่ที่ S. pneumoniae ไวต่อ penicillin)",
                    "dose_mg_per_kg_per_day": 45,
                    "frequency": 2,
                    "duration_days": 10,
                    "note": "📌 สำหรับผู้ป่วยที่ไม่ได้รับยาปฏิชีวนะใน 30 วันที่ผ่านมา และไม่ได้ไปศูนย์ดูแลเด็ก (AAP guideline)"
                },
                {
                    "sub_indication": "High-dose regimen (พื้นที่ที่ S. pneumoniae ดื้อต่อ penicillin ≥10%)",
                    "dose_mg_per_kg_per_day": 80,
                    "frequency": 2,
                    "duration_days": 10,
                    "max_mg_per_dose": 2000,
                    "note": "📌 แนะนำโดย IDSA และใช้ในพื้นที่ที่มีเชื้อดื้อมาก"
                }
            ]
        }
    },
    "Cephalexin": {
        "concentration_mg_per_ml": 125 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "Acute Otitis Media (AOM)": [
            {
                "sub_indication": "Alternative agent",
                "dose_mg_per_kg_per_day": [75, 100],
                "frequency": 4,
                "duration_days": 10,
                "note": "❗ ไม่แนะนำให้ใช้เป็น empiric therapy; ใช้เฉพาะเมื่อทราบเชื้อที่ไวต่อยา"
            }
            ],
            "Pneumonia (community acquired)": [
            {
                "sub_indication": "Step-down therapy for mild infection",
                "dose_mg_per_kg_per_day": [75, 100],
                "frequency": [3, 4],
                "duration_days_range": [5, 10],
                "max_mg_per_day": 4000,
                "note": "📝 ใช้เป็น step-down therapy หลัง IV สำหรับ pneumonia ไม่ซับซ้อน"
            }
            ],
            "SSTI": [
            {
                "sub_indication": "Cellulitis, erysipelas, purulent/fluctuant SSTI",
                "dose_mg_per_kg_per_day": [25, 100],
                "frequency": [3, 4],
                "duration_days_range": [5, 10],
                "max_mg_per_dose": 500,
                "note": "❗ หลีกเลี่ยงการใช้เดี่ยวถ้าสงสัย MRSA; ใช้ dose สูงสุดในกรณีรุนแรงหรือสงสัย MSSA"
            },
            {
                "sub_indication": "Impetigo, ecthyma",
                "dose_mg_per_kg_per_day": [25, 50],
                "frequency": [3, 4],
                "duration_days": 7,
                "max_mg_per_day": 2000
            }
            ],
            "Pharyngitis/Tonsillitis": [
            {
                "sub_indication": "Group A Streptococcus (penicillin allergy)",
                "dose_mg_per_kg_per_day": 40,
                "frequency": 2,
                "duration_days": 10,
                "max_mg_per_dose": 500
            }
            ],
            "UTI": [
            {
                "sub_indication": "Mild to moderate (eg, cystitis)",
                "dose_mg_per_kg_per_day": [25, 50],
                "frequency": [2, 4],
                "duration_days": 5,
                "max_mg_per_dose": 500,
                "note": "📝 ระยะเวลาอาจขยายหากการตอบสนองไม่ดี"
            },
            {
                "sub_indication": "Severe (eg, pyelonephritis)",
                "dose_mg_per_kg_per_day": [50, 100],
                "frequency": [3, 4],
                "duration_days_range": [7, 10],
                "max_mg_per_dose": 1000,
                "note": "📝 ไม่แนะนำให้เกิน 10 วัน; ใช้ตามการตอบสนองทางคลินิก"
            }
            ]
        }
    },
    "Cefdinir": {
    "concentration_mg_per_ml": 125 / 5,
    "bottle_size_ml": 60,
    "indications": {
        "Chronic bronchitis, acute bacterial exacerbation": [
        {
            "sub_indication": "Adolescents",
            "dose_mg": 300,
            "frequency": 2,
            "duration_days_range": [5, 10],
            "note": "📝 อาจใช้ 600 mg วันละครั้งนาน 10 วันได้"
        }
        ],
        "Otitis Media": [
        {
            "sub_indication": "Alternative agent for penicillin allergy",
            "dose_mg_per_kg_per_day": 14,
            "frequency": [2],  # เน้น BID
            "duration_days_range": [5, 10],
            "max_mg_per_day": 600,
            "note": "📝 ใช้ 10 วันในเด็กอายุน้อยหรือรุนแรง; 5–7 วันถ้าอายุ ≥2 ปี และไม่ซับซ้อน"
        }
        ],
        "Pneumonia (community acquired)": [
        {
            "sub_indication": "Adolescents",
            "dose_mg": 300,
            "frequency": 2,
            "duration_days": 10,
            "note": "📝 ใช้เฉพาะเมื่อไม่มีตัวเลือกอื่น และไม่แนะนำใน S. pneumoniae ดื้อยา"
        }
        ],
        "Rhinosinusitis": [
        {
            "sub_indication": "Penicillin allergy (alternative)",
            "dose_mg_per_kg_per_day": 14,
            "frequency": [2],
            "duration_days": 10,
            "max_mg_per_day": 600,
            "note": "📝 ตัวเลือกไม่แนะนำ; ใช้เมื่อแพ้ penicillin"
        },
        {
            "sub_indication": "Adolescents",
            "dose_mg": 300,
            "frequency": 2,
            "duration_days": 10
        }
        ],
        "SSTI": [
        {
            "sub_indication": "Uncomplicated",
            "dose_mg_per_kg_per_day": 14,
            "frequency": 2,
            "duration_days": 10,
            "max_mg_per_dose": 300,
            "note": "❗ ไม่อยู่ในแนวทาง IDSA แนะนำ; ใช้เมื่อไม่มีทางเลือก"
        },
        {
            "sub_indication": "Adolescents",
            "dose_mg": 300,
            "frequency": 2,
            "duration_days": 10
        }
        ],
        "Pharyngitis/Tonsillitis": [
        {
            "sub_indication": "Group A Streptococcus (penicillin allergy)",
            "dose_mg_per_kg_per_day": 14,
            "frequency": [1, 2],
            "duration_days": 10,
            "max_mg_per_day": 600,
            "note": "📝 แนะนำใช้ dose BID หากให้แค่ 5 วัน; แต่โดยทั่วไปควรใช้ 10 วัน"
        },
        {
            "sub_indication": "Adolescents",
            "dose_mg": 300,
            "frequency": 2,
            "duration_days": 10
        }
        ]
    }
    },
    "Cefixime": {
    "concentration_mg_per_ml": 100 / 5,
    "bottle_size_ml": 50,
    "indications": {
        "Febrile neutropenia": [
        {
            "sub_indication": "Low-risk (step-down after IV)",
            "dose_mg_per_kg_per_day": 8,
            "frequency": [1, 2],
            "note": "ใช้แบบ once daily หรือแบ่งวันละ 2 ครั้งหลัง IV antibiotic 48–72 ชม."
        }
        ],
        "Gonococcal infection": [
        {
            "sub_indication": "Uncomplicated cervix/urethra/rectum (≥45 kg)",
            "fixed_dose_mg": 800,
            "frequency": 1,
            "note": "เฉพาะเมื่อ ceftriaxone ใช้ไม่ได้; ให้ครั้งเดียว 800 mg"
        }
        ],
        "Irinotecan-associated diarrhea (prophylaxis)": [
        {
            "sub_indication": "Prophylaxis before irinotecan",
            "dose_mg_per_kg_per_day": 8,
            "frequency": 1,
            "max_mg_per_dose": 400,
            "duration_days_range": [5, 10],
            "note": "เริ่มก่อน irinotecan 2 วันและให้ต่อเนื่องระหว่างการรักษา"
        }
        ],
        "Otitis media": [
        {
            "sub_indication": "Alternative agent (AOM)",
            "dose_mg_per_kg_per_day": 8,
            "frequency": [1, 2],
            "duration_days_range": [5, 10],
            "max_mg_per_day": 400,
            "note": "ใช้ในกรณีไม่ตอบสนองต่อ first-line หรือร่วมกับ clindamycin"
        }
        ],
        "Rhinosinusitis": [
        {
            "sub_indication": "Acute bacterial (alt agent)",
            "dose_mg_per_kg_per_day": 8,
            "frequency": [1, 2],
            "duration_days_range": [5, 10],
            "max_mg_per_day": 400,
            "note": "ไม่ใช่ first-line; ใช้ร่วมกับยาอื่นหลังล้มเหลวจากการรักษาเบื้องต้น"
        }
        ],
        "Pharyngitis/Tonsillitis": [
        {
            "sub_indication": "Group A Strep (penicillin allergy)",
            "dose_mg_per_kg_per_day": 8,
            "frequency": [1, 2],
            "duration_days": 10,
            "max_mg_per_day": 400,
            "note": "ใช้กรณีแพ้ penicillin; narrow-spectrum cephalosporins เป็นทางเลือกที่ดีกว่า"
        }
        ],
        "Typhoid fever": [
        {
            "sub_indication": "Salmonella typhi",
            "dose_mg_per_kg_per_day": [15, 20],
            "frequency": 2,
            "duration_days_range": [7, 14],
            "note": "ข้อมูลจำกัด; การตอบสนองแตกต่างกันตามพื้นที่และเชื้อ"
        }
        ],
        "Urinary tract infection": [
        {
            "sub_indication": "Uncomplicated or complicated UTI",
            "dose_mg_per_kg_per_day": 8,
            "frequency": [1, 2],
            "duration_days_range": [5, 10],
            "note": "สำหรับ cystitis ใช้ 5 วัน, pyelonephritis ใช้ 7–10 วัน"
        }
        ]
    }
    },
    "Augmentin": {
    "concentration_mg_per_ml": 400 / 5,  # ตัวอย่าง: 400 mg amoxicillin + 57 mg clavulanate per 5 mL
    "bottle_size_ml": 60,
    "indications": {
        "Impetigo": [
        {
            "dose_mg_per_kg_per_day": [25, 45],
            "frequency": [2, 3],
            "duration_days": 7,
            "max_mg_per_dose": 875,
            "note": "📝 ให้แบ่งทุก 8–12 ชม.; max 500 mg ถ้าให้ทุก 8 ชม., 875 mg ถ้าทุก 12 ชม."
        }
        ],
        "Osteoarticular infection": [
        {
            "sub_indication": "Step-down therapy",
            "dose_mg_per_kg_per_day": 120,
            "frequency": [3, 4],
            "max_mg_per_day": 3000,
            "note": "📝 ไม่ควรให้ clavulanate เกิน 125 mg ต่อ dose; IV+PO อย่างน้อย 2–4 สัปดาห์"
        }
        ],
        "Otitis Media": [
        {
            "sub_indication": "High-dose regimen",
            "dose_mg_per_kg_per_day": [80, 90],
            "frequency": 2,
            "max_mg_per_day": 4000,
            "note": "📝 แนะนำในประเทศที่มี S. pneumoniae ดื้อ penicillin"
        },
        {
            "sub_indication": "Standard-dose regimen",
            "dose_mg_per_kg_per_day": [40, 45],
            "frequency": [2, 3],
            "max_mg_per_day": 1750,
            "note": "📝 ใช้ในพื้นที่ที่เชื้อดื้อ penicillin ต่ำ"
        }
        ],
        "Pneumonia (community acquired)": [
        {
            "sub_indication": "Empiric therapy",
            "dose_mg_per_kg_per_day": 90,
            "frequency": 2,
            "max_mg_per_day": 4000,
            "note": "📝 ใช้ 5 วัน ถ้าดีขึ้นเร็ว; นาน 7–10 วันถ้ารุนแรง/มีโรคร่วม"
        },
        {
            "sub_indication": "H. influenzae (step-down or mild)",
            "dose_mg_per_kg_per_day": [45, 90],
            "frequency": [2, 3],
            "note": "📝 ขึ้นกับความรุนแรงและปัจจัยเสี่ยง"
        }
        ],
        "Rhinosinusitis": [
        {
            "sub_indication": "Standard-dose regimen",
            "dose_mg_per_kg_per_day": [40, 45],
            "frequency": [2, 3],
            "max_mg_per_dose": 875,
            "note": "📝 max 500 mg ถ้าให้ทุก 8 ชม.; หรือ 875 mg ทุก 12 ชม."
        },
        {
            "sub_indication": "High-dose regimen",
            "dose_mg_per_kg_per_day": [80, 90],
            "frequency": [2, 3],
            "max_mg_per_day": 4000,
            "note": "📝 ใช้เมื่อเสี่ยงสูง เช่น แพทย์เด็ก, อายุน้อย, แพ้ penicillin"
        }
        ],
        "Streptococcus group A carriage": [
        {
            "dose_mg_per_kg_per_day": 40,
            "frequency": 3,
            "duration_days": 10,
            "max_mg_per_day": 2000,
            "note": "📝 ใช้เฉพาะกรณี chronic carriage ที่จำเป็นต้องรักษา"
        }
        ],
        "Urinary Tract Infection": [
        {
            "dose_mg_per_kg_per_day": [20, 50],
            "frequency": [2, 3],
            "duration_days_range": [3, 14],
            "max_mg_per_day": 1750,
            "note": "📝 ปรับตามความรุนแรง อายุ และ clinical response"
        }
        ]
    }
    },
    "Azithromycin": {
        "concentration_mg_per_ml": 200 / 5,
        "bottle_size_ml": 15,
        "indications": {
            "Pertussis": [
                {
                    "sub_indication": "Infants <6 months",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 5,
                    "max_mg_per_day": None,
                    "note": "ใช้วันละครั้ง เป็นเวลา 5 วัน"
                },
                {
                    "sub_indication": "Infants ≥6 months, Children, Adolescents",
                    "dose_by_day": {
                        "Day 1": {
                            "dose_mg_per_kg": 10,
                            "max_mg_per_day": 500
                        },
                        "Day 2-5": {
                            "dose_mg_per_kg": 5,
                            "max_mg_per_day": 250
                        }
                    },
                    "frequency": 1,
                    "duration_days": 5,
                    "note": "เริ่มด้วย 10 mg/kg (max 500 mg) วันที่ 1 แล้วตามด้วย 5 mg/kg (max 250 mg) วันที่ 2-5"
                }
            ],
            "Pneumonia (community acquired)": [
                {
                    "sub_indication": "5-day regimen (mild infection / step-down therapy)",
                    "dose_mg_per_kg_per_day": [10, 5],
                    "frequency": 1,
                    "duration_days": 5,
                    "max_mg_per_day": [500, 250],
                    "note": "Day 1: 10 mg/kg (max 500 mg), Day 2–5: 5 mg/kg (max 250 mg)"
                },
                {
                    "sub_indication": "3-day regimen",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 3,
                    "max_mg_per_day": 500,
                    "note": "ใช้ในผู้ป่วยที่ไม่รุนแรง หรือกรณีมีข้อจำกัด; severe case อาจใช้ 5–7 วัน"
                }
            ],
            "Pharyngitis/Tonsillitis": [
                {
                    "sub_indication": "5-day regimen",
                    "dose_mg_per_kg_per_day": 12,
                    "frequency": 1,
                    "duration_days": 5,
                    "max_mg_per_day": 500,
                    "note": "ใช้ในผู้ที่แพ้ penicillin รุนแรง (severe allergy)"
                },
                {
                    "sub_indication": "3-day regimen",
                    "dose_mg_per_kg_per_day": 20,
                    "frequency": 1,
                    "duration_days": 3,
                    "max_mg_per_day": 1000,
                    "note": "ข้อมูลจำกัด แต่มีการใช้แบบ 3 วัน; ควรใช้ total ≥60 mg/kg ตลอดคอร์สเพื่อประสิทธิภาพสูง"
                }
            ],
            "Typhoid Fever": [
                {
                    "sub_indication": "7-day regimen (10 mg/kg/day)",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 7,
                    "max_mg_per_day": 500,
                    "note": "💊 ขนาดปานกลาง: 10 mg/kg/day นาน 7 วัน"
                },
                {
                    "sub_indication": "5–7-day regimen (20 mg/kg/day)",
                    "dose_mg_per_kg_per_day": 20,
                    "frequency": 1,
                    "duration_days": [5, 7],
                    "max_mg_per_day": 1000,
                    "note": "💊 ขนาดสูง: 20 mg/kg/day นาน 5–7 วัน; พิจารณาในกรณีรุนแรงหรือตอบสนองไม่ดี"
                }
            ],
            "Gonococcal infection": [
                {
                    "sub_indication": "uncomplicated infections of the cervix, urethra, or rectum",
                    "dose_mg": 2000,
                    "frequency": 1,
                    "duration_days": 1,
                    "note": "🍼 Children >45 kg and Adolescents\n💉 ใช้เมื่อไม่สามารถใช้ ceftriaxone ได้; ให้ร่วมกับ gentamicin IM"
                }
            ],
            "Rhinosinusitis": [
                {
                    "sub_indication": "Infants ≥6 months, Children, and Adolescents",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 3,
                    "max_mg_per_day": 500,
                    "note": "📌 ใช้ในกรณีแพ้ยาอื่นหรือจำเป็น; macrolides ไม่แนะนำให้ใช้เป็น empiric therapy เนื่องจากอัตราดื้อยาสูง"
                }
            ],
            "Chlamydia": [
                {
                    "sub_indication": "Urogenital/anogenital or oropharyngeal infection",
                    "age_group": "Children <8 years weighing ≥45 kg or Children ≥8 years and Adolescents",
                    "dose_mg": 1000,
                    "frequency": 1,
                    "duration_days": 1,
                    "max_mg_per_day": 1000,
                    "note": "💊 ให้เพียงครั้งเดียว 1,000 mg; พิจารณาร่วมกับยา gonorrhea ถ้ามีความเสี่ยง"
                }
            ],
            "Pneumonia, congenital": [
                {
                    "sub_indication": "Infants",
                    "dose_mg_per_kg_per_day": 20,
                    "frequency": 1,
                    "duration_days": 3,
                    "max_mg_per_day": None,
                    "note": "📌 ใช้ขนาด 20 mg/kg/day วันละครั้ง เป็นเวลา 3 วัน"
                }
            ],
            "Diarrhea (Campylobacter infection)": [
                {
                    "sub_indication": "Immunocompetent patients",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 3,
                    "max_mg_per_day": 500,
                    "note": "📌 โดยทั่วไปไม่แนะนำให้ใช้ในผู้ป่วยภูมิคุ้มกันปกติที่ไม่มีภาวะแทรกซ้อน"
                },
                {
                    "sub_indication": "Patients with HIV",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 5,
                    "max_mg_per_day": 500,
                    "note": "⚠️ ผู้ติดเชื้อ HIV ควรได้รับยาอย่างน้อย 5 วัน"
                },
                {
                    "sub_indication": "Immunocompromised or complicated infection",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": [7,14],
                    "max_mg_per_day": 500,
                    "note": "📌 ระยะเวลาอาจขยายถึง 7–14 วันตามภาวะแทรกซ้อนและระดับภูมิคุ้มกัน"
                }
            ],
            "Diarrhea (Shigellosis infection)": [
                {
                    "sub_indication": "Patients without HIV (5-day regimen)",
                    "dose_by_day": {
                        "Day 1": {
                            "dose_mg_per_kg_per_day": 12,
                            "max_mg_per_day": 500
                        },
                        "Day 2-5": {
                            "dose_mg_per_kg_per_day": 5,
                            "max_mg_per_day": 250
                        }
                    },
                    "frequency": 1,
                    "duration_days": 5,
                    "note": "เริ่มด้วย 12 mg/kg (max 500 mg) วันที่ 1 แล้วตามด้วย 5 mg/kg (max 250 mg) วันที่ 2–5"
                },
                {
                    "sub_indication": "Patients without HIV (3-day regimen)",
                    "dose_mg_per_kg_per_day": 10,
                    "max_mg_per_day": 500,
                    "frequency": 1,
                    "duration_days": 3,
                    "note": "📌 10 mg/kg/day once daily for 3 days (max 500 mg/day)"
                },
                {
                    "sub_indication": "Patients with HIV",
                    "dose_mg": 500,
                    "max_mg_per_day": 500,
                    "frequency": 1,
                    "duration_days": 5,
                    "note": "ผู้ป่วย HIV ให้ 500 mg/day เป็นเวลา 5 วัน"
                }
            ],
            "Diarrhea (Cholera infection)":[
                {
                    "sub_indication": "Alternative agent",
                    "dose_mg": 1000,
                    "frequency": 1,
                    "duration_days": 1,
                    "note": "📌 ให้ 1,000 mg เป็น single dose (off-label use สำหรับ cholera)"
                }
            ],
            "Babesiosis": [
                {
                    "sub_indication": "Mild to moderate disease (oral step-up)",
                    "dose_by_day": {
                        "Day 1": {
                            "dose_mg": 500,
                            "max_mg_per_day": 500
                        },
                        "Day 2+": {
                            "dose_mg": 250,
                            "max_mg_per_day": 250
                        }
                    },
                    "frequency": 1,
                    "duration_days": [7,10],
                    "note": "เริ่มด้วย 500 mg วันแรก ตามด้วย 250 mg/day ร่วมกับ atovaquone จนครบ 7–10 วัน"
                },
                {
                    "sub_indication": "Severe disease (IV initial)",
                    "dose_mg": 500,
                    "max_mg_per_day": 500,
                    "frequency": 1,
                    "duration_days": 2,
                    "note": "IV 500 mg/day + atovaquone อย่างน้อย 2 วัน จากนั้นเปลี่ยนเป็น oral"
                },
                {
                    "sub_indication": "Severe disease (oral step-down)",
                    "dose_mg": 250,
                    "max_mg_per_day": 500,
                    "frequency": 1,
                    "duration_days": 5,
                    "note": "หลังจาก IV → เปลี่ยนเป็น oral 250–500 mg/day + atovaquone จนครบคอร์ส"
                },
                {
                    "sub_indication": "Immunocompromised (extended therapy)",
                    "dose_mg": 500,
                    "max_mg_per_day": 1000,
                    "frequency": 1,
                    "duration_days": 42,
                    "note": "ในผู้ป่วยภูมิคุ้มกันต่ำ อาจต้องให้ต่อเนื่อง ≥6 สัปดาห์ ร่วมกับ atovaquone"
                }
            ],
            "Cat Scratch Disease": [
                {
                    "sub_indication": "Lymphadenitis (Infants, Children, Adolescents)",
                    "dose_by_day": {
                        "Day 1": {
                            "dose_mg_per_kg": 10,
                            "max_mg_per_day": 500
                        },
                        "Day 2-5": {
                            "dose_mg_per_kg": 5,
                            "max_mg_per_day": 250
                        }
                    },
                    "frequency": 1,
                    "duration_days": 5,
                    "note": "📌 เริ่มด้วย 10 mg/kg (max 500 mg) วันที่ 1 แล้วตามด้วย 5 mg/kg (max 250 mg) วันที่ 2–5"
                }
            ],
            "Mycobacterium avium complex infection": [
                {
                    "sub_indication": "Primary prophylaxis (Infants and Children)",
                    "dose_mg_per_kg_per_day": 20,
                    "frequency": 1,
                    "duration_days": 7,  # weekly
                    "max_mg_per_day": 1200,
                    "note": "📌 20 mg/kg once weekly (preferred) (max 1,200 mg/dose)"
                },
                {
                    "sub_indication": "Primary prophylaxis (alternative, Infants and Children)",
                    "dose_mg_per_kg_per_day": 5,
                    "frequency": 1,
                    "duration_days": 7,
                    "max_mg_per_day": 250,
                    "note": "📌 5 mg/kg/day once daily (alternative regimen) (max 250 mg/day)"
                },
                {
                    "sub_indication": "Treatment (Infants and Children)",
                    "dose_mg_per_kg_per_day": 12,
                    "frequency": 1,
                    "duration_days": 365,  # ≥12 months
                    "max_mg_per_day": 500,
                    "note": "📌 ใช้เป็นส่วนหนึ่งของ combination therapy ต่อเนื่อง ≥12 เดือน"
                },
                {
                    "sub_indication": "Secondary prophylaxis (Infants and Children)",
                    "dose_mg_per_kg_per_day": 5,
                    "frequency": 1,
                    "duration_days": 180,  # ≥6 months
                    "max_mg_per_day": 250,
                    "note": "📌 Long-term suppression (secondary prophylaxis) after completion of treatment ≥12 months"
                },
                {
                    "sub_indication": "Primary prophylaxis (Adolescents)",
                    "dose_mg_per_kg_per_day": 20,
                    "frequency": 1,
                    "duration_days": 7,
                    "max_mg_per_day": 1200,
                    "note": "📌 1,200 mg once weekly or 600 mg twice weekly for CD4 <50"
                },
                {
                    "sub_indication": "Treatment and secondary prophylaxis (Adolescents)",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 365,
                    "max_mg_per_day": 600,
                    "note": "📌 500–600 mg daily as part of appropriate combination regimen ≥12 เดือน"
                }
            ],
            "Nontuberculous mycobacteria (NTM) infection, pulmonary": [
                {
                    "sub_indication": "Patients with cystic fibrosis (Children)",
                    "dose_mg_per_kg_per_day": [10, 12],
                    "frequency": 1,
                    "duration_days": 365,
                    "max_mg_per_day": 500,
                    "note": "📌 ให้ 10–12 mg/kg/day วันละครั้ง เป็นเวลา ≥12 เดือน หลัง culture conversion"
                },
                {
                    "sub_indication": "Patients with cystic fibrosis (Adolescents)",
                    "dose_mg": [250, 500],
                    "frequency": 1,
                    "duration_days": 365,
                    "note": "📌 ให้ 250–500 mg/day วันละครั้ง ≥12 เดือน สำหรับ adolescent"
                },
                {
                    "sub_indication": "Patients without cystic fibrosis",
                    "dose_mg_per_kg_per_day": 10,
                    "frequency": 1,
                    "duration_days": 365,
                    "max_mg_per_day": 500,
                    "note": "📌 Infants ≥6 เดือน, Children, Adolescents: 10 mg/kg/day (max 500 mg/day) ≥12 เดือน"
                },
                {
                    "sub_indication": "Solid organ transplant recipients",
                    "dose_mg_per_kg_per_day": [10, 12],
                    "frequency": 1,
                    "duration_days": 365,
                    "max_mg_per_day": 500,
                    "note": "📌 Infants, Children, Adolescents (oral/IV): 10–12 mg/kg/day once daily ≥12 เดือน"
                }
            ],
            "Cystic Fibrosis (maintenance)": [
                {
                    "sub_indication": "Weight-directed dosing (≥3 months)",
                    "dose_mg_per_kg_per_dose": 10,
                    "frequency_per_week": 3,
                    "max_mg_per_dose": 500,
                    "note": "📌 10 mg/kg/dose สัปดาห์ละ 3 ครั้ง (เช่น Mon/Wed/Fri), max 500 mg/dose"
                },
                {
                    "sub_indication": "Fixed dosing (≥6 years, weight 18–<36 kg)",
                    "dose_mg": 250,
                    "frequency_per_week": 3,
                    "note": "📌 250 mg สัปดาห์ละ 3 ครั้ง (เช่น Mon/Wed/Fri)"
                },
                {
                    "sub_indication": "Fixed dosing (≥6 years, weight ≥36 kg)",
                    "dose_mg": 500,
                    "frequency_per_week": 3,
                    "note": "📌 500 mg สัปดาห์ละ 3 ครั้ง (เช่น Mon/Wed/Fri)"
                }
            ],
            "Asthma, poorly controlled": [
                {
                    "sub_indication": "Weight <20 kg",
                    "dose_mg": 125,
                    "frequency_per_week": 3,
                    "note": "📌 125 mg สัปดาห์ละ 3 ครั้ง (เหมาะกับผู้ป่วยน้ำหนักน้อยกว่า 20 kg)"
                },
                {
                    "sub_indication": "Weight 20–30 kg",
                    "dose_mg": 250,
                    "frequency_per_week": 3,
                    "note": "📌 250 mg สัปดาห์ละ 3 ครั้ง (เหมาะกับผู้ป่วยน้ำหนัก 20–30 kg)"
                },
                {
                    "sub_indication": "Weight >30–40 kg",
                    "dose_mg": 375,
                    "frequency_per_week": 3,
                    "note": "📌 375 mg สัปดาห์ละ 3 ครั้ง (เหมาะกับผู้ป่วยน้ำหนักมากกว่า 30–40 kg)"
                },
                {
                    "sub_indication": "Weight >40 kg",
                    "dose_mg": 500,
                    "frequency_per_week": 3,
                    "note": "📌 500 mg สัปดาห์ละ 3 ครั้ง (เหมาะกับผู้ป่วยน้ำหนักมากกว่า 40 kg)"
                }
            ],
            "Other": "INDICATION_OTHERS"
        },
        "common_indications": ["Gonococcal infection", "Pharyngitis/Tonsillitis","Rhinosinusitis","Pneumonia (community acquired)" ]
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
    "concentration_mg_per_ml": 120 / 5,
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
    "Ibuprofen": {
        "concentration_mg_per_ml": 100 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "Analgesic": {
                "weight_based": {
                    "dose_mg_per_kg_per_dose": [4, 10],
                    "frequency": [6, 8],
                    "max_mg_per_dose": 600,
                    "max_mg_per_day": 2400,
                    "note": "⚠️ ไม่แนะนำใช้ >10 วัน เว้นแต่แพทย์สั่ง"
                }
            },
            "Fever": {
                "weight_based": {
                    "dose_mg_per_kg_per_dose": [5, 10],
                    "frequency": [6, 8],
                    "max_mg_per_dose": 600,
                    "max_mg_per_day": 2400,
                    "note": "⚠️ ไม่แนะนำใช้ >3 วัน เว้นแต่แพทย์สั่ง"
                }
            },
            "Juvenile idiopathic arthritis (JIA)": {
                "weight_based": {
                    "dose_mg_per_kg_per_day": [30, 50],
                    "frequency": [6, 8],
                    "max_mg_per_dose": 800,
                    "max_mg_per_day": 2400,
                    "note": "เริ่มต้นที่ 30 mg/kg/day และปรับเพิ่มหากจำเป็น"
                }
            }
        },
        "common_indications": [
            "Analgesic",
            "Fever",
            "Juvenile idiopathic arthritis (JIA)"
        ]
    },


    "Cetirizine": {
    "concentration_mg_per_ml": 5 / 5,
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
        "bottle_size_ml": 15,
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
        CarouselColumn(title='Amoxicillin', text='250 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Amoxicillin')]),
        CarouselColumn(title='Cephalexin', text='125 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cephalexin')]),
        CarouselColumn(title='Cefdinir', text='125 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cefdinir')]),
        CarouselColumn(title='Cefixime', text='100 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cefixime')]),
        CarouselColumn(title='Augmentin', text='600 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Augmentin')]),
    ])
    carousel2 = CarouselTemplate(columns=[
        CarouselColumn(title='Azithromycin', text='200 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Azithromycin')]),
        CarouselColumn(title='Paracetamol', text='120 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Paracetamol')]),
        CarouselColumn(title='Ibuprofen', text='100 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Ibuprofen')]),
        CarouselColumn(title='Domperidone', text='1 mg/1 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Domperidone')]),
        CarouselColumn(title='Ferrous drop', text='15 mg/0.6 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Ferrous drop')]),
    ])
    carousel3 = CarouselTemplate(columns=[
        CarouselColumn(title='Cetirizine', text='1 mg/1 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cetirizine')]),
        CarouselColumn(title='Hydroxyzine', text='10 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Hydroxyzine')]),
        CarouselColumn(title='Chlorpheniramine', text='2 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Chlorpheniramine')]),
        CarouselColumn(title='Salbutamol', text='2 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Salbutamol')]),
    ])
    messaging_api.reply_message(
    ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[
            TemplateMessage(alt_text="เลือกยากลุ่มแรก", template=carousel1),
            TemplateMessage(alt_text="เลือกยากลุ่มเพิ่มเติม", template=carousel2),
            TemplateMessage(alt_text="เลือกยากลุ่มถัดไป", template=carousel3)
        ]
    ))
    return

def send_indication_carousel(event, drug_name, show_all=False):
    # ✅ แก้ไขให้หา drug_name แบบ case-insensitive
    matched_drug = next((k for k in DRUG_DATABASE if k.lower() == drug_name.lower()), None)
    drug_info = DRUG_DATABASE.get(matched_drug)
    
    logging.info(f"🧪 ตรวจสอบ drug_name: {drug_name}")
    logging.info(f"🧪 matched_drug: {matched_drug}")
    logging.info(f"🧪 ใน DRUG_DATABASE: {matched_drug in DRUG_DATABASE if matched_drug else 'ไม่พบ'}")
    logging.info(f"🧪 drug_info: {drug_info}")
    logging.info(f"📦 กำลังหา drug: {drug_name}")
    logging.info(f"🔎 drug_info found: {drug_info is not None}")
    
    if not drug_info or "indications" not in drug_info:
        logging.info("⛔ ไม่พบข้อมูล indications")
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
        text = "ไม่มีข้อมูลขนาดยา"
        action_text = f"Indication: {name}"

        if name != "Indication อื่นๆ":
            indication_info = indications[name]
            dose = None
            unit = None

            if isinstance(indication_info, list):
                first_entry = indication_info[0] if indication_info and isinstance(indication_info[0], dict) else {}
                dose = (
                    first_entry.get("dose_mg_per_kg_per_day")
                    or first_entry.get("dose_mg_per_kg_per_dose")
                    or first_entry.get("dose_mg")
                )

                if "dose_mg_per_kg_per_day" in first_entry:
                    unit = "mg/kg/day"
                elif "dose_mg_per_kg_per_dose" in first_entry:
                    unit = "mg/kg/dose"
                elif "dose_mg" in first_entry:
                    unit = "mg/day"

                # ✅ ลองค้น dose จาก dose_by_day
                if dose is None and isinstance(first_entry.get("dose_by_day"), dict):
                    for day_data in first_entry["dose_by_day"].values():
                        dose = (
                            day_data.get("dose_mg_per_kg_per_day")
                            or day_data.get("dose_mg_per_kg")
                            or day_data.get("dose_mg")
                        )
                        if "dose_mg_per_kg_per_day" in day_data:
                            unit = "mg/kg/day"
                        elif "dose_mg_per_kg" in day_data:
                            unit = "mg/kg"
                        elif "dose_mg" in day_data:
                            unit = "mg"
                        if dose:
                            break

            elif isinstance(indication_info, dict):
                for sub in indication_info.values():
                    if isinstance(sub, dict):
                        dose = (
                            sub.get("dose_mg_per_kg_per_day")
                            or sub.get("dose_mg_per_kg_per_dose")
                            or sub.get("dose_mg")
                        )
                        if "dose_mg_per_kg_per_day" in sub:
                            unit = "mg/kg/day"
                        elif "dose_mg_per_kg_per_dose" in sub:
                            unit = "mg/kg/dose"
                        elif "dose_mg" in sub:
                            unit = "mg/day"
                        if dose:
                            break

            if dose is not None and unit:
                text = f"{dose} {unit}"
        else:
            text = "ดูข้อบ่งใช้อื่นทั้งหมด"
            action_text = f"MoreIndication: {matched_drug or drug_name}"

        actions = [MessageAction(label=label, text=action_text)]
        logging.info(f"📄 Adding column: {title} → {text}")
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
    logging.info(f"📋 จำนวน indication ที่จะแสดง: {len(names_to_show)}")
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

    # ✅ รองรับกรณี indication เป็น dict ซ้อน (sub-indications)
    if isinstance(indication_info, dict) and all(isinstance(v, dict) for v in indication_info.values()):
        for sub_ind, sub_info in indication_info.items():
            dose_per_kg = sub_info.get("dose_mg_per_kg_per_day")
            if dose_per_kg is None:
                continue  # ✅ ข้ามถ้าไม่ใช่แบบ weight-based

            freqs = sub_info["frequency"] if isinstance(sub_info["frequency"], list) else [sub_info["frequency"]]
            days = sub_info["duration_days"]
            max_mg_day = sub_info.get("max_mg_per_day")
            max_mg_per_dose = sub_info.get("max_mg_per_dose")
            note = sub_info.get("note")

            if isinstance(dose_per_kg, list):
                min_dose, max_dose = dose_per_kg
                min_total_mg_day = weight * min_dose
                max_total_mg_day = weight * max_dose

                if max_mg_day:
                    min_total_mg_day = min(min_total_mg_day, max_mg_day)
                    max_total_mg_day = min(max_total_mg_day, max_mg_day)

                ml_per_day_min = min_total_mg_day / conc
                ml_per_day_max = max_total_mg_day / conc
                ml_total = ml_per_day_max * days
                total_ml += ml_total

                min_freq = min(freqs)
                max_freq = max(freqs)
                reply_lines.append(
                    f"📌 {sub_ind}: {min_dose} – {max_dose} mg/kg/day → {min_total_mg_day:.0f} – {max_total_mg_day:.0f} mg/day ≈ "
                    f"{ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                    f"(ครั้งละ ~{ml_per_day_max / max_freq:.1f} – {ml_per_day_min / min_freq:.1f} ml)"
                )
            else:
                total_mg_day = weight * dose_per_kg
                if max_mg_day:
                    total_mg_day = min(total_mg_day, max_mg_day)
                ml_per_day = total_mg_day / conc
                ml_total = ml_per_day * days
                total_ml += ml_total

                if len(freqs) == 1:
                    freq = freqs[0]
                    ml_per_dose = ml_per_day / freq
                    if max_mg_per_dose:
                        ml_per_dose = min(ml_per_dose, max_mg_per_dose / conc)
                    reply_lines.append(
                        f"📌 {sub_ind}: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                        f"ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
                    )
                else:
                    min_freq = min(freqs)
                    max_freq = max(freqs)
                    reply_lines.append(
                        f"📌 {sub_ind}: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                        f"แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน (ครั้งละ ~{ml_per_day / max_freq:.1f} – {ml_per_day / min_freq:.1f} ml)"
                    )

            if note:
                reply_lines.append(f"📝 หมายเหตุ: {note}")

    # ✅ รองรับหลายช่วงวัน (list)
    elif isinstance(indication_info, list):
        for phase in indication_info:
            if not isinstance(phase, dict):
                continue

            # ✅ ตรวจว่าใช้แบบไหน: weight-based หรือ fixed dose
            if "dose_mg_per_kg_per_day" in phase:
                dose_per_kg = phase["dose_mg_per_kg_per_day"]
                total_mg_day = weight * dose_per_kg
                max_mg_day = phase.get("max_mg_per_day")
                if max_mg_day:
                    total_mg_day = min(total_mg_day, max_mg_day)
            elif "dose_mg" in phase:
                total_mg_day = phase["dose_mg"]
            else:
                continue  # ❌ ข้ามถ้าไม่มี dose ทั้งสองแบบ

            title = get_indication_title(phase)
            if title:
                reply_lines.append(f"\n🔹 {title}")

            freqs = phase["frequency"] if isinstance(phase["frequency"], list) else [phase["frequency"]]
            days = phase.get("duration_days") or phase.get("duration_days_range", [0])[0]

            ml_per_day = total_mg_day / conc
            ml_phase = ml_per_day * days
            total_ml += ml_phase

            if len(freqs) == 1:
                freq = freqs[0]
                ml_per_dose = ml_per_day / freq
                if "max_mg_per_dose" in phase:
                    ml_per_dose = min(ml_per_dose, phase["max_mg_per_dose"] / conc)
                day_label = f"📆 {phase['day_range']}:" if "day_range" in phase else "📌"

                reply_lines.append(
                    f"{day_label} {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                    f"ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
                )
            else:
                min_freq = min(freqs)
                max_freq = max(freqs)
                day_label = f"📆 {phase['day_range']}:" if "day_range" in phase else "📌"

                reply_lines.append(
                    f"{day_label} {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                    f"แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน (ครั้งละ ~{ml_per_day / max_freq:.1f} – {ml_per_day / min_freq:.1f} ml)"
                )

    # ✅ กรณี indication เป็น dict ธรรมดา
    else:
        dose_per_kg = indication_info.get("dose_mg_per_kg_per_day")
        if dose_per_kg is None:
            return "❌ ไม่พบข้อมูล dose_mg_per_kg_per_day ใน indication นี้"

        freqs = indication_info["frequency"] if isinstance(indication_info["frequency"], list) else [indication_info["frequency"]]
        days = indication_info["duration_days"]
        max_mg_day = indication_info.get("max_mg_per_day")

        if isinstance(dose_per_kg, list):
            min_dose, max_dose = dose_per_kg
            min_total_mg_day = weight * min_dose
            max_total_mg_day = weight * max_dose

            if max_mg_day:
                min_total_mg_day = min(min_total_mg_day, max_mg_day)
                max_total_mg_day = min(max_total_mg_day, max_mg_day)

            ml_per_day_min = min_total_mg_day / conc
            ml_per_day_max = max_total_mg_day / conc
            total_ml = ml_per_day_max * days

            min_freq = min(freqs)
            max_freq = max(freqs)
            reply_lines.append(
                f"ขนาดยา: {min_dose} – {max_dose} mg/kg/day → {min_total_mg_day:.0f} – {max_total_mg_day:.0f} mg/day ≈ "
                f"{ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                f"(ครั้งละ ~{ml_per_day_max / max_freq:.1f} – {ml_per_day_min / min_freq:.1f} ml)"
            )
        else:
            total_mg_day = weight * dose_per_kg
            if max_mg_day:
                total_mg_day = min(total_mg_day, max_mg_day)

            ml_per_day = total_mg_day / conc
            total_ml = ml_per_day * days

            if len(freqs) == 1:
                freq = freqs[0]
                ml_per_dose = ml_per_day / freq
                if "max_mg_per_dose" in indication_info:
                    ml_per_dose = min(ml_per_dose, indication_info["max_mg_per_dose"] / conc)
                reply_lines.append(
                    f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                    f"ครั้งละ ~{ml_per_dose:.1f} ml × {freq} ครั้ง/วัน × {days} วัน"
                )
            else:
                min_freq = min(freqs)
                max_freq = max(freqs)
                reply_lines.append(
                    f"ขนาดยา: {dose_per_kg} mg/kg/day → {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                    f"แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                    f"(ครั้งละ ~{ml_per_day / max_freq:.1f} – {ml_per_day / min_freq:.1f} ml)"
                )
        note = indication_info.get("note")
        if note:
            reply_lines.append(f"\n📝 หมายเหตุ: {note}")

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

        # ตรวจสอบ age_group ที่มีอยู่จริง
        possible_groups = indication_info.keys()
        
        age_group = None
        if age < 1:
            age_group = "6_to_11_months"
        elif 1 <= age < 2:
            age_group = "12_to_23_months"
        elif 2 <= age <= 5 and "2_to_5_years" in possible_groups:
            age_group = "2_to_5_years"
        elif 6 <= age <= 11 and "6_to_11_years" in possible_groups:
            age_group = "6_to_11_years"
        elif age >= 12 and "above_or_equal_12" in possible_groups:
            age_group = "above_or_equal_12"
        elif age > 5 and "above_5" in possible_groups:
            age_group = "above_5"

        group_data = indication_info.get(age_group)
        if not group_data:
            return f"❌ ไม่พบข้อมูลกลุ่มอายุที่เหมาะสม (อายุ {age} ปี)"

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
        # ✅ ตรวจสอบก่อนว่า entry มี key 'dose_mg_per_kg_per_day'
        dose_per_kg = entry.get("dose_mg_per_kg_per_day")
        if dose_per_kg is None:
            continue  # ข้ามถ้าไม่มี key นี้

        if entry["min_age_years"] <= age < entry["max_age_years"]:
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
                # ✅ หาด้วย .get() อย่างปลอดภัยจาก list ของ dict
                dose = next(
                    (item.get("dose_mg_per_kg_per_day") or item.get("dose_mg")
                    for item in indication_info if isinstance(item, dict)),
                    "?"
                )
            elif isinstance(indication_info, dict):
                sample_group = next(iter(indication_info.values()))
                if isinstance(sample_group, dict):
                    dose = sample_group.get("dose_mg_per_kg_per_day") \
                        or sample_group.get("dose_mg") \
                        or sample_group.get("initial_dose_mg") \
                        or sample_group.get("dose_mg_range", ["?"])[0] \
                        or sample_group.get("dose_range_mg", ["?"])[0] \
                        or "?"
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

def get_indication_title(indication_dict):
    """
    คืนค่าชื่อย่อยของ indication จาก key ที่เหมาะสม เช่น label, sub_indication, title, name
    """
    for key in ["label", "sub_indication", "title", "name"]:
        if key in indication_dict:
            return indication_dict[key]
    return None

def create_quick_reply_items(drug, drug_info):
    items = []

    for indication_name, entry in drug_info["indications"].items():
        if isinstance(entry, list):
            for idx, sub in enumerate(entry):
                title = get_indication_title(sub) or f"{indication_name} #{idx+1}"
                label = title[:20]  # LINE จำกัด label ไม่เกิน 20 ตัวอักษร
                items.append(
                    QuickReplyButton(
                        action=PostbackAction(
                            label=label,
                            data=f"{drug}|{indication_name}|{idx}"
                        )
                    )
                )
        else:
            label = indication_name[:20]
            items.append(
                QuickReplyButton(
                    action=PostbackAction(
                        label=label,
                        data=f"{drug}|{indication_name}|0"
                    )
                )
            )
    return items


def get_indication_entry(drug, indication_name, entry_index=0):
    entries = DRUG_DATABASE[drug]["indications"][indication_name]
    if isinstance(entries, list):
        return entries[int(entry_index)]
    return entries

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

        # ✅ กรณี azithromycin ใช้ special_indication_carousel
        if drug_name == "Azithromycin":
            send_indication_carousel(event, drug_name)

        # ✅ ยาพิเศษอื่น ๆ ที่อยู่ใน SPECIAL_DRUGS
        elif drug_name in SPECIAL_DRUGS:
            send_special_indication_carousel(event, drug_name)

        # ✅ ยาทั่วไปที่อยู่ใน DRUG_DATABASE
        elif drug_name in DRUG_DATABASE:
            send_indication_carousel(event, drug_name)

    if text.startswith("Indication:") and user_id in user_drug_selection:
        indication = text.replace("Indication:", "").strip()
        user_drug_selection[user_id]["indication"] = indication
        drug = user_drug_selection[user_id].get("drug")

        if user_id in user_ages:
            user_ages.pop(user_id)

        if drug in SPECIAL_DRUGS:
            example_age = round(random.uniform(1, 18), 1)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"📆 กรุณาพิมพ์อายุของเด็ก เช่น {example_age} ปี")]
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