"""Load/equipment representation."""


class Load:
    """A single equipment rack or unit placed inside a data hall."""

    def __init__(self, id: str, weight_kg: float, x: float, y: float):
        """Create a load.

        Args:
            id: Unique identifier for this equipment.
            weight_kg: Weight in kilograms.
            x: X position in metres from the hall origin.
            y: Y position in metres from the hall origin.
        """
        self.id = id
        self.weight_kg = weight_kg
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Load({self.id!r}, {self.weight_kg}kg @ ({self.x}, {self.y}))"
