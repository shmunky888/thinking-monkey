# CLAUDE.md

Repository guidance. Last updated: 2026-09-20.

## Run and dependencies

Use Python 3.12 with the local `venv/`. Install `requirements.txt` with `./venv/bin/python -m pip install -r requirements.txt`, then run `./run.sh` or `./venv/bin/python main.py`. Dependencies are MediaPipe, NumPy, OpenCV contrib, and PySide6. The GUI is a single native Qt window. Camera access is requested only after Start camera.

Space starts/pauses/resumes capture, O toggles overlay visibility, and Q/Esc quits. Pause releases the webcam. Startup, stopping, off, live, and failure states are explicit; recoverable failures show Retry camera after cleanup. The overlay button is disabled until the camera starts. The status dot pulses while the camera is live.

## Architecture

- `main.py`: `PoseMatcher` loads reaction images. `frames(stop, overlay)` opens the webcam and sequentially runs MediaPipe Pose, FaceMesh, and Hands on mirrored frames. Its `ExitStack` releases the camera and models on completion, initialization failure, or iterator closure. `run()` launches `gui.run_gui()`.
- `TrackingState`: immutable per-frame detection state, active reference, match flag, and smoothed FPS.
- `gui.py`: `PoseWindow` owns the UI. `CameraWorker` runs capture/inference on a `QThread`, with stop/overlay events and a locked one-slot latest-frame mailbox. A 33ms UI timer consumes available frames without accumulating a queue. An 800ms dot timer pulses the status indicator while the camera is live. Closing waits for worker cleanup without blocking the UI thread.
- `ImageView`: owns copied `QImage` pixels and paints images with preserved aspect ratio. Camera and reaction stay in the same window.

## Detector invariants

- `check_index_finger_up()` requires the index tip above its PIP and the other fingers folded, with the existing relaxed tolerances.
- `check_smile()` maps the 3D mouth-width/face-width ratio to a clamped 0–100 score. A score of at least 75 plus a raised index finger selects reference 1.
- `check_finger_near_mouth()` measures normalized **2D image distance** from index tip to mouth center; the default threshold is 0.12. Hand/face depth origins differ. This does not prove physical contact.
- A raised index finger near the mouth selects reference 2. Smile has priority when both match. Each matching frame renews the 1.5-second hold.
- Disabling the overlay changes drawing only, not detection or matching.

## Assets and visual system

Original reaction sources are `f139fdf3202282f05db2fc08ef97ea0b.jpg` (smile) and `think_monkey.png` (thinking). They resolve relative to `main.py`; `make_reference_image()` provides a synthetic T-pose fallback.

Follow `DESIGN.md`, the QSS in `gui.py`, and `.impeccable/surfaces/main-py.md`. The approved Camera workspace uses Qt system typography, a 7:3 camera/sidebar layout, a 1200×800 default and 900×650 minimum, explicit keyboard focus, and a 180ms match-strip opacity transition. `.impeccable/design.json` has static HTML/CSS documentation equivalents, not application components.

## Verification

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m unittest test_gui
```

The ignored local `test_main.py` also runs this suite plus the previous geometry checks. Keep tests independent of a real webcam. Inspect native evidence in `.impeccable/build/native-verification.json`; do not claim web gates passed for this desktop app. Actual webcam/permission behavior needs physical-camera verification.
