"""
The reference comparison's camera solve (tools/Compare.py), without Blender or a frame: points projected by a known
camera must give that camera back; one point moved in the "frame" must be named by its leave-one-out error, and the
others not; a known focal length must be kept. Run: py -3 -m unittest discover -s tools/tests
"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import Compare as C  # noqa: E402

CENTRE = np.array([424.0, 239.0])
# A shed-like box: corners, a door and a window on two faces (Blender axes, metres)
POINTS = np.array([[-1.3, -1.3, 0.0], [1.3, -1.3, 0.0], [-1.3, -1.3, 2.2], [1.3, -1.3, 2.2], [-0.9, -1.35, 2.1],
                   [0.9, -1.35, 2.1], [-0.9, -1.35, 0.0], [1.3, 1.3, 2.2], [-1.33, 0.4, 1.8], [-1.33, -0.4, 1.8],
                   [-1.33, 0.4, 0.9], [0.0, -1.44, 3.6]])


def camera(f=400.0):
    return C.look_at(np.array([-5.0, -7.0, 2.5]), np.array([0.0, 0.0, 1.2]), f)


class SolveTests(unittest.TestCase):
    def test_a_known_camera_is_recovered(self):
        truth = camera()
        x = C.project(truth, POINTS, CENTRE)
        params = C.solve(POINTS, x, CENTRE)
        self.assertLess(np.abs(C.project(params, POINTS, CENTRE) - x).max(), 0.01)
        self.assertAlmostEqual(params[0], 400.0, delta=0.5)

    def test_a_moved_landmark_stands_out_in_its_leave_one_out_error(self):
        truth = camera()
        x = C.project(truth, POINTS, CENTRE) + np.random.default_rng(1).normal(0, 0.7, (len(POINTS), 2))
        x[8] += [12.0, 0.0]                      # the window's corner 12 px off in the frame
        params = C.solve(POINTS, x, CENTRE)
        errors = []
        for i in range(len(POINTS)):
            keep = [k for k in range(len(POINTS)) if k != i]
            loo = C.project(C.solve(POINTS[keep], x[keep], CENTRE, params), POINTS[i:i + 1], CENTRE)[0]
            errors.append(float(np.linalg.norm(loo - x[i])))
        self.assertEqual(int(np.argmax(errors)), 8)
        self.assertGreater(errors[8], 8.0)
        self.assertLess(sorted(errors)[-2], 6.0)

    def test_a_fixed_focal_length_is_kept(self):
        truth = camera(f=480.0)
        x = C.project(truth, POINTS[:7], CENTRE)
        params = C.solve(POINTS[:7], x, CENTRE, focal=480.0)
        self.assertEqual(params[0], 480.0)
        self.assertLess(np.abs(C.project(params, POINTS[:7], CENTRE) - x).max(), 0.05)


if __name__ == "__main__":
    unittest.main()
