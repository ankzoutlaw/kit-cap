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
# Brand colors
# ---------------------------------------------------------------------------
RED = "#ED1C24"
DARK_RED = "#B71C1C"
DARK_GREY = "#333333"
MID_GREY = "#666666"
LIGHT_GREY = "#F5F5F5"
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
    "cool_zone": (0.85, 0.92, 0.98),
    "normal_zone": (0.93, 0.93, 0.93),
    "stressed_zone": (1.0, 0.90, 0.88),
}


def lerp_color(base, hot, t):
    return tuple(b + (h - b) * t for b, h in zip(base, hot))


def draw_hall(hall, hidden_state):
    fig, ax = plt.subplots(figsize=(9, 4))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    third = hall.length_m / 3

    hot = (0.93, 0.11, 0.14)
    zone_names = list(ZONES)

    for i, zone in enumerate(zone_names):
        risk = hidden_state.zone_risk[zone]
        color = lerp_color(ZONE_COLORS_BASE[zone], hot, risk)
        blocked = risk >= ZONE_RISK_THRESHOLD

        # Zone rectangle
        rect = patches.Rectangle(
            (i * third, 0), third, hall.width_m,
            facecolor=color,
            edgecolor=DARK_RED if blocked else "#999999",
            linewidth=3.0 if blocked else 1.5,
            linestyle="--" if blocked else "-",
        )
        ax.add_patch(rect)

        # Blocked overlay hatching
        if blocked:
            hatch_rect = patches.Rectangle(
                (i * third, 0), third, hall.width_m,
                facecolor="none", edgecolor=DARK_RED,
                linewidth=0, hatch="///", alpha=0.15,
            )
            ax.add_patch(hatch_rect)

        # Zone label above
        name = ZONE_DISPLAY[zone]
        rng = ZONE_RANGE[zone]
        status = "  BLOCKED" if blocked else ""
        label_color = DARK_RED if blocked else DARK_GREY
        ax.text(
            i * third + third / 2, hall.width_m + 3,
            f"{name}\n({rng})\nRisk: {risk:.2f}{status}",
            ha="center", va="bottom", fontsize=8, weight="bold",
            color=label_color,
        )

    # Equipment markers
    for load in hall.placed_loads:
        ax.plot(load.x, load.y, "s", color=DARK_RED, markersize=7,
                markeredgecolor="white", markeredgewidth=0.5)
        ax.annotate(
            load.id, (load.x, load.y),
            textcoords="offset points", xytext=(6, -8),
            fontsize=5.5, color=MID_GREY,
        )

    # Legend
    legend_y = -9
    legend_items = [
        ((0.85, 0.92, 0.98), "Low risk"),
        ((0.95, 0.70, 0.55), "Medium risk"),
        ((0.93, 0.11, 0.14), "Blocked"),
    ]
    for j, (c, lbl) in enumerate(legend_items):
        lx = 2 + j * 25
        ax.add_patch(patches.Rectangle(
            (lx, legend_y), 4, 3, facecolor=c, edgecolor="#999999", linewidth=0.8,
        ))
        ax.text(lx + 5.5, legend_y + 1.5, lbl, fontsize=6.5, va="center",
                color=DARK_GREY)

    ax.set_xlim(-2, hall.length_m + 2)
    ax.set_ylim(-14, hall.width_m + 18)
    ax.set_xlabel("Position (m)", color=DARK_GREY, fontsize=9)
    ax.set_ylabel("Depth (m)", color=DARK_GREY, fontsize=9)
    ax.set_title("Data Hall \u2014 Top-Down View",
                 fontsize=11, weight="bold", color=DARK_GREY, pad=10)
    ax.set_aspect("equal")
    ax.tick_params(colors=DARK_GREY, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#CCCCCC")
    plt.tight_layout()
    return fig


def draw_sensors(history):
    df = pd.DataFrame([h["sensors"] for h in history])
    df["tick"] = [h["tick"] for h in history]

    fig, axes = plt.subplots(2, 2, figsize=(9, 4.5))
    fig.patch.set_facecolor("white")
    metrics = [
        ("temperature_c", "Temperature Trend (\u00b0C)", RED),
        ("vibration_mm_s", "Vibration Trend (mm/s)", "#FF6F00"),
        ("power_kw", "Power Trend (kW)", "#455A64"),
        ("cooling_efficiency", "Cooling Efficiency Trend", GREEN),
    ]

    for ax, (col, label, color) in zip(axes.flat, metrics):
        ax.set_facecolor("white")
        ax.plot(df["tick"], df[col], color=color, linewidth=1.4)
        ax.fill_between(df["tick"], df[col], alpha=0.08, color=color)
        ax.set_title(label, fontsize=8.5, weight="bold", color=DARK_GREY, pad=6)
        ax.set_xlabel("Time Step", fontsize=7, color=MID_GREY)
        ax.tick_params(labelsize=6.5, colors=MID_GREY)
        ax.grid(True, alpha=0.15, color="#CCCCCC")
        for spine in ax.spines.values():
            spine.set_color("#E0E0E0")

    plt.tight_layout(h_pad=2.5)
    return fig


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 1.2rem; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #B71C1C; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
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

    /* KPI cards */
    [data-testid="stMetric"] {
        background-color: #F5F5F5;
        padding: 12px 16px;
        border-radius: 4px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #666666; }
    [data-testid="stMetricValue"] { color: #333333; font-weight: 700; }

    /* Visible state row */
    .visible-state-row [data-testid="stMetric"] {
        border-left: 4px solid #1565C0;
    }
    /* Hidden state row */
    .hidden-state-row [data-testid="stMetric"] {
        border-left: 4px solid #B71C1C;
        background-color: #FFF8F8;
    }

    /* Callout box */
    .kit-callout {
        background: #FFF8E1;
        border-left: 4px solid #FFB300;
        padding: 14px 18px;
        border-radius: 4px;
        margin-bottom: 1rem;
        font-size: 0.92rem;
        color: #333333;
        line-height: 1.6;
    }
    .kit-callout strong { color: #E65100; }

    /* Placement outcome card */
    .placement-card {
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .placement-accepted {
        background: #E8F5E9;
        border-left: 4px solid #2E7D32;
        color: #1B5E20;
    }
    .placement-blocked {
        background: #FFEBEE;
        border-left: 4px solid #B71C1C;
        color: #B71C1C;
    }

    /* Recommendation box */
    .rec-box {
        background: #E3F2FD;
        border-left: 4px solid #1565C0;
        padding: 12px 16px;
        border-radius: 4px;
        font-size: 0.9rem;
        color: #0D47A1;
        line-height: 1.5;
    }

    /* Narrative summary */
    .narrative-box {
        background: #F3E5F5;
        border-left: 4px solid #7B1FA2;
        padding: 14px 18px;
        border-radius: 4px;
        font-size: 0.9rem;
        color: #4A148C;
        line-height: 1.5;
        margin-top: 0.5rem;
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
        f'<h1 style="color:{RED}; margin-bottom:0;">Kit_Cap</h1>'
        f'<p style="color:{MID_GREY}; margin-top:0; font-size:1.05rem; '
        f'font-style:italic;">Decision-driven digital twin for safe '
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
        status_html = '<span style="color:#2E7D32; font-weight:700;">Running</span>'
    else:
        status_html = '<span style="color:#FFFFFF; font-weight:600;">Idle</span>'

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
        '<p style="margin-bottom:0.2rem; font-size:0.8rem; font-weight:700; '
        'color:#1565C0; text-transform:uppercase; letter-spacing:0.05em;">'
        'Visible State &mdash; what operators can see</p>',
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
        '<p style="margin-bottom:0.2rem; margin-top:0.8rem; font-size:0.8rem; '
        'font-weight:700; color:#B71C1C; text-transform:uppercase; '
        'letter-spacing:0.05em;">'
        'Hidden State &mdash; inferred by the digital twin</p>',
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
            f'<div class="kit-callout" style="background:#E8F5E9; '
            f'border-left-color:#2E7D32; margin-top:0.5rem;">'
            f'{st.session_state.placement_status_msg}</div>',
            unsafe_allow_html=True,
        )

    # ---- Two-column: Placement Outcome + Recommendation ----
    col_place, col_rec = st.columns(2)

    with col_place:
        st.markdown("##### Latest Placement Decision")
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
        st.markdown("##### Placement Recommendation")
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
    st.markdown("##### Data Hall Layout & Zone Risk")
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
    st.markdown("##### Placement Decision Demo")
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
    st.markdown("##### Sensor Trends")
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
