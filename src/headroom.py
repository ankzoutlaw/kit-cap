"""Capacity headroom calculator."""

DEFAULT_ALERT_THRESHOLD_PCT = 10.0


class Headroom:
    """Calculates how much spare capacity a data hall has."""

    def __init__(self, hall, alert_threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT):
        """Create a headroom calculator for a data hall.

        Args:
            hall: A Hall instance to monitor.
            alert_threshold_pct: Raise an alert when headroom drops
                                 below this percentage (default 10%).
        """
        self.hall = hall
        self.alert_threshold_pct = alert_threshold_pct

    def remaining_capacity_kg(self) -> float:
        """Return how many kg of capacity remain."""
        return self.hall.max_capacity_kg - self.hall.current_capacity()

    def headroom_pct(self) -> float:
        """Return remaining capacity as a percentage (0-100)."""
        if self.hall.max_capacity_kg == 0:
            return 0.0
        return (self.remaining_capacity_kg() / self.hall.max_capacity_kg) * 100

    def alert(self) -> bool:
        """Return True if headroom is below the alert threshold."""
        return self.headroom_pct() < self.alert_threshold_pct
