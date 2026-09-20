"""Headless regression check: ./venv/bin/python test_main.py"""
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import os
import runpy

import main


def landmarks(count):
    return SimpleNamespace(landmark=[SimpleNamespace(x=0.5, y=0.5, z=0.0)
                                     for _ in range(count)])


def check():
    hand, face = landmarks(21), landmarks(468)
    hand.landmark[8].z = -0.5
    assert main.check_finger_near_mouth(hand, face), "Different depth origins must not reject image contact"
    hand.landmark[8].x = 0.8
    assert not main.check_finger_near_mouth(hand, face)
    assert not main.check_finger_near_mouth(hand, None)
    assert not main.check_finger_near_mouth(None, face)
    assert main.check_finger_near_mouth(hand, face, threshold=0.4)

    hand.landmark[8].y = 0.4
    assert main.check_index_finger_up(hand)
    hand.landmark[12].y = 0.3
    assert not main.check_index_finger_up(hand)
    assert main.check_smile(face) == 0
    face.landmark[234].x, face.landmark[454].x = 0.0, 1.0
    face.landmark[61].x, face.landmark[291].x = 0.2, 0.7
    assert main.check_smile(face) == 100
    face.landmark[291].x = 0.4
    assert main.check_smile(face) == 0

    # Importing helpers must not replace the caller's interpreter.
    with patch.object(main.sys, "executable", "/another/python"), patch.object(main.os, "execv") as execute:
        runpy.run_path(main.__file__, run_name="import_check")
        execute.assert_not_called()

    # Construction loads references from the app directory without opening hardware.
    with patch.object(main.cv2, "VideoCapture") as capture, patch.object(main.cv2, "imread", side_effect=[None, None]) as read:
        app = main.PoseMatcher()
        capture.assert_not_called()
        assert all(os.path.dirname(call.args[0]) == main.script_dir for call in read.call_args_list)
        assert app.ref_img1.shape == app.ref_img2.shape == (480, 640, 3)
    with patch.object(main.cv2, "imread", side_effect=["smile image", None]):
        assert main.PoseMatcher().ref_img2.shape == (480, 640, 3)

    # Exercise acquisition failures, loop failures, and both exit keys without a camera.
    for failure in ("camera", "pose", "face", "hands", "window", "read", "process", None, "escape", "match"):
        with ExitStack() as patches:
            mock = lambda obj, attr, **kw: patches.enter_context(patch.object(obj, attr, **kw))
            camera = mock(main.cv2, "VideoCapture").return_value
            camera.isOpened.return_value = failure != "camera"
            camera.read.return_value = (True, main.np.zeros((480, 640, 3), dtype=main.np.uint8))
            models = []
            for name, module, factory in (("pose", main.mp_pose, "Pose"), ("face", main.mp_face_mesh, "FaceMesh"), ("hands", main.mp_hands, "Hands")):
                model = MagicMock()
                model.__enter__.return_value = model
                model.process.return_value = SimpleNamespace(pose_landmarks=None, multi_face_landmarks=None, multi_hand_landmarks=None)
                mock(module, factory, return_value=model, side_effect=RuntimeError(name) if failure == name else None)
                models.append(model)
            window = mock(main.cv2, "namedWindow", side_effect=RuntimeError("window") if failure == "window" else None)
            show = mock(main.cv2, "imshow")
            mock(main.cv2, "waitKey", return_value=27 if failure == "escape" else ord("q"))
            destroy = mock(main.cv2, "destroyAllWindows")
            mock(main.time, "sleep")
            mock(main.time, "time", side_effect=AssertionError("Use a monotonic clock"))
            mock(main, "print")
            if failure == "read":
                camera.read.side_effect = [(False, None), AssertionError("Must not retry forever")]
            if failure == "process":
                models[0].process.side_effect = RuntimeError("process")
            hand = landmarks(21)
            models[2].process.return_value.multi_hand_landmarks = [hand]
            draw = mock(main, "draw_hand")
            if failure == "match":
                hand.landmark[8].y = 0.4
                face = landmarks(468)
                models[1].process.return_value.multi_face_landmarks = [face]
                mock(main, "draw_face")
                mock(main, "check_smile", return_value=0)
            app = main.PoseMatcher()
            expected_failure = failure not in (None, "escape", "match")
            try:
                app.run()
            except RuntimeError:
                assert expected_failure, failure
            else:
                assert not expected_failure, failure
                draw.assert_called_once()  # Hands remain visible without a face.
                if failure == "match":
                    assert app.matched and app.active_ref == 2
                    assert show.call_args_list[0].args[0] == "Matched Image"
            camera.release.assert_called_once()
            destroy.assert_called_once()
            for model in models:
                assert model.__exit__.call_count == model.__enter__.call_count


if __name__ == "__main__":
    check()
    print("All regression checks passed.")
