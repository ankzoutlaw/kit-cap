# Kit_Cap - Build Plan

## Environment
- Python 3.10.9 | pip 23.3.1 | git 2.53.0
- Platform: Windows 11

## Architecture

### Concept
A digital twin of a **single data hall** in a data center facility. The simulation models:

- **Equipment placement** - racks and units placed at positions within the hall
- **Capacity headroom** - tracks remaining capacity vs. maximum, raises alerts
- **Hidden simulation state** - internal state (wear, thermal, drift) not directly
  visible to operators but influencing twin behaviour over time

### Module layout

```
claude-test/
├── app.py           # Kit_Cap Streamlit dashboard
├── main.py          # CLI demo entry point
├── src/
│   ├── hall.py      # Data hall model (dimensions, zones, capacity)
│   ├── load.py      # Equipment load representation
│   └── headroom.py  # Capacity headroom calculator
├── sim/
│   ├── engine.py    # Time-step loop
│   ├── hidden.py    # Hidden state (wear, thermal drift, zone risk)
│   ├── sensors.py   # Mock sensor stream
│   └── scenarios.py # Predefined scenario configs
├── data/
│   └── defaults.json
├── PLAN.md
├── requirements.txt
└── .gitignore
```

### Data flow

```
[Equipment input] --> Hall.place(load)
                        |
                        v
                  Headroom.check()  -->  alert if capacity < threshold
                        |
                        v
                  Sim.step()        -->  updates hidden state each tick
```

## Phases

### Phase 1 - Scaffold
- [x] Confirm toolchain
- [x] Create PLAN.md
- [x] Init git repo
- [x] Create project structure

### Phase 2 - Core model
- [x] Implement Hall, Load, Headroom classes
- [x] Zone-based risk with hidden state feedback
- [x] Unit tests

### Phase 3 - Simulation loop
- [x] Time-step engine with hidden state
- [x] Mock sensor stream
- [x] Scenario system (5 presets)

### Phase 4 - Dashboard
- [x] Kit_Cap Streamlit app
- [x] Red/white data center theme
- [x] KPI cards, hall map, sensor charts, rejection log
