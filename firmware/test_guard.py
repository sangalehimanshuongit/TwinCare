"""Test suite for the command guard (DI-05, software half).

An independent Python oracle labels every command from the written rules, then the
compiled C guard checks the same stream. The suite passes only if every unsafe
command is rejected for the right reason and every safe command is accepted.
"""
import json, random, subprocess, pathlib
from collections import Counter

HERE = pathlib.Path(__file__).parent
SESSION, U_MIN, U_MAX, STEP, FRESH = 42, 0.0, 0.5, 0.03, 5000
NAMES = {0: "accepted", 1: "wrong session", 2: "duplicate", 3: "stale", 4: "out of limit", 5: "step too large"}


def oracle(cmds):
    cur, last = 0.05, None
    out = []
    for cid, sess, dose, issued, now in cmds:
        if sess != SESSION: r = 1
        elif last is not None and cid <= last: r = 2
        elif now < issued or now - issued > FRESH: r = 3
        elif dose < U_MIN or dose > U_MAX: r = 4
        elif abs(dose - cur) > STEP + 1e-6: r = 5
        else: r = 0
        if r == 0: cur, last = dose, cid
        out.append(r)
    return out


rng = random.Random(501)
cmds, cid, now, cur = [], 0, 10_000, 0.05
# Edge cases first: exact boundaries that must be accepted, and just-over values that must not.
edge = [
    (1, SESSION, 0.08, now, now),            # +0.03 exactly: accept
    (2, SESSION, 0.08, now, now + FRESH),    # age exactly 5 s, no change: accept
    (3, SESSION, 0.08, now, now + FRESH + 1),  # 1 ms too old: stale
    (3, SESSION, 0.08, now + 6000, now + 6000),  # id 3 already used? no, 3 was rejected so id 3 is free: accept
    (3, SESSION, 0.08, now + 6000, now + 6000),  # replay of id 3: duplicate
    (4, 7, 0.08, now + 6000, now + 6000),    # wrong session
    (5, SESSION, 0.12, now + 6000, now + 6000),  # +0.04: step too large
    (6, SESSION, 0.51, now + 6000, now + 6000),  # above max: out of limit
    (7, SESSION, -0.01, now + 6000, now + 6000), # below min: out of limit
]
cmds += edge
cid = 7
# Track the guard's state as the oracle would, so valid commands are realistic steps from the current dose.
state_cur, state_last = 0.08, 3   # after the edge cases: id 3 accepted at 0.08
def step_from(cur, lo, hi):
    for _ in range(50):
        d = round(cur + rng.choice([-1, 1]) * rng.uniform(lo, hi), 3)
        if U_MIN <= d <= U_MAX: return d
    return round(cur, 3)
for i in range(10_000):
    kind = rng.choices(["ok", "session", "dup", "stale", "limit", "step"], weights=[50, 10, 10, 10, 10, 10])[0]
    now += rng.randint(200, 1500)
    cid += 1
    c = [cid, SESSION, step_from(state_cur, 0.0, 0.029), now - rng.randint(0, FRESH), now]
    if kind == "session": c[1] = rng.choice([0, 7, 41, 43, 999])
    elif kind == "dup": c[0] = rng.randint(1, state_last)
    elif kind == "stale": c[3] = now - rng.randint(FRESH + 1, 60_000)
    elif kind == "limit": c[2] = rng.choice([round(rng.uniform(0.501, 2.0), 3), round(rng.uniform(-1.0, -0.001), 3)])
    elif kind == "step": c[2] = step_from(state_cur, 0.035, 0.2)
    cmds.append(tuple(c))
    # update tracked state with the same rules the oracle uses
    cid_, sess_, dose_, iss_, now_ = c
    ok = (sess_ == SESSION and cid_ > state_last and 0 <= now_ - iss_ <= FRESH and U_MIN <= dose_ <= U_MAX and abs(dose_ - state_cur) <= STEP + 1e-6)
    if ok: state_cur, state_last = dose_, cid_

expected = oracle(cmds)
proc = subprocess.run([str(HERE / "guard")], input="\n".join(",".join(str(x) for x in c) for c in cmds),
                      capture_output=True, text=True, check=True)
got = [int(x) for x in proc.stdout.split()]
assert len(got) == len(expected)
mismatch = [(i, cmds[i], expected[i], got[i]) for i in range(len(cmds)) if expected[i] != got[i]]
exp_c, got_c = Counter(expected), Counter(got)
unsafe = sum(1 for e in expected if e != 0)
unsafe_rejected = sum(1 for e, g in zip(expected, got) if e != 0 and g != 0)
safe = sum(1 for e in expected if e == 0)
safe_accepted = sum(1 for e, g in zip(expected, got) if e == 0 and g == 0)
summary = {
    "commands": len(cmds), "edge_cases": len(edge),
    "unsafe": unsafe, "unsafe_rejected": unsafe_rejected,
    "safe": safe, "safe_accepted": safe_accepted,
    "reason_mismatches": len(mismatch),
    "by_reason_expected": {NAMES[k]: v for k, v in sorted(exp_c.items())},
    "edge_results": [NAMES[g] for g in got[:len(edge)]],
    "c_log": proc.stderr.strip(),
    "pass": not mismatch and unsafe == unsafe_rejected and safe == safe_accepted,
}
(HERE / "test_guard_results.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
