# Kit_Cap
### Data Center Capacity Digital Twin

> **Safe capacity \u2260 available capacity.**
> Kit_Cap models the hidden thermal state of a data hall and uses it to block unsafe equipment placements \u2014 even when raw headroom says there\u2019s room.

![Architecture](architecture.png)

---

## What it solves

Data center capacity tools answer *how much space is left*.
Kit_Cap answers *where it is safe to place equipment right now* \u2014 by running a live simulation of thermal stress, zone wear, and sensor drift beneath the dashboard.

---

## Live demo

```bash
git clone <repo-url>
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`, pick a scenario, run the simulation.

---

## How it works

| Layer | What it does |
|-------|-------------|
| **Core model** | Hall with 3 thermal zones, per-rack load placement, capacity headroom |
| **Hidden state** | Per-zone risk accumulates silently each tick based on utilization and zone position |
| **Feedback loop** | When zone risk \u2265 0.7, `can_place()` rejects new equipment regardless of capacity |
| **Prediction** | Linear extrapolation of risk gradient \u2192 *"~8 ticks to unsafe state"* |
| **Recommendation** | On rejection, surfaces the safest alternative zone |
| **Sensor stream** | Mock temperature, vibration, power, and cooling readings per tick |
| **Scenarios** | 5 presets (Thermal Hotspot, Cooling Degradation, Load Imbalance, Sensor Drift, Normal) |

---

## Scenarios

| Scenario | Demonstrates |
|----------|-------------|
| Normal | Baseline degradation over time |
| Thermal Hotspot | Zone risk spikes, placement blocked in stressed zone |
| Cooling Degradation | CRAC/CRAH efficiency loss, rising global temperature |
| Load Imbalance | Uneven weight distribution, vibration anomaly |
| Sensor Drift | Temperature reading drifts \u2014 model vs sensor divergence |

---

## Stack

- **Python 3.10** \u2014 zero heavy dependencies in the simulation core
- **Streamlit** \u2014 interactive dashboard with scenario controls
- **Matplotlib** \u2014 top-down hall map with risk colour gradients
- **Pandas** \u2014 rejection log and zone risk table
- **pytest** \u2014 17 unit tests covering model, engine, sensors, scenarios

---

## Key engineering decisions

**Hidden state as a first-class citizen.**
Most capacity tools are stateless \u2014 they answer point-in-time queries. Kit_Cap maintains internal state that evolves each tick. This is what makes it a *twin* rather than a dashboard.

**Placement gating via hidden state.**
`Hall.can_place(load, hidden_state)` is the core interface. Passing `hidden_state` is optional \u2014 the model degrades gracefully to pure capacity checking without it.

**Separation of concerns.**
`Hall` manages physical constraints. `HiddenState` manages thermal degradation. `Headroom` manages capacity monitoring. `SimulationEngine` composes them. Each is independently testable.

**Predictive output.**
The \u201cTime to Unsafe State\u201d KPI extrapolates the current risk gradient linearly. Simple math, but it shifts the system from reactive monitoring to forward-looking decision support.

---

## Project structure

```
kit_cap/
\u251c\u2500\u2500 app.py               # Streamlit dashboard
\u251c\u2500\u2500 main.py              # CLI demo (no dependencies)
\u251c\u2500\u2500 src/
\u2502   \u251c\u2500\u2500 hall.py          # Data hall model + zone logic
\u2502   \u251c\u2500\u2500 load.py          # Equipment data class
\u2502   \u2514\u2500\u2500 headroom.py      # Capacity headroom calculator
\u251c\u2500\u2500 sim/
\u2502   \u251c\u2500\u2500 engine.py        # Time-step simulation engine
\u2502   \u251c\u2500\u2500 hidden.py        # Hidden state (thermal, wear, zone risk)
\u2502   \u251c\u2500\u2500 sensors.py       # Mock sensor stream
\u2502   \u2514\u2500\u2500 scenarios.py     # Scenario configuration
\u251c\u2500\u2500 tests/               # 17 pytest unit tests
\u251c\u2500\u2500 architecture.png     # System architecture diagram
\u2514\u2500\u2500 requirements.txt
```

---

## Tests

```bash
python -m pytest tests/ -v
# 17 passed
```

---

*Built by Ankit Tripathi \u2014 contact.ankit.tripathi@gmail.com*
