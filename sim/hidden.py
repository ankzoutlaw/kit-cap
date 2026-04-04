"""Hidden simulation state - wear, thermal drift, zone risk.

These values are not directly visible to operators but influence
the twin's behaviour over time.
"""


class HiddenState:
    """Internal state that degrades silently as the data hall is used."""

    def __init__(self):
        self.thermal_stress = 0.0  # 0 = cool, 1 = critical
        self.wear_level = 0.0     # 0 = new, 1 = end-of-life
        self.zone_risk = {
            "cool_zone": 0.0,
            "normal_zone": 0.0,
            "stressed_zone": 0.0,
        }
        self.zone_rate_overrides = {}  # scenario can override per-zone rates

    def update(self, hall):
        """Advance hidden state by one tick.

        - Thermal stress rises proportionally to utilization.
        - Wear increases by a small fixed amount every tick.
        - Zone risk increases per zone based on how much equipment sits there.
          The stressed_zone accumulates risk faster when utilization is high.
        """
        utilization = hall.utilization_pct() / 100  # 0-1

        # --- Global thermal & wear ---
        heat_gain = 0.02 * utilization
        heat_loss = 0.005
        self.thermal_stress = min(1.0, max(0.0, self.thermal_stress + heat_gain - heat_loss))
        self.wear_level = min(1.0, self.wear_level + 0.005)

        # --- Per-zone risk ---
        zone_loads = {"cool_zone": 0, "normal_zone": 0, "stressed_zone": 0}
        for load in hall.placed_loads:
            zone = hall.zone_for(load.x)
            zone_loads[zone] += 1

        # Risk rates: stressed zone heats up fastest, cool zone slowest
        rate = {"cool_zone": 0.005, "normal_zone": 0.01, "stressed_zone": 0.02}
        rate.update(self.zone_rate_overrides)  # scenario overrides

        for zone in self.zone_risk:
            if zone_loads[zone] > 0:
                gain = rate[zone] * (1 + utilization)
            else:
                gain = -0.005
            self.zone_risk[zone] = min(1.0, max(0.0, self.zone_risk[zone] + gain))

    def __repr__(self):
        risks = ", ".join(f"{z}={v:.3f}" for z, v in self.zone_risk.items())
        return (f"HiddenState(thermal={self.thermal_stress:.3f}, "
                f"wear={self.wear_level:.3f}, {risks})")
