"""Kit_Cap - Data Center Digital Twin - Streamlit Dashboard."""

import time
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
# M3 Expressive Color Tokens
# ---------------------------------------------------------------------------
PRIMARY = "#006A6A"
ON_PRIMARY = "#FFFFFF"
PRIMARY_CONTAINER = "#6FF7F6"
ON_PRIMARY_CONTAINER = "#002020"
SECONDARY = "#4A6363"
ON_SECONDARY = "#FFFFFF"
SECONDARY_CONTAINER = "#CCE8E7"
ON_SECONDARY_CONTAINER = "#051F1F"
TERTIARY = "#4B607C"
ON_TERTIARY = "#FFFFFF"
TERTIARY_CONTAINER = "#D3E4FF"
ON_TERTIARY_CONTAINER = "#041C35"
ERROR = "#BA1A1A"
ON_ERROR = "#FFFFFF"
ERROR_CONTAINER = "#FFEDEA"
SURFACE = "#F5FAFA"
ON_SURFACE = "#171D1D"
SURFACE_CONTAINER = "#E0E8E8"
SURFACE_CONTAINER_HIGH = "#D5DEDE"
OUTLINE = "#6F7979"
OUTLINE_VARIANT = "#BEC9C8"
GREEN = "#2E7D32"
AMBER = "#E65100"

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

ZONE_DISPLAY = {
    "cool_zone": "Cool Zone",
    "normal_zone": "Normal Zone",
    "stressed_zone": "Stressed Zone",
}

ZONE_RANGE = {
    "cool_zone": "0\u201333 m",
    "normal_zone": "33\u201366 m",
    "stressed_zone": "66\u2013100 m",
}


def get_loads(scenario):
    if scenario == "Load Imbalance":
        return IMBALANCE_LOADS
    return DEFAULT_LOADS


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def init_simulation_state():
    """Initialise session state on first run only."""
    if "engine" not in st.session_state:
        st.session_state.scenario = "Normal"
        st.session_state.auto_run = False
        _build_engine("Normal")


def _build_engine(scenario_name):
    """Create a fresh engine, place loads, and take tick-0 snapshot."""
    hall = Hall(length_m=100, width_m=50, max_capacity_kg=500_000)
    engine = SimulationEngine(hall)
    apply_scenario(scenario_name, engine.sensors, engine.hidden_state)

    st.session_state.engine = engine
    st.session_state.history = []
    st.session_state.rejection_log = []
    st.session_state.last_placement = None
    st.session_state.demo_log = []
    st.session_state.demo_narrative = ""
    st.session_state.placement_status_msg = ""

    # Place initial equipment
    for load in get_loads(scenario_name):
        _try_place_logged(engine, load)

    # Record tick-0 snapshot so the dashboard has something to show
    snap = engine.step()
    record_history(snap)


def reset_simulation():
    """Reset everything for the current scenario."""
    _build_engine(st.session_state.scenario)
    st.session_state.auto_run = False


def step_simulation(n_steps=1):
    """Advance the simulation by *n_steps* ticks and record each snapshot."""
    engine = st.session_state.engine
    st.session_state.placement_status_msg = ""

    for _ in range(n_steps):
        snap = engine.step()
        record_history(snap)


def record_history(snapshot):
    """Append a snapshot to the history list."""
    st.session_state.history.append(snapshot)


def get_current_snapshot():
    """Recompute a live snapshot from current engine state without advancing tick.

    This reflects placement mutations that happened between ticks —
    utilization, headroom, and load count update immediately.
    Thermal stress and zone risk remain at their last-ticked values
    and will evolve on the next simulation step.
    """
    engine = st.session_state.engine
    hall = engine.hall
    hs = engine.hidden_state
    headroom = engine.headroom

    return {
        "tick": engine.tick,
        "loads": len(hall.placed_loads),
        "utilization_pct": round(hall.utilization_pct(), 2),
        "remaining_kg": round(headroom.remaining_capacity_kg(), 2),
        "headroom_pct": round(headroom.headroom_pct(), 2),
        "headroom_alert": headroom.alert(),
        "thermal_stress": round(hs.thermal_stress, 3),
        "wear_level": round(hs.wear_level, 3),
        "zone_risk": {z: round(v, 3) for z, v in hs.zone_risk.items()},
        "rejected_count": engine.rejected_count,
    }


# ---------------------------------------------------------------------------
# Placement helper
# ---------------------------------------------------------------------------

def _safest_zone(hidden_state):
    """Return the zone name with the lowest current risk."""
    return min(hidden_state.zone_risk, key=hidden_state.zone_risk.get)


def _try_place_logged(engine, load):
    """Place equipment and log the reason if rejected."""
    hall = engine.hall
    hs = engine.hidden_state
    zone = hall.zone_for(load.x)
    risk = hs.zone_risk[zone]

    ok = engine.try_place(load)

    result = {
        "tick": engine.tick,
        "equipment": load.id,
        "weight_kg": load.weight_kg,
        "zone": zone,
        "risk": risk,
        "accepted": ok,
        "reason": "",
        "recommendation": "",
    }

    if ok:
        result["reason"] = "Placement accepted"
    else:
        in_bounds = 0 <= load.x <= hall.length_m and 0 <= load.y <= hall.width_m
        within_cap = (hall.current_capacity() + load.weight_kg) <= hall.max_capacity_kg
        if not in_bounds:
            result["reason"] = "Out of bounds"
        elif not within_cap:
            result["reason"] = "Exceeds hall capacity"
        else:
            result["reason"] = "Placement blocked: zone thermal risk exceeds safe threshold"
            best = _safest_zone(hs)
            best_risk = hs.zone_risk[best]
            result["recommendation"] = f"Redirect to {ZONE_DISPLAY[best]} (risk {best_risk:.2f})"

        st.session_state.rejection_log.append({
            "Tick": engine.tick,
            "Equipment": load.id,
            "Weight (kg)": f"{load.weight_kg:,.0f}",
            "Zone": ZONE_DISPLAY[zone],
            "Risk": f"{risk:.2f}",
            "Reason": result["reason"],
            "Recommendation": result["recommendation"],
        })

    st.session_state.last_placement = result
    return ok


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------

def _get_recommendation(hidden_state):
    """Return a placement recommendation based on current zone risks."""
    safe_zones = [
        (z, r) for z, r in hidden_state.zone_risk.items()
        if r < ZONE_RISK_THRESHOLD
    ]
    if not safe_zones:
        return None, None
    best = min(safe_zones, key=lambda x: x[1])
    return best  # (zone_key, risk)


# ---------------------------------------------------------------------------
# Placement demo logic
# ---------------------------------------------------------------------------

ZONE_COORDS = {
    "cool_zone": (10, 25),
    "normal_zone": (50, 25),
    "stressed_zone": (90, 25),
}


def _demo_attempt(equip_id, weight_kg, zone_key):
    """Attempt a placement in the given zone and return a result dict."""
    engine = st.session_state.engine
    x, y = ZONE_COORDS[zone_key]
    load = Load(equip_id, weight_kg, x=x, y=y)
    risk = engine.hidden_state.zone_risk[zone_key]
    ok = engine.try_place(load)

    result = {
        "tick": engine.tick,
        "equipment_id": equip_id,
        "weight_kg": weight_kg,
        "requested_zone": ZONE_DISPLAY[zone_key],
        "final_zone": ZONE_DISPLAY[zone_key],
        "zone_risk": round(risk, 3),
        "status": "Accepted" if ok else "Blocked",
        "reason": (
            "Placement accepted: zone risk within safe threshold" if ok
            else "Placement blocked: zone thermal risk exceeds safe threshold"
        ),
    }

    if not ok:
        best = _safest_zone(engine.hidden_state)
        best_risk = engine.hidden_state.zone_risk[best]
        result["recommendation"] = f"{ZONE_DISPLAY[best]} (risk {best_risk:.2f})"
        st.session_state.placement_status_msg = ""
    else:
        result["recommendation"] = ""
        st.session_state.placement_status_msg = (
            "Placement accepted. Hall state updated. "
            "Thermal stress and zone risk will evolve on the next tick "
            "using the updated load layout."
        )

    st.session_state.last_placement = {
        "tick": engine.tick,
        "equipment": equip_id,
        "weight_kg": weight_kg,
        "zone": zone_key,
        "risk": risk,
        "accepted": ok,
        "reason": result["reason"],
        "recommendation": result.get("recommendation", ""),
    }

    return result


def _run_placement_story(equip_id, weight_kg):
    """Scripted demo: try stressed zone, if blocked redirect to safest."""
    engine = st.session_state.engine
    log = st.session_state.demo_log

    # Step 1: attempt stressed zone
    r1 = _demo_attempt(equip_id, weight_kg, "stressed_zone")
    log.append(r1)

    if r1["status"] == "Blocked":
        # Step 2: find safest zone and redirect
        best_zone, best_risk = _get_recommendation(engine.hidden_state)
        if best_zone is not None:
            r2 = _demo_attempt(equip_id, weight_kg, best_zone)
            r2["requested_zone"] = ZONE_DISPLAY["stressed_zone"]
            r2["final_zone"] = ZONE_DISPLAY[best_zone]
            log.append(r2)

            if r2["status"] == "Accepted":
                st.session_state.demo_narrative = (
                    f"System blocked unsafe placement of {equip_id} in "
                    f"Stressed Zone (risk {r1['zone_risk']:.2f}) and "
                    f"redirected to {ZONE_DISPLAY[best_zone]} "
                    f"(risk {r2['zone_risk']:.2f}). Placement succeeded."
                )
            else:
                st.session_state.demo_narrative = (
                    f"System blocked placement in Stressed Zone and "
                    f"attempted {ZONE_DISPLAY[best_zone]}, but that zone "
                    f"was also blocked (risk {r2['zone_risk']:.2f})."
                )
        else:
            st.session_state.demo_narrative = (
                f"System blocked placement in Stressed Zone. "
                f"No safe zone is currently available for redirection."
            )
    else:
        st.session_state.demo_narrative = (
            f"{equip_id} was placed in Stressed Zone "
            f"(risk {r1['zone_risk']:.2f}). Zone is currently within "
            f"safe threshold — no redirection needed."
        )


# ---------------------------------------------------------------------------
# Prediction helper
# ---------------------------------------------------------------------------

def _predict_ticks_to_unsafe(history):
    """Estimate ticks until the hottest zone crosses the risk threshold."""
    if len(history) < 2:
        return None

    prev = history[-2]["zone_risk"]
    curr = history[-1]["zone_risk"]

    best_ticks = None
    for zone in curr:
        risk = curr[zone]
        if risk >= ZONE_RISK_THRESHOLD:
            continue
        delta = risk - prev[zone]
        if delta <= 0:
            continue
        remaining = ZONE_RISK_THRESHOLD - risk
        ticks = remaining / delta
        if best_ticks is None or ticks < best_ticks:
            best_ticks = ticks

    return round(best_ticks) if best_ticks is not None else None


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

ZONE_COLORS_BASE = {
    "cool_zone": (0.44, 0.97, 0.96),       # M3 primary-container tint
    "normal_zone": (0.88, 0.91, 0.91),      # M3 surface-container tint
    "stressed_zone": (1.0, 0.90, 0.88),     # warm tint
}


def lerp_color(base, hot, t):
    return tuple(b + (h - b) * t for b, h in zip(base, hot))


def draw_hall(hall, hidden_state):
    fig, ax = plt.subplots(figsize=(9, 4))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    third = hall.length_m / 3

    hot = (0.73, 0.10, 0.10)  # M3 error color
    zone_names = list(ZONES)

    for i, zone in enumerate(zone_names):
        risk = hidden_state.zone_risk[zone]
        color = lerp_color(ZONE_COLORS_BASE[zone], hot, risk)
        blocked = risk >= ZONE_RISK_THRESHOLD

        # Zone rectangle with rounded corners
        rect = patches.FancyBboxPatch(
            (i * third + 0.5, 0.5), third - 1, hall.width_m - 1,
            boxstyle="round,pad=0.5",
            facecolor=color,
            edgecolor=ERROR if blocked else OUTLINE_VARIANT,
            linewidth=3.0 if blocked else 1.5,
            linestyle="--" if blocked else "-",
        )
        ax.add_patch(rect)

        # Blocked overlay hatching
        if blocked:
            hatch_rect = patches.Rectangle(
                (i * third, 0), third, hall.width_m,
                facecolor="none", edgecolor=ERROR,
                linewidth=0, hatch="///", alpha=0.15,
            )
            ax.add_patch(hatch_rect)

        # Zone label above
        name = ZONE_DISPLAY[zone]
        rng = ZONE_RANGE[zone]
        status = "  BLOCKED" if blocked else ""
        label_color = ERROR if blocked else ON_SURFACE
        ax.text(
            i * third + third / 2, hall.width_m + 3,
            f"{name}\n({rng})\nRisk: {risk:.2f}{status}",
            ha="center", va="bottom", fontsize=8, weight="bold",
            color=label_color,
        )

    # Equipment markers
    for load in hall.placed_loads:
        ax.plot(load.x, load.y, "s", color=PRIMARY, markersize=7,
                markeredgecolor="white", markeredgewidth=0.5)
        ax.annotate(
            load.id, (load.x, load.y),
            textcoords="offset points", xytext=(6, -8),
            fontsize=5.5, color=OUTLINE,
        )

    # Legend
    legend_y = -9
    legend_items = [
        ((0.44, 0.97, 0.96), "Low risk"),
        ((0.95, 0.70, 0.55), "Medium risk"),
        ((0.73, 0.10, 0.10), "Blocked"),
    ]
    for j, (c, lbl) in enumerate(legend_items):
        lx = 2 + j * 25
        ax.add_patch(patches.FancyBboxPatch(
            (lx, legend_y), 4, 3, boxstyle="round,pad=0.3",
            facecolor=c, edgecolor=OUTLINE_VARIANT, linewidth=0.8,
        ))
        ax.text(lx + 5.5, legend_y + 1.5, lbl, fontsize=6.5, va="center",
                color=ON_SURFACE)

    ax.set_xlim(-2, hall.length_m + 2)
    ax.set_ylim(-14, hall.width_m + 18)
    ax.set_xlabel("Position (m)", color=ON_SURFACE, fontsize=9)
    ax.set_ylabel("Depth (m)", color=ON_SURFACE, fontsize=9)
    ax.set_title("Data Hall \u2014 Top-Down View",
                 fontsize=11, weight="bold", color=ON_SURFACE, pad=10)
    ax.set_aspect("equal")
    ax.tick_params(colors=ON_SURFACE, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(OUTLINE_VARIANT)
    plt.tight_layout()
    return fig


def draw_sensors(history):
    df = pd.DataFrame([h["sensors"] for h in history])
    df["tick"] = [h["tick"] for h in history]

    fig, axes = plt.subplots(2, 2, figsize=(9, 4.5))
    fig.patch.set_facecolor(SURFACE)
    metrics = [
        ("temperature_c", "Temperature Trend (\u00b0C)", ERROR),
        ("vibration_mm_s", "Vibration Trend (mm/s)", TERTIARY),
        ("power_kw", "Power Trend (kW)", SECONDARY),
        ("cooling_efficiency", "Cooling Efficiency Trend", PRIMARY),
    ]

    for ax, (col, label, color) in zip(axes.flat, metrics):
        ax.set_facecolor(SURFACE)
        ax.plot(df["tick"], df[col], color=color, linewidth=1.8)
        ax.fill_between(df["tick"], df[col], alpha=0.10, color=color)
        ax.set_title(label, fontsize=8.5, weight="bold", color=ON_SURFACE, pad=6)
        ax.set_xlabel("Time Step", fontsize=7, color=OUTLINE)
        ax.tick_params(labelsize=6.5, colors=OUTLINE)
        ax.grid(True, alpha=0.15, color=OUTLINE_VARIANT)
        for spine in ax.spines.values():
            spine.set_color(OUTLINE_VARIANT)

    plt.tight_layout(h_pad=2.5)
    return fig


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
    /* ── M3 Expressive Global ── */
    .block-container { padding-top: 1.5rem; }
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #F5FAFA;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #E0E8E8;
        border-right: 1px solid #BEC9C8;
    }
    [data-testid="stSidebar"] * { color: #171D1D !important; }
    [data-testid="stSidebar"] button {
        background-color: #D5DEDE !important;
        color: #171D1D !important;
        border: 1px solid #BEC9C8 !important;
        border-radius: 100px !important;
        transition: all 0.2s ease;
        font-weight: 500;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #BEC9C8 !important;
        border-color: #006A6A !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #006A6A !important;
        color: #FFFFFF !important;
        border: 1px solid #006A6A !important;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #005454 !important;
    }
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stSlider span {
        color: #171D1D !important;
    }

    /* ── KPI Cards ── */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 16px 20px;
        border-radius: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s ease, transform 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.10);
        transform: translateY(-1px);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.82rem;
        color: #6F7979;
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    [data-testid="stMetricValue"] {
        color: #171D1D;
        font-weight: 700;
        font-size: 1.5rem;
    }

    /* Visible state row */
    .visible-state-row [data-testid="stMetric"] {
        border-left: 4px solid #006A6A;
    }
    /* Hidden state row */
    .hidden-state-row [data-testid="stMetric"] {
        border-left: 4px solid #4B607C;
        background-color: #F0F3F8;
    }

    /* ── Callout Box ── */
    .kit-callout {
        background: #D3E4FF;
        border-left: 4px solid #4B607C;
        padding: 16px 20px;
        border-radius: 16px;
        margin-bottom: 1.2rem;
        font-size: 0.92rem;
        color: #041C35;
        line-height: 1.6;
    }
    .kit-callout strong { color: #4B607C; }

    /* ── Placement Cards ── */
    .placement-card {
        padding: 16px 20px;
        border-radius: 16px;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        line-height: 1.6;
        transition: box-shadow 0.2s ease;
    }
    .placement-accepted {
        background: #CCE8E7;
        border-left: 4px solid #2E7D32;
        color: #051F1F;
    }
    .placement-blocked {
        background: #FFEDEA;
        border-left: 4px solid #BA1A1A;
        color: #BA1A1A;
    }

    /* ── Recommendation Box ── */
    .rec-box {
        background: rgba(111, 247, 246, 0.3);
        border-left: 4px solid #006A6A;
        padding: 14px 18px;
        border-radius: 16px;
        font-size: 0.9rem;
        color: #002020;
        line-height: 1.6;
    }

    /* ── Narrative Summary ── */
    .narrative-box {
        background: #D3E4FF;
        border-left: 4px solid #4B607C;
        padding: 16px 20px;
        border-radius: 16px;
        font-size: 0.9rem;
        color: #041C35;
        line-height: 1.6;
        margin-top: 0.5rem;
    }

    /* ── M3 Pill Buttons (main area) ── */
    .stButton > button {
        border-radius: 100px !important;
        font-weight: 600;
        transition: all 0.2s ease;
        letter-spacing: 0.02em;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"] {
        border-radius: 16px;
        border: 1px solid #BEC9C8;
        overflow: hidden;
    }

    /* ── DataFrames ── */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* ── Dividers ── */
    hr {
        border-color: #BEC9C8 !important;
        opacity: 0.4;
    }

    /* ── Section Headers ── */
    .m3-section-header {
        color: #171D1D;
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
        letter-spacing: -0.01em;
    }

    /* ── Inputs ── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        border-radius: 12px !important;
        border-color: #BEC9C8 !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {
        border-color: #006A6A !important;
        box-shadow: 0 0 0 1px #006A6A !important;
    }
    [data-testid="stSelectbox"] > div > div {
        border-radius: 12px !important;
    }
</style>
"""


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Kit_Cap", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ---- Header ----
    st.markdown(
        f'<h1 style="color:{PRIMARY}; margin-bottom:0; font-size:2.5rem; '
        f'font-weight:800; letter-spacing:-0.02em;">Kit_Cap</h1>'
        f'<p style="color:{OUTLINE}; margin-top:0; font-size:1.1rem; '
        f'font-weight:400;">Decision-driven digital twin for safe '
        f'capacity placement</p>',
        unsafe_allow_html=True,
    )

    # ---- Callout panel ----
    st.markdown(
        '<div class="kit-callout">'
        '<strong>What this demonstrates</strong><br>'
        'Safe capacity is not the same as available capacity. '
        'Hidden zone risk can block unsafe placement before failure occurs. '
        'The twin combines visible metrics and inferred system state to make '
        'placement decisions that raw headroom alone cannot.'
        '</div>',
        unsafe_allow_html=True,
    )

    init_simulation_state()
    engine = st.session_state.engine

    # ================================================================
    # SIDEBAR
    # ================================================================

    # ---- Scenario selector ----
    st.sidebar.markdown(
        '<h2 style="margin-bottom:0.5rem;">Scenario</h2>',
        unsafe_allow_html=True,
    )
    for name in SCENARIOS:
        if st.sidebar.button(name, use_container_width=True):
            st.session_state.scenario = name
            reset_simulation()
            st.rerun()

    st.sidebar.markdown(f"**Active:** {st.session_state.scenario}")
    st.sidebar.caption(SCENARIOS[st.session_state.scenario]["description"])

    # ---- Controls ----
    st.sidebar.divider()
    st.sidebar.markdown(
        '<h3 style="margin-bottom:0.2rem;">Controls</h3>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(
        "Use Step or Run 5 to evolve system state at your own pace."
    )

    ctrl_cols = st.sidebar.columns(3)
    btn_reset = ctrl_cols[0].button("Reset", use_container_width=True)
    btn_step1 = ctrl_cols[1].button("Step", type="primary", use_container_width=True)
    btn_step5 = ctrl_cols[2].button("Run 5", use_container_width=True)

    auto_run = st.sidebar.toggle("Auto-run", value=st.session_state.auto_run)
    st.session_state.auto_run = auto_run

    # ---- Tick / Status ----
    current_tick = st.session_state.history[-1]["tick"] if st.session_state.history else 0
    if auto_run:
        status_html = f'<span style="color:{PRIMARY}; font-weight:700;">Running</span>'
    else:
        status_html = f'<span style="color:{ON_SURFACE}; font-weight:600;">Idle</span>'

    st.sidebar.markdown(
        f'<p style="margin-top:0.6rem; font-size:1.05rem;">'
        f'Tick <strong style="font-size:1.3rem;">{current_tick}</strong>'
        f'&nbsp;&nbsp;&bull;&nbsp;&nbsp;{status_html}</p>',
        unsafe_allow_html=True,
    )

    # ---- Handle buttons ----
    if btn_reset:
        reset_simulation()
        st.rerun()
    if btn_step1:
        step_simulation(1)
        st.rerun()
    if btn_step5:
        step_simulation(5)
        st.rerun()

    # ================================================================
    # MAIN DASHBOARD
    # ================================================================
    history = st.session_state.history
    # Use live snapshot for KPIs so placement mutations show immediately.
    # History snapshots are only appended on simulation ticks.
    live = get_current_snapshot()

    # ---- Visible State ----
    predicted = _predict_ticks_to_unsafe(history)
    predicted_label = f"~{predicted} ticks" if predicted is not None else "Stable"

    # Visible state metrics
    vis = st.container()
    vis.markdown(
        f'<p style="margin-bottom:0.2rem; font-size:0.8rem; font-weight:700; '
        f'color:{PRIMARY}; text-transform:uppercase; letter-spacing:0.05em;">'
        f'Visible State &mdash; what operators can see</p>',
        unsafe_allow_html=True,
    )
    with vis:
        st.markdown('<div class="visible-state-row">', unsafe_allow_html=True)
        v1, v2, v3 = st.columns(3)
        v1.metric("Utilization", f"{live['utilization_pct']:.1f}%",
                  help="Current hall weight as a percentage of max capacity")
        v2.metric("Headroom", f"{live['headroom_pct']:.1f}%",
                  help="Remaining capacity available for new equipment")
        v3.metric("Unsafe Placements Prevented", str(live["rejected_count"]),
                  help="Equipment placements blocked because zone risk exceeded the safety threshold")
        st.markdown('</div>', unsafe_allow_html=True)

    # Hidden state metrics
    hid = st.container()
    hid.markdown(
        f'<p style="margin-bottom:0.2rem; margin-top:0.8rem; font-size:0.8rem; '
        f'font-weight:700; color:{TERTIARY}; text-transform:uppercase; '
        f'letter-spacing:0.05em;">'
        f'Hidden State &mdash; inferred by the digital twin</p>',
        unsafe_allow_html=True,
    )
    with hid:
        st.markdown('<div class="hidden-state-row">', unsafe_allow_html=True)
        h1, h2, h3 = st.columns(3)
        h1.metric("Thermal Stress", f"{live['thermal_stress']:.3f}",
                  help="Global heat accumulation (0 = cool, 1 = critical)")
        h2.metric("Wear", f"{live['wear_level']:.3f}",
                  help="Structural wear from continuous operation (0 = new, 1 = end-of-life)")
        h3.metric("Time to Unsafe", predicted_label,
                  help="Estimated ticks until the fastest-rising zone crosses the risk threshold")
        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Placement status message ----
    if st.session_state.placement_status_msg:
        st.markdown(
            f'<div class="kit-callout" style="background:{SECONDARY_CONTAINER}; '
            f'border-left-color:{PRIMARY}; margin-top:0.5rem;">'
            f'{st.session_state.placement_status_msg}</div>',
            unsafe_allow_html=True,
        )

    # ---- Two-column: Placement Outcome + Recommendation ----
    col_place, col_rec = st.columns(2)

    with col_place:
        st.markdown(f'<p style="color:{ON_SURFACE}; font-size:1.05rem; '
                    f'font-weight:600; margin-bottom:0.3rem;">Latest Placement Decision</p>',
                    unsafe_allow_html=True)
        lp = st.session_state.last_placement
        if lp is not None:
            zone_label = ZONE_DISPLAY.get(lp["zone"], lp["zone"])
            if lp["accepted"]:
                st.markdown(
                    f'<div class="placement-card placement-accepted">'
                    f'<strong>{lp["equipment"]}</strong> '
                    f'({lp["weight_kg"]:,.0f} kg) placed in '
                    f'<strong>{zone_label}</strong> '
                    f'at tick {lp["tick"]}<br>'
                    f'Zone risk: {lp["risk"]:.2f} &mdash; within safe threshold'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                card = (
                    f'<div class="placement-card placement-blocked">'
                    f'<strong>{lp["equipment"]}</strong> '
                    f'({lp["weight_kg"]:,.0f} kg) &rarr; '
                    f'<strong>{zone_label}</strong> '
                    f'at tick {lp["tick"]}<br>'
                    f'<strong>Status:</strong> Blocked &mdash; {lp["reason"]}<br>'
                    f'Zone risk: {lp["risk"]:.2f}'
                )
                if lp["recommendation"]:
                    card += f'<br><em>{lp["recommendation"]}</em>'
                card += '</div>'
                st.markdown(card, unsafe_allow_html=True)
        else:
            st.caption("No placement attempts yet.")

    with col_rec:
        st.markdown(f'<p style="color:{ON_SURFACE}; font-size:1.05rem; '
                    f'font-weight:600; margin-bottom:0.3rem;">Placement Recommendation</p>',
                    unsafe_allow_html=True)
        rec_zone, rec_risk = _get_recommendation(engine.hidden_state)
        if rec_zone is not None:
            st.markdown(
                f'<div class="rec-box">'
                f'<strong>Recommended zone:</strong> '
                f'{ZONE_DISPLAY[rec_zone]} ({ZONE_RANGE[rec_zone]})<br>'
                f'Current risk: {rec_risk:.3f}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="placement-card placement-blocked">'
                '<strong>No safe placement currently available.</strong><br>'
                'All zones exceed the risk threshold. '
                'Allow the system to cool before placing new equipment.'
                '</div>',
                unsafe_allow_html=True,
            )

    # ---- Hall visualization ----
    st.markdown("---")
    st.markdown(f'<p class="m3-section-header">Data Hall Layout & Zone Risk</p>',
                unsafe_allow_html=True)
    fig_hall = draw_hall(engine.hall, engine.hidden_state)
    st.pyplot(fig_hall)
    plt.close(fig_hall)

    # ---- Zone risk table ----
    zr = live["zone_risk"]
    risk_df = pd.DataFrame([
        {
            "Zone": ZONE_DISPLAY[z],
            "Range": ZONE_RANGE[z],
            "Risk": f"{v:.3f}",
            "Status": "BLOCKED" if v >= ZONE_RISK_THRESHOLD else "OK",
        }
        for z, v in zr.items()
    ])
    st.dataframe(risk_df, use_container_width=True, hide_index=True)

    # ================================================================
    # PLACEMENT DECISION DEMO
    # ================================================================
    st.markdown("---")
    st.markdown(f'<p class="m3-section-header">Placement Decision Demo</p>',
                unsafe_allow_html=True)
    st.caption(
        "Test the twin's placement logic. Choose equipment and a target "
        "zone, or run the scripted story to see reject-then-redirect."
    )

    # ---- Recommendation label ----
    rec_zone, rec_risk = _get_recommendation(engine.hidden_state)
    if rec_zone is not None:
        st.markdown(
            f'<div class="rec-box">'
            f'<strong>Recommended zone:</strong> {ZONE_DISPLAY[rec_zone]} '
            f'({ZONE_RANGE[rec_zone]})<br>'
            f'<strong>Reason:</strong> lowest current risk ({rec_risk:.3f}) '
            f'below safe threshold'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="placement-card placement-blocked">'
            '<strong>No safe placement currently available.</strong><br>'
            'All zones exceed the risk threshold.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ---- Input controls ----
    demo_c1, demo_c2, demo_c3 = st.columns([1, 1, 1])
    with demo_c1:
        demo_id = st.text_input("Equipment ID", value="rack-X", key="demo_id")
    with demo_c2:
        demo_weight = st.number_input(
            "Weight (kg)", min_value=1_000, max_value=200_000,
            value=20_000, step=5_000, key="demo_weight",
        )
    with demo_c3:
        demo_zone = st.selectbox(
            "Target Zone",
            options=["stressed_zone", "normal_zone", "cool_zone"],
            format_func=lambda z: ZONE_DISPLAY[z],
            key="demo_zone",
        )

    # ---- Action buttons ----
    btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
    with btn_c1:
        btn_attempt = st.button("Attempt Placement", type="primary",
                                use_container_width=True)
    with btn_c2:
        btn_redirect = st.button("Redirect to Lowest-Risk Zone",
                                 use_container_width=True)
    with btn_c3:
        btn_story = st.button("Run Placement Story",
                              use_container_width=True)

    # ---- Handle demo actions ----
    if btn_attempt:
        r = _demo_attempt(demo_id, demo_weight, demo_zone)
        st.session_state.demo_log.append(r)
        st.session_state.demo_narrative = ""
        st.rerun()

    if btn_redirect:
        best_z, _ = _get_recommendation(engine.hidden_state)
        if best_z is not None:
            r = _demo_attempt(demo_id, demo_weight, best_z)
            r["requested_zone"] = ZONE_DISPLAY[demo_zone]
            r["final_zone"] = ZONE_DISPLAY[best_z]
            st.session_state.demo_log.append(r)
            st.session_state.demo_narrative = (
                f"Redirected {demo_id} from {ZONE_DISPLAY[demo_zone]} to "
                f"{ZONE_DISPLAY[best_z]} (risk {r['zone_risk']:.2f}). "
                f"Status: {r['status']}."
            )
        else:
            st.session_state.demo_narrative = (
                "No safe zone available for redirection. "
                "All zones exceed the risk threshold."
            )
        st.rerun()

    if btn_story:
        st.session_state.demo_log.clear()
        _run_placement_story(demo_id, demo_weight)
        st.rerun()

    # ---- Latest result card ----
    if st.session_state.demo_log:
        last = st.session_state.demo_log[-1]
        if last["status"] == "Accepted":
            st.markdown(
                f'<div class="placement-card placement-accepted">'
                f'<strong>{last["equipment_id"]}</strong> '
                f'({last["weight_kg"]:,.0f} kg) placed in '
                f'<strong>{last["final_zone"]}</strong><br>'
                f'Zone risk: {last["zone_risk"]:.3f} &mdash; '
                f'{last["reason"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            card = (
                f'<div class="placement-card placement-blocked">'
                f'<strong>{last["equipment_id"]}</strong> '
                f'({last["weight_kg"]:,.0f} kg) &rarr; '
                f'<strong>{last["requested_zone"]}</strong><br>'
                f'Zone risk: {last["zone_risk"]:.3f} &mdash; '
                f'{last["reason"]}'
            )
            if last.get("recommendation"):
                card += (
                    f'<br><em>Redirect to: {last["recommendation"]}</em>'
                )
            card += '</div>'
            st.markdown(card, unsafe_allow_html=True)

    # ---- Narrative summary ----
    if st.session_state.demo_narrative:
        st.markdown(
            f'<div class="narrative-box">'
            f'<strong>Summary:</strong> {st.session_state.demo_narrative}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ---- Demo event log ----
    if st.session_state.demo_log:
        with st.expander(
            f"Placement Event Log ({len(st.session_state.demo_log)} events)",
            expanded=True,
        ):
            log_df = pd.DataFrame(st.session_state.demo_log)
            display_cols = [
                "tick", "equipment_id", "weight_kg", "requested_zone",
                "final_zone", "zone_risk", "status", "reason",
            ]
            st.dataframe(
                log_df[[c for c in display_cols if c in log_df.columns]],
                use_container_width=True,
                hide_index=True,
            )

    # ---- Rejection log (collapsed) ----
    if st.session_state.rejection_log:
        with st.expander(
            f"Blocked Placement Log ({len(st.session_state.rejection_log)} events)",
            expanded=False,
        ):
            st.dataframe(
                pd.DataFrame(st.session_state.rejection_log),
                use_container_width=True,
                hide_index=True,
            )

    # ---- Sensor trends ----
    st.markdown("---")
    st.markdown(f'<p class="m3-section-header">Sensor Trends</p>',
                unsafe_allow_html=True)
    fig_sensors = draw_sensors(history)
    st.pyplot(fig_sensors)
    plt.close(fig_sensors)

    # ---- Debug panel ----
    with st.expander("Debug: Hall State", expanded=False):
        hall = engine.hall
        st.markdown(
            f"**Placed loads:** {len(hall.placed_loads)}  \n"
            f"**Total capacity used:** {hall.current_capacity():,.0f} kg "
            f"/ {hall.max_capacity_kg:,.0f} kg  \n"
            f"**Utilization:** {hall.utilization_pct():.1f}%  \n"
            f"**Load IDs:** {', '.join(l.id for l in hall.placed_loads)}"
        )

    # ---- Auto-run loop (renders dashboard first, then sleeps) ----
    if st.session_state.auto_run:
        time.sleep(0.85)
        step_simulation(1)
        st.rerun()


if __name__ == "__main__":
    main()
