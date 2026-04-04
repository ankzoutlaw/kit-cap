"""Kit_Cap - Data Center Digital Twin - Streamlit Dashboard."""

import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

matplotlib.rcParams["font.family"] = "DejaVu Sans"

from src.hall import Hall, ZONES, ZONE_RISK_THRESHOLD
from src.load import Load
from sim.engine import SimulationEngine
from sim.scenarios import SCENARIOS, apply_scenario

# ---------------------------------------------------------------------------
# Brand colors
# ---------------------------------------------------------------------------
RED = "#ED1C24"
DARK_RED = "#B71C1C"
DARK_GREY = "#333333"
LIGHT_GREY = "#F5F5F5"


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def init_state():
    """Initialise session state on first run."""
    if "engine" not in st.session_state:
        hall = Hall(length_m=100, width_m=50, max_capacity_kg=500_000)
        engine = SimulationEngine(hall)
        st.session_state.engine = engine
        st.session_state.history = []
        st.session_state.scenario = "Normal"
        st.session_state.has_run = False
        st.session_state.rejection_log = []


def reset_sim(scenario_name):
    """Reset everything and apply a scenario."""
    engine = st.session_state.engine
    engine.reset()
    apply_scenario(scenario_name, engine.sensors, engine.hidden_state)
    st.session_state.history = []
    st.session_state.scenario = scenario_name
    st.session_state.has_run = False
    st.session_state.rejection_log = []


# ---------------------------------------------------------------------------
# Default loads per scenario
# ---------------------------------------------------------------------------

DEFAULT_LOADS = [
    Load("rack-A",  80_000, x=10, y=5),
    Load("rack-B", 120_000, x=50, y=20),
    Load("rack-C",  95_000, x=80, y=10),
    Load("rack-D",  60_000, x=85, y=40),
]

IMBALANCE_LOADS = [
    Load("rack-H1", 130_000, x=75, y=10),
    Load("rack-H2", 120_000, x=80, y=30),
    Load("rack-H3", 100_000, x=90, y=20),
    Load("rack-L1",  10_000, x=10, y=25),
]


def get_loads(scenario):
    if scenario == "Load Imbalance":
        return IMBALANCE_LOADS
    return DEFAULT_LOADS


def _predict_ticks_to_unsafe(history):
    """Estimate ticks until the hottest zone crosses the risk threshold.

    Uses the last two snapshots to compute the risk rate of the fastest-
    rising zone, then linearly extrapolates to ZONE_RISK_THRESHOLD.
    Returns None if no zone is rising or already all blocked.
    """
    if len(history) < 2:
        return None

    prev = history[-2]["zone_risk"]
    curr = history[-1]["zone_risk"]

    best_ticks = None
    for zone in curr:
        risk = curr[zone]
        if risk >= ZONE_RISK_THRESHOLD:
            continue  # already blocked
        delta = risk - prev[zone]
        if delta <= 0:
            continue  # not rising
        remaining = ZONE_RISK_THRESHOLD - risk
        ticks = remaining / delta
        if best_ticks is None or ticks < best_ticks:
            best_ticks = ticks

    return round(best_ticks) if best_ticks is not None else None


def _safest_zone(hidden_state):
    """Return the zone name with the lowest current risk."""
    return min(hidden_state.zone_risk, key=hidden_state.zone_risk.get)


def try_place_logged(engine, load):
    """Place equipment and log the reason if rejected."""
    hall = engine.hall
    hs = engine.hidden_state
    zone = hall.zone_for(load.x)
    risk = hs.zone_risk[zone]

    ok = engine.try_place(load)
    if not ok:
        in_bounds = 0 <= load.x <= hall.length_m and 0 <= load.y <= hall.width_m
        within_cap = (hall.current_capacity() + load.weight_kg) <= hall.max_capacity_kg
        if not in_bounds:
            reason = "Out of bounds"
            recommendation = ""
        elif not within_cap:
            reason = "Exceeds hall capacity"
            recommendation = ""
        else:
            reason = "Placement blocked: zone thermal risk exceeds safe threshold"
            best = _safest_zone(hs)
            best_risk = hs.zone_risk[best]
            best_label = best.replace("_", " ")
            recommendation = f"Recommended: place in {best_label} (risk {best_risk:.2f})"

        st.session_state.rejection_log.append({
            "Equipment": load.id,
            "Weight (kg)": f"{load.weight_kg:,.0f}",
            "Zone": zone.replace("_", " ").title(),
            "Risk": f"{risk:.2f}",
            "Reason": reason,
            "Recommendation": recommendation,
        })
    return ok


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

ZONE_COLORS_BASE = {
    "cool_zone": (0.85, 0.92, 0.98),       # light blue-grey
    "normal_zone": (0.95, 0.95, 0.95),      # near-white
    "stressed_zone": (1.0, 0.88, 0.88),     # light red tint
}

ZONE_LABELS = {
    "cool_zone": "Cool Zone\n(0\u201333m)",
    "normal_zone": "Normal Zone\n(33\u201366m)",
    "stressed_zone": "Stressed Zone\n(66\u2013100m)",
}


def lerp_color(base, hot, t):
    """Blend base toward hot (red) by factor t (0-1)."""
    return tuple(b + (h - b) * t for b, h in zip(base, hot))


def draw_hall(hall, hidden_state):
    """Return a matplotlib figure showing the top-down data hall view."""
    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    third = hall.length_m / 3

    hot = (0.93, 0.11, 0.14)  # Kit_Cap red
    zone_names = list(ZONES)

    for i, zone in enumerate(zone_names):
        risk = hidden_state.zone_risk[zone]
        color = lerp_color(ZONE_COLORS_BASE[zone], hot, risk)
        rect = patches.Rectangle(
            (i * third, 0), third, hall.width_m,
            facecolor=color, edgecolor="#999999", linewidth=1.5,
        )
        ax.add_patch(rect)
        label = ZONE_LABELS[zone]
        status = "  [BLOCKED]" if risk >= ZONE_RISK_THRESHOLD else ""
        ax.text(
            i * third + third / 2, hall.width_m + 2.5,
            f"{label}\nrisk {risk:.2f}{status}",
            ha="center", va="bottom", fontsize=8, weight="bold",
            color=DARK_RED if risk >= ZONE_RISK_THRESHOLD else DARK_GREY,
        )

    # Draw equipment
    for load in hall.placed_loads:
        ax.plot(load.x, load.y, "s", color=DARK_RED, markersize=8)
        ax.annotate(
            load.id, (load.x, load.y),
            textcoords="offset points", xytext=(5, 5),
            fontsize=6, color=DARK_GREY,
        )

    ax.set_xlim(-2, hall.length_m + 2)
    ax.set_ylim(-5, hall.width_m + 14)
    ax.set_xlabel("x (m)", color=DARK_GREY)
    ax.set_ylabel("y (m)", color=DARK_GREY)
    ax.set_title("Data Hall - Top-Down View", fontsize=11, weight="bold", color=DARK_GREY)
    ax.set_aspect("equal")
    ax.tick_params(colors=DARK_GREY)
    for spine in ax.spines.values():
        spine.set_color("#CCCCCC")
    plt.tight_layout()
    return fig


def draw_sensors(history):
    """Return a matplotlib figure with 4 sensor subplots."""
    df = pd.DataFrame([h["sensors"] for h in history])
    df["tick"] = [h["tick"] for h in history]

    fig, axes = plt.subplots(2, 2, figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    metrics = [
        ("temperature_c", "Temperature (C)", RED),
        ("vibration_mm_s", "Vibration (mm/s)", "#FF6F00"),
        ("power_kw", "Power (kW)", "#455A64"),
        ("cooling_efficiency", "Cooling Eff.", "#2E7D32"),
    ]

    for ax, (col, label, color) in zip(axes.flat, metrics):
        ax.set_facecolor("white")
        ax.plot(df["tick"], df[col], color=color, linewidth=1.2)
        ax.set_ylabel(label, fontsize=8, color=DARK_GREY)
        ax.set_xlabel("tick", fontsize=8, color=DARK_GREY)
        ax.tick_params(labelsize=7, colors=DARK_GREY)
        ax.grid(True, alpha=0.2, color="#CCCCCC")
        for spine in ax.spines.values():
            spine.set_color("#CCCCCC")

    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stSidebar"] {
        background-color: #B71C1C;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] button {
        background-color: #1A1A1A !important;
        color: #FFFFFF !important;
        border: 1px solid #444444 !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #333333 !important;
        border-color: #ED1C24 !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #ED1C24 !important;
        border: 1px solid #ED1C24 !important;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #FF3333 !important;
    }
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stSlider span {
        color: #FFFFFF !important;
    }
    [data-testid="stMetric"] {
        background-color: #F5F5F5;
        border-left: 4px solid #ED1C24;
        padding: 12px 16px;
        border-radius: 4px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #666666;
    }
    [data-testid="stMetricValue"] {
        color: #333333;
        font-weight: 700;
    }
</style>
"""


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Kit_Cap", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # --- Header ---
    st.markdown(
        f'<h1 style="color:{RED}; margin-bottom:0;">Kit_Cap</h1>'
        f'<p style="color:{DARK_GREY}; margin-top:0; font-size:1.1rem;">'
        f'Data Center Capacity Digital Twin</p>',
        unsafe_allow_html=True,
    )

    # --- What this demonstrates ---
    with st.expander("What this demonstrates", expanded=False):
        st.markdown(
            "**Safe capacity \u2260 available capacity.**\n\n"
            "Kit_Cap models a single **data hall** as a digital twin "
            "- a live simulation that tracks more than what operators can see.\n\n"
            "- **Visible state:** utilization, headroom, sensor readings\n"
            "- **Hidden state:** per-zone thermal risk, structural wear\n"
            "- **Feedback loop:** when hidden risk in a zone exceeds a safety "
            "threshold, the system **blocks new equipment placements** in that zone - "
            "even if raw capacity says there is room\n\n"
            "Select a scenario from the sidebar to see how different failure "
            "modes (hotspots, cooling loss, sensor drift) affect placement "
            "decisions over time."
        )

    init_state()
    engine = st.session_state.engine

    # --- Sidebar: scenario selector ---
    st.sidebar.markdown(
        '<h2 style="margin-bottom:0.5rem;">Scenarios</h2>',
        unsafe_allow_html=True,
    )
    for name, info in SCENARIOS.items():
        if st.sidebar.button(name, use_container_width=True):
            reset_sim(name)
            st.rerun()
    st.sidebar.markdown(f"**Active:** {st.session_state.scenario}")
    st.sidebar.caption(SCENARIOS[st.session_state.scenario]["description"])

    # --- Sidebar: simulation controls ---
    st.sidebar.divider()
    ticks = st.sidebar.slider("Ticks to simulate", 5, 60, 30)

    if st.sidebar.button("Run Simulation", type="primary", use_container_width=True):
        reset_sim(st.session_state.scenario)
        engine = st.session_state.engine

        # Place equipment
        for load in get_loads(st.session_state.scenario):
            try_place_logged(engine, load)

        # Run ticks
        for _ in range(ticks):
            snap = engine.step()
            st.session_state.history.append(snap)

        # Try a late placement into stressed zone
        late = Load("rack-X", 20_000, x=90, y=25)
        try_place_logged(engine, late)

        st.session_state.has_run = True
        st.rerun()

    if not st.session_state.has_run:
        st.info("Select a scenario and click **Run Simulation** to start.")
        return

    history = st.session_state.history
    latest = history[-1]

    # --- KPI cards ---
    predicted = _predict_ticks_to_unsafe(history)
    predicted_label = f"~{predicted} ticks" if predicted is not None else "N/A"

    cols = st.columns(6)
    cols[0].metric("Utilization", f"{latest['utilization_pct']:.1f}%")
    cols[1].metric("Headroom", f"{latest['headroom_pct']:.1f}%")
    cols[2].metric("Thermal Stress", f"{latest['thermal_stress']:.3f}")
    cols[3].metric("Wear Level", f"{latest['wear_level']:.3f}")
    cols[4].metric("Unsafe Placements Prevented", str(latest["rejected_count"]))
    cols[5].metric("Time to Unsafe State", predicted_label)

    # --- Hall view ---
    st.subheader("Data Hall Layout & Zone Risk")
    fig_hall = draw_hall(engine.hall, engine.hidden_state)
    st.pyplot(fig_hall)
    plt.close(fig_hall)

    # --- Rejection log ---
    if st.session_state.rejection_log:
        st.subheader("Rejected Placements")
        st.dataframe(
            pd.DataFrame(st.session_state.rejection_log),
            use_container_width=True,
            hide_index=True,
        )

    # --- Sensor stream ---
    st.subheader("Sensor Stream")
    fig_sensors = draw_sensors(history)
    st.pyplot(fig_sensors)
    plt.close(fig_sensors)

    # --- Zone risk table ---
    st.subheader("Zone Risk Detail")
    zr = latest["zone_risk"]
    risk_df = pd.DataFrame([
        {
            "Zone": ZONE_LABELS[z].split("\n")[0],
            "Range": ZONE_LABELS[z].split("\n")[1],
            "Risk": f"{v:.3f}",
            "Status": "BLOCKED" if v >= ZONE_RISK_THRESHOLD else "OK",
        }
        for z, v in zr.items()
    ])
    st.dataframe(risk_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
