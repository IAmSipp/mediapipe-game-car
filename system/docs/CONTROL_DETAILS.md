# เขียนกฎควบคุมเอง

ตั้ง `USE_PRESET = False` ใน setting/control_settings.py แล้วแก้ setting/hand_controls.py โหมดนี้ไม่ใช้ท่าสำเร็จรูป SENSITIVITY หรือ HOLD_SECONDS ของไฟล์ง่าย

- `is_control_gesture()` เปลี่ยนท่ามือที่ใช้ทั้งสองข้าง
- `control_states()` เขียนเงื่อนไขซ้าย/ขวาแยกกัน คืน (ผ่านซ้าย, ผ่านขวา)
- `choose_lane()` เลือกเลน ถ้าผ่านทั้งสองข้างคืน None
- `get_lane_command()` เป็นฟังก์ชันที่เกมเรียก คืน LEFT, RIGHT หรือ None
- `USE_HANDS`/`USE_POSE` เลือกโมเดลที่กฎต้องใช้ ต้องเปิดอย่างน้อยหนึ่งอย่าง
- แก้ LEFT_INSTRUCTION / RIGHT_INSTRUCTION / HOLD_INSTRUCTION ให้ตรงกับกฎ

ตัวอย่างใช้ยกแขน: ใน hand_controls.py แทนค่า USE_HANDS/USE_POSE และแทนฟังก์ชัน control_states() ด้วยตัวอย่างนี้ เก็บฟังก์ชันอื่นไว้ได้

<!-- pose-custom-example -->
```python
USE_HANDS = False
USE_POSE = True


def control_states(hands, pose_landmarks):
    if len(pose_landmarks) != 33:
        return False, False

    # ตาม MediaPipe Pose: ไหล่ 11/12, ข้อมือ 15/16 (ซ้าย/ขวาจริงของผู้เล่น)
    left_shoulder = pose_landmarks[11]
    right_shoulder = pose_landmarks[12]
    left_wrist = pose_landmarks[15]
    right_wrist = pose_landmarks[16]

    left_visible = left_wrist.visibility > 0.6 and left_shoulder.visibility > 0.6
    right_visible = right_wrist.visibility > 0.6 and right_shoulder.visibility > 0.6

    # y ยิ่งน้อยยิ่งอยู่สูง ผู้เรียนเปลี่ยนเงื่อนไขสองบรรทัดนี้ได้
    left_arm_raised = left_visible and left_wrist.y < left_shoulder.y
    right_arm_raised = right_visible and right_wrist.y < right_shoulder.y
    return left_arm_raised, right_arm_raised
```

hands เป็นรายการมือ มี side, landmarks 21 จุด และ confidence ส่วน pose_landmarks มี 33 จุดหรือ [] เมื่อไม่พบ ภาพส่งโมเดลไม่กลับกระจก ส่วนภาพแสดงผลเป็นกระจก

ดูตัวอย่างเปลี่ยนกำมือเป็นชูนิ้วชี้ใน [README หลัก](../../README.md#ตัวอย่างแก้ท่ามือเดิม) ซ้าย/ขวาหมายถึงข้างจริงของผู้เล่น ควรลองกับกล้องและแสงจริงก่อนเวิร์กชอป
