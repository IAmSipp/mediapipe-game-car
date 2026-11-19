# Hand Drive — เกมรถด้วย MediaPipe

## โครงสร้าง

```text
Car/
├── main.py                  เปิดเกม
├── requirements.txt         แพ็กเกจที่ใช้
├── setting/                 ผู้เรียนปรับแต่งที่นี่
│   ├── control_settings.py  เลือกท่าซ้าย/ขวา ความไว เวลาค้าง
│   ├── hand_controls.py     กฎควบคุมแบบเขียนเอง
│   ├── game_settings.py     ความเร็ว คะแนน ขนาด สี
│   └── README.md            คู่มือสั้น
└── system/                  ระบบที่เตรียมให้
    ├── app.py / game.py / camera.py / controls.py
    ├── download_model.py
    ├── models/              Hand และ Pose พร้อมใช้
    ├── tests/
    ├── docs/                ตัวอย่างละเอียด
    └── artifacts/           ผลทดสอบที่สร้างขึ้น
```

## ติดตั้งและรัน (Windows PowerShell)

ใช้ Python 64-bit 3.10–3.13 ทดสอบจริงบน Windows x64 / Python 3.13.1 เปิด Terminal ในโฟลเดอร์เกมแล้วรันทีละบรรทัด:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m system.download_model
.\.venv\Scripts\python.exe main.py
```

เครื่องนี้เตรียม .venv และโมเดลแล้ว จึงใช้เฉพาะบรรทัดเปิดเกมได้ หากมีกล้องหลายตัว ใช้ main.py --camera 1 กดเมาส์ START/PLAY AGAIN และ Esc เพื่อออก

macOS/Linux ใช้ python3 สร้าง venv และแทนเส้นทาง Python ด้วย .venv/bin/python ยังไม่ได้ทดสอบสองระบบนี้ ต้องมีฟอนต์ไทย เช่น Noto Sans Thai/Thonburi

## ปรับแต่ง

อ่าน [คู่มือสั้น](setting/README.md) หรือ [ตัวอย่างละเอียด](system/docs/CONTROL_DETAILS.md)

- เลือก LEFT_ACTION/RIGHT_ACTION ใน setting/control_settings.py เช่น ชูนิ้วชี้ซ้าย/ขวา ใช้มือเดียวสองท่า หรือมือผสมร่างกายได้
- `USE_PRESET = True` ใช้ท่าสำเร็จรูปตาม LEFT_ACTION/RIGHT_ACTION
- `USE_PRESET = False` ใช้เฉพาะกฎจาก setting/hand_controls.py ไม่อ่านชื่อท่า ความไว หรือเวลาค้างของสำเร็จรูป
- เปลี่ยนกลับได้โดยโค้ดที่เขียนเองยังอยู่ ไม่มีการรวมกฎสองโหมด
- ภาพเป็นกระจก ป้าย Left/Right หมายถึงข้างจริงของผู้เล่น สถานะใต้ภาพบอกไปซ้าย/ไปขวา/อยู่เลนเดิม หรือให้ค้างท่าอีกนิด
- แก้ความเร็ว คะแนน เวลาเกิด ขนาด สี ใน setting/game_settings.py คะแนนและการเคลื่อนที่คำนวณจากเวลาจริง เล่นใหม่รีเซ็ตครบ

## ตัวอย่างแก้ท่ามือเดิม

แทนฟังก์ชัน is_control_gesture() ใน setting/hand_controls.py ด้วยตัวอย่างนี้ ต้องตั้ง USE_PRESET = False ก่อน แล้วกฎเขียนเองจะตรวจชูนิ้วชี้แทนกำมือ ถ้าใช้ท่าสำเร็จรูป “ชูนิ้วชี้” อยู่แล้วไม่ต้องแก้:

<!-- pointing-example -->
```python
POINTING_DISTANCE_RATIO = 1.15


def is_control_gesture(landmarks):
    wrist = landmarks[0]
    index_tip = landmarks[8]
    index_joint = landmarks[6]
    middle_tip = landmarks[12]
    middle_joint = landmarks[10]
    ring_tip = landmarks[16]
    ring_joint = landmarks[14]
    pinky_tip = landmarks[20]
    pinky_joint = landmarks[18]

    index_pointing = distance(index_tip, wrist) > distance(index_joint, wrist) * POINTING_DISTANCE_RATIO
    middle_closed = distance(middle_tip, wrist) < distance(middle_joint, wrist) * CLOSED_DISTANCE_RATIO
    ring_closed = distance(ring_tip, wrist) < distance(ring_joint, wrist) * CLOSED_DISTANCE_RATIO
    pinky_closed = distance(pinky_tip, wrist) < distance(pinky_joint, wrist) * CLOSED_DISTANCE_RATIO

    # นิ้วชี้เหยียด อีกสามนิ้วงอ ไม่บังคับตำแหน่งนิ้วโป้ง
    if index_pointing and middle_closed and ring_closed and pinky_closed:
        return True
    else:
        return False
```

## โมเดลและการแก้ปัญหา

โมเดลอยู่ใน system/models หากหายให้รัน python -m system.download_model ตัวดาวน์โหลดใช้ [Hand float16 รุ่น 1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task) และ [Pose Lite รุ่น 1](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) ดาวน์โหลดครั้งเดียวแล้วเล่นออฟไลน์ได้

กล้องไม่พร้อม: ปิดแอปที่ใช้กล้อง ตรวจสิทธิ์ Camera access / desktop apps ใน Windows ลอง --camera 1 แล้วเปิดเกมใหม่ ดูรายละเอียดใน Terminal เกมจะหยุดเมื่อกล้องขาดและไม่ใช้ข้อมูลเก่า ปิดกล้องและ Pygame ใน finally

ModuleNotFoundError: ใช้ Python ใน .venv ตามคำสั่ง อย่าติดตั้ง opencv-python ซ้อนกับ opencv-contrib-python ไทยเป็นสี่เหลี่ยมให้ติดตั้ง Tahoma หรือ Noto Sans Thai

## เอกสารทางการ

- [Hand Landmarker Python และหมายเลขจุด](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker?tab=Python)
- [Pose Landmarker Python และหมายเลขจุด](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker?tab=Python)
- [MediaPipe Python setup](https://developers.google.com/edge/mediapipe/solutions/setup_python)

ใช้ Tasks API, RunningMode.VIDEO และ detect_for_video พร้อม timestamp เพิ่มต่อเนื่อง ภาพส่งโมเดลไม่กลับกระจก กลับเฉพาะภาพ/จุดตอนแสดงผล

## การตรวจสอบ

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s system/tests -v
```

ทดสอบผ่าน 47 รายการ ครอบคลุมท่าสำเร็จรูปทุกชื่อ การเลือก True/False ว่าใช้เฉพาะกฎของโหมดที่เลือก โมเดลที่ต้องใช้ กฎเขียนเองไม่ขึ้นกับค่าของสำเร็จรูป และเส้นทางคำสั่งถึงรถ รวมถึงเริ่มเกม ชน เล่นใหม่ คืน resource และตัวอย่างโค้ดจากคู่มือ

เคยทดสอบ Hand/Pose โมเดลจริงกับภาพนิ่งทางการและเฟรมว่าง แต่ยังไม่ได้เล่นกับกล้องสดในสภาพแวดล้อมนี้ (กล้องหมายเลข 0 เปิดไม่ได้) จึงต้องลองความแม่นยำของท่ากับกล้อง ผู้เล่น และแสงจริงเพิ่มเติม
