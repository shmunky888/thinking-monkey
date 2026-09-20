---
name: Pose Matcher
description: A native camera workspace with a matte silver frame and clear gesture feedback.
colors:
  camera-action: "#C75517"
  camera-hover: "#B84C12"
  camera-pressed: "#9C3F0D"
  workspace: "#E7E9E8"
  graphite: "#252B2C"
  panel: "#FAFBF9"
  white: "#FFFFFF"
  divider: "#CCD1CE"
  panel-border: "#D4D9D5"
  secondary-text: "#515A5A"
  instruction-text: "#505958"
  neutral-strip: "#DCE1DD"
  neutral-strip-text: "#4D5951"
  matched-panel: "#E3EDE1"
  matched-border: "#78976F"
  matched-strip: "#D9E8D8"
  matched-text: "#29482E"
  button-border: "#AEB8B2"
  button-hover-border: "#68766E"
  button-pressed: "#D7DDD8"
  button-checked: "#F1F5EE"
  button-checked-border: "#788A79"
  focus: "#425D79"
  disabled-text: "#6B756E"
  disabled-action-text: "#606962"
  disabled-fill: "#D6DCD7"
  disabled-border: "#B8C2BB"
typography:
  title:
    fontFamily: "Qt system GeneralFont"
    fontSize: "22px"
    fontWeight: 600
  pose-title:
    fontFamily: "Qt system GeneralFont"
    fontSize: "18px"
    fontWeight: 600
  match-label:
    fontFamily: "Qt system GeneralFont"
    fontSize: "16px"
    fontWeight: 600
  control:
    fontFamily: "Qt system GeneralFont"
    fontSize: "16px"
    fontWeight: 500
  body:
    fontFamily: "Qt system GeneralFont"
    fontSize: "14px"
rounded:
  strip: "8px"
  control: "9px"
  panel: "10px"
spacing:
  detail: "6px"
  strip: "8px"
  controls: "12px"
  chrome: "14px"
  content: "16px"
  row-horizontal: "18px"
  header-horizontal: "20px"
  image-message: "24px"
components:
  button-primary:
    backgroundColor: "{colors.camera-action}"
    textColor: "{colors.white}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-primary-hover:
    backgroundColor: "{colors.camera-hover}"
  button-primary-pressed:
    backgroundColor: "{colors.camera-pressed}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.graphite}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-secondary-checked:
    backgroundColor: "{colors.button-checked}"
  pose-row:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
    padding: "16px 18px"
  pose-row-matched:
    backgroundColor: "{colors.matched-panel}"
  match-strip:
    backgroundColor: "{colors.neutral-strip}"
    textColor: "{colors.neutral-strip-text}"
    typography: "{typography.match-label}"
    rounded: "{rounded.strip}"
    padding: "8px"
  match-strip-matched:
    backgroundColor: "{colors.matched-strip}"
    textColor: "{colors.matched-text}"
  camera-view:
    backgroundColor: "{colors.graphite}"
    rounded: "{rounded.panel}"
---

# Design System: Pose Matcher

## Overview

**Creative North Star: "Camera workspace"**

A compact camera workspace puts live video, the reaction image, and gesture instructions in one native desktop window. Matte silver, off-white panels, graphite video framing, and an orange camera action give the controls a quiet, practical hierarchy.

This records the implemented Python/PySide6 interface in `gui.py` and overlay in `main.py`, following the approved `.impeccable/mocks/decision/camera.png`. Last updated: 2026-09-20.

**Key Characteristics:**
- Native system typography and visible keyboard focus.
- Flat surfaces with fine borders and gently rounded corners.
- Original reaction images and aspect-ratio-preserving live video.
- Explicit camera states and restrained match feedback.

## Colors

Orange identifies the camera action. Silver and off-white frame the content; graphite anchors text and the viewfinder. Green panels and match text mark an active reaction without replacing its textual label.

The frontmatter records the QSS palette. Camera status dots additionally use off/stopping gray (`#7B847E`), starting/no-pose amber (`#B45A23`), connected green (`#3C8650`), and error red (`#AD3C27`), always beside status text. The dot pulses at 800ms while the camera is live. Image placeholders use `#DCE2DF` on graphite or `#515A54` on the reaction surface.

**The State Has Words Rule.** Pair color changes with readable camera or match labels.

## Typography

Use `QFontDatabase.systemFont(GeneralFont)` with Qt's Fusion widget style. The family follows the operating system; there is no bundled display font. The hierarchy is window title, pose title, match/control label, then body copy, as recorded above. Camera placeholder text is 17px and reaction placeholder text is 15px. Let Qt determine native font metrics; pose copy wraps at narrow widths.

## Layout

The default window is 1200×800 logical pixels; minimum is 900×650. A horizontal layout gives the camera and sidebar stretch factors of 7:3. This is a sizing preference subject to widget minimums. The sidebar contains the reaction, match strip, and two instruction rows. Header and bottom controls remain outside the image region.

Content has 16px side/bottom margins and a 16px column gap. Sidebar and toolbar spacing is 12px. Header margins are 20px horizontally and 14px vertically; toolbar margins are 18px and 14px. Pose rows have 18px horizontal/16px vertical padding and a minimum height of 110px. Buttons have a 52px minimum height; the camera button has a 190px minimum width. The match strip has a 44px minimum height. Native layouts resize continuously; no web breakpoints or mobile layout are implemented.

**The Whole Image Rule.** Fit camera and reaction images with `KeepAspectRatio`, centered with letterboxing as needed. Never stretch or crop the original reaction to fill its view.

## Elevation & Depth

Surfaces are flat. Fine borders, tonal fills, and the dark camera field separate regions; there are no shadows or floating overlays. The toolbar uses a single top divider.

## Shapes

Use the documented panel, control, and strip radii. Camera and reaction painting clips to the rounded image region. Icons are small, antialiased Qt line drawings, with 24px toolbar icons and 44px gesture illustrations. The smile gesture includes a distinct raised finger.

## Components

- **Camera action:** orange button with hover, pressed, focus, and disabled states. Its label changes through Start camera, Cancel, Pause camera, Stopping…, Resume camera, and Retry camera. The camera starts off. Pausing releases the webcam; stopping temporarily disables the action.
- **Overlay and quit:** off-white controls. Overlay is a checked toggle with explicit on/off text and a matching open/closed eye icon; it starts disabled until the camera runs. Hiding the overlay leaves matching active. All buttons have visible focus borders (2px); padding contracts by 1px to avoid a size jump. The primary focus border is graphite and secondary focus is blue. Preserve disabled text/fill/border treatments.
- **Pose rows:** line illustration, wrapping title, and short instruction. The active row gains the matched fill and border. These rows are instructions, not clickable controls.
- **Match strip:** a text label with neutral and matched treatments. On a new active reaction, opacity rises from 0.65 to 1 over 180ms using Qt's default easing. Returning to neutral restores full opacity immediately. This is separate from the detector's 1.5-second reaction hold.
- **Image views:** native `QImage` painting with centered, plain-text empty/error messages. Errors retain a visible recovery path through Retry camera.
- **Tracking overlay:** fine warm-light arm/hand strokes, quieter facial contours, dark edging, and open joint rings; the index finger uses an orange accent. `main.py` owns the BGR drawing colors.

The schema-v2 sidecar contains static HTML/CSS documentation equivalents of these native components. They are previews only; the application has no browser runtime.

## Do's and Don'ts

- **Do** keep camera and reaction visible together.
- **Do** preserve original image proportions and native keyboard focus.
- **Do** pair camera and match colors with readable state labels.
- **Don't** obscure the pose with controls or decorative overlays.
- **Don't** substitute browser typography or web layout gates for native Qt verification.
