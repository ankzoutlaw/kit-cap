# Kit_Cap - Data Center Capacity Digital Twin

A minimal digital twin of a single data hall, built as a visual demo with Streamlit.

## What it does

- Models a 100m x 50m data hall with equipment placement, capacity tracking, and zone-based risk
- Runs a time-step simulation with hidden state (thermal stress, wear, per-zone risk)
- Generates mock sensor data (temperature, vibration, power, cooling efficiency)
- Blocks equipment placement in zones where hidden risk exceeds a threshold
- Five scenarios demonstrate different failure modes

## Scenarios

| Scenario | What happens |
|----------|-------------|
| Normal | Baseline - no anomalies |
| Thermal Hotspot | Stressed zone overheats, blocks placement faster |
| Cooling Degradation | CRAC/CRAH efficiency drops, temperature rises globally |
| Load Imbalance | Equipment concentrated in one zone, vibration spikes |
| Sensor Drift | Temperature sensor drifts upward over time |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run tests

```bash
python -m pytest tests/ -v
```

## Project structure

```
├── app.py               # Kit_Cap Streamlit dashboard
├── main.py              # CLI demo (no dependencies)
├── src/
│   ├── hall.py          # Data hall model with zones
│   ├── load.py          # Equipment load data class
│   └── headroom.py      # Capacity headroom calculator
├── sim/
│   ├── engine.py        # Simulation engine
│   ├── hidden.py        # Hidden state (thermal, wear, zone risk)
│   ├── sensors.py       # Mock sensor stream
│   └── scenarios.py     # Predefined scenario configs
├── data/
│   └── defaults.json    # Default data hall configuration
├── tests/
│   ├── test_hall.py     # Core model tests
│   └── test_sim.py      # Simulation tests
├── requirements.txt
└── PLAN.md
```
