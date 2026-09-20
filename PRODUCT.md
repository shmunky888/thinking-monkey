# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop

The user confirmed a local Python desktop app. This is an OpenCV desktop
application, not a web, iOS, or Android surface.

## Users

People using their own webcam for casual pose matching.

## Product Purpose

Recognize a pose in the live camera feed and reveal the corresponding reaction
image. A successful session makes the two supported gestures easy to discover,
perform, and recognize.

## Operating Context

Run locally with `./run.sh` and a connected webcam. The confirmed redesign brings
the camera, pose instructions, and matched image together in one desktop window.

## Capabilities and Constraints

- Detect a raised index finger with folded remaining fingers.
- Match a smile plus raised index finger, or a raised index finger near the mouth.
- The smile pose takes priority when both poses match.
- A match remains visible for 1.5 seconds after the last matching frame.
- Preserve local MediaPipe detection and the existing reference images.
- Camera and model resources must be released on exit or initialization failure.
- Existing implementation uses Python, OpenCV, MediaPipe, and NumPy.
- No account, recording, upload, or sharing workflow is currently implemented.
- Broader audience, distribution, branding, and accessibility requirements remain
  open decisions.

## Brand Commitments

The existing application name is Pose Matcher. The user requested a modern GUI
and previously requested a cleaner skeleton overlay and updated typography.

## Evidence on Hand

- `main.py`: implemented detection and matching behavior.
- `f139fdf3202282f05db2fc08ef97ea0b.jpg`: smile reaction image.
- `think_monkey.png`: thinking reaction image.
- `test_main.py`: local headless regression checks.

## Product Principles

- Keep the camera and reaction visible in one place.
- Explain the actual supported gestures with immediate tracking feedback.
- Preserve the playful reaction images while making controls easy to understand.
- Keep processing local and camera state explicit.
