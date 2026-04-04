"""Mock sensor stream - per-tick readings for the data hall."""

import random


class SensorReading:
    """One tick's worth of sensor data."""

    def __init__(self, temperature_c, vibration_mm_s, power_kw, cooling_efficiency):
        self.temperature_c = temperature_c
        self.vibration_mm_s = vibration_mm_s
        self.power_kw = power_kw
        self.cooling_efficiency = cooling_efficiency

    def as_dict(self):
        return {
            "temperature_c": round(self.temperature_c, 1),
            "vibration_mm_s": round(self.vibration_mm_s, 2),
            "power_kw": round(self.power_kw, 1),
            "cooling_efficiency": round(self.cooling_efficiency, 2),
        }


class SensorStream:
    """Generates mock sensor readings based on data hall state and modifiers.

    Modifiers allow scenarios to bias the readings (e.g. raise
    temperature baseline, degrade cooling).
    """

    def __init__(self):
        self.modifiers = {
            "temp_offset": 0.0,
            "vibration_scale": 1.0,
            "power_offset": 0.0,
            "cooling_penalty": 0.0,
            "drift_rate": 0.0,
        }
        self._drift_accum = 0.0

    def read(self, hall, hidden_state) -> SensorReading:
        """Generate one sensor reading for the current tick."""
        util = hall.utilization_pct() / 100  # 0-1
        thermal = hidden_state.thermal_stress

        self._drift_accum += self.modifiers["drift_rate"]

        temp = 18 + 30 * thermal + self.modifiers["temp_offset"] + self._drift_accum
        temp += random.gauss(0, 0.5)

        vibration = (0.5 + 2.0 * util) * self.modifiers["vibration_scale"]
        vibration += random.gauss(0, 0.1)
        vibration = max(0, vibration)

        power = 50 + 150 * util + self.modifiers["power_offset"]
        power += random.gauss(0, 2)

        cooling = max(0, min(1.0, 0.95 - 0.3 * thermal - self.modifiers["cooling_penalty"]))
        cooling += random.gauss(0, 0.02)
        cooling = max(0, min(1.0, cooling))

        return SensorReading(temp, vibration, power, cooling)
