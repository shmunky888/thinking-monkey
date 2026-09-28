"""Run headlessly: QT_QPA_PLATFORM=offscreen ./venv/bin/python -m unittest test_gui."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from contextlib import ExitStack
from threading import Event
from types import SimpleNamespace
from unittest import TestCase, main as unittest_main
from unittest.mock import MagicMock, patch
import time

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main
from gui import PoseWindow, CameraWorker


class DesktopTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_controls_and_match(self):
        matcher = main.PoseMatcher()
        window = PoseWindow(matcher, auto_start=False)
        window.show()
        self.app.processEvents()
        self.assertEqual(window.camera_button.text(), 'Start camera')
        self.assertTrue(window.overlay_button.isChecked())
        self.assertFalse(window.overlay_button.isEnabled())
        window.overlay_button.setEnabled(True)  # simulate camera running
        QTest.mouseClick(window.overlay_button, Qt.MouseButton.LeftButton)
        self.assertFalse(window.overlay_button.isChecked())
        self.assertEqual(window.overlay_button.text(), 'Overlay off')
        state = main.TrackingState(True, True, 1, 90, True, False, 1, True, 30.0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        window.show_frame(frame, state)
        self.assertEqual(window.reaction.image, window.reference_images[1])
        self.assertFalse(window.reaction.image.isNull())
        self.assertEqual(window.fps_label.text(), '30 FPS')
        state = main.TrackingState(False, False, 0, 0, False, False, None, False, 25.0)
        window.show_frame(frame, state)
        self.assertTrue(window.reaction.image.isNull())
        window.camera_failed('Test camera failure')
        self.assertEqual(window.status_label.text(), 'Camera unavailable')
        self.assertIn('Test camera failure', window.camera.message.text())
        for size in [(900, 650), (1200, 800)]:
            window.resize(*size)
            self.app.processEvents()
            self.assertGreater(window.camera.width(), window.reaction.width())
            for control in (window.camera_button, window.overlay_button, window.quit_button):
                self.assertTrue(window.rect().contains(control.mapTo(window, control.rect().bottomRight())))
        window.close()

    def test_latest_frame_buffer_is_bounded(self):
        matcher = MagicMock()
        matcher.frames.return_value = ((np.zeros((2, 2, 3), np.uint8), i) for i in range(100))
        worker = CameraWorker(matcher, overlay=True)
        worker.run()
        self.assertEqual(worker.take_latest()[1], 99)
        self.assertIsNone(worker.take_latest())

    def test_start_pause_restart_and_close(self):
        matcher = main.PoseMatcher()
        released = Event()

        def frames(stop, overlay):
            try:
                while not stop.is_set():
                    yield np.zeros((48, 64, 3), np.uint8), main.TrackingState(False, False, 0, 0, False, False, None, False, 30.)
                    stop.wait(.005)
            finally:
                released.set()

        def until(predicate):
            deadline = time.monotonic() + 2
            while not predicate() and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertTrue(predicate())

        with patch.object(matcher, 'frames', side_effect=frames):
            window = PoseWindow(matcher)
            window.show()
            try:
                QTest.mouseClick(window.camera_button, Qt.MouseButton.LeftButton)
                until(lambda: window.camera_button.text() == 'Pause camera')
                self.assertTrue(window.overlay_button.isEnabled())
                QTest.keyClick(window, Qt.Key.Key_O)
                self.assertFalse(window.worker.overlay_event.is_set())
                QTest.mouseClick(window.camera_button, Qt.MouseButton.LeftButton)
                until(lambda: window.worker is None)
                self.assertTrue(released.is_set())
                self.assertTrue(window.camera.image.isNull())
                released.clear()
                QTest.mouseClick(window.camera_button, Qt.MouseButton.LeftButton)
                until(lambda: window.camera_button.text() == 'Pause camera')
                QTest.keyClick(window, Qt.Key.Key_Escape)
                until(lambda: window.worker is None)
                self.assertTrue(released.is_set())
                self.assertFalse(window.isVisible())
            finally:
                window.close()
                until(lambda: window.worker is None)

    def test_worker_error_can_be_retried(self):
        matcher = main.PoseMatcher()
        window = PoseWindow(matcher)
        with patch.object(matcher, 'frames', side_effect=RuntimeError('Device busy')):
            window.toggle_camera()
            deadline = time.monotonic() + 2
            while window.worker is not None and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertIsNone(window.worker)
            self.assertEqual(window.camera_button.text(), 'Retry camera')
            self.assertTrue(window.camera_button.isEnabled())
            self.assertIn('Device busy', window.camera.message.text())
        window.close()

    def test_gesture_geometry_and_reference_fallback(self):
        def landmarks(count):
            return SimpleNamespace(landmark=[SimpleNamespace(x=.5, y=.5, z=0.) for _ in range(count)])
        hand, face = landmarks(21), landmarks(468)
        hand.landmark[8].z = -.5
        self.assertTrue(main.check_finger_near_mouth(hand, face))
        hand.landmark[8].x = .8
        self.assertFalse(main.check_finger_near_mouth(hand, face))
        self.assertFalse(main.check_finger_near_mouth(hand, None))
        hand.landmark[8].y = .4
        self.assertTrue(main.check_index_finger_up(hand))
        hand.landmark[12].y = .3
        self.assertFalse(main.check_index_finger_up(hand))
        self.assertEqual(main.check_smile(face), 0)
        face.landmark[234].x, face.landmark[454].x = 0., 1.
        face.landmark[61].x, face.landmark[291].x = .2, .7
        self.assertEqual(main.check_smile(face), 100)
        with patch.object(main.cv2, 'imread', return_value=None), patch.object(main.cv2, 'VideoCapture') as capture:
            matcher = main.PoseMatcher()
            capture.assert_not_called()
            self.assertEqual(matcher.ref_img1.shape, (480, 640, 3))
            self.assertEqual(matcher.ref_img2.shape, (480, 640, 3))

    def test_camera_failure_releases_device(self):
        camera = MagicMock()
        camera.isOpened.return_value = False
        with patch.object(main.cv2, 'VideoCapture', return_value=camera):
            with self.assertRaisesRegex(RuntimeError, 'camera'):
                next(main.PoseMatcher().frames(Event(), Event()))
        camera.release.assert_called_once()

    def test_detection_priority_hold_and_cleanup(self):
        with ExitStack() as stack:
            camera = MagicMock()
            camera.isOpened.return_value = True
            camera.read.return_value = (True, np.zeros((480, 640, 3), np.uint8))
            stack.enter_context(patch.object(main.cv2, 'VideoCapture', return_value=camera))
            models = []
            for module, factory in ((main.mp_pose, 'Pose'), (main.mp_face_mesh, 'FaceMesh'), (main.mp_hands, 'Hands')):
                model = MagicMock()
                model.__enter__.return_value = model
                model.process.return_value = SimpleNamespace(pose_landmarks=None, multi_face_landmarks=[object()], multi_hand_landmarks=[object()])
                stack.enter_context(patch.object(module, factory, return_value=model))
                models.append(model)
            stack.enter_context(patch.object(main, 'check_smile', side_effect=[90, 0, 0, 0]))
            stack.enter_context(patch.object(main, 'check_index_finger_up', side_effect=[True, True, False, False]))
            stack.enter_context(patch.object(main, 'check_finger_near_mouth', return_value=True))
            draw = stack.enter_context(patch.object(main, 'draw_hand'))
            stack.enter_context(patch.object(main, 'draw_face'))
            matcher = main.PoseMatcher()
            # Clock: stream reset, then four frames. Last frame expires hold.
            stack.enter_context(patch.object(main.time, 'monotonic', side_effect=[1., 2., 3., 4., 6.]))
            frames = matcher.frames(Event(), Event())
            first = next(frames)[1]
            self.assertEqual(first.active_ref, 1)  # smile wins simultaneous matches
            second = next(frames)[1]
            self.assertEqual(second.active_ref, 2)
            held = next(frames)[1]
            self.assertFalse(held.matched)
            self.assertEqual(held.active_ref, 2)
            self.assertIsNone(next(frames)[1].active_ref)
            draw.assert_not_called()  # overlay off still detects
            frames.close()
            camera.release.assert_called_once()
            for model in models:
                model.__exit__.assert_called_once()

    def test_initialization_failure_closes_earlier_models(self):
        camera = MagicMock()
        camera.isOpened.return_value = True
        pose = MagicMock()
        with patch.object(main.cv2, 'VideoCapture', return_value=camera), \
             patch.object(main.mp_pose, 'Pose', return_value=pose), \
             patch.object(main.mp_face_mesh, 'FaceMesh', side_effect=RuntimeError('model failure')):
            with self.assertRaisesRegex(RuntimeError, 'model failure'):
                next(main.PoseMatcher().frames(Event(), Event()))
        camera.release.assert_called_once()
        pose.__exit__.assert_called_once()


if __name__ == '__main__':
    unittest_main()
