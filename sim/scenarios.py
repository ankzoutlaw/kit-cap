"""Predefined scenarios that modify simulation behaviour."""


SCENARIOS = {
    "Normal": {
        "description": "Baseline operation - no anomalies.",
        "sensor_modifiers": {},
        "zone_rate_overrides": {},
    },
    "Thermal Hotspot": {
        "description": "Stressed zone overheats due to poor airflow.",
        "sensor_modifiers": {"temp_offset": 12.0},
        "zone_rate_overrides": {"stressed_zone": 0.06},
    },
    "Cooling Degradation": {
        "description": "CRAC/CRAH units lose efficiency over time.",
        "sensor_modifiers": {"cooling_penalty": 0.3, "temp_offset": 5.0},
        "zone_rate_overrides": {},
    },
    "Load Imbalance": {
        "description": "Most equipment concentrated in one zone - vibration spikes.",
        "sensor_modifiers": {"vibration_scale": 2.5},
        "zone_rate_overrides": {"stressed_zone": 0.04, "cool_zone": 0.002},
    },
    "Sensor Drift": {
        "description": "Temperature sensor drifts upward over time.",
        "sensor_modifiers": {"drift_rate": 0.3},
        "zone_rate_overrides": {},
    },
}


def apply_scenario(name, sensor_stream, hidden_state):
    """Configure a sensor stream and hidden state for a named scenario.

    Args:
        name: Key into SCENARIOS dict.
        sensor_stream: SensorStream instance to configure.
        hidden_state: HiddenState instance to configure.
    """
    scenario = SCENARIOS[name]

    # Reset sensor modifiers to defaults, then apply overrides
    sensor_stream.modifiers = {
        "temp_offset": 0.0,
        "vibration_scale": 1.0,
        "power_offset": 0.0,
        "cooling_penalty": 0.0,
        "drift_rate": 0.0,
    }
    sensor_stream._drift_accum = 0.0
    sensor_stream.modifiers.update(scenario["sensor_modifiers"])

    # Override zone risk rates if specified
    hidden_state.zone_rate_overrides = dict(scenario["zone_rate_overrides"])
