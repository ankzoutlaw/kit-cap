"""Data hall model - dimensions, zones, capacity."""

# Zone names, split evenly along the x-axis
ZONES = ("cool_zone", "normal_zone", "stressed_zone")

# Maximum zone risk before placement is blocked
ZONE_RISK_THRESHOLD = 0.7


class Hall:
    """A single data hall in a data center facility."""

    def __init__(self, length_m: float, width_m: float, max_capacity_kg: float):
        """Create a data hall.

        Args:
            length_m: Hall length in metres (x-axis).
            width_m: Hall width in metres (y-axis).
            max_capacity_kg: Maximum total equipment weight the hall can hold.
        """
        self.length_m = length_m
        self.width_m = width_m
        self.max_capacity_kg = max_capacity_kg
        self.placed_loads = []

    def zone_for(self, x: float) -> str:
        """Return the zone name for a given x position.

        The hall is split into three equal segments along the x-axis:
          0 .. 1/3  -> cool_zone
          1/3 .. 2/3 -> normal_zone
          2/3 .. 1   -> stressed_zone
        """
        frac = x / self.length_m
        if frac < 1 / 3:
            return "cool_zone"
        elif frac < 2 / 3:
            return "normal_zone"
        else:
            return "stressed_zone"

    def current_capacity(self) -> float:
        """Return the total weight of all placed equipment in kg."""
        return sum(load.weight_kg for load in self.placed_loads)

    def utilization_pct(self) -> float:
        """Return capacity utilization as a percentage (0-100)."""
        if self.max_capacity_kg == 0:
            return 0.0
        return (self.current_capacity() / self.max_capacity_kg) * 100

    def can_place(self, load, hidden_state=None) -> bool:
        """Check whether equipment fits within bounds, capacity, and zone risk.

        Args:
            load: The Load to check.
            hidden_state: Optional HiddenState. If provided, placement is
                          rejected when the target zone's risk exceeds
                          ZONE_RISK_THRESHOLD.

        Returns True if the equipment can be placed.
        """
        in_bounds = 0 <= load.x <= self.length_m and 0 <= load.y <= self.width_m
        within_capacity = (self.current_capacity() + load.weight_kg) <= self.max_capacity_kg

        if not (in_bounds and within_capacity):
            return False

        if hidden_state is not None:
            zone = self.zone_for(load.x)
            if hidden_state.zone_risk[zone] >= ZONE_RISK_THRESHOLD:
                return False

        return True

    def place(self, load, hidden_state=None) -> bool:
        """Place equipment in the data hall.

        Args:
            load: The Load to place.
            hidden_state: Optional HiddenState for zone-risk checks.

        Returns True if placed successfully, False otherwise.
        """
        if not self.can_place(load, hidden_state):
            return False
        self.placed_loads.append(load)
        return True
