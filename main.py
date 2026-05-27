import os
import sys

# Ensure we run using the local virtual environment Python if available
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(script_dir, 'venv', 'bin', 'python')
if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    os.execv(venv_python, [venv_python] + sys.argv)

import cv2
from typing import Tuple, List, Dict, Any
import mediapipe as mp
import numpy as np
import time

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

# Pose landmark indices -> our body key names
POSE_MAP = {
    0: "nose", 11: "l_shoulder", 12: "r_shoulder",
    13: "l_elbow", 14: "r_elbow", 15: "l_wrist", 16: "r_wrist",
    23: "l_hip", 24: "r_hip", 25: "l_knee", 26: "r_knee",
    27: "l_ankle", 28: "r_ankle",
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

# GUI buttons
BTN_QUIT = (500, 420, 120, 45)




def draw_button(img: Any, rect: Tuple[int, int, int, int], text: str, color: Tuple[int, int, int], text_color: Tuple[int, int, int] = (255, 255, 255)) -> None:
    x, y, w, h = rect
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), color, -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
    cv2.rectangle(img, (x, y), (x+w, y+h), (200,200,200), 1, cv2.LINE_AA)
    ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.putText(img, text, (x + (w-ts[0])//2, y + (h+ts[1])//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2, cv2.LINE_AA)


def draw_face(canvas: Any, face_lm: Any, w: int, h: int, color: Tuple[int, int, int] = (0, 0, 255), thickness: int = 1) -> None:
    pts = {}
    for lm in face_lm.landmark:
        pts[len(pts)] = (int(lm.x * w), int(lm.y * h))

    def ln(conns, col=color, th=thickness):
        for s, e in conns:
            if s in pts and e in pts:
                cv2.line(canvas, pts[s], pts[e], col, th, cv2.LINE_AA)

    ln(FACE_OUTLINE); ln(EYEBROW_LEFT, color, thickness)
    ln(EYEBROW_RIGHT, color, thickness); ln(EYE_LEFT, color, thickness)
    ln(EYE_RIGHT, color, thickness); ln(MOUTH_OUTER, color, thickness)
    for i in [0,33,263,61,291,10,152]:
        if i in pts:
            cv2.circle(canvas, pts[i], 2, color, -1, cv2.LINE_AA)


def draw_arms(canvas: Any, landmarks: Any, w: int, h: int, color: Tuple[int, int, int] = (0, 0, 255), thickness: int = 1) -> None:
    pts = {}
    for idx in ARM_LANDMARKS:
        lm = landmarks[idx]
        if lm.visibility > 0.5:
            pts[idx] = (int(lm.x * w), int(lm.y * h))
    for s, e in ARM_CONNECTIONS:
        if s in pts and e in pts:
            cv2.line(canvas, pts[s], pts[e], color, thickness, cv2.LINE_AA)
    for pt in pts.values():
        cv2.circle(canvas, pt, 2, color, -1, cv2.LINE_AA)


def draw_hand(canvas: Any, hand_lm: Any, w: int, h: int, color: Tuple[int, int, int] = (0, 0, 255), thickness: int = 1) -> None:
    pts = {}
    for lm in hand_lm.landmark:
        pts[len(pts)] = (int(lm.x * w), int(lm.y * h))
    for s, e in HAND_CONNECTIONS:
        if s in pts and e in pts:
            cv2.line(canvas, pts[s], pts[e], color, thickness, cv2.LINE_AA)
    for i, pt in pts.items():
        cv2.circle(canvas, pt, 2, color, -1, cv2.LINE_AA)


def normalize_landmarks(landmarks: Any) -> Dict[str, Tuple[float, float]]:
    """Normalize pose landmarks relative to torso center and size."""
    # Use shoulder midpoint and torso length as reference
    l_sh = landmarks[11]
    r_sh = landmarks[12]
    l_hip = landmarks[23]
    r_hip = landmarks[24]

    cx = (l_sh.x + r_sh.x + l_hip.x + r_hip.x) / 4
    cy = (l_sh.y + r_sh.y + l_hip.y + r_hip.y) / 4

    torso_w = abs(l_sh.x - r_sh.x) + 0.001
    torso_h = abs((l_sh.y + r_sh.y)/2 - (l_hip.y + r_hip.y)/2) + 0.001
    scale = max(torso_w, torso_h)

    result = {}
    for idx, name in POSE_MAP.items():
        lm = landmarks[idx]
        if lm.visibility > 0.4:
            result[name] = ((lm.x - cx) / scale, (lm.y - cy) / scale)
    return result


def compute_match_score(norm_live: Dict[str, Tuple[float, float]]) -> int:
    """Compare normalized live pose to reference body. Returns 0-100."""
    if not norm_live:
        return 0

    total_dist = 0
    count = 0
    for name, ref_pt in REF_BODY.items():
        if name in norm_live:
            live_pt = norm_live[name]
            dist = ((live_pt[0] - ref_pt[0])**2 + (live_pt[1] - ref_pt[1])**2) ** 0.5
            total_dist += dist
            count += 1

    if count < 4:
        return 0

    avg_dist = total_dist / count
    # Convert to score: dist=0 -> 100, dist=0.5 -> ~50, dist>1 -> low
    score = max(0, 100 - (avg_dist * 100))
    return int(score)


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


def check_finger_near_mouth(hand_landmarks: Any, face_landmarks: Any) -> bool:
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
    mouth_cz = (f_lm[61].z + f_lm[291].z) / 2
    
    index_tip = h_lm[8]
    
    # Normalized distance in 3D
    dist = ((index_tip.x - mouth_cx)**2 + (index_tip.y - mouth_cy)**2 + (index_tip.z - mouth_cz)**2) ** 0.5
    # Relaxed from 0.08 to 0.12 to make it significantly easier to match near the mouth/chin
    return dist < 0.12


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
    for a, b in body_conns:
        cv2.line(canvas, px(REF_BODY[a]), px(REF_BODY[b]), (0,255,0), 4, cv2.LINE_AA)

    for pt in REF_BODY.values():
        cv2.circle(canvas, px(pt), 6, (0,0,255), -1, cv2.LINE_AA)

    # Head
    nose_px = px(REF_BODY["nose"])
    sw = abs(REF_BODY["l_shoulder"][0] - REF_BODY["r_shoulder"][0]) * W
    cv2.circle(canvas, nose_px, int(sw * 0.28), (0,255,0), 3, cv2.LINE_AA)

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
        for s, e in HAND_CONNECTIONS:
            cv2.line(canvas, px(hand_pts[s]), px(hand_pts[e]), (255,100,0), 2, cv2.LINE_AA)
        for i, pt in enumerate(hand_pts):
            r = 5 if i in FINGER_TIPS else (4 if i == 0 else 3)
            c = (0,255,255) if i in FINGER_TIPS else ((255,255,255) if i == 0 else (200,200,200))
            cv2.circle(canvas, px(pt), r, c, -1, cv2.LINE_AA)

    cv2.putText(canvas, "MATCH THIS POSE", (180, 455),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255,255,255), 2, cv2.LINE_AA)

    return canvas


class PoseMatcher:
    def __init__(self):
        self.WIN = "Pose Matcher"
        self.running = True
        self.fps = 0.0
        self.last_time = time.time()
        self.match_score = 0
        self.matched = False
        self.match_hold_time = 0
        self.ref_window_open = False

        # Reference images
        self.ref_img1 = cv2.imread("f139fdf3202282f05db2fc08ef97ea0b.jpg")
        if self.ref_img1 is None:
            self.ref_img1 = make_reference_image()

        self.ref_img2 = cv2.imread("think_monkey.png")
        if self.ref_img2 is None:
            self.ref_img2 = self.ref_img1

        self.active_ref = None  # Tracks which reference image matched (1 or 2)

        # Camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        time.sleep(1)

        if not self.cap.isOpened():
            sys.stderr.write("Error: Cannot open camera.\n")
            sys.exit(1)

        # MediaPipe
        self.pose = mp_pose.Pose(
            static_image_mode=False, model_complexity=1,
            min_detection_confidence=0.5, min_tracking_confidence=0.5,
        )
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False, max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5,
        )
        self.hands = mp_hands.Hands(
            static_image_mode=False, max_num_hands=2,
            min_detection_confidence=0.6, min_tracking_confidence=0.5,
        )

        cv2.namedWindow(self.WIN)

        print("=" * 55)
        print("  Pose Matcher — Real-Time")
        print("=" * 55)
        print("  Match the reference pose shown on screen.")
        print("  When your pose matches, the picture appears!")
        print("  Q / ESC to exit.")
        print("=" * 55)

        self.run()

    def run(self) -> None:
        """Main loop with resource cleanup and a small sleep to limit CPU usage."""
        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                pose_res = self.pose.process(rgb)
                face_res = self.face_mesh.process(rgb)
                hands_res = self.hands.process(rgb)

                has_arms = False
                has_face = False
                hand_count = 0
                has_index_up = False
                smile_score = 0

                if pose_res.pose_landmarks:
                    lm = pose_res.pose_landmarks.landmark
                    has_arms = True
                    draw_arms(frame, lm, w, h)

                if face_res.multi_face_landmarks:
                    self.last_face = face_res.multi_face_landmarks[0]
                    has_face = True
                    draw_face(frame, self.last_face, w, h)
                    smile_score = check_smile(self.last_face)

                finger_near_mouth = False
                if hands_res.multi_hand_landmarks:
                    hand_count = len(hands_res.multi_hand_landmarks)
                    for hand_lm in hands_res.multi_hand_landmarks:
                        draw_hand(frame, hand_lm, w, h)
                        if check_index_finger_up(hand_lm):
                            has_index_up = True
                            if has_face and check_finger_near_mouth(hand_lm, self.last_face):
                                finger_near_mouth = True

                # Compute match score based on index finger pointing up and face smiling
                if has_index_up:
                    self.match_score = smile_score
                else:
                    self.match_score = 0

                # Pose 1: Smiling + Index finger pointing up
                matched_1 = has_index_up and (smile_score >= 75)
                # Pose 2: Index finger raised and near/touching the mouth (thinking/biting pose)
                matched_2 = has_index_up and finger_near_mouth

                if matched_1:
                    self.matched = True
                    self.active_ref = 1
                elif matched_2:
                    self.matched = True
                    self.active_ref = 2
                else:
                    self.matched = False

                if self.matched:
                    self.match_hold_time = time.time() + 1.5  # hold for 1.5s

                # FPS
                now = time.time()
                self.fps = 0.9 * self.fps + 0.1 / max(now - self.last_time, 0.001)
                self.last_time = now

                # Status
                parts = []
                if has_arms: parts.append("Arms")
                if has_face: parts.append("Face")
                if hand_count: parts.append(f"Hands({hand_count})")
                status = f"Tracking: {', '.join(parts)}" if parts else "No detection"
                cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0,255,0) if parts else (0,0,255), 2, cv2.LINE_AA)

                cv2.putText(frame, f"FPS:{self.fps:.0f}", (560, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150,150,150), 1, cv2.LINE_AA)

                # If matched, show reference image in a separate window, 100% clearly
                if self.matched or now < self.match_hold_time:
                    if not self.ref_window_open:
                        cv2.namedWindow("Matched Image", cv2.WINDOW_AUTOSIZE)
                        self.ref_window_open = True
                    
                    # Select the matched reference image
                    ref_to_show = self.ref_img1 if self.active_ref == 1 else self.ref_img2
                    cv2.imshow("Matched Image", ref_to_show)
                    
                    cv2.putText(frame, "MATCH!", (250, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,0), 3, cv2.LINE_AA)
                else:
                    if self.ref_window_open:
                        try:
                            cv2.destroyWindow("Matched Image")
                        except cv2.error:
                            pass
                        self.ref_window_open = False
                        self.active_ref = None

                cv2.imshow(self.WIN, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
                # Small sleep to reduce CPU load
                time.sleep(0.01)
        except Exception as e:
            sys.stderr.write(f"Error in main loop: {e}\n")
        finally:
            self.cap.release()
            self.pose.close()
            self.face_mesh.close()
            self.hands.close()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    PoseMatcher()

