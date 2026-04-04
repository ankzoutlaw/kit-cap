"""Kit_Cap - Data Center Digital Twin - CLI Demo."""

import json

from src.hall import Hall
from src.load import Load
from sim.engine import SimulationEngine


def load_defaults(path="data/defaults.json"):
    """Read data hall configuration from a JSON file."""
    with open(path) as f:
        return json.load(f)


def print_header():
    print(f"{'tick':>4}  {'util%':>6}  {'headroom%':>9}  "
          f"{'thermal':>7}  {'wear':>5}  "
          f"{'cool':>5}  {'normal':>6}  {'stressed':>8}")
    print("-" * 70)


def print_snap(snap):
    zr = snap["zone_risk"]
    print(f"{snap['tick']:4d}  "
          f"{snap['utilization_pct']:6.1f}  "
          f"{snap['headroom_pct']:9.1f}  "
          f"{snap['thermal_stress']:7.3f}  "
          f"{snap['wear_level']:5.3f}  "
          f"{zr['cool_zone']:5.3f}  "
          f"{zr['normal_zone']:6.3f}  "
          f"{zr['stressed_zone']:8.3f}")


def main():
    # --- Setup ---
    cfg = load_defaults()
    hall = Hall(**cfg["hall"])
    engine = SimulationEngine(hall)

    print(f"Data Hall: {hall.length_m}m x {hall.width_m}m, "
          f"max {hall.max_capacity_kg:,.0f} kg")
    print(f"Zones: cool [0-33m], normal [33-66m], stressed [66-100m]\n")

    # --- Place initial equipment ---
    loads = [
        Load("rack-A",   80_000, x=10, y=5),   # cool zone
        Load("rack-B",  120_000, x=50, y=20),   # normal zone
        Load("rack-C",   95_000, x=80, y=10),   # stressed zone
        Load("rack-D",   60_000, x=85, y=40),   # stressed zone
    ]

    print("--- Initial placement ---")
    for load in loads:
        zone = hall.zone_for(load.x)
        ok = hall.place(load, engine.hidden_state)
        status = "placed" if ok else "REJECTED"
        print(f"  {status}: {load}  [{zone}]")

    # --- Run simulation to build up zone risk ---
    print("\n--- Simulation (21 ticks) ---")
    print_header()
    for _ in range(21):
        snap = engine.step()
        print_snap(snap)

    # --- Attempt late placement into stressed zone ---
    print("\n--- Late placement attempt ---")
    late_load = Load("rack-X", 20_000, x=90, y=25)  # stressed zone
    zone = hall.zone_for(late_load.x)
    risk = engine.hidden_state.zone_risk[zone]
    ok = hall.place(late_load, engine.hidden_state)
    status = "placed" if ok else "REJECTED"
    print(f"  {status}: {late_load}  [{zone}, risk={risk:.3f}]")

    if not ok:
        print(f"  -> Zone '{zone}' risk ({risk:.3f}) exceeds threshold (0.7)")

    # --- Try same equipment in cool zone instead ---
    fallback = Load("rack-X", 20_000, x=5, y=25)  # cool zone
    zone2 = hall.zone_for(fallback.x)
    risk2 = engine.hidden_state.zone_risk[zone2]
    ok2 = hall.place(fallback, engine.hidden_state)
    status2 = "placed" if ok2 else "REJECTED"
    print(f"  {status2}: {fallback}  [{zone2}, risk={risk2:.3f}]")

    if ok2:
        print(f"  -> Redirected to '{zone2}' (risk {risk2:.3f}, within threshold)")


if __name__ == "__main__":
    main()
