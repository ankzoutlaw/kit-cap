"""Generate architecture diagram for Kit_Cap portfolio README."""

import matplotlib
matplotlib.rcParams["font.family"] = "DejaVu Sans"
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

RED       = "#ED1C24"
DARK_RED  = "#B71C1C"
BLACK     = "#1A1A1A"
GREY      = "#555555"
LIGHT     = "#F5F5F5"
WHITE     = "#FFFFFF"
BORDER    = "#CCCCCC"

fig, ax = plt.subplots(figsize=(12, 6.5))
fig.patch.set_facecolor(WHITE)
ax.set_facecolor(WHITE)
ax.set_xlim(0, 12)
ax.set_ylim(0, 6.5)
ax.axis("off")


def box(x, y, w, h, label, sublabel="", color=LIGHT, text_color=BLACK, bold=False):
    rect = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.05",
        facecolor=color, edgecolor=BORDER, linewidth=1.2,
    )
    ax.add_patch(rect)
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2 + (0.15 if sublabel else 0),
            label, ha="center", va="center",
            fontsize=9, fontweight=weight, color=text_color)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.22,
                sublabel, ha="center", va="center",
                fontsize=7, color=GREY)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=GREY,
                                lw=1.4, mutation_scale=12))


def section_label(x, y, text):
    ax.text(x, y, text, fontsize=7.5, color=GREY,
            fontstyle="italic", ha="center")


# --- Title ---
ax.text(6, 6.15, "Kit_Cap — Architecture",
        ha="center", va="center", fontsize=13,
        fontweight="bold", color=BLACK)
ax.text(6, 5.82, "Data Center Capacity Digital Twin",
        ha="center", va="center", fontsize=9, color=GREY)

# --- Layer: Input ---
box(0.3, 4.5, 1.7, 0.75, "Equipment", "rack / load input", color=LIGHT, bold=False)
box(0.3, 3.55, 1.7, 0.75, "Scenario", "Normal / Hotspot / ...", color=LIGHT, bold=False)
section_label(1.15, 4.4, "")
ax.text(1.15, 5.35, "INPUT", fontsize=7.5, color=GREY,
        fontstyle="italic", ha="center")

# --- Layer: Core Model ---
box(2.5, 4.5, 1.8, 0.75, "Hall", "zones, capacity", color=LIGHT, bold=True)
box(2.5, 3.55, 1.8, 0.75, "Headroom", "remaining %, alert", color=LIGHT)
box(2.5, 2.6,  1.8, 0.75, "Load", "id, weight, x, y", color=LIGHT)
ax.text(3.4, 5.35, "CORE MODEL", fontsize=7.5, color=GREY,
        fontstyle="italic", ha="center")

# --- Layer: Simulation Engine ---
box(4.9, 3.1, 2.1, 2.1, "Simulation\nEngine", "tick-step loop", color=BLACK,
    text_color=WHITE, bold=True)
ax.text(5.95, 5.35, "ENGINE", fontsize=7.5, color=GREY,
        fontstyle="italic", ha="center")

# --- Layer: Hidden State ---
box(7.5, 4.5, 2.0, 0.75, "Hidden State", "thermal, wear, zone risk", color=DARK_RED,
    text_color=WHITE, bold=True)
box(7.5, 3.55, 2.0, 0.75, "Sensor Stream", "temp, vibration, power", color=LIGHT)
box(7.5, 2.6,  2.0, 0.75, "Scenarios", "risk rate overrides", color=LIGHT)
ax.text(8.5, 5.35, "HIDDEN LAYER", fontsize=7.5, color=DARK_RED,
        fontstyle="italic", ha="center")

# --- Layer: Output ---
box(10.1, 4.5, 1.6, 0.75, "KPI Cards", "util, headroom...", color=RED,
    text_color=WHITE)
box(10.1, 3.55, 1.6, 0.75, "Zone Map", "risk colours", color=RED,
    text_color=WHITE)
box(10.1, 2.6,  1.6, 0.75, "Prediction", "ticks to unsafe", color=RED,
    text_color=WHITE)
ax.text(10.9, 5.35, "DASHBOARD", fontsize=7.5, color=RED,
        fontstyle="italic", ha="center")

# --- Arrows: Input -> Core ---
arrow(2.0, 4.875, 2.5, 4.875)
arrow(2.0, 3.925, 2.5, 3.925)

# --- Arrows: Core -> Engine ---
arrow(4.3, 4.875, 4.9, 4.1)
arrow(4.3, 3.925, 4.9, 3.7)
arrow(4.3, 2.975, 4.9, 3.4)

# --- Arrows: Scenario -> Engine ---
arrow(2.0, 3.925, 4.9, 3.6)

# --- Arrows: Engine -> Hidden State ---
arrow(7.0, 4.5, 7.5, 4.875)
arrow(7.0, 3.8, 7.5, 3.925)

# --- Hidden State feedback -> Engine ---
ax.annotate("", xy=(5.95, 5.2), xytext=(8.5, 5.2),
            arrowprops=dict(arrowstyle="-|>", color=DARK_RED,
                            lw=1.4, mutation_scale=12,
                            connectionstyle="arc3,rad=0"))
ax.text(7.2, 5.28, "feedback loop", fontsize=7, color=DARK_RED, ha="center")

# --- Arrows: Engine -> Dashboard ---
arrow(7.0, 4.1, 10.1, 4.875)
arrow(7.0, 3.8, 10.1, 3.925)
arrow(7.0, 3.5, 10.1, 2.975)

# --- Key insight box ---
insight = mpatches.FancyBboxPatch(
    (0.3, 1.5), 11.4, 0.75,
    boxstyle="round,pad=0.05",
    facecolor="#FFF3F3", edgecolor=RED, linewidth=1.5,
)
ax.add_patch(insight)
ax.text(6.0, 1.875,
        "Key insight:  Safe capacity \u2260 available capacity  "
        "\u2014  hidden zone risk blocks placements even when headroom exists",
        ha="center", va="center", fontsize=9,
        color=DARK_RED, fontweight="bold")

plt.tight_layout()
plt.savefig("architecture.png", dpi=150, bbox_inches="tight",
            facecolor=WHITE)
print("Saved architecture.png")
