import os
import sys

# Ensure we run using the local virtual environment Python if available
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(script_dir, 'venv', 'bin', 'python')
if __name__ == "__main__" and os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    os.execv(venv_python, [venv_python] + sys.argv)

import cv2
from contextlib import ExitStack
from dataclasses import dataclass
from threading import Event
from typing import Tuple, Any
import mediapipe as mp
import numpy as np
import time

UI_FONT = cv2.FONT_HERSHEY_DUPLEX
# OpenCV colors are BGR. Dark edging keeps the overlay legible over video.
TRACK_LINE = (225, 237, 242)
TRACK_DETAIL = (164, 177, 182)
TRACK_EDGE = (24, 22, 20)
TRACK_ACCENT = (90, 154, 250)

# MediaPipe
mp_pose = mp.solutions.pose
mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands


# --- Reference pose definition (normalized 0-1) ---
# T-pose: arms out, legs apart, open hands
REF_BODY = {
    "nose":       (0.50, 0.18),
    "l_shoulder": (0.38, 0.28),
    "r_shoulder": (0.62, 0.28),
    "l_elbow":    (0.22, 0.28),
    "r_elbow":    (0.78, 0.28),
    "l_wrist":    (0.08, 0.28),
    "r_wrist":    (0.92, 0.28),
    "l_hip":      (0.42, 0.55),
    "r_hip":      (0.58, 0.55),
    "l_knee":     (0.40, 0.75),
    "r_knee":     (0.60, 0.75),
    "l_ankle":    (0.38, 0.92),
    "r_ankle":    (0.62, 0.92),
}

# Arm connections
ARM_CONNECTIONS = [(11,13),(13,15),(12,14),(14,16),(11,12)]
ARM_LANDMARKS = [11, 12, 13, 14, 15, 16]

# Hand connections & tips
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),(0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),(5,9),(9,13),(13,17),
]
FINGER_TIPS = [4, 8, 12, 16, 20]

# Face
FACE_OUTLINE = [
    (10,338),(338,297),(297,332),(332,284),(284,251),(251,389),(389,356),
    (356,454),(454,323),(323,361),(361,288),(288,397),(397,365),(365,379),
    (379,378),(378,400),(400,377),(377,152),(152,148),(148,176),(176,149),
    (149,150),(150,136),(136,172),(172,58),(58,132),(132,93),(93,234),
    (234,127),(127,162),(162,21),(21,54),(54,103),(103,67),(67,109),(109,10),
]
EYEBROW_LEFT = [(70,63),(63,105),(105,66),(66,107)]
EYEBROW_RIGHT = [(300,293),(293,334),(334,296),(296,336)]
EYE_LEFT = [(33,7),(7,163),(163,144),(144,145),(145,153),(153,154),(154,155),
            (155,133),(133,173),(173,157),(157,158),(158,159),(159,160),(160,161),(161,246),(246,33)]
EYE_RIGHT = [(362,382),(382,381),(381,380),(380,374),(374,373),(373,390),(390,249),
             (249,263),(263,466),(466,388),(388,387),(387,386),(386,385),(385,384),(384,398),(398,362)]
MOUTH_OUTER = [
    (61,146),(146,91),(91,181),(181,84),(84,17),(17,314),(314,405),(405,321),
    (321,375),(375,291),(291,409),(409,270),(270,269),(269,267),(267,0),
    (0,37),(37,39),(39,40),(40,185),(185,61),
]

def draw_connections(canvas: Any, pts: dict, connections: list,
                     color: Tuple[int, int, int], thickness: int = 1) -> None:
    """Draw the dark casing first so connected strokes stay uninterrupted."""
    for stroke, width in ((TRACK_EDGE, thickness + 2), (color, thickness)):
        for start, end in connections:
            if start in pts and end in pts:
                cv2.line(canvas, pts[start], pts[end], stroke, width, cv2.LINE_AA)


def draw_joint(canvas: Any, point: Tuple[int, int],
               color: Tuple[int, int, int] = TRACK_LINE, radius: int = 3) -> None:
    """A small open ring separates the joint from its connecting bones."""
    cv2.circle(canvas, point, radius + 1, TRACK_EDGE, -1, cv2.LINE_AA)
    cv2.circle(canvas, point, radius, color, 1, cv2.LINE_AA)


def draw_face(canvas: Any, face_lm: Any, w: int, h: int, color: Tuple[int, int, int] = TRACK_DETAIL, thickness: int = 1) -> None:
    pts = {}
    for lm in face_lm.landmark:
        pts[len(pts)] = (int(lm.x * w), int(lm.y * h))

    connections = FACE_OUTLINE + EYEBROW_LEFT + EYEBROW_RIGHT + EYE_LEFT + EYE_RIGHT + MOUTH_OUTER
    draw_connections(canvas, pts, connections, color, thickness)


def draw_arms(canvas: Any, landmarks: Any, w: int, h: int, color: Tuple[int, int, int] = TRACK_LINE, thickness: int = 1) -> None:
    pts = {}
    for idx in ARM_LANDMARKS:
        lm = landmarks[idx]
        if lm.visibility > 0.5:
            pts[idx] = (int(lm.x * w), int(lm.y * h))
    draw_connections(canvas, pts, ARM_CONNECTIONS, color, thickness)
    for pt in pts.values():
        draw_joint(canvas, pt, color, radius=4)


def draw_hand(canvas: Any, hand_lm: Any, w: int, h: int, color: Tuple[int, int, int] = TRACK_LINE, thickness: int = 1) -> None:
    pts = {}
    for lm in hand_lm.landmark:
        pts[len(pts)] = (int(lm.x * w), int(lm.y * h))
    draw_connections(canvas, pts, HAND_CONNECTIONS, color, thickness)
    # The index finger drives both gestures; give it a single consistent accent.
    for start, end in ((5, 6), (6, 7), (7, 8)):
        if start in pts and end in pts:
            cv2.line(canvas, pts[start], pts[end], TRACK_ACCENT, thickness, cv2.LINE_AA)
    for idx in [0, *FINGER_TIPS]:
        if idx in pts:
            draw_joint(canvas, pts[idx], TRACK_ACCENT if idx == 8 else color,
                       radius=4 if idx == 0 else 2)


def check_index_finger_up(hand_landmarks: Any) -> bool:
    """
    Check if the index finger is pointed up, and other fingers (middle, ring, pinky) are folded.
    """
    lm = hand_landmarks.landmark
    # Index finger extended up (tip 8 y coordinate is smaller than pip 6 y coordinate)
    # Relaxed from -0.05 to -0.02 to allow tilted/softer pointing angles
    index_up = lm[8].y < lm[6].y - 0.02
    
    # Other fingers folded (tips are lower than their respective PIPs/MCPs, so y is larger)
    # Relaxed from -0.02 to -0.05 to allow natural slight curling without needing rigid folding
    middle_folded = lm[12].y > lm[10].y - 0.05
    ring_folded = lm[16].y > lm[14].y - 0.05
    pinky_folded = lm[20].y > lm[18].y - 0.05
    
    return index_up and middle_folded and ring_folded and pinky_folded


def check_smile(face_landmarks: Any) -> int:
    """
    Check if the face is smiling. Returns a score from 0 to 100.
    """
    lm = face_landmarks.landmark
    def dist(p1, p2):
        return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2) ** 0.5
        
    mouth_w = dist(lm[61], lm[291])
    face_w = dist(lm[234], lm[454])
    
    if face_w == 0:
        return 0
        
    smile_ratio = mouth_w / face_w
    
    # Map smile ratio (0.33 to 0.44) to 0-100%
    score = int((smile_ratio - 0.33) / (0.44 - 0.33) * 100)
    score = max(0, min(100, score))
    return score


def check_finger_near_mouth(hand_landmarks: Any, face_landmarks: Any, threshold: float = 0.12) -> bool:
    """
    Check if the index finger tip is near the mouth.
    """
    if not hand_landmarks or not face_landmarks:
        return False
    
    h_lm = hand_landmarks.landmark
    f_lm = face_landmarks.landmark
    
    # Mouth center
    mouth_cx = (f_lm[61].x + f_lm[291].x) / 2
    mouth_cy = (f_lm[61].y + f_lm[291].y) / 2
    
    index_tip = h_lm[8]
    
    # Hand z is relative to the wrist; face z is relative to the head.
    # ponytail: 2D proximity cannot prove contact; use shared depth if needed.
    dist = ((index_tip.x - mouth_cx)**2 + (index_tip.y - mouth_cy)**2) ** 0.5
    return dist < threshold


def make_reference_image() -> Any:
    """Draw the reference T-pose as a stick figure image."""
    W, H = 640, 480
    canvas = np.full((H, W, 3), (30, 30, 30), dtype=np.uint8)

    def px(pt):
        return (int(pt[0] * W), int(pt[1] * H))

    # Body connections
    body_conns = [
        ("nose","l_shoulder"),("nose","r_shoulder"),("l_shoulder","r_shoulder"),
        ("l_shoulder","l_elbow"),("l_elbow","l_wrist"),
        ("r_shoulder","r_elbow"),("r_elbow","r_wrist"),
        ("l_shoulder","l_hip"),("r_shoulder","r_hip"),("l_hip","r_hip"),
        ("l_hip","l_knee"),("l_knee","l_ankle"),
        ("r_hip","r_knee"),("r_knee","r_ankle"),
    ]
    body_pts = {name: px(point) for name, point in REF_BODY.items()}
    draw_connections(canvas, body_pts, body_conns, TRACK_LINE)
    for pt in body_pts.values():
        draw_joint(canvas, pt, radius=4)

    # Head
    nose_px = px(REF_BODY["nose"])
    sw = abs(REF_BODY["l_shoulder"][0] - REF_BODY["r_shoulder"][0]) * W
    cv2.circle(canvas, nose_px, int(sw * 0.28), TRACK_LINE, 1, cv2.LINE_AA)

    # Hands
    def make_hand(cx, cy, sx, sy):
        pts = [(cx,cy)]
        pts += [(cx+sx*0.3,cy-sy*0.1),(cx+sx*0.5,cy-sy*0.2),(cx+sx*0.65,cy-sy*0.25),(cx+sx*0.8,cy-sy*0.3)]
        pts += [(cx+sx*0.15,cy-sy*0.15),(cx+sx*0.15,cy-sy*0.4),(cx+sx*0.15,cy-sy*0.6),(cx+sx*0.15,cy-sy*0.8)]
        pts += [(cx,cy-sy*0.15),(cx,cy-sy*0.4),(cx,cy-sy*0.65),(cx,cy-sy*0.85)]
        pts += [(cx-sx*0.15,cy-sy*0.15),(cx-sx*0.15,cy-sy*0.38),(cx-sx*0.15,cy-sy*0.58),(cx-sx*0.15,cy-sy*0.75)]
        pts += [(cx-sx*0.3,cy-sy*0.12),(cx-sx*0.3,cy-sy*0.3),(cx-sx*0.3,cy-sy*0.45),(cx-sx*0.3,cy-sy*0.58)]
        return pts

    for hand_pts in [make_hand(0.08,0.28,0.08,0.12), make_hand(0.92,0.28,-0.08,0.12)]:
        pts = {idx: px(point) for idx, point in enumerate(hand_pts)}
        draw_connections(canvas, pts, HAND_CONNECTIONS, TRACK_LINE)
        for idx in [0, *FINGER_TIPS]:
            draw_joint(canvas, pts[idx], TRACK_ACCENT if idx == 8 else TRACK_LINE,
                       radius=3 if idx == 0 else 2)

    cv2.putText(canvas, "MATCH THIS POSE", (180, 455),
                UI_FONT, 0.85, (255,255,255), 1, cv2.LINE_AA)

    return canvas


@dataclass(frozen=True)
class TrackingState:
    has_arms: bool
    has_face: bool
    hand_count: int
    smile_score: int
    index_up: bool
    finger_near_mouth: bool
    active_ref: int | None
    matched: bool
    fps: float


class PoseMatcher:
    def __init__(self):
        self.ref_img1 = cv2.imread(os.path.join(script_dir, "f139fdf3202282f05db2fc08ef97ea0b.jpg"))
        if self.ref_img1 is None:
            self.ref_img1 = make_reference_image()
        self.ref_img2 = cv2.imread(os.path.join(script_dir, "think_monkey.png"))
        if self.ref_img2 is None:
            self.ref_img2 = make_reference_image()

    def frames(self, stop: Event, overlay: Event):
        """Yield processed frames; closing the iterator releases camera and models."""
        with ExitStack() as resources:
            cap = cv2.VideoCapture(0)
            resources.callback(cap.release)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not cap.isOpened():
                raise RuntimeError("Cannot open camera. Check camera access and close other camera apps.")
            if stop.is_set():
                return
            pose = resources.enter_context(mp_pose.Pose(
                static_image_mode=False, model_complexity=1,
                min_detection_confidence=0.5, min_tracking_confidence=0.5,
            ))
            face_mesh = resources.enter_context(mp_face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.5, min_tracking_confidence=0.5,
            ))
            hands = resources.enter_context(mp_hands.Hands(
                static_image_mode=False, max_num_hands=2,
                min_detection_confidence=0.6, min_tracking_confidence=0.5,
            ))
            last_time = time.monotonic()
            fps = 0.0
            active_ref = None
            hold_until = 0.0
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Cannot read camera. Reconnect it, then try again.")
                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pose_res = pose.process(rgb)
                face_res = face_mesh.process(rgb)
                hands_res = hands.process(rgb)
                draw_overlay = overlay.is_set()
                has_arms = bool(pose_res.pose_landmarks)
                face = face_res.multi_face_landmarks[0] if face_res.multi_face_landmarks else None
                hand_landmarks = hands_res.multi_hand_landmarks or []
                smile_score = check_smile(face) if face else 0
                index_up = False
                finger_near_mouth = False
                if has_arms and draw_overlay:
                    draw_arms(frame, pose_res.pose_landmarks.landmark, w, h)
                if face and draw_overlay:
                    draw_face(frame, face, w, h)
                for hand in hand_landmarks:
                    if draw_overlay:
                        draw_hand(frame, hand, w, h)
                    if check_index_finger_up(hand):
                        index_up = True
                        if check_finger_near_mouth(hand, face):
                            finger_near_mouth = True
                now = time.monotonic()
                matched = False
                if index_up and smile_score >= 75:
                    active_ref, matched = 1, True
                elif index_up and finger_near_mouth:
                    active_ref, matched = 2, True
                if matched:
                    hold_until = now + 1.5
                elif now >= hold_until:
                    active_ref = None
                fps = 0.9 * fps + 0.1 / max(now - last_time, 0.001)
                last_time = now
                if stop.is_set():
                    break
                yield frame, TrackingState(has_arms, face is not None, len(hand_landmarks),
                                           smile_score, index_up, finger_near_mouth,
                                           active_ref, matched, fps)
                stop.wait(0.01)

    def run(self) -> None:
        from gui import run_gui
        run_gui(self)


if __name__ == "__main__":
    PoseMatcher().run()
