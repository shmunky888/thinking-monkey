"""Native single-window interface; camera and inference stay off the UI thread."""
import sys
from contextlib import closing
from threading import Event, Lock
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, QSize, QRectF, QPropertyAnimation, Signal, Slot
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from main import PoseMatcher, TrackingState

STYLE = """
QWidget { color: #252B2C; font-size: 14px; }
QWidget#workspace { background: #E7E9E8; }
QLabel { background: transparent; }
QLabel#title { font-size: 22px; font-weight: 600; }
QLabel#cameraStatus { color: #515A5A; }
QFrame#toolbar { border-top: 1px solid #CCD1CE; }
QFrame#poseRow { background: #FAFBF9; border: 1px solid #D4D9D5; border-radius: 10px; }
QFrame#poseRow[matched="true"] { background: #E3EDE1; border-color: #78976F; }
QLabel#poseTitle { font-size: 18px; font-weight: 600; }
QLabel#poseCopy { color: #505958; }
QLabel#matchState { background: #DCE1DD; color: #4D5951; border-radius: 8px; font-size: 16px; font-weight: 600; padding: 8px; }
QLabel#matchState[matched="true"] { background: #D9E8D8; color: #29482E; }
QPushButton { background: #FAFBF9; border: 1px solid #AEB8B2; border-radius: 9px; padding: 12px 20px; font-size: 16px; font-weight: 500; }
QPushButton:hover { background: #FFFFFF; border-color: #68766E; }
QPushButton:pressed { background: #D7DDD8; }
QPushButton:checked { background: #F1F5EE; border-color: #788A79; }
QPushButton:focus { border: 2px solid #425D79; padding: 11px 19px; }
QPushButton:disabled { color: #6B756E; background: #D6DCD7; border-color: #B8C2BB; }
QPushButton#cameraButton { background: #C75517; color: #FFFFFF; border-color: #C75517; }
QPushButton#cameraButton:hover { background: #B84C12; border-color: #B84C12; }
QPushButton#cameraButton:pressed { background: #9C3F0D; }
QPushButton#cameraButton:focus { border: 2px solid #252B2C; }
QPushButton#cameraButton:disabled { color: #606962; background: #D6DCD7; border-color: #B8C2BB; }
QToolTip { color: #FAFBF9; background: #252B2C; border: 0; padding: 6px; }
"""


def icon(kind: str, color: str = '#252B2C', size: int = 24) -> QIcon:
    """Small line icons use Qt geometry and stay sharp on high-DPI displays."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == 'camera':
        painter.drawRoundedRect(QRectF(2, 5, 14, 14), 2, 2)
        path = QPainterPath()
        path.moveTo(16, 9); path.lineTo(22, 6); path.lineTo(22, 18); path.lineTo(16, 15)
        painter.drawPath(path)
    elif kind == 'eye':
        path = QPainterPath()
        path.moveTo(2, 12); path.quadTo(12, 0, 22, 12); path.quadTo(12, 24, 2, 12)
        painter.drawPath(path)
        painter.drawEllipse(QRectF(9, 9, 6, 6))
    elif kind == 'eye-off':
        path = QPainterPath()
        path.moveTo(2, 12); path.quadTo(12, 0, 22, 12); path.quadTo(12, 24, 2, 12)
        painter.drawPath(path)
        painter.drawEllipse(QRectF(9, 9, 6, 6))
        painter.setPen(QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(4, 20, 20, 4)
    elif kind == 'quit':
        painter.drawLine(6, 6, 18, 18); painter.drawLine(18, 6, 6, 18)
    elif kind == 'smile':
        painter.drawEllipse(QRectF(1, 3, 14, 17))
        painter.drawPoint(5, 9); painter.drawPoint(11, 9)
        path = QPainterPath()
        path.moveTo(4, 13); path.quadTo(8, 18, 12, 13)
        painter.drawPath(path)
        painter.setPen(QPen(QColor('#C75517'), 1.6, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        finger = QPainterPath()
        finger.moveTo(18, 22); finger.lineTo(16, 18); finger.lineTo(16, 13)
        finger.quadTo(17, 11, 18, 13); finger.lineTo(18, 5)
        finger.quadTo(18, 2, 20, 3); finger.lineTo(20, 14)
        finger.quadTo(22, 13, 22, 16); finger.lineTo(21, 21)
        painter.drawPath(finger)
    elif kind == 'thinking':
        painter.drawEllipse(QRectF(3, 2, 18, 20))
        painter.drawPoint(8, 9); painter.drawPoint(16, 9)
        path = QPainterPath()
        path.moveTo(10, 21); path.lineTo(13, 15); path.quadTo(14, 13, 15, 15); path.lineTo(13, 21)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def as_image(frame: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    # Own the pixels: the worker's next frame must never invalidate Qt's buffer.
    return QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()


class ImageView(QWidget):
    def __init__(self, name: str, dark: bool = True):
        super().__init__()
        self.image = QImage()
        self.dark = dark
        self.setAccessibleName(name)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(180, 120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet('color: #DCE2DF; font-size: 17px;' if dark else 'color: #515A54; font-size: 15px;')
        layout.addWidget(self.message)
        layout.addStretch()

    def set_image(self, image: QImage) -> None:
        self.image = image
        self.message.setVisible(image.isNull())
        self.update()

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.set_image(QImage())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor('#252B2C' if self.dark else '#DCE1DD'))
        if not self.image.isNull():
            bounds = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF((self.width() - bounds.width()) / 2, (self.height() - bounds.height()) / 2,
                            bounds.width(), bounds.height())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self.image)
        painter.end()


class CameraWorker(QThread):
    failed = Signal(str)

    def __init__(self, matcher: 'PoseMatcher', overlay: bool):
        super().__init__()
        self.matcher = matcher
        self.stop_event = Event()
        self.overlay_event = Event()
        if overlay:
            self.overlay_event.set()
        self._lock = Lock()
        self._latest = None

    def run(self):
        try:
            with closing(self.matcher.frames(self.stop_event, self.overlay_event)) as frames:
                for frame, state in frames:
                    with self._lock:
                        self._latest = (frame, state)
        except Exception as error:
            self.failed.emit(str(error) or 'The camera could not start. Try again.')

    def take_latest(self):
        # One-slot mailbox: a slow UI drops old frames instead of building a queue.
        with self._lock:
            packet, self._latest = self._latest, None
        return packet


class PoseWindow(QWidget):
    def __init__(self, matcher: 'PoseMatcher', auto_start: bool = False):
        super().__init__()
        self.matcher = matcher
        self.worker = None
        self._stopping = False
        self._closing = False
        self._error = False
        self._active_ref = None
        self._dot_visible = True
        self.setObjectName('workspace')
        self.setWindowTitle('Pose Matcher')
        self.setWindowIcon(icon('smile', size=32))
        self.setMinimumSize(900, 650)
        self.resize(1200, 800)
        self.setStyleSheet(STYLE)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
        self.reference_images = {1: as_image(matcher.ref_img1), 2: as_image(matcher.ref_img2)}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(20, 14, 20, 14)
        title = QLabel('Pose Matcher')
        title.setObjectName('title')
        header.addWidget(title)
        header.addStretch()
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(9, 9)
        header.addWidget(self.status_dot)
        header.addSpacing(6)
        self.status_label = QLabel('Camera is off')
        self.status_label.setObjectName('cameraStatus')
        header.addWidget(self.status_label)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setContentsMargins(16, 0, 16, 16)
        content.setSpacing(16)
        self.camera = ImageView('Live camera with optional pose tracking overlay')
        self.camera.show_message('Your camera, your pose.\n\nStart the camera to try either gesture.')
        content.addWidget(self.camera, 7)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        self.reaction = ImageView('Matched reaction image', dark=False)
        self.reaction.show_message('Your reaction appears here\nwhen a pose matches.')
        sidebar.addWidget(self.reaction, 1)
        self.match_label = QLabel('Try either pose')
        self.match_label.setObjectName('matchState')
        self.match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.match_label.setMinimumHeight(44)
        self.match_effect = QGraphicsOpacityEffect(self.match_label)
        self.match_effect.setOpacity(1.0)
        self.match_label.setGraphicsEffect(self.match_effect)
        self.match_animation = QPropertyAnimation(self.match_effect, b'opacity', self)
        self.match_animation.setDuration(180)
        sidebar.addWidget(self.match_label)
        self.pose_rows = []
        for name, title_text, copy in [
            ('smile', 'Smile + finger up', 'Raise your index finger and smile.'),
            ('thinking', 'Thinking pose', 'Bring your raised finger near your mouth.'),
        ]:
            row = QFrame()
            row.setObjectName('poseRow')
            row.setMinimumHeight(110)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 16, 18, 16)
            row_layout.setSpacing(16)
            glyph = QLabel()
            glyph.setPixmap(icon(name, size=44).pixmap(QSize(44, 44)))
            glyph.setFixedSize(44, 44)
            glyph.setAccessibleName(title_text + ' gesture')
            row_layout.addWidget(glyph)
            text = QVBoxLayout()
            text.setSpacing(6)
            heading = QLabel(title_text)
            heading.setObjectName('poseTitle')
            heading.setWordWrap(True)
            heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            description = QLabel(copy)
            description.setObjectName('poseCopy')
            description.setWordWrap(True)
            description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            text.addWidget(heading)
            text.addWidget(description)
            row_layout.addLayout(text, 1)
            sidebar.addWidget(row)
            self.pose_rows.append(row)
        content.addLayout(sidebar, 3)
        root.addLayout(content, 1)

        toolbar = QFrame()
        toolbar.setObjectName('toolbar')
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(18, 14, 18, 14)
        controls.setSpacing(12)
        self.camera_button = QPushButton('Start camera')
        self.camera_button.setObjectName('cameraButton')
        self.camera_button.setIcon(icon('camera', '#FFFFFF'))
        self.camera_button.setMinimumWidth(190)
        self.camera_button.setToolTip('Start or pause the camera (Space). Pausing releases the webcam.')
        self.camera_button.clicked.connect(self.toggle_camera)
        self.overlay_button = QPushButton('Overlay on')
        self.overlay_button.setIcon(icon('eye'))
        self.overlay_button.setCheckable(True)
        self.overlay_button.setChecked(True)
        self.overlay_button.setEnabled(False)
        self.overlay_button.setToolTip('Show or hide the skeleton (O). Pose matching stays active.')
        self.overlay_button.toggled.connect(self.toggle_overlay)
        self.quit_button = QPushButton('Quit')
        self.quit_button.setIcon(icon('quit'))
        self.quit_button.setToolTip('Close the app and release the camera (Q or Esc).')
        self.quit_button.clicked.connect(self.close)
        for button in (self.camera_button, self.overlay_button, self.quit_button):
            button.setMinimumHeight(52)
            button.setIconSize(QSize(24, 24))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        controls.addWidget(self.camera_button)
        controls.addWidget(self.overlay_button)
        controls.addStretch()
        self.fps_label = QLabel('— FPS')
        self.fps_label.setMinimumWidth(64)
        self.fps_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.fps_label.setToolTip('Frames per second. Tracking runs at camera rate.')
        controls.addWidget(self.fps_label)
        controls.addSpacing(12)
        controls.addWidget(self.quit_button)
        root.addWidget(toolbar)
        self.set_status('Camera is off', '#7B847E')
        self.shortcuts = []
        for key, callback in [('Space', self.toggle_camera), ('O', self.overlay_button.click),
                              ('Q', self.close), ('Esc', self.close)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.read_frame)
        self.timer.start()
        self.dot_timer = QTimer(self)
        self.dot_timer.setInterval(800)
        self.dot_timer.timeout.connect(self._pulse_dot)
        if auto_start:
            QTimer.singleShot(0, self.toggle_camera)

    def set_status(self, text: str, color: str):
        self.status_label.setText(text)
        self._status_color = color
        self._dot_visible = True
        self.status_dot.setStyleSheet(f'background: {color}; border-radius: 4px;')

    @Slot()
    def _pulse_dot(self):
        """Blink the status dot while the camera is live."""
        self._dot_visible = not self._dot_visible
        c = self._status_color if self._dot_visible else 'transparent'
        self.status_dot.setStyleSheet(f'background: {c}; border-radius: 4px;')

    @Slot()
    def toggle_camera(self):
        if self._stopping or self._closing:
            return
        if self.worker is not None:
            self._stopping = True
            self.worker.stop_event.set()
            self.camera_button.setEnabled(False)
            self.camera_button.setText('Stopping…')
            self.set_status('Stopping camera…', '#7B847E')
            self.camera.show_message('Stopping camera…')
            self.clear_match()
            return
        self._error = False
        self.camera_button.setEnabled(True)
        self.camera_button.setText('Cancel')
        self.overlay_button.setEnabled(True)
        self.set_status('Starting camera…', '#B45A23')
        self.camera.show_message('Starting your camera…\nLoading pose tracking.')
        self.worker = CameraWorker(self.matcher, self.overlay_button.isChecked())
        self.worker.failed.connect(self.camera_failed)
        self.worker.finished.connect(self.camera_finished)
        self.worker.start()

    @Slot(bool)
    def toggle_overlay(self, checked: bool):
        self.overlay_button.setText('Overlay on' if checked else 'Overlay off')
        self.overlay_button.setIcon(icon('eye' if checked else 'eye-off'))
        if self.worker:
            (self.worker.overlay_event.set if checked else self.worker.overlay_event.clear)()

    @Slot()
    def read_frame(self):
        if self.worker is None or self._stopping or self._error or self._closing:
            return
        packet = self.worker.take_latest()
        if packet:
            self.show_frame(*packet)

    def show_frame(self, frame: np.ndarray, state: 'TrackingState'):
        self.camera.set_image(as_image(frame))
        self.camera_button.setEnabled(True)
        self.camera_button.setText('Pause camera')
        tracking = state.has_face or state.hand_count
        self.set_status('Camera connected' if tracking else 'No pose detected', '#3C8650' if tracking else '#B45A23')
        if not self.dot_timer.isActive():
            self.dot_timer.start()
        self.fps_label.setText(f'{state.fps:.0f} FPS')
        if self._active_ref != state.active_ref:
            self._active_ref = state.active_ref
            if state.active_ref is not None:
                self.reaction.set_image(self.reference_images[state.active_ref])
            else:
                self.reaction.show_message('Your reaction appears here\nwhen a pose matches.')
            for index, row in enumerate(self.pose_rows, 1):
                row.setProperty('matched', index == state.active_ref)
                row.style().unpolish(row)
                row.style().polish(row)
            self.match_label.setProperty('matched', state.active_ref is not None)
            self.match_label.style().unpolish(self.match_label)
            self.match_label.style().polish(self.match_label)
            self.match_animation.stop()
            if state.active_ref is not None:
                self.match_animation.setStartValue(0.65)
                self.match_animation.setEndValue(1.0)
                self.match_animation.start()
            else:
                self.match_effect.setOpacity(1.0)
        if state.active_ref:
            name = 'Smile + finger up' if state.active_ref == 1 else 'Thinking pose'
            self.match_label.setText(f'Matched · {name}')
        else:
            self.match_label.setText('Try either pose')

    def clear_match(self):
        self.match_animation.stop()
        self.match_effect.setOpacity(1.0)
        self._active_ref = None
        self.reaction.show_message('Your reaction appears here\nwhen a pose matches.')
        self.match_label.setText('Try either pose')
        for widget in [self.match_label, *self.pose_rows]:
            widget.setProperty('matched', False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.fps_label.setText('— FPS')

    @Slot(str)
    def camera_failed(self, message: str):
        self._error = True
        self.dot_timer.stop()
        self.set_status('Camera unavailable', '#AD3C27')
        self.camera.show_message(f'{message}\n\nCheck your connection and camera permission,\nthen click Retry camera.')
        self.clear_match()
        self.camera_button.setText('Retry camera')
        self.camera_button.setEnabled(self.worker is None)

    @Slot()
    def camera_finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        self._stopping = False
        self.dot_timer.stop()
        if self._closing:
            self.close()
            return
        self.camera_button.setEnabled(True)
        self.overlay_button.setEnabled(False)
        self.clear_match()
        if not self._error:
            self.set_status('Camera is off', '#7B847E')
            self.camera.show_message('Camera paused.\n\nResume whenever you\'re ready.')
            self.camera_button.setText('Resume camera')

    def closeEvent(self, event):
        if self.worker is not None:
            self._closing = True
            self.worker.stop_event.set()
            self.camera_button.setEnabled(False)
            self.overlay_button.setEnabled(False)
            self.dot_timer.stop()
            self.set_status('Closing camera…', '#7B847E')
            event.ignore()
        else:
            self.timer.stop()
            self.dot_timer.stop()
            event.accept()


def run_gui(matcher: 'PoseMatcher') -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Pose Matcher')
    app.setStyle('Fusion')
    window = PoseWindow(matcher)
    window.show()
    app.exec()
