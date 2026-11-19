"""ใช้ไฟล์นี้เมื่อ USE_PRESET = False ใน control_settings.py"""

from math import sqrt

USE_HANDS = True
USE_POSE = False  # เปิดถ้าต้องใช้จุดร่างกายด้วย

CLOSED_DISTANCE_RATIO = 1.0


GESTURE_NAME = "FIST"
LEFT_INSTRUCTION = "กำมือซ้าย เพื่อไปเลนซ้าย"
RIGHT_INSTRUCTION = "กำมือขวา เพื่อไปเลนขวา"
HOLD_INSTRUCTION = "ไม่ทำท่า / ไม่พบ / ทำสองข้าง = อยู่เลนเดิม"


def distance(point_a, point_b):
    return sqrt(
        (point_a.x - point_b.x) ** 2
        + (point_a.y - point_b.y) ** 2
        + (point_a.z - point_b.z) ** 2
    )


def is_hand_closed(landmarks):
    closed_ratio = CLOSED_DISTANCE_RATIO
    # MediaPipe: ข้อมือ 0; ปลายนิ้ว 8/12/16/20; ข้อ PIP 6/10/14/18
    wrist = landmarks[0]
    index_tip = landmarks[8]
    index_joint = landmarks[6]
    middle_tip = landmarks[12]
    middle_joint = landmarks[10]
    ring_tip = landmarks[16]
    ring_joint = landmarks[14]
    pinky_tip = landmarks[20]
    pinky_joint = landmarks[18]

    index_closed = distance(index_tip, wrist) < distance(index_joint, wrist) * closed_ratio
    middle_closed = distance(middle_tip, wrist) < distance(middle_joint, wrist) * closed_ratio
    ring_closed = distance(ring_tip, wrist) < distance(ring_joint, wrist) * closed_ratio
    pinky_closed = distance(pinky_tip, wrist) < distance(pinky_joint, wrist) * closed_ratio

    # ไม่ตรวจนิ้วโป้ง เพื่อให้กำแบบวางนิ้วโป้งไว้นอกกำปั้นได้
    if index_closed and middle_closed and ring_closed and pinky_closed:
        return True
    else:
        return False


def is_control_gesture(landmarks):
    # เปลี่ยนตรงนี้ ถ้าอยากใช้ท่าอื่นสั่งไปซ้ายหรือขวา
    return is_hand_closed(landmarks)


def hand_gesture_states(hands):
    """hands = [{'side': 'Left'/'Right', 'landmarks': จุด 21 จุด}, ...]"""
    left_hand_closed = False
    right_hand_closed = False

    for hand in hands:
        if hand["side"] == "Left":
            if is_control_gesture(hand["landmarks"]):
                left_hand_closed = True
        elif hand["side"] == "Right":
            if is_control_gesture(hand["landmarks"]):
                right_hand_closed = True

    return left_hand_closed, right_hand_closed


def control_states(hands, pose_landmarks):
    # เปลี่ยนตรงนี้ ถ้าจะเขียนกฎซ้าย/ขวาแยกกัน หรือใช้ร่างกาย
    return hand_gesture_states(hands)


def choose_lane(left_active, right_active):
    if left_active and right_active:
        return None
    elif left_active:
        return "LEFT"
    elif right_active:
        return "RIGHT"
    else:
        return None


def get_lane_command(hands, pose_landmarks=None):
    if pose_landmarks is None:
        pose_landmarks = []
    left_active, right_active = control_states(hands, pose_landmarks)
    return choose_lane(left_active, right_active)
