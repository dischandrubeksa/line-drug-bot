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
                    "sub_indication": "High-dose regimen × 5–7 วัน",
                    "dose_mg_per_kg_per_day": [80, 90],
                    "frequency": 2,
                    "duration_days_range": [5, 7],
                    "max_mg_per_day": 4000,
                    "note": "📝 แนะนำในประเทศที่มี penicillin-nonsusceptible Streptococcus pneumoniae"
                },
                {
                    "sub_indication": "High-dose regimen × 10 วัน",
                    "dose_mg_per_kg_per_day": [80, 90],
                    "frequency": 2,
                    "duration_days": 10,
                    "max_mg_per_day": 4000,
                    "note": "📝 แนะนำในประเทศที่มี penicillin-nonsusceptible Streptococcus pneumoniae"
                },
                {
                    "sub_indication": "Standard-dose regimen",
                    "dose_mg_per_kg_per_day": [40, 45],
                    "frequency": [2, 3],
                    "duration_days": 10,
                    "max_mg_per_day": 1750,
                    "note": "📝 ใช้ในพื้นที่ที่มีอุบัติการณ์เชื้อดื้อยา penicillin ต่ำ"
                }
            ],
            "Pneumonia (community acquired)": [
                {
                    "label": "Empiric therapy (bacterial pneumonia)",
                    "dose_mg_per_kg_per_day": 90,
                    "frequency": 2,
                    "duration_days": 7,
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
                    "note": "อาจรักษานาน 14 วัน"
                },
                {
                    "name": "Carditis",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 21,
                    "max_mg_per_dose": 500,
                    "note": "อาจรักษานาน 14–21 วัน"
                },
                {
                    "name": "Arthritis (initial, recurrent, or refractory)",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 28,
                    "max_mg_per_dose": 500,
                },
                {
                    "name": "Acrodermatitis chronica atrophicans",
                    "dose_mg_per_kg_per_day": 50,
                    "frequency": 3,
                    "duration_days": 28,
                    "max_mg_per_dose": 500,
                    "note": "อาจรักษานาน 21–28 วัน"
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
    "bottle_size_ml": 30,
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
    "bottle_size_ml": 30,
    "indications": {
        "Gonococcal infection": [
        {
            "sub_indication": "Uncomplicated cervix/urethra/rectum (≥45 kg)",
            "dose_mg": 800,
            "frequency": 1,
            "duration_days": 1,
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
    "concentration_mg_per_ml": 600 / 5,  # ตัวอย่าง: 600 mg amoxicillin + 57 mg clavulanate per 5 mL
    "bottle_size_ml": 70,
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
        "Otitis Media": [
        {
            "sub_indication": "High-dose regimen",
            "dose_mg_per_kg_per_day": [80, 90],
            "frequency": 2,
            "duration_days_range": [5,7,10],
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
        "Fever / Pain": {
            "label": "10–15 mg/kg/dose",
            "dose_mg_per_kg_per_dose": [10, 15],
            "frequency": "ทุก 4–6 ชม.",
            "max_mg_per_day": 4000,
            "note": "ขนาดสูงสุด 75 mg/kg/dose ไม่เกิน 5 ครั้ง/วัน"
        }
    },
    "common_indications": ["Fever / Pain"]
    },

    "Paracetamol drop": {
    "concentration_mg_per_ml": 60 / 0.6,
    "bottle_size_ml": 15,
    "indications": {
        "Fever / Pain": {
            "label": "10–15 mg/kg/dose",
            "dose_mg_per_kg_per_dose": [10, 15],
            "frequency": "ทุก 4–6 ชม.",
            "max_mg_per_day": 4000,
            "note": "ขนาดสูงสุด 75 mg/kg/dose ไม่เกิน 5 ครั้ง/วัน"
        }
    },
    "common_indications": ["Fever / Pain"]
    },

    "Chlorpheniramine": {
        "concentration_mg_per_ml": 2 / 5,  # 2 mg per 5 mL
        "bottle_size_ml": 60,
        "requires_age": True,
        "indications": {
            "Upper respiratory allergy symptoms (hay fever)": [
                {
                    "sub_indication": "อายุตั้งแต่ 2 ถึง <6 ปี",
                    "age_min": 2,
                    "age_max": 5.9,
                    "dose_mg": 1,
                    "frequency": "ทุก 6–8 ชั่วโมง",
                    "max_mg_per_day": 6,
                    "note": "ใช้ด้วยความระมัดระวังในเด็กเล็ก; ไม่แนะนำในเด็ก <2 ปี"
                },
                {
                    "sub_indication": "อายุตั้งแต่ 6 ถึง <12 ปี",
                    "age_min": 6,
                    "age_max": 11.9,
                    "dose_mg": 2,
                    "frequency": "ทุก 6–8 ชั่วโมง",
                    "max_mg_per_day": 12
                },
                {
                    "sub_indication": "อายุตั้งแต่ 12 ปี ขึ้นไป",
                    "age_min": 12,
                    "dose_mg": 4,
                    "frequency": "ทุก 6–8 ชั่วโมง",
                    "max_mg_per_day": 24
                }
            ]
        },
        "common_indications": ["Upper respiratory allergy symptoms (hay fever)"]
    },
    "Salbutamol": {
        "concentration_mg_per_ml": 2 / 5,  # ตัวอย่าง: 2 mg per 5 mL syrup
        "bottle_size_ml": 60,
        "requires_age": True,
        "indications": {
            "Bronchospasm (if inhaled not tolerated)": [
                {
                    "sub_indication": "อายุตั้งแต่ 2 ถึง <6 ปี",
                    "age_min": 2,
                    "age_max": 5.9,
                    "dose_mg_per_kg_per_dose": [0.1, 0.2],  # ✅ ระบุหลายค่าได้ใน list
                    "frequency": 3,
                    "max_mg_per_dose": [2, 4],
                    "max_mg_per_day": 12,
                    "note": "เริ่มต้น 0.1 mg/kg/dose ขนาดยาสูงสุดไม่เกิน 2 mg ต่อครั้ง; อาจสามารถเพิ่มเป็น 0.2 mg/kg/dose ขนาดยาสูงสุดไม่เกิน 4 mg ต่อครั้ง และ 12 mg/วัน"
                },
                {
                    "sub_indication": "อายุมากกว่า 6 ถึง 14 ปี", 
                    "age_min": 6.01,
                    "age_max": 14,
                    "dose_mg": 2,
                    "frequency": [3, 4],
                    "max_mg_per_day": 24
                },
                {
                    "sub_indication": "อายุมากกว่า 14 ปี",
                    "age_min": 14.01,
                    "dose_mg_range": [2, 4],
                    "frequency": [3, 4],
                    "max_mg_per_day": 32
                }
            ]
        },
        "common_indications": ["Bronchospasm (if inhaled not tolerated)"],
        "note": "⚠️ ไม่แนะนำให้ใช้ยานี้ในรูปแบบรับประทานหากสามารถใช้ inhaled ได้ เนื่องจากผลข้างเคียงสูงกว่าและประสิทธิภาพต่ำกว่า"
    },

    "Domperidone": {
        "concentration_mg_per_ml": 1,  # 1 mg/ml
        "bottle_size_ml": 30,
        "requires_age": True,
        "indications": {
            "GI Motility Disorders / Nausea, Vomiting": [
                {
                    "sub_indication": "อายุ ≥12 ปี และน้ำหนัก <35 kg",
                    "age_min": 12,
                    "weight_max": 34.9,
                    "dose_mg_per_kg_per_dose": 0.25,
                    "frequency": [1, 2, 3],
                    "max_mg_per_day": 30,
                    "note": "⚠️ ไม่ควรใช้ในเด็ก <12 ปี; ใช้ขนาดต่ำสุดและระยะเวลาสั้นที่สุด"
                },
                {
                    "sub_indication": "อายุ ≥12 ปี และน้ำหนัก ≥35 kg",
                    "age_min": 12,
                    "weight_min": 35,
                    "dose_mg": 10,
                    "frequency": 3,
                    "max_mg_per_day": 30,
                    "note": "⚠️ ไม่ควรใช้ในเด็ก <12 ปี; ใช้ขนาดต่ำสุดและระยะเวลาสั้นที่สุด"
                }
            ]
        }
    },
    "Ibuprofen": {
        "concentration_mg_per_ml": 100 / 5,
        "bottle_size_ml": 60,
        "indications": {
            "Analgesic": [
                {
                    "type": "weight_based",
                    "dose_mg_per_kg_per_dose": [4, 10],
                    "frequency": "ทุก 6–8 ชั่วโมง",
                    "max_mg_per_dose": 600,
                    "max_mg_per_day": 2400,
                    "max_mg_per_kg_per_day": 40,
                    "note": "ไม่แนะนำให้ใช้ติดต่อกันเกิน 10 วันหากไม่มีคำแนะนำจากแพทย์"
                } 
            ],
            "Fever": [
                {
                    "type": "weight_based",
                    "dose_mg_per_kg_per_dose": [5, 10],
                    "frequency": "ทุก 6–8 ชั่วโมง",
                    "max_mg_per_dose": 600,
                    "max_mg_per_day": 2400,
                    "max_mg_per_kg_per_day": 40,
                    "note": "ไม่ควรใช้เกิน 3 วันหากไม่มีคำแนะนำจากแพทย์"
                } 

            ],
            "Juvenile Idiopathic Arthritis (JIA)": [
                {
                    "type": "weight_based",
                    "dose_mg_per_kg_per_day": [30, 50],
                    "divided_doses": 3,
                    "max_mg_per_dose": 800,
                    "max_mg_per_day": 2400,
                    "note": "เริ่มจากขนาดต่ำและปรับเพิ่มหากจำเป็น"
                }
            ]
        }
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
            "dose_mg": 2.5,
            "frequency": [1, 2],
            "max_mg_per_dose": 2.5,
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
        "6_to_11_months": {
        "dose_mg": 2.5,
        "frequency": 1,
        "max_mg_per_day": 2.5
        },
        "12_to_23_months": {
        "dose_mg": 2.5,
        "frequency": 1,
        "max_mg_per_day": 5
        },
        "2_to_5_years": {
        "dose_range_mg": [2.5, 5],
        "frequency": 1,
        "max_mg_per_day": 5
        },
        "6_to_11_years": {
        "dose_range_mg": [5, 10],
        "frequency": 1,
        "max_mg_per_day": 10
        },
        "above_or_equal_12": {
        "dose_range_mg": [5, 10],
        "frequency": 1,
        "max_mg_per_day": 10
        }
    },

      "Urticaria, chronic spontaneous": {
        "6_to_11_months": {
          "dose_mg": 2.5,
          "frequency": 1,
          "max_mg_per_day": 2.5
        },
        "12_to_23_months": {
        "dose_mg": 2.5,
        "frequency": 1,
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
        "dose_range_mg": [5, 10],
        "frequency": 1,
        "max_mg_per_day": 10
        },
        "above_or_equal_12": {
        "dose_range_mg": [5, 10],
        "frequency": 1,
        "max_mg_per_day": 10
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
    "Carbocysteine": {
    "concentration_mg_per_ml": 450 / 5,
    "bottle_size_ml": 120,
    "indications": {
        "mucolytic (age-based)": [
            {
                "sub_indication": "อายุ 2 ถึง <6 ปี",
                "age_min": 2,
                "age_max": 5.9,
                "dose_mg": [62.5, 125],
                "frequency": 4,
                "max_mg_per_day": 500
            },
            {
                "sub_indication": "อายุ 6 ถึง <12 ปี",
                "age_min": 6,
                "age_max": 11.9,
                "dose_mg": [100, 250],
                "frequency": 3,
                "max_mg_per_day": 750
            },
            {
                "sub_indication": "อายุ 12 ถึง <15 ปี",
                "age_min": 12,
                "age_max": 14.9,
                "dose_mg": [100, 750],
                "frequency": 3,
                "max_mg_per_day": 2250
            },
            {
                "sub_indication": "อายุ ≥15 ปี",
                "age_min": 15,
                "dose_mg": [500, 750],
                "frequency": [2, 3],
                "max_mg_per_day": 2250
            }
        ],
        "mucolytic (weight-based)": {
            "age_min": 2,
            "dose_mg_per_kg_per_day": [15, 20],
            "frequency": [3, 4],
            "max_mg_per_day": 2250
        }
    }
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
            }
        },
        "common_indications": [
        "Anxiety",
        "Pruritus (age-based)",
        "Pruritus (weight_based)",
        "Pruritus from opioid",
        ]
    },
    "Ferrous drop": {
        "concentration_mg_per_ml": 15 / 0.6,
        "bottle_size_ml": 15,
        "indications": {
            "Iron deficiency, treatment": {
                "label": "3 mg/kg/day",
                "all_ages": {
                    "initial_dose_mg_per_kg_per_day": 3,
                    "max_dose_range_mg_per_day": [60, 120],
                    "usual_max_mg_per_day": 150,
                    "absolute_max_mg_per_day": 200,
                    "frequency": [1, 2, 3],  # ✅ เพิ่ม 2 เข้าไปด้วย รองรับ dose แบ่ง 2 ครั้ง
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

def send_drug_ATB_selection(event):
    # ✅ เตรียม column แต่ละชุด
    columnsA1 = [
        CarouselColumn(title='Amoxicillin', text='250 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Amoxicillin')]),
        CarouselColumn(title='Augmentin', text='600 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Augmentin')]),
        CarouselColumn(title='Azithromycin', text='200 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Azithromycin')]),
    ]
    columnsA2 = [
        
        CarouselColumn(title='Cephalexin', text='125 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cephalexin')]),
        CarouselColumn(title='Cefdinir', text='125 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cefdinir')]),
        CarouselColumn(title='Cefixime', text='100 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cefixime')]),
    ]
    messages = []
    if columnsA1:
        messages.append(TemplateMessage(alt_text="เลือกยาฆ่าเชื้อ", template=CarouselTemplate(columns=columnsA1)))
    if columnsA2:
        messages.append(TemplateMessage(alt_text="เลือกยาฆ่าเชื้อเพิ่มเติม", template=CarouselTemplate(columns=columnsA2)))
    
    if messages:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )

def send_drug_APY_selection(event):
    # ✅ เตรียม column แต่ละชุด
    columnsA1 = [
        CarouselColumn(title='Paracetamol', text='120 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Paracetamol')]), 
        CarouselColumn(title='Paracetamol drop', text='60 mg/0.6 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Paracetamol drop')]),
        CarouselColumn(title='Ibuprofen', text='100 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Ibuprofen')]),
    ]
    messages = []
    if columnsA1:
        messages.append(TemplateMessage(alt_text="เลือกยาแก้ปวด ลดไข้", template=CarouselTemplate(columns=columnsA1)))
    
    if messages:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )

def send_drug_AH_selection(event):
    # ✅ เตรียม column แต่ละชุด
    columnsA1 = [
        CarouselColumn(title='Cetirizine', text='1 mg/1 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Cetirizine')]),
        CarouselColumn(title='Hydroxyzine', text='10 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Hydroxyzine')]),
        CarouselColumn(title='Chlorpheniramine', text='2 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Chlorpheniramine')]),
    ]

    messages = []
    if columnsA1:
        messages.append(TemplateMessage(alt_text="เลือกยาแก้แพ้", template=CarouselTemplate(columns=columnsA1)))
    
    if messages:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )

def send_drug_OT_selection(event):
    # ✅ เตรียม column แต่ละชุด
    columnsA1 = [
        CarouselColumn(title='Carbocysteine', text='450 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Carbocysteine')]),
        CarouselColumn(title='Domperidone', text='1 mg/1 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Domperidone')]),
        CarouselColumn(title='Salbutamol', text='2 mg/5 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Salbutamol')]),
        CarouselColumn(title='Ferrous drop', text='15 mg/0.6 ml', actions=[MessageAction(label='เลือก', text='เลือกยา: Ferrous drop')]),
    ]
   
    messages = []
    if columnsA1:
        messages.append(TemplateMessage(alt_text="เลือกยาอื่นๆ", template=CarouselTemplate(columns=columnsA1)))
    
    if messages:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )


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



def calculate_warfarin(inr, twd, bleeding, supplement=None):
    if bleeding == "yes":
        return "\U0001f6a8 มี major bleeding → หยุด Warfarin, ให้ Vitamin K1 10 mg IV"

    warning = ""
    if supplement:
        herb_map = {
            "กระเทียม": "garlic", "ใบแปะก๊วย": "ginkgo", "โสม": "ginseng",
            "ขมิ้น": "turmeric", "น้ำมันปลา": "fish oil", "dong quai": "dong quai", "cranberry": "cranberry",
            "ตังกุย": "dong quai", "โกจิ": "goji berry", "คาร์โมไมล์": "chamomile", "ขิง": "ginger", "ชะเอมเทศ": "licorice",
            "ชาเขียว": "green tea", "นมถั่วเหลือง": "soy milk", "คลอโรฟิลล์": "chlorophyll",
            "วิตามินเค": "vitamin K", "โคเอนไซม์ Q10": "Coenzyme Q10", "St.John’s Wort": "St.John’s Wort"
        }
        high_risk = list(herb_map.keys())
        matched = [name for name in high_risk if name in supplement]
        if matched:
            herbs = ", ".join(matched)
            warning = f"\n\u26a0\ufe0f พบว่าสมุนไพร/อาหารเสริมที่อาจมีผลต่อ INR ได้แก่: {herbs}\nโปรดพิจารณาความเสี่ยงต่อการเปลี่ยนแปลง INR อย่างใกล้ชิด"
        else:
            warning = "\n\u26a0\ufe0f มีการใช้อาหารเสริมหรือสมุนไพร → พิจารณาความเสี่ยงต่อการเปลี่ยนแปลง INR"

    followup_text = get_followup_text(inr)

    if inr < 1.5:
        result = f"\U0001f539 INR < 1.5 → เพิ่มขนาดยา 10–20%\nขนาดยาใหม่: {twd * 1.1:.1f} – {twd * 1.2:.1f} mg/สัปดาห์"
    elif 1.5 <= inr <= 1.9:
        result = f"\U0001f539 INR 1.5–1.9 → เพิ่มขนาดยา 5–10%\nขนาดยาใหม่: {twd * 1.05:.1f} – {twd * 1.10:.1f} mg/สัปดาห์"
    elif 2.0 <= inr <= 3.0:
        result = "✅ INR 2.0–3.0 → คงขนาดยาเดิม"
    elif 3.1 <= inr <= 3.9:
        result = f"\U0001f539 INR 3.1–3.9 → ลดขนาดยา 5–10%\nขนาดยาใหม่: {twd * 0.9:.1f} – {twd * 0.95:.1f} mg/สัปดาห์"
    elif 4.0 <= inr <= 4.9:
        result = f"⚠\ufe0f INR 4.0–4.9 → หยุดยา 1 วัน และลดขนาดยา 10%\nขนาดยาใหม่: {twd * 0.9:.1f} mg/สัปดาห์"
    elif 5.0 <= inr <= 8.9:
        result = "⚠\ufe0f INR 5.0–8.9 → หยุดยา 1–2 วัน และพิจารณาให้ Vitamin K1 1 mg"
    else:
        result = "\U0001f6a8 INR ≥ 9.0 → หยุดยา และพิจารณาให้ Vitamin K1 5–10 mg"

    return f"{result}{warning}\n\n{followup_text}"

def get_inr_followup(inr):
    if inr < 1.5: return 7
    elif inr <= 1.9: return 14
    elif inr <= 3.0: return 56
    elif inr <= 3.9: return 14
    elif inr <= 6.0: return 7
    elif inr <= 8.9: return 5
    elif inr > 9.0: return 2
    return None

def get_followup_text(inr):
    days = get_inr_followup(inr)
    if days:
        date = (datetime.now() + timedelta(days=days)).strftime("%-d %B %Y")
        return f"📅  คำแนะนำ: ควรตรวจ INR ภายใน {days} วัน\n📌 วันที่ควรตรวจ: {date}"
    else:
        return ""



def send_supplement_flex(reply_token):
    flex_content = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🌿 สมุนไพร/อาหารเสริม", "weight": "bold", "size": "lg"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "ผู้ป่วยใช้สิ่งใดบ้าง?", "wrap": True, "size": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "height": "sm", "color": "#84C1FF",
                         "action": {"type": "message", "label": "ไม่ได้ใช้", "text": "ไม่ได้ใช้"}},
                        *[
                            {"type": "button", "style": "primary", "height": "sm", "color": "#AEC6CF",
                             "action": {"type": "message", "label": herb, "text": herb}}
                            for herb in ["กระเทียม", "ใบแปะก๊วย", "โสม", "ขมิ้น", "ขิง", "น้ำมันปลา", "ใช้หลายชนิด", "สมุนไพร/อาหารเสริมชนิดอื่นๆ"]
                        ]
                    ]
                }
            ]
        },
        "styles": {
            "header": {"backgroundColor": "#D0E6FF"},
            "body": {"backgroundColor": "#FFFFFF"}
        }
    }

    flex_container = FlexContainer.from_dict(flex_content)

    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[FlexMessage(alt_text="เลือกสมุนไพร/อาหารเสริม", contents=flex_container)]
        )
    )
def send_interaction_flex(reply_token):
    interaction_drugs = [
        "Amiodarone", "Gemfibrozil", "Azole antifungal", "Trimethoprim/Sulfamethoxazole",
        "Macrolides(ex.Erythromycin)", "NSAIDs", "Quinolones(ex.Ciprofloxacin)"
    ]
    flex_content = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": "💊 ยาที่อาจมีปฏิกิริยารุนแรงกับ Warfarin", "weight": "bold", "size": "lg"}]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "ผู้ป่วยได้รับยาใดบ้าง?", "wrap": True, "size": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "height": "sm", "color": "#84C1FF",
                         "action": {"type": "message", "label": "ไม่ได้ใช้", "text": "ไม่ได้ใช้"}}
                    ] + [
                        {"type": "button", "style": "primary", "height": "sm", "color": "#FFD700",
                         "action": {"type": "message", "label": drug, "text": drug}}
                        for drug in interaction_drugs
                    ] + [
                        {"type": "button", "style": "primary", "height": "sm", "color": "#FFB6C1",
                         "action": {"type": "message", "label": "ใช้หลายชนิด", "text": "ใช้หลายชนิด"}},
                        {"type": "button", "style": "primary", "height": "sm", "color": "#D8BFD8",
                         "action": {"type": "message", "label": "ยาชนิดอื่นๆ", "text": "ยาชนิดอื่นๆ"}}
                    ]
                }
            ]
        },
        "styles": {
            "header": {"backgroundColor": "#F9E79F"},
            "body": {"backgroundColor": "#FFFFFF"}
        }
    }
    flex_container = FlexContainer.from_dict(flex_content)
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[FlexMessage(alt_text="เลือกยาที่มีปฏิกิริยา", contents=flex_container)]
        )
    )

def calculate_dose(drug, indication, weight, age=None):
    
    MIN_AGE_LIMITS = {
        "Cefixime": 0.5,          # 6 เดือน
        "Cefdinir": 0.5,          # 6 เดือน
        "Azithromycin": 0.5,      # 6 เดือน
        "Cephalexin": 0.083,      # 1 เดือน
    }
     
    if age is not None:
        min_age = MIN_AGE_LIMITS.get(drug)
        if min_age is not None and age < min_age:
            # 🔁 แปลง min_age (float) → ปี เดือน
            total_months = int(round(min_age * 12))
            display_years = total_months // 12
            display_months = total_months % 12

            parts = []
            if display_years > 0:
                parts.append(f"{display_years} ปี")
            if display_months > 0:
                parts.append(f"{display_months} เดือน")
            if not parts:
                parts.append("0 เดือน")

            readable_min_age = " ".join(parts)

            return f"❌ ไม่แนะนำให้ใช้ {drug} ในเด็กอายุน้อยกว่า {readable_min_age}"
    
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
                min_freq = min(freqs)
                max_freq = max(freqs)
                min_dose_per_time = min(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
                max_dose_per_time = max(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
                min_dose_per_time, max_dose_per_time = sorted([min_dose_per_time, max_dose_per_time])

                
                reply_lines.append(
                    f"📌 {sub_ind}: {min_dose} – {max_dose} mg/kg/day → {min_total_mg_day:.0f} – {max_total_mg_day:.0f} mg/day ≈ "
                    f"{ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                    f"(ครั้งละ ~{min_dose_per_time:.1f} – {max_dose_per_time:.1f} ml)"
                )
                 # ✅ เพิ่มส่วนนี้เพื่อคำนวณขวดของ sub นี้เท่านั้น
                bottles_needed = math.ceil(ml_total / bottle_size)
                reply_lines.append(f"→ รวม {ml_total:.1f} ml ≈ {bottles_needed} ขวด (ขวดละ {bottle_size} ml)")
            else:
                total_mg_day = weight * dose_per_kg
                if max_mg_day:
                    total_mg_day = min(total_mg_day, max_mg_day)
                ml_per_day = total_mg_day / conc
                ml_total = ml_per_day * days

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
                # ✅ เพิ่มตรงนี้เพื่อแสดงจำนวนขวดเฉพาะของ sub นี้
                bottles_needed = math.ceil(ml_total / bottle_size)
                reply_lines.append(f"→ รวม {ml_total:.1f} ml ≈ {bottles_needed} ขวด (ขวดละ {bottle_size} ml)")


            if note:
                reply_lines.append(f"📝 หมายเหตุ: {note}")

    # ✅ รองรับหลายช่วงวัน (list)
    elif isinstance(indication_info, list):
        for phase in indication_info:
            if not isinstance(phase, dict):
                continue

            total_mg_day = None
            dose_type = None

            # ✅ ตรวจว่าใช้แบบไหน: weight-based หรือ fixed dose
            if "dose_mg_per_kg_per_day" in phase:
                dose_per_kg = phase["dose_mg_per_kg_per_day"]
                max_mg_day = phase.get("max_mg_per_day")
                dose_type = "weight_based"

                if isinstance(dose_per_kg, list):
                    min_dose, max_dose = dose_per_kg
                    min_total_mg_day = weight * min_dose
                    max_total_mg_day = weight * max_dose
                    if max_mg_day:
                        min_total_mg_day = min(min_total_mg_day, max_mg_day)
                        max_total_mg_day = min(max_total_mg_day, max_mg_day)
                    total_mg_day = (min_total_mg_day, max_total_mg_day)
                else:
                    total_mg_day = weight * dose_per_kg
                    if max_mg_day:
                        total_mg_day = min(total_mg_day, max_mg_day)

            elif "dose_mg" in phase:
                total_mg_day = phase["dose_mg"]
                dose_type = "fixed"

            else:
                continue  # ❌ ข้ามถ้าไม่มี dose

            # ✅ ชื่อ label/title
            title = get_indication_title(phase)
            if title:
                reply_lines.append(f"\n🔹 {title}")

            freqs = phase["frequency"] if isinstance(phase["frequency"], list) else [phase["frequency"]]
            days = phase.get("duration_days") or phase.get("duration_days_range", [0])[0]
            day_label = f"📆 {phase['day_range']}:" if "day_range" in phase else "📌"

            if isinstance(total_mg_day, tuple):
                min_mg, max_mg = total_mg_day
                ml_per_day_min = min_mg / conc
                ml_per_day_max = max_mg / conc
                ml_total = ml_per_day_max * days  # ✅ แยก ml เฉพาะของช่วงนี้ แก้ตรงนี้เมื่อกี้ 


                min_freq = min(freqs)
                max_freq = max(freqs)
                min_dose_per_time = min(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
                max_dose_per_time = max(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
                min_dose_per_time, max_dose_per_time = sorted([min_dose_per_time, max_dose_per_time])
                
                if min_freq == max_freq:
                    reply_lines.append(
                        f"{day_label} {min_mg:.0f} – {max_mg:.0f} mg/day ≈ {ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, "
                        f"แบ่งวันละ {min_freq} ครั้ง × {days} วัน "
                        f"(ครั้งละ ~{min_dose_per_time:.1f} – {max_dose_per_time:.1f} ml)"
                    )
                else:
                    reply_lines.append(
                        f"{day_label} {min_mg:.0f} – {max_mg:.0f} mg/day ≈ {ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, "
                        f"แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                        f"(ครั้งละ ~{min_dose_per_time:.1f} – {max_dose_per_time:.1f} ml)"
                    )
                # ✅ คำนวณขวดเฉพาะของช่วงนี้
                bottles_needed = math.ceil(ml_total / bottle_size)
                reply_lines.append(f"→ รวม {ml_total:.1f} ml ≈ {bottles_needed} ขวด (ขวดละ {bottle_size} ml)")  

            else:
                ml_per_day = total_mg_day / conc
                ml_phase = ml_per_day * days

                min_freq = min(freqs)
                max_freq = max(freqs)

                if min_freq == max_freq:
                    ml_per_dose = ml_per_day / min_freq
                    if "max_mg_per_dose" in phase:
                        ml_per_dose = min(ml_per_dose, phase["max_mg_per_dose"] / conc)

                    reply_lines.append(
                        f"{day_label} {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                        f"แบ่งวันละ {min_freq} ครั้ง × {days} วัน (ครั้งละ ~{ml_per_dose:.1f} ml)"
                    )
                else:
                    reply_lines.append(
                        f"{day_label} {total_mg_day:.0f} mg/day ≈ {ml_per_day:.1f} ml/day, "
                        f"แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                        f"(ครั้งละ ~{ml_per_day / max_freq:.1f} – {ml_per_day / min_freq:.1f} ml)"
                    )
                # ✅ คำนวณขวดเฉพาะของช่วงนี้
                bottles_needed = math.ceil(ml_phase / bottle_size)
                reply_lines.append(f"→ รวม {ml_phase:.1f} ml ≈ {bottles_needed} ขวด (ขวดละ {bottle_size} ml)")

            note = phase.get("note")
            if note:
                reply_lines.append(f"📝 หมายเหตุ: {note}")



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
            min_dose_per_time = min(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
            max_dose_per_time = max(ml_per_day_min / min_freq, ml_per_day_max / max_freq)
            min_dose_per_time, max_dose_per_time = sorted([min_dose_per_time, max_dose_per_time])

            reply_lines.append(
                f"ขนาดยา: {min_dose} – {max_dose} mg/kg/day → {min_total_mg_day:.0f} – {max_total_mg_day:.0f} mg/day ≈ "
                f"{ml_per_day_min:.1f} – {ml_per_day_max:.1f} ml/day, แบ่งวันละ {min_freq} – {max_freq} ครั้ง × {days} วัน "
                f"(ครั้งละ ~{min_dose_per_time:.1f} – {max_dose_per_time:.1f} ml)"
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

    return "\n".join(reply_lines)

def calculate_special_drug(user_id, drug, weight, age):
    info = SPECIAL_DRUGS[drug]
    indication = user_drug_selection.get(user_id, {}).get("indication")
    indication_info = next(iter(info["indications"].values()))
    concentration = info["concentration_mg_per_ml"]

    if drug == "Carbocysteine":
        concentration = info["concentration_mg_per_ml"]

        if indication == "mucolytic (age-based)":
            data = info["indications"]["mucolytic (age-based)"]

            reply_lines = [f"🧪 {drug} - การใช้แบบอิงอายุ", f"(น้ำหนัก {weight:.1f} kg, อายุ {age:.1f} ปี):\n"]

            matched = False
            for profile in data:
                if age >= profile["age_min"] and ("age_max" not in profile or age <= profile["age_max"]):
                    freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
                    freq_str = f"{min(freqs)}–{max(freqs)}" if len(freqs) > 1 else f"{freqs[0]}"
                    dose_range = profile["dose_mg"] if isinstance(profile["dose_mg"], list) else [profile["dose_mg"]]

                    reply_lines.append(f"🔹 {profile['sub_indication']}")
                    for dose in dose_range:
                        dose_per_time = min(dose, profile["max_mg_per_day"])
                        volume = round(dose_per_time / concentration, 1)
                        reply_lines.append(f"ขนาดยา: {dose_per_time:.1f} mg × วันละ {freq_str} ครั้ง ≈ ~{volume:.1f} ml/ครั้ง")

                    if "note" in profile:
                        reply_lines.append(f"\n📌 หมายเหตุ: {profile['note']}")
                    matched = True
                    break

            if not matched:
                reply_lines.append("❌ ไม่พบช่วงอายุที่รองรับ")

            return "\n".join(reply_lines)

        elif indication == "mucolytic (weight-based)":
            data = info["indications"]["mucolytic (weight-based)"]
            if age < data["age_min"]:
                return f"❌ ไม่แนะนำการใช้ Carbocysteine ตามน้ำหนักในเด็กอายุน้อยกว่า {data['age_min']} ปี"

            dose_min, dose_max = data["dose_mg_per_kg_per_day"]
            freqs = data["frequency"]
            max_dose = data["max_mg_per_day"]

            reply_lines = [f"🧪 {drug} - การใช้แบบอิงน้ำหนัก", f"(น้ำหนัก {weight:.1f} kg, อายุ {age:.1f} ปี):\n"]

            for dose_per_kg in [dose_min, dose_max]:
                total_mg_day = weight * dose_per_kg
                reply_lines.append(f"💊 ขนาดรวมทั้งวัน: {dose_per_kg:.1f} mg/kg/day × {weight:.1f} kg = {total_mg_day:.1f} mg/day")

                for freq in freqs:
                    dose_per_time = min(total_mg_day / freq, max_dose)
                    volume = round(dose_per_time / concentration, 1)
                    reply_lines.append(f"  → วันละ {freq} ครั้ง → ครั้งละ ~{dose_per_time:.1f} mg ≈ ~{volume:.1f} ml/ครั้ง")

            reply_lines.append("\n📌 หมายเหตุ: ขนาดยาไม่ควรเกิน 2,250 mg/วัน")
            return "\n".join(reply_lines)

        else:
            return f"❌ ยังไม่รองรับข้อบ่งใช้ {indication} ของ {drug}"
    
    if drug == "Hydroxyzine" and age < 2:
        return "❌ ไม่แนะนำให้ใช้ Hydroxyzine ในเด็กอายุน้อยกว่า 2 ปี"

    if drug == "Hydroxyzine":
        if indication in ["Anxiety", "Pruritus (age-based)"]:
            data = info["indications"][indication]
            concentration = info["concentration_mg_per_ml"]

            if age < 6:
                profile = data["under_6"]
                freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
                dose = profile["dose_mg"]
                volume = round(dose / concentration, 1)
                freq_str = f"{min(freqs)}–{max(freqs)}" if len(freqs) > 1 else f"{freqs[0]}"

                reply_lines = [
                    f"🧪 {drug} - {indication}",
                    f"(น้ำหนัก {weight:.1f} kg, อายุ {age:.1f} ปี):\n",
                    f"🔹 อายุน้อยกว่า 6 ปี",
                    f"ขนาดยา: {dose:.1f} mg × วันละ {freq_str} ครั้ง ≈ ~{volume:.1f} ml/ครั้ง",
                ]

                # หมายเหตุแยกตาม indication
                if indication == "Anxiety":
                    reply_lines.append("")
                    reply_lines.append("📌 หมายเหตุเพิ่มเติม: แม้ FDA จะอนุมัติให้ใช้ในเด็ก <6 ปี แต่แนวทางผู้เชี่ยวชาญส่วนใหญ่ไม่แนะนำให้ใช้ยาในกลุ่มนี้")
                elif indication == "Pruritus (age-based)":
                    reply_lines.append("")
                    reply_lines.append(
                        "📌 หมายเหตุ: อ้างอิงจากการศึกษาทางเภสัชจลนศาสตร์ ยานี้อาจให้วันละครั้ง (ก่อนนอน) หรือวันละ 2 ครั้งก็เพียงพอ เนื่องจากมีครึ่งชีวิตยาว"
                    )

                return "\n".join(reply_lines)

            else:
                profile = data["above_or_equal_6"]
                freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
                dose_range = profile["dose_mg_range"]
                max_dose = profile["max_mg_per_dose"]
                freq_str = f"{min(freqs)}–{max(freqs)}" if len(freqs) > 1 else f"{freqs[0]}"

                reply_lines = [
                    f"🧪 {drug} - {indication}",
                    f"(น้ำหนัก {weight:.1f} kg, อายุ {age:.1f} ปี):\n",
                    f"🔹 อายุตั้งแต่ 6 ปีขึ้นไป"
                ]

                for dose in dose_range:
                    dose_per_time = min(dose, max_dose)
                    volume = round(dose_per_time / concentration, 1)
                    reply_lines.append(f"ขนาดยา: {dose_per_time:.1f} mg × วันละ {freq_str} ครั้ง ≈ ~{volume:.1f} ml/ครั้ง")

                reply_lines.append("")

                # หมายเหตุแยกตาม indication
                if indication == "Anxiety":
                    reply_lines.append("📌 หมายเหตุเพิ่มเติม: แนวทางผู้เชี่ยวชาญไม่แนะนำให้ใช้ Hydroxyzine ในเด็กเพื่อรักษาภาวะวิตกกังวล")
                elif indication == "Pruritus (age-based)":
                    reply_lines.append(
                        "📌 หมายเหตุ: จากการศึกษาทางเภสัชจลนศาสตร์ อาจให้วันละครั้ง (ก่อนนอน) หรือวันละ 2 ครั้งก็เพียงพอ เนื่องจากมีครึ่งชีวิตยาว"
                    )

                return "\n".join(reply_lines)

        elif indication == "Pruritus (weight_based)":
            data = info["indications"][indication]

            if weight <= 40:
                profile = data["≤40kg"]
                dose_per_kg = profile["dose_mg_per_kg_per_day"]
                freqs = sorted(profile["frequency"])  # เช่น [6, 8]
                max_dose = profile["max_mg_per_dose"]
                concentration = info["concentration_mg_per_ml"]

                total_mg_day = weight * dose_per_kg

                dose_lines = []
                for freq in freqs:
                    dose_per_time = min(total_mg_day / freq, max_dose)
                    volume = round(dose_per_time / concentration, 1)
                    dose_lines.append((freq, dose_per_time, volume))

                reply_text = (
                    f"🧪 {drug} - {indication} (≤40kg)\n"
                    f"(น้ำหนัก {weight:.1f} kg, อายุ {age:.1f} ปี):\n\n"
                    f"ขนาดยา: {total_mg_day:.1f} mg/day\n"
                    f"  → วันละ {dose_lines[0][0]} ครั้ง → ครั้งละ ~{dose_lines[0][1]:.1f} mg ≈ ~{dose_lines[0][2]:.1f} ml/ครั้ง\n"
                    f"  → วันละ {dose_lines[1][0]} ครั้ง → ครั้งละ ~{dose_lines[1][1]:.1f} mg ≈ ~{dose_lines[1][2]:.1f} ml/ครั้ง\n\n"
                    f"📌 หมายเหตุ: จากการศึกษาทางเภสัชจลนศาสตร์ อาจให้วันละครั้ง (ก่อนนอน) หรือวันละ 2 ครั้งก็เพียงพอ เนื่องจากมีครึ่งชีวิตยาว"
                )

                return reply_text

        else:
            return f"❌ ยังไม่รองรับข้อบ่งใช้ {indication} ของ {drug}"

    
    if drug in ["Cetirizine"]:
        data = info["indications"][indication]
        concentration = info["concentration_mg_per_ml"]

        if drug == "Cetirizine" and age < 0.5:
            return "❌ ไม่แนะนำให้ใช้ในเด็กอายุน้อยกว่า 6 เดือน"

        # ✅ แปลงช่วงอายุ
        if drug == "Cetirizine" and indication == "Anaphylaxis (adjunctive only)":
            if age < 2:
                age_key = "6_to_23_months"
            elif 2 <= age <= 5:
                age_key = "2_to_5_years"
            else:
                age_key = "above_5"
        else:
            if age < 1:
                age_key = "6_to_11_months"
            elif 1 <= age < 2:
                age_key = "12_to_23_months"
            elif 2 <= age <= 5:
                age_key = "2_to_5_years"
            elif 6 <= age <= 11:
                if "6_to_11_years" in data:
                    age_key = "6_to_11_years"
                elif "above_or_equal_6" in data:
                    age_key = "above_or_equal_6"
                else:
                    return f"❌ ยังไม่มีข้อมูลช่วงอายุนี้ใน indication {indication}"   
            elif age >= 12:
                age_key = "above_or_equal_12"
            else:
                return f"❌ ไม่พบช่วงอายุที่เหมาะสม (อายุ {age} ปี)"

        # ✅ ตรวจสอบว่ามีข้อมูลช่วงอายุนี้หรือไม่
        profile = data.get(age_key)
        if not profile:
            return f"❌ ยังไม่มีข้อมูลช่วงอายุนี้ใน indication {indication}"

        lines = [f"{drug} - {indication} (อายุ {age:.1f} ปี):"]

        def format_frequency(freqs):
            freqs = sorted(set(freqs))
            if len(freqs) == 1:
                return f"{freqs[0]}"
            if freqs == list(range(freqs[0], freqs[-1] + 1)):
                return f"{freqs[0]}–{freqs[-1]}"
            return " หรือ ".join(str(f) for f in freqs)

        # 👉 แบบ initial_dose + options
        if "initial_dose_mg" in profile and "options" in profile:
            init_dose = profile["initial_dose_mg"]
            init_freq = profile["frequency"]
            init_vol = round(init_dose / concentration, 1)
            lines.append("💊 ขนาดยาแนะนำ:")
            lines.append(f"• เริ่มต้น: {init_dose} mg × {init_freq} ครั้ง/วัน ≈ ~{init_vol} ml/ครั้ง")
            if profile.get("options"):
                lines.append("• ตัวเลือกอื่น:")
                for opt in profile["options"]:
                    dose = opt["dose_mg"]
                    freq = opt["frequency"]
                    vol = round(dose / concentration, 1)
                    lines.append(f"   - {dose} mg × {freq} ครั้ง/วัน ≈ ~{vol} ml/ครั้ง")
        else:
            # ✅ กรณีปกติ: dose_mg_range หรือ dose_mg + frequency
            freqs = profile["frequency"] if isinstance(profile["frequency"], list) else [profile["frequency"]]
            if "dose_mg_range" in profile:
                dose_range = profile["dose_mg_range"]
            elif "dose_range_mg" in profile:
                dose_range = profile["dose_range_mg"]  # 👈 รองรับชื่อเก่าที่ผิด
            elif "dose_mg" in profile:
                dose_range = [profile["dose_mg"]]
            else:
                return "❌ ไม่พบข้อมูล dose_mg ที่เหมาะสมใน profile"
            
            max_dose = profile.get("max_mg_per_dose", None)

            for dose in dose_range:
                dose_per_time = min(dose, max_dose) if max_dose else dose
                vol = round(dose_per_time / concentration, 1)
                freq_text = format_frequency(freqs)
                lines.append(f"💊 ขนาดยา: {dose_per_time} mg × {freq_text} ครั้ง/วัน ≈ ~{vol} ml/ครั้ง")

            if max_dose:
                lines.append(f"\n📌 ขนาดยาสูงสุดต่อครั้ง: {max_dose} mg")

        if "max_mg_per_day" in profile:
            lines.append(f"📌 ขนาดยาสูงสุดต่อวัน: {profile['max_mg_per_day']} mg")

        return "\n".join(lines)


    
    if drug == "Ferrous drop":
        indication_info = info["indications"][indication]["all_ages"]
        dose_per_kg = indication_info["initial_dose_mg_per_kg_per_day"]
        max_range = indication_info["max_dose_range_mg_per_day"]
        usual_max = indication_info.get("usual_max_mg_per_day")
        absolute_max = indication_info.get("absolute_max_mg_per_day")
        concentration = info.get("concentration_mg_per_ml")
        note = indication_info.get("note", "")

        # คำนวณ total dose
        total_mg_day = weight * dose_per_kg
        total_mg_day = max(total_mg_day, max_range[0])
        total_mg_day = min(total_mg_day, max_range[1])
        if absolute_max:
            total_mg_day = min(total_mg_day, absolute_max)

        # เริ่มข้อความ
        reply_lines = [
            f"🧪 {drug} - {indication} (น้ำหนัก {weight:.1f} kg):\n",
            f"💊 {dose_per_kg:.0f} mg/kg/day → {total_mg_day:.1f} mg/day"
        ]

        # รองรับความถี่ 1–3 ครั้ง/วัน
        for freq in [1, 2, 3]:
            dose_per_time = total_mg_day / freq
            line = f"→ วันละ {freq} ครั้ง → ครั้งละ ~{dose_per_time:.1f} mg"
            if concentration:
                volume = round(dose_per_time / concentration, 1)
                line += f" ≈ ~{volume:.1f} ml/ครั้ง"
            reply_lines.append(line)

        if usual_max:
            reply_lines.append(f"\n(max usual: {usual_max} mg/day)")
        if absolute_max:
            reply_lines.append(f"(absolute max: {absolute_max} mg/day)")

        if note:
            reply_lines.append(f"\n📌 หมายเหตุ: {note}")

        return "\n".join(reply_lines)
    
    if drug == "Domperidone" and age < 1 / 12:  # 1 เดือน = 1/12 ปี
        return "❌ ไม่แนะนำให้ใช้ Domperidone ในเด็กอายุน้อยกว่า 1 เดือน"

    if drug == "Domperidone":
        indication_data = info["indications"].get(indication)
        if not indication_data:
            return f"❌ ไม่พบข้อมูลข้อบ่งใช้ {indication}"

        lines = [f"{drug} - {indication} (น้ำหนัก {weight} kg, อายุ {age} ปี):"]

        matched_group = None
        for group in indication_data:
            min_age = group.get("age_min", 0)
            max_age = group.get("age_max", float("inf"))
            min_weight = group.get("weight_min", 0)
            max_weight = group.get("weight_max", float("inf"))

            if min_age <= age <= max_age and min_weight <= weight <= max_weight:
                matched_group = group
                break

        if not matched_group:
            return "❌ ไม่พบข้อมูลที่ตรงกับช่วงอายุและน้ำหนักนี้"

        sub = matched_group.get("sub_indication", "ไม่ระบุช่วง")
        lines.append(f"\n🔹 {sub}")

        if "dose_mg_per_kg_per_dose" in matched_group:
            dose = weight * matched_group["dose_mg_per_kg_per_dose"]
            dose = min(dose, matched_group["max_mg_per_day"])
            ml = dose / concentration

            freqs = matched_group["frequency"]
            if isinstance(freqs, list) and len(freqs) > 1:
                min_f, max_f = min(freqs), max(freqs)
                freq_text = f"วันละ {min_f}–{max_f} ครั้ง"
            else:
                freq_text = f"วันละ {freqs[0] if isinstance(freqs, list) else freqs} ครั้ง"

            lines.append(
                f"ขนาดยา: {matched_group['dose_mg_per_kg_per_dose']} mg/kg/dose → {dose:.1f} mg/dose × {freq_text} "
                f"(max {matched_group['max_mg_per_day']} mg/day) ≈ ~{ml:.1f} ml/dose"
            )

        elif "dose_mg" in matched_group:
            dose = matched_group["dose_mg"]
            freq = matched_group["frequency"]
            ml = dose / concentration
            lines.append(
                f"ขนาดยา: {dose} mg × {freq} ครั้ง/วัน (max {matched_group['max_mg_per_day']} mg/day) ≈ ~{ml:.1f} ml/ครั้ง"
            )

        if matched_group.get("note"):
            lines.append(f"📝 หมายเหตุ: {matched_group['note']}")

        return "\n".join(lines)
    
    if drug == "Salbutamol" and age < 2:
        return "❌ ไม่แนะนำให้ใช้ Salbutamol ในเด็กอายุน้อยกว่า 2 ปี"

    if drug == "Salbutamol":
        indication_data = info["indications"].get(indication)
        if not indication_data:
            return f"❌ ไม่พบข้อมูลข้อบ่งใช้ {indication}"

        matched_group = None
        for group in indication_data:
            age_min = group.get("age_min", 0)
            age_max = group.get("age_max", float("inf"))
            if age_min <= age <= age_max:
                matched_group = group
                break

        if not matched_group:
            return f"❌ ไม่พบข้อมูลสำหรับอายุ {age} ปี"

        lines = [f"🧪 {drug} - {indication}", f"(น้ำหนัก {weight} kg, อายุ {age} ปี):"]

        sub = matched_group.get("sub_indication")
        if sub:
            lines.append(f"\n🔹 {sub}")

        # ✅ ตรวจสอบกรณี dose_mg_per_kg_per_dose เป็น list
        if "dose_mg_per_kg_per_dose" in matched_group and isinstance(matched_group["dose_mg_per_kg_per_dose"], list):
            doses = matched_group["dose_mg_per_kg_per_dose"]
            max_doses = matched_group.get("max_mg_per_dose", [float("inf")] * len(doses))
            freq = matched_group["frequency"]

            for i, dose_per_kg in enumerate(doses):
                total_mg = weight * dose_per_kg
                total_mg = min(total_mg, max_doses[i])
                ml = total_mg / concentration
                lines.append(
                    f"\nขนาดยา: {dose_per_kg} mg/kg/dose → {total_mg:.1f} mg/dose × วันละ {freq} ครั้ง (max {max_doses[i]} mg/dose) ≈ ~{ml:.1f} ml/ครั้ง"
                )

        elif "dose_mg" in matched_group:
            dose = matched_group["dose_mg"]
            freqs = matched_group["frequency"] if isinstance(matched_group["frequency"], list) else [matched_group["frequency"]]
            ml = dose / concentration

            if isinstance(freqs, list) and len(freqs) > 1 and all(isinstance(f, (int, float)) for f in freqs):
                freq_text = f"วันละ {min(freqs)}–{max(freqs)} ครั้ง"
                lines.append(f"ขนาดยา: {dose} mg × {freq_text} ≈ ~{ml:.1f} ml/ครั้ง")
            else:
                for freq in freqs:
                    lines.append(f"ขนาดยา: {dose} mg × วันละ {freq} ครั้ง ≈ ~{ml:.1f} ml/ครั้ง")

        elif "dose_mg_range" in matched_group:
            freqs = matched_group["frequency"]
            for d in matched_group["dose_mg_range"]:
                ml = d / concentration
                for freq in freqs:
                    lines.append(f"ขนาดยา: {d} mg × วันละ {freq} ครั้ง ≈ ~{ml:.1f} ml/ครั้ง")

        if matched_group.get("note"):
            lines.append(f"\n📝 หมายเหตุ: {matched_group['note']}")

        if info.get("note"):
            lines.append(f"\n📌 หมายเหตุเพิ่มเติม: {info['note']}")

        return "\n".join(lines)

    if drug == "Chlorpheniramine" and age < 2:
        return "❌ ไม่แนะนำให้ใช้ Chlorpheniramine ในเด็กอายุน้อยกว่า 2 ปี"

    if drug == "Chlorpheniramine":
        indication_data = info["indications"].get(indication)
        if not indication_data:
            return f"❌ ไม่พบข้อมูลข้อบ่งใช้ {indication}"

        lines = [f"{drug} - {indication} (น้ำหนัก {weight} kg, อายุ {age} ปี):"]

        if age < 2:
            return "❌ ไม่แนะนำให้ใช้ในเด็กอายุน้อยกว่า 2 ปี"

        matched_group = None
        for group in indication_data:
            min_age = float(group.get("age_min", 0))
            max_age = float(group.get("age_max", float("inf")))

            # ✅ ตรวจ weight เฉพาะกรณีที่มี weight_min/max
            min_weight = float(group.get("weight_min", -float("inf")))
            max_weight = float(group.get("weight_max", float("inf")))
            check_weight = "weight_min" in group or "weight_max" in group

            age_match = min_age <= age <= max_age
            weight_match = (not check_weight) or (min_weight <= weight <= max_weight)

            if age_match and weight_match:
                matched_group = group
                break

        if not matched_group:
            return f"❌ ไม่พบข้อมูลที่ตรงกับช่วงอายุ{'และน้ำหนัก' if check_weight else ''}นี้"

        sub = matched_group.get("sub_indication", "ไม่ระบุช่วง")
        lines.append(f"\n🔹 {sub}")

        if "dose_mg_per_kg_per_dose" in matched_group:
            dose = weight * matched_group["dose_mg_per_kg_per_dose"]
            dose = min(dose, matched_group["max_mg_per_day"])
            ml = dose / concentration

            freqs = matched_group["frequency"]
            if isinstance(freqs, list) and len(freqs) > 1:
                min_f, max_f = min(freqs), max(freqs)
                freq_text = f"วันละ {min_f}–{max_f} ครั้ง"
            else:
                freq_text = f"วันละ {freqs[0] if isinstance(freqs, list) else freqs} ครั้ง"

            lines.append(
                f"ขนาดยา: {matched_group['dose_mg_per_kg_per_dose']} mg/kg/dose → {dose:.1f} mg/dose × {freq_text} "
                f"(max {matched_group['max_mg_per_day']} mg/day) ≈ ~{ml:.1f} ml/dose"
            )

        elif "dose_mg" in matched_group:
            dose = matched_group["dose_mg"]
            freq = matched_group["frequency"]
            ml = dose / concentration
            lines.append(
                f"ขนาดยา: {dose} mg × {freq} ครั้ง/วัน (max {matched_group['max_mg_per_day']} mg/day) ≈ ~{ml:.1f} ml/ครั้ง"
            )

        if matched_group.get("note"):
            lines.append(f"📝 หมายเหตุ: {matched_group['note']}")

        return "\n".join(lines)

    
    # ✅ Ibuprofen และยาอื่น ๆ ที่ใช้โครงสร้าง weight_based
    if drug == "Ibuprofen" and age < 0.25:
        return "❌ ไม่แนะนำให้ใช้ Ibuprofen ในเด็กอายุน้อยกว่า 3 เดือน"

    if drug == "Ibuprofen":
        indication_data = info["indications"].get(indication)
        if not indication_data:
            return f"❌ ไม่พบข้อมูลข้อบ่งใช้ {indication}"

        reply_lines = [f"{drug} - {indication} (น้ำหนัก {weight} kg):"]

        for item in indication_data:
            if item.get("type") != "weight_based":
                continue

            if "dose_mg_per_kg_per_dose" in item:
                for d in item["dose_mg_per_kg_per_dose"]:
                    total_mg = weight * d
                    total_ml = total_mg / concentration
                    reply_lines.append(
                        f"💊 {d} mg/kg → ~{total_mg:.1f} mg (~{total_ml:.2f} ml) {item['frequency']}"
                    )
            elif "dose_mg_per_kg_per_day" in item:
                for d in item["dose_mg_per_kg_per_day"]:
                    total_mg_day = weight * d
                    doses = item.get("divided_doses", 3)
                    dose_per_time = total_mg_day / doses
                    dose_ml = dose_per_time / concentration
                    reply_lines.append(
                        f"💊 {d} mg/kg/day → ~{total_mg_day:.1f} mg/day → แบ่ง {doses} ครั้ง → ครั้งละ ~{dose_per_time:.1f} mg (~{dose_ml:.2f} ml)"
                    )

            if item.get("max_mg_per_dose"):
                reply_lines.append(f"🔢 Max ต่อครั้ง: {item['max_mg_per_dose']} mg")
            if item.get("max_mg_per_day"):
                reply_lines.append(f"🔢 Max ต่อวัน: {item['max_mg_per_day']} mg")
            if item.get("note"):
                reply_lines.append(f"📌 {item['note']}")

        return "\n".join(reply_lines)


    if drug == "Paracetamol":
        dose_range = indication_info.get("dose_mg_per_kg_per_dose")
        frequency = indication_info.get("frequency")
        max_mg_per_day = indication_info.get("max_mg_per_day")
        note = indication_info.get("note", "")
        concentration = info.get("concentration_mg_per_ml", 1)

        if dose_range:
            min_dose, max_dose = dose_range
            min_total = weight * min_dose
            max_total = weight * max_dose

            min_ml = min_total / concentration
            max_ml = max_total / concentration

            result = (
                f"{drug} (น้ำหนัก {weight} kg):\n"
                f"ขนาดยา: {min_dose}–{max_dose} mg/kg/ครั้ง → {min_total:.1f}–{max_total:.1f} mg/ครั้ง\n"
                f"ปริมาณยา: {min_ml:.1f}–{max_ml:.1f} ml/ครั้ง\n"
                f"ความถี่: {frequency}"
            )
            if max_mg_per_day:
                result += f"\n⚠️ ไม่เกิน {max_mg_per_day} mg/วัน"
            if note:
                result += f"\n📝 {note}"
            return result
        return "❌ ไม่พบข้อมูลขนาดยา"

    if drug == "Paracetamol drop":
        dose_range = indication_info.get("dose_mg_per_kg_per_dose")
        frequency = indication_info.get("frequency")
        max_mg_per_day = indication_info.get("max_mg_per_day")
        note = indication_info.get("note", "")
        concentration = info.get("concentration_mg_per_ml", 1)

        if dose_range:
            min_dose, max_dose = dose_range
            min_total = weight * min_dose
            max_total = weight * max_dose

            min_ml = min_total / concentration
            max_ml = max_total / concentration

            result = (
                f"{drug} (น้ำหนัก {weight} kg):\n"
                f"ขนาดยา: {min_dose}–{max_dose} mg/kg/ครั้ง → {min_total:.1f}–{max_total:.1f} mg/ครั้ง\n"
                f"ปริมาณยา: {min_ml:.1f}–{max_ml:.1f} ml/ครั้ง\n"
                f"ความถี่: {frequency}"
            )
            if max_mg_per_day:
                result += f"\n⚠️ ไม่เกิน {max_mg_per_day} mg/วัน"
            if note:
                result += f"\n📝 {note}"
            return result
        return "❌ ไม่พบข้อมูลขนาดยา"

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
    common = drug_info.get("common_indications", list(indications.keys()))  # fallback

    columns = []
    for name in common:
        title = name[:40]
        indication_info = indications.get(name)

        try:
            dose = "?"
            if isinstance(indication_info, list):
                sample = indication_info[0] if indication_info else {}

                # ✅ ใช้ label หากมี
                dose = sample.get("label") or (
                    f"{sample['dose_mg_per_kg_per_day']} mg/kg/day" if "dose_mg_per_kg_per_day" in sample else
                    f"{sample['dose_mg_per_kg_per_dose']} mg/kg/dose" if "dose_mg_per_kg_per_dose" in sample else
                    f"{sample['dose_mg_range'][0]}–{sample['dose_mg_range'][1]} mg" if "dose_mg_range" in sample else
                    f"{sample['dose_mg']} mg" if "dose_mg" in sample else
                    f"{sample['initial_dose_mg']} mg" if "initial_dose_mg" in sample else "?"
                )

            elif isinstance(indication_info, dict):
                sample = next(iter(indication_info.values()))
                if isinstance(sample, dict):
                    dose = sample.get("label") or (
                        f"{sample['dose_mg_per_kg_per_day']} mg/kg/day" if "dose_mg_per_kg_per_day" in sample else
                        f"{sample['dose_mg_per_kg_per_dose']} mg/kg/dose" if "dose_mg_per_kg_per_dose" in sample else
                        f"{sample['dose_mg_range'][0]}–{sample['dose_mg_range'][1]} mg" if "dose_mg_range" in sample else
                        f"{sample['dose_mg']} mg" if "dose_mg" in sample else
                        f"{sample['initial_dose_mg']} mg" if "initial_dose_mg" in sample else "?"
                    )
            else:
                dose = "?"

        except Exception:
            dose = "?"
        columns.append(CarouselColumn(
            title=title,
            text=dose,
            actions=[MessageAction(label="เลือก", text=f"Indication: {name}")]
        ))

    if not columns:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"❌ ไม่พบข้อบ่งใช้สำหรับ {drug_name}")]
            )
        )
        return

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
    reply_token = event.reply_token
    user_text = event.message.text
    user_id = event.source.user_id
    text = user_text.strip()

    auto_response_commands = {
        "คำนวณขนาดยา warfarin",
        "เลือก: warfarin guideline",
        "สมุนไพร/อาหารเสริมที่ควรระวัง",
        "warfarin drug interaction",
        "drug use evaluation",
        "แจ้งประกาศยาใหม่",
        "ติดต่อหัวหน้าแผนก",
        "เลือก: รายชื่อยา DUE",
        "คำนวณขนาดยาเด็ก",
    }
    if text_lower in auto_response_commands:
        return

    if text_lower in ['คำนวณยา warfarin']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_sessions[user_id] = {"flow": "warfarin", "step": "ask_inr"}
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="🧪 กรุณาใส่ค่า INR (เช่น 2.5)")]
            )
        )
        return

    elif text_lower in ['เลือก: ยาปฏิชีวนะ']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_ages.pop(user_id, None)
        send_drug_ATB_selection(event)
        return
    
    elif text_lower in ['เลือก: ยาแก้แพ้']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_ages.pop(user_id, None)
        send_drug_AH_selection(event)
        return
    
    elif text_lower in ['เลือก: ยาแก้ปวด ลดไข้']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_ages.pop(user_id, None)
        send_drug_APY_selection(event)
        return
    
    elif text_lower in ['เลือก: ยาอื่นๆ']:
        user_sessions.pop(user_id, None)
        user_drug_selection.pop(user_id, None)
        user_ages.pop(user_id, None)
        send_drug_OT_selection(event)
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
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
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
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
                )
                return

            elif step == "ask_bleeding":
                if text.lower().strip(".") not in ["yes", "no"]:
                    reply = "❌ ตอบว่า yes หรือ no เท่านั้น"
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
                    )
                    return
                session["bleeding"] = text.lower()
                if text.lower().strip(".") == "yes":
                # ✅ มี bleeding → แสดงผลทันทีและจบ flow
                    result = calculate_warfarin(session["inr"], session["twd"], session["bleeding"])
                    user_sessions.pop(user_id, None)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=result)])
                )
                
                else:   
                    # ถ้าไม่มี bleeding → ไปถามเรื่องสมุนไพรต่อ
                    session["step"] = "choose_supplement"
                    send_supplement_flex(reply_token)
                return


            elif step == "choose_supplement":
                if text == "ไม่ได้ใช้":
                    session["supplement"] = ""
                    session["step"] = "choose_interaction"
                    send_interaction_flex(reply_token)
                    return

                elif text == "สมุนไพร/อาหารเสริมชนิดอื่นๆ":
                    session["step"] = "ask_custom_supplement"
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text="🌿 กรุณาพิมพ์ชื่อสมุนไพร/อาหารเสริมที่ใช้ เช่น ตังกุย ขิง ชาเขียว")]
                        )
                    )
                    return
                
                elif step == "ask_custom_supplement":
                    session["supplement"] = text
                    session["step"] = "choose_interaction"
                    send_interaction_flex(reply_token)
                    return

                else:
                    session["supplement"] = text
                    session["step"] = "choose_interaction"
                    send_interaction_flex(reply_token)
                    return

            elif step == "ask_custom_supplement":
                session["supplement"] = text
                session["step"] = "choose_interaction"
                send_interaction_flex(reply_token)
                return

            elif step == "choose_interaction":
                if text == "ไม่ได้ใช้":
                    interaction_note = ""
                    supplement = session.get("supplement", "")
                    result = calculate_warfarin(session["inr"], session["twd"], session["bleeding"], supplement)
                    final_result = f"{result.split('\n\n')[0]}{interaction_note}\n\n{result.split('\n\n')[1]}"
                    user_sessions.pop(user_id, None)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=final_result)])
                    )
                    return

                elif text in ["ใช้หลายชนิด", "ยาชนิดอื่นๆ"]:
                    session["step"] = "ask_interaction"
                    reply = "💊 โปรดพิมพ์ชื่อยาที่ใช้อยู่ เช่น Amiodarone, NSAIDs"
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
                    )
                    return

                else:
                    interaction_note = f"\n⚠️ พบการใช้ยา: {text} ซึ่งอาจมีปฏิกิริยากับ Warfarin"
                    supplement = session.get("supplement", "")
                    result = calculate_warfarin(session["inr"], session["twd"], session["bleeding"], supplement)
                    final_result = f"{result.split('\n\n')[0]}{interaction_note}\n\n{result.split('\n\n')[1]}"
                    user_sessions.pop(user_id, None)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=final_result)])
                    )
                    return

            elif step == "ask_interaction":
                interaction_note = f"\n⚠️ พบการใช้ยา: {text.strip()} ซึ่งอาจมีปฏิกิริยากับ Warfarin"
                supplement = session.get("supplement", "")
                result = calculate_warfarin(session["inr"], session["twd"], session["bleeding"], supplement)
                final_result = f"{result.split('\n\n')[0]}{interaction_note}\n\n{result.split('\n\n')[1]}"
                user_sessions.pop(user_id, None)
                messaging_api.reply_message(
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=final_result)])
                )
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

        # ล้างอายุก่อน (กันข้อมูลซ้ำเดิม)
        if user_id in user_ages:
            user_ages.pop(user_id)

        # ✅ แก้ตรงนี้: ถามอายุของเด็กเสมอทั้ง SPECIAL_DRUGS และ DRUG_DATABASE
        example_age = random.randint(1, 18)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"📆 กรุณาพิมพ์อายุของเด็ก เช่น {example_age} ปี")]
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

                    # ✅ แปลงปีและเดือนเป็นตัวเลขเต็ม
                    total_months = int(age_years * 12)
                    display_years = total_months // 12
                    display_months = total_months % 12

                    # ✅ สร้างข้อความแสดงอายุ เช่น "1 ปี 6 เดือน"
                    parts = []
                    if display_years > 0:
                        parts.append(f"{display_years} ปี")
                    if display_months > 0:
                        parts.append(f"{display_months} เดือน")
                    if not parts:
                        parts.append("0 เดือน")

                    age_text = " ".join(parts)

                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"🎯 อายุ {age_text}แล้ว กรุณาใส่น้ำหนัก เช่น {example_weight} กก")]
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
                            age = user_ages.get(user_id)
                            reply = calculate_dose(drug, indication, weight, age)
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

    # กรณีที่ยังไม่มีการเลือกยา    
    elif user_id not in user_sessions and user_id not in user_drug_selection:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❓ พิมพ์ 'คำนวณยา warfarin' หรือ 'คำนวณยาเด็ก' เพื่อเริ่มต้นใช้งาน")]
            )
        )
        return
    else:
        # ข้อความทั่วไปที่ไม่เข้าเงื่อนไข
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❗️ กรุณาพิมพ์อายุ เช่น '5 ปี' หรือ น้ำหนัก เช่น '18 กก'")]
            )
        )
        return
        

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
