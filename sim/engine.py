"""Simulation engine - time-step loop."""

from sim.hidden import HiddenState
from sim.sensors import SensorStream
from src.headroom import Headroom


class SimulationEngine:
    """Drives the digital twin forward one step at a time."""

    def __init__(self, hall, alert_threshold_pct=10.0):
        """Create an engine bound to a data hall.

        Args:
            hall: The Hall instance to simulate.
            alert_threshold_pct: Headroom alert threshold.
        """
        self.hall = hall
        self.hidden_state = HiddenState()
        self.headroom = Headroom(hall, alert_threshold_pct)
        self.sensors = SensorStream()
        self.tick = 0
        self.rejected_count = 0

    def step(self) -> dict:
        """Advance the simulation by one tick and return a snapshot."""
        self.hidden_state.update(self.hall)
        reading = self.sensors.read(self.hall, self.hidden_state)
        self.tick += 1

        return {
            "tick": self.tick,
            "loads": len(self.hall.placed_loads),
            "utilization_pct": round(self.hall.utilization_pct(), 2),
            "remaining_kg": round(self.headroom.remaining_capacity_kg(), 2),
            "headroom_pct": round(self.headroom.headroom_pct(), 2),
            "headroom_alert": self.headroom.alert(),
            "thermal_stress": round(self.hidden_state.thermal_stress, 3),
            "wear_level": round(self.hidden_state.wear_level, 3),
            "zone_risk": {z: round(v, 3) for z, v in self.hidden_state.zone_risk.items()},
            "sensors": reading.as_dict(),
            "rejected_count": self.rejected_count,
        }

    def try_place(self, load) -> bool:
        """Attempt to place equipment, tracking rejections."""
        ok = self.hall.place(load, self.hidden_state)
        if not ok:
            self.rejected_count += 1
        return ok

    def reset(self):
        """Reset engine state for a new scenario run."""
        self.hall.placed_loads.clear()
        self.hidden_state = HiddenState()
        self.sensors = SensorStream()
        self.tick = 0
        self.rejected_count = 0
