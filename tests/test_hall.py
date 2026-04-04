"""Tests for Hall and Load."""

import unittest

from src.hall import Hall
from src.load import Load
from sim.hidden import HiddenState


class TestLoad(unittest.TestCase):

    def test_attributes(self):
        load = Load("x", 100, 5, 10)
        self.assertEqual(load.id, "x")
        self.assertEqual(load.weight_kg, 100)
        self.assertEqual(load.x, 5)
        self.assertEqual(load.y, 10)


class TestHall(unittest.TestCase):

    def setUp(self):
        self.hall = Hall(100, 50, 1000)

    def test_place_within_bounds(self):
        load = Load("a", 500, 50, 25)
        self.assertTrue(self.hall.place(load))
        self.assertEqual(len(self.hall.placed_loads), 1)

    def test_reject_out_of_bounds(self):
        load = Load("a", 100, 200, 25)
        self.assertFalse(self.hall.place(load))

    def test_reject_over_capacity(self):
        load = Load("a", 1500, 50, 25)
        self.assertFalse(self.hall.place(load))

    def test_utilization(self):
        self.hall.place(Load("a", 500, 10, 10))
        self.assertAlmostEqual(self.hall.utilization_pct(), 50.0)

    def test_zone_mapping(self):
        self.assertEqual(self.hall.zone_for(10), "cool_zone")
        self.assertEqual(self.hall.zone_for(50), "normal_zone")
        self.assertEqual(self.hall.zone_for(80), "stressed_zone")

    def test_reject_high_zone_risk(self):
        hs = HiddenState()
        hs.zone_risk["stressed_zone"] = 0.8
        load = Load("a", 100, 80, 25)
        self.assertFalse(self.hall.can_place(load, hs))

    def test_allow_low_zone_risk(self):
        hs = HiddenState()
        hs.zone_risk["cool_zone"] = 0.1
        load = Load("a", 100, 10, 25)
        self.assertTrue(self.hall.can_place(load, hs))


class TestHeadroom(unittest.TestCase):

    def test_headroom(self):
        from src.headroom import Headroom
        hall = Hall(100, 50, 1000)
        hall.place(Load("a", 900, 10, 10))
        hr = Headroom(hall, alert_threshold_pct=15)
        self.assertAlmostEqual(hr.remaining_capacity_kg(), 100)
        self.assertAlmostEqual(hr.headroom_pct(), 10.0)
        self.assertTrue(hr.alert())


if __name__ == "__main__":
    unittest.main()
