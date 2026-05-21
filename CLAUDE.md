# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run

```bash
./run.sh                    # runs via venv/bin/python main.py
./venv/bin/python main.py   # direct invocation
```

Requires a webcam connected to the machine. Press Q or ESC to quit.

## Dependencies

Python 3.12 virtualenv in `venv/`. Key packages: `opencv-python`, `mediapipe`, `numpy`.

```bash
./venv/bin/pip install <package>   # always use venv pip, not system pip
```

No tkinter — this is Homebrew Python; GUI is via OpenCV windows.

## Architecture

Single-file app (`main.py`) that runs a real-time pose matcher using the webcam.

**Detection pipeline** — each frame runs three MediaPipe models in parallel:
1. `mp.solutions.pose` — body skeleton (arms, shoulders, hips, legs)
2. `mp.solutions.face_mesh` — 468-point face landmarks
3. `mp.solutions.hands` — 21-point hand landmarks per hand

**Two pose modes:**
- **Pose 1 (smile + finger up):** Index finger pointed up + smile score >= 75% → shows `f139fdf3202282f05db2fc08ef97ea0b.jpg`
- **Pose 2 (thinking):** Index finger near mouth → shows `think_monkey.png`

Match triggers a 1.5s hold that displays the reference image in a separate OpenCV window.

**Key internals:**
- `normalize_landmarks()` — normalizes pose relative to torso center/scale
- `compute_match_score()` — compares normalized live pose to `REF_BODY` dict (currently unused in favor of finger/smile detection)
- `check_index_finger_up()` — detects index pointing up with other fingers folded
- `check_smile()` — mouth-width-to-face-width ratio mapped to 0-100
- `check_finger_near_mouth()` — 3D distance between index tip and mouth center
- `make_reference_image()` — generates a stick-figure T-pose fallback if reference images are missing

## Reference images

Two images in repo root: a smile reference (`f139...jpg`) and a thinking/monkey reference (`think_monkey.png`). If missing, `make_reference_image()` generates a synthetic T-pose fallback.

## .gitignore

Ignores `venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`.
