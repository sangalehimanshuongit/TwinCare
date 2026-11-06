"""DI-03 dry run v2: the v1 pipeline with fairer scoring, after red-team review.

Changes from v1 (forecaster_dryrun.py):
1. Only warnable drops count toward sensitivity: the drop must start late enough that a
   10-minute warning was possible (onset >= minute 16, since scoring starts at minute 5 and
   an alert needs 2 consecutive minutes).
2. A continuous alert counts again every 10 minutes, so an alert that stays on cannot hide
   as one false alert. Time spent alerting is reported too.
3. Every threshold, for the model and the pressure alarm, is chosen on TRAINING episodes only
   (best training sensitivity within the false-alert limit, ties go to the setting that alerts most,
   which gives the alarm its best chance), then applied once to the test set.

Still NOT verification of DI-03: the same model generates training and test data.
"""
import json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "reference"))
import lag_aware_sim as ref  # noqa: E402

HORIZON, PERSIST, LOOKBACK, REALERT, FIRST, LAST = 10, 2, 20, 10, 5, 50
WARNABLE = FIRST + PERSIST - 1 + HORIZON          # earliest onset that a 10-min warning could precede


def episode(rng):
    ref.D_MAX = float(rng.uniform(0, 24))
    ref.D_START = float(rng.uniform(3, 20)) * 60
    ref.D_RAMP = float(rng.uniform(8, 20)) * 60
    k = float(rng.uniform(65, 120)); td = float(rng.choice([60, 90, 120, 150, 180])); tau = float(rng.uniform(120, 240))
    t, mp, u, _ = ref.simulate("reactive", k=k, td=td, tau=tau, seed=int(rng.integers(1e9)))
    meas = mp + rng.normal(0, ref.NOISE_SD, len(mp))
    m1 = np.array([meas[i * 60:(i + 1) * 60].mean() for i in range(60)])
    true1 = np.array([mp[i * 60:(i + 1) * 60].mean() for i in range(60)])
    dose = np.array([u[min(i * 60 + 59, len(u) - 1)] for i in range(60)])
    return m1, true1, dose


def features(m1, dose, i):
    w5 = m1[i - 4:i + 1]; w2 = m1[i - 1:i + 1]
    s5 = np.polyfit(np.arange(5), w5, 1)[0]; s2 = w2[1] - w2[0]
    pending = dose[i] - dose[max(0, i - 3)]
    return [m1[i], s5, s2, dose[i], pending, m1[i] + 10 * s5]


def build(eps):
    X, y, idx = [], [], []
    for e, (m1, true1, dose) in enumerate(eps):
        for i in range(FIRST, LAST):
            if true1[i] < 65:
                continue
            X.append(features(m1, dose, i))
            y.append(int((true1[i + 1:i + 1 + HORIZON] < 65).any()))
            idx.append((e, i))
    return np.array(X), np.array(y), idx


def alerts_from(scores, idx, thr, n_eps, hi=True):
    raw = {}
    for (e, i), s in zip(idx, scores):
        raw.setdefault(e, {})[i] = (s >= thr) if hi else (s <= thr)
    return {e: [i for i in sorted(raw.get(e, {})) if raw[e][i] and raw[e].get(i - 1, False)] for e in range(n_eps)}


def onset_of(true1):
    below = np.where(true1[FIRST:] < 65)[0]
    return int(below[0]) + FIRST if len(below) else None


def score(eps, alerts):
    events = warnable = warned = 0; warn_times = []; false_alerts = 0; minutes = 0; alert_min = 0
    for e, (m1, true1, dose) in enumerate(eps):
        onset = onset_of(true1)
        scored = [i for i in range(FIRST, LAST) if true1[i] >= 65]
        minutes += len(scored)
        a = [i for i in alerts[e] if i in set(scored)]
        alert_min += len(a)
        if onset is not None:
            events += 1
            if onset >= WARNABLE:
                warnable += 1
                pre = [i for i in a if onset - LOOKBACK <= i < onset]
                if pre:
                    wt = onset - pre[0]; warn_times.append(wt)
                    warned += int(wt >= HORIZON)
        # split alerting into runs, then re-count every REALERT minutes of continuous alerting
        runs, cur = [], []
        for i in a:
            if cur and i != cur[-1] + 1:
                runs.append(cur); cur = []
            cur.append(i)
        if cur:
            runs.append(cur)
        for r in runs:
            for k in range(0, len(r), REALERT):
                start = r[k]
                if onset is None or not (start <= onset <= start + 15):
                    false_alerts += 1
    return {"drops": events, "warnable_drops": warnable,
            "sensitivity_10min": round(warned / warnable, 3) if warnable else None,
            "median_warning_min": float(np.median(warn_times)) if warn_times else None,
            "false_alerts_per_h": round(false_alerts / (minutes / 60), 2),
            "time_alerting": round(alert_min / minutes, 3)}


def pick(scores, idx, eps, grid, limit, hi):
    best = None
    for thr in grid:
        s = score(eps, alerts_from(scores, idx, thr, len(eps), hi))
        if s["false_alerts_per_h"] <= limit and (best is None or s["sensitivity_10min"] > best[1]["sensitivity_10min"]
                                                 or (s["sensitivity_10min"] == best[1]["sensitivity_10min"] and s["time_alerting"] > best[1]["time_alerting"])):
            best = (float(thr), s)
    return best


rng = np.random.default_rng(503)
train = [episode(rng) for _ in range(300)]
test = [episode(np.random.default_rng(90_000 + k)) for k in range(150)]
Xtr, ytr, itr = build(train)
Xte, yte, ite = build(test)
mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit((Xtr - mu) / sd, ytr)
ptr = clf.predict_proba((Xtr - mu) / sd)[:, 1]
pte = clf.predict_proba((Xte - mu) / sd)[:, 1]

MGRID, AGRID = np.round(np.linspace(0.05, 0.95, 91), 2), np.round(np.arange(65.0, 75.01, 0.25), 2)
res = {"train_episodes": len(train), "test_episodes": len(test), "warnable_from_minute": WARNABLE,
       "realert_min": REALERT, "operating_points": {}}
for limit in (1.0, 2.0):
    m = pick(ptr, itr, train, MGRID, limit, True)
    a = pick(Xtr[:, 0], itr, train, AGRID, limit, False)
    res["operating_points"][f"{limit:g}"] = {
        "model": {"threshold": m[0], "train": m[1], "test": score(test, alerts_from(pte, ite, m[0], len(test), True))},
        "map_alarm": {"threshold_mmHg": a[0], "train": a[1], "test": score(test, alerts_from(Xte[:, 0], ite, a[0], len(test), False))}}
# matched time alerting, on the test set, for context only
res["curve_test"] = {"model": [dict(thr=float(t), **score(test, alerts_from(pte, ite, t, len(test), True))) for t in np.round(np.linspace(0.1, 0.9, 17), 2)],
                     "map_alarm": [dict(thr=float(t), **score(test, alerts_from(Xte[:, 0], ite, t, len(test), False))) for t in np.arange(66, 75, 0.5)]}
res["note"] = "Synthetic dry run: the same model generates training and test data, so results are optimistic and do not verify DI-03."
(HERE / "forecaster_results_v2.json").write_text(json.dumps(res, indent=2))
print(json.dumps({k: v for k, v in res.items() if k != "curve_test"}, indent=1))
for k in ("model", "map_alarm"):
    print(k)
    for r in res["curve_test"][k]:
        print("  ", r["thr"], r["sensitivity_10min"], r["false_alerts_per_h"], r["time_alerting"], r["median_warning_min"])
