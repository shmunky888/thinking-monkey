---
version: 1
slug: "main-py"
primary_target: "main.py"
related_targets: ["gui.py"]
---

# Camera workspace

Mode: Operate. Desktop Python/Qt application. User confirmed a single window for
casual pose matching and selected Camera workspace with comp-first in the choice
page. The existing reference images and detector remain authoritative content.
Approved comp: `.impeccable/mocks/decision/camera.png`.

## Direction contract

THESIS: Camera and reaction share one workspace; controls never obscure the pose.

OWN-WORLD: Matte silver frame, off-white instruction panels, graphite viewfinder,
orange camera action, quiet native sans labels, fine dividers and 10px corners.

STORY: Start the camera, follow either gesture, see its reaction beside yourself.
Camera-off, starting, live, stopped, failed, and matched states are explicit.

FIRST VIEWPORT: Slim title/status header; camera fills the left two-thirds;
reaction, match state, and two instruction rows fill the right third; a bottom
bar contains camera, overlay, FPS, and quit. Signature interaction: the reaction
appears immediately on a match, accompanied by a restrained 180ms state reveal.
Real video and original monkey images replace illustrative comp imagery.

FORM: Compact digital-camera display, grounded candidate 3, seed 30bf17d5.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Native implementation

Use PySide6 widgets with native keyboard focus and accessible labels. Preserve
video aspect ratio and keep buttons operable while detection runs on a worker.
Minimum desktop window 900x650; inspect 1200x800 and 900x650. Font measurements
and region ratios from the approved image guide Qt logical sizing. HTML/CSS-only
phase checks are inapplicable to this Python desktop surface.
