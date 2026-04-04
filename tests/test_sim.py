"""Tests for simulation engine, hidden state, and sensors."""

import unittest

from src.hall import Hall
from src.load import Load
from sim.hidden import HiddenState
from sim.engine import SimulationEngine
from sim.sensors import SensorStream
from sim.scenarios import SCENARIOS, apply_scenario


class TestHiddenState(unittest.TestCase):

    def test_wear_increases(self):
        hall = Hall(100, 50, 1000)
        hs = HiddenState()
        hs.update(hall)
        self.assertGreater(hs.wear_level, 0)

    def test_thermal_rises_with_load(self):
        hall = Hall(100, 50, 1000)
        hall.place(Load("a", 900, 50, 25))
        hs = HiddenState()
        for _ in range(10):
            hs.update(hall)
        self.assertGreater(hs.thermal_stress, 0.05)

    def test_zone_risk_respects_overrides(self):
        hall = Hall(100, 50, 1000)
        hall.place(Load("a", 500, 80, 25))  # stressed zone
        hs = HiddenState()
        hs.zone_rate_overrides = {"stressed_zone": 0.1}
        hs.update(hall)
        self.assertGreater(hs.zone_risk["stressed_zone"], 0.1)


class TestEngine(unittest.TestCase):

    def test_step_returns_snapshot(self):
        hall = Hall(100, 50, 1000)
        engine = SimulationEngine(hall)
        snap = engine.step()
        self.assertIn("tick", snap)
        self.assertIn("sensors", snap)
        self.assertEqual(snap["tick"], 1)

    def test_try_place_tracks_rejections(self):
        hall = Hall(100, 50, 1000)
        engine = SimulationEngine(hall)
        engine.try_place(Load("a", 2000, 50, 25))  # over capacity
        self.assertEqual(engine.rejected_count, 1)

    def test_reset(self):
        hall = Hall(100, 50, 1000)
        engine = SimulationEngine(hall)
        engine.try_place(Load("a", 500, 50, 25))
        engine.step()
        engine.reset()
        self.assertEqual(engine.tick, 0)
        self.assertEqual(len(engine.hall.placed_loads), 0)


class TestSensors(unittest.TestCase):

    def test_reading_keys(self):
        hall = Hall(100, 50, 1000)
        hs = HiddenState()
        stream = SensorStream()
        reading = stream.read(hall, hs)
        d = reading.as_dict()
        self.assertIn("temperature_c", d)
        self.assertIn("vibration_mm_s", d)
        self.assertIn("power_kw", d)
        self.assertIn("cooling_efficiency", d)


class TestScenarios(unittest.TestCase):

    def test_all_scenarios_apply(self):
        for name in SCENARIOS:
            stream = SensorStream()
            hs = HiddenState()
            apply_scenario(name, stream, hs)


if __name__ == "__main__":
    unittest.main()
