"""
Preliminary analysis for the TwinCare progress review.

Question: when a vasopressor dose takes minutes to act, what happens if the
system decides on the current MAP alone, versus on a twin forecast that
includes the falling trend and the doses already given but not yet felt?

Patient (embedded-patient stand-in): MAP = P0 - D(t) + K * e(t), where the drug
effect e(t) follows the commanded dose u through a transport delay TD and a
first-order lag TAU. D(t) is a vasodilatory disturbance (hypotension onset).

The twin runs its OWN copy of the model with nominal parameters (K_TWIN,
TD_TWIN, TAU_TWIN). It never sees the patient's true parameters or D(t); it
infers the disturbance from measured MAP.

ALL PARAMETERS ARE ILLUSTRATIVE AND UNCALIBRATED. The delay-plus-lag structure
is a common simplification in vasopressor-control studies; calibrating it
(e.g. against Kao et al., IEEE TBME 2023) is a planned next step.

Run:  python3 lag_aware_sim.py
  -> lag_aware_sim.png   (figure for the slide)
  -> robustness.csv      (12 patient variants x 5 noise seeds)
"""
import csv
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
import matplotlib.pyplot as plt

# outputs go next to this file, whatever folder it is launched from
OUT_DIR = Path(__file__).resolve().parent

# ---- scenario (illustrative) -------------------------------------------------
DT = 1.0                      # s, integration step
T_END = 60 * 60               # s, 60-minute episode
P0 = 67.0                     # mmHg, MAP with no drug effect
U0 = 0.05                     # ug/kg/min, established infusion at t = 0
K_TRUE, TD_TRUE, TAU_TRUE = 85.0, 120.0, 180.0   # patient: mmHg/(ug/kg/min), s, s
K_TWIN, TD_TWIN, TAU_TWIN = 100.0, 120.0, 180.0  # twin's nominal model (K off by 15%)
D_MAX, D_START, D_RAMP = 18.0, 5 * 60, 15 * 60   # disturbance: 18 mmHg over 15 min
NOISE_SD = 1.0                # mmHg measurement noise

# ---- decision rules shared by both policies ------------------------------------
DECIDE_EVERY = 60             # s, one proposal per minute
STEP = 0.03                   # ug/kg/min, bounded dose change per decision
U_MIN, U_MAX = 0.0, 0.5       # ug/kg/min, hard limits (device-enforced)
LOW, HIGH = 65.0, 75.0        # mmHg, target band
TREND_MIN = (TD_TWIN + TAU_TWIN) / 60   # min, forecast horizon = time for a dose to act
TREND_WINDOW = 5              # decisions used to estimate the trend


def disturbance(t):
    if t < D_START:
        return 0.0
    return D_MAX * min(1.0, (t - D_START) / D_RAMP)


def simulate(policy, k=K_TRUE, td=TD_TRUE, tau=TAU_TRUE, seed=7):
    rng = np.random.default_rng(seed)
    n = int(T_END / DT) + 1
    t = np.arange(n) * DT
    u_hist = np.full(n, U0)
    e, e_twin = U0, U0
    true_map = np.zeros(n)
    meas = np.zeros(n)
    d_hist = []
    changes = 0
    u = U0
    for i in range(n):
        j = i - int(td / DT)
        e += DT * ((u_hist[j] if j >= 0 else U0) - e) / tau
        j = i - int(TD_TWIN / DT)
        e_twin += DT * ((u_hist[j] if j >= 0 else U0) - e_twin) / TAU_TWIN
        true_map[i] = P0 - disturbance(t[i]) + k * e
        meas[i] = true_map[i] + rng.normal(0, NOISE_SD)

        if i > 0 and i % int(DECIDE_EVERY / DT) == 0:
            m = meas[max(0, i - 60):i + 1].mean()   # 1-min mean, both policies
            if policy == "reactive":
                basis = m
            else:
                d_hat = P0 + K_TWIN * e_twin - m       # unexplained fall
                d_hist.append(d_hat)
                slope = 0.0
                if len(d_hist) >= TREND_WINDOW:
                    x = np.arange(TREND_WINDOW)
                    slope = max(0.0, np.polyfit(x, d_hist[-TREND_WINDOW:], 1)[0])
                pending = u - e_twin                    # given, not yet felt
                basis = P0 - (d_hat + slope * TREND_MIN) + K_TWIN * (e_twin + pending)
            new_u = u
            if basis < LOW:
                new_u = min(U_MAX, u + STEP)
            elif basis > HIGH:
                new_u = max(U_MIN, u - STEP)
            if new_u != u:
                changes += 1
                u = new_u
        u_hist[i] = u
    return t / 60.0, true_map, u_hist, changes


def metrics(t_min, mp, u, changes):
    dt_min = t_min[1] - t_min[0]
    return {
        "min_below_65": round(float((mp < LOW).sum() * dt_min), 1),
        "min_above_75": round(float((mp > HIGH).sum() * dt_min), 1),
        "lowest_map": round(float(mp.min()), 1),
        "peak_map": round(float(mp.max()), 1),
        "peak_dose": round(float(u.max()), 2),
        "dose_changes": changes,
    }


if __name__ == "__main__":
    runs = {p: simulate(p) for p in ("reactive", "twin")}
    for p, (t, mp, u, c) in runs.items():
        print(p, metrics(t, mp, u, c))

    # robustness: twin keeps its nominal model while the patient varies
    rows = []
    for k in (70, 85, 100, 115):
        for td in (60, 120, 180):
            for p in ("reactive", "twin"):
                ms = [metrics(*simulate(p, k=k, td=td, seed=s)) for s in range(5)]
                rows.append({"patient_K": k, "patient_delay_s": td, "policy": p,
                             **{key: round(float(np.mean([m[key] for m in ms])), 1)
                                for key in ms[0]}})
    with open(OUT_DIR / "robustness.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for key in ("min_below_65", "min_above_75", "dose_changes"):
        r = [row[key] for row in rows if row["policy"] == "reactive"]
        tw = [row[key] for row in rows if row["policy"] == "twin"]
        wins = sum(b <= a for a, b in zip(r, tw))
        print(f"{key}: reactive mean {np.mean(r):.1f}, twin mean {np.mean(tw):.1f}, "
              f"twin <= reactive in {wins}/12 patient variants")

    navy, orange, band = "#17304F", "#C2620A", "#DCEFF8"
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 7.2), dpi=150, sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.12})
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=21, colors="#33475B")
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#9AAAB8")
    ax1.axhspan(LOW, HIGH, color=band, zorder=0)
    ax1.text(6.2, HIGH + 1.0, "Target 65–75 mmHg", fontsize=21, color="#2B5D7D")
    t, mp_r, u_r, _ = runs["reactive"]
    _, mp_t, u_t, _ = runs["twin"]
    ax1.plot(t, mp_r, color=orange, lw=3.6, label="Reactive rule")
    ax1.plot(t, mp_t, color=navy, lw=3.6, label="Twin forecast")
    ax1.set_ylabel("MAP (mmHg)", fontsize=22, color="#33475B")
    ax1.legend(frameon=False, fontsize=21, loc="lower right")
    ax1.axvline(D_START / 60, color="#9AAAB8", lw=1.2, ls="--")
    ax1.text(D_START / 60 + 0.6, 58.6, "onset", fontsize=20, color="#5B6B7A")
    ax1.set_ylim(58, 80)
    ax2.step(t, u_r, where="post", color=orange, lw=2.6)
    ax2.step(t, u_t, where="post", color=navy, lw=2.6)
    ax2.set_ylabel("Dose\n(µg/kg/min)", fontsize=20, color="#33475B")
    ax2.set_xlabel("Time (min)", fontsize=22, color="#33475B")
    ax2.set_xlim(0, T_END / 60)
    fig.savefig(OUT_DIR / "lag_aware_sim.png", bbox_inches="tight", facecolor="white")
    print(f"saved {OUT_DIR / 'lag_aware_sim.png'} and {OUT_DIR / 'robustness.csv'}")
    plt.show()
