# Pose Matcher

A local Python desktop app that matches two webcam gestures and shows the corresponding reaction image beside your live feed. The single PySide6 window includes gesture instructions, camera state, an optional tracking overlay, and FPS.

Last updated: 2026-09-20.

## Setup and run

Use Python 3.12 and a connected webcam:

```bash
python3.12 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./run.sh
```

You can also launch with `./venv/bin/python main.py`. Dependencies are pinned or bounded in `requirements.txt`: MediaPipe, NumPy, OpenCV contrib, and PySide6. Allow camera access when your operating system requests it.

The camera starts off. Click **Start camera**, then try either gesture:

- **Smile + finger up:** raise your index finger, fold the other fingers, and smile. A smile score of at least 75 triggers the smile reaction.
- **Thinking pose:** raise your index finger with the other fingers folded and bring its tip near your mouth in the image.

The smile pose takes priority if both match. Each matching frame renews a 1.5-second reaction hold. Thinking detection uses normalized 2D image distance, so it detects proximity in the image rather than physical contact.

## Controls and recovery

| Control | Shortcut | Behavior |
| --- | --- | --- |
| Start / pause / resume camera | Space | Start capture or release the webcam when paused. |
| Overlay on / off | O | Show or hide tracking lines; matching continues. |
| Quit | Q or Esc | Close after releasing the camera and models. |

Buttons support keyboard focus. During startup, the camera action becomes **Cancel**. While stopping it is briefly disabled. If camera opening, frame reading, or model initialization fails, the camera view shows the error and **Retry camera** becomes available after cleanup. Check camera permissions, reconnect the webcam, or close another camera app before retrying.

Processing stays local. No account, recording, upload, or sharing workflow is implemented.

## Development

- `main.py`: MediaPipe detection, overlay drawing, reaction selection, and camera/model cleanup.
- `gui.py`: native single-window UI and background camera worker.
- `f139fdf3202282f05db2fc08ef97ea0b.jpg` and `think_monkey.png`: original smile and thinking reaction images. Missing images fall back to a generated T-pose; paths resolve relative to `main.py`.
- `DESIGN.md`: implemented visual system; `.impeccable/design.json` supplies static documentation previews.

Run the headless GUI regression suite without a webcam:

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m unittest test_gui
```

The existing ignored `test_main.py` runs the same suite plus its earlier geometry checks when invoked directly. Native visual evidence is recorded in `.impeccable/build/native-verification.json`; browser gates do not apply. Live webcam permissions and capture still need a physical-camera check on the target machine.
