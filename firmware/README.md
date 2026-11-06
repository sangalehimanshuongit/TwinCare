# Firmware prototypes

Desktop builds of the C code that will run on the board, first written 14 Oct 2026. They follow the board's rules: 32-bit decimal maths, a fixed 1-second step and no memory allocated while running. Each program has a Python test that checks it against a design input.

| Program | What it does | Test | Result |
|---|---|---|---|
| [patient_sim.c](patient_sim.c) | Simulated patient: blood pressure responds to the dose after a delay | [verify_sim.py](verify_sim.py) | Pass. It matches the reference model within 0.0002 mmHg over 6 scenarios (DI-02). The drug takes effect at the set delay in 3 of 3 cases (DI-01) |
| [guard.c](guard.c) | Command guard: rechecks each approved dose just before it runs (DI-05) | [test_guard.py](test_guard.py) | Pass. It rejects all 5,030 unsafe commands with the right reason and accepts all 4,979 safe ones |

Both tests ran again on 2 Nov 2026 from this repository and gave the same results. Full results: [verify_sim_results.json](verify_sim_results.json), [test_guard_results.json](test_guard_results.json).

## Simulated patient

MAP (mean arterial pressure) is the average blood pressure over one heartbeat. The model is:

```
MAP = P0 - D(t) + K * e(t)
```

- **P0:** the starting MAP.
- **D(t):** the scripted fall in pressure that the drug must correct.
- **K:** how strongly this patient responds to the drug.
- **e(t):** the drug effect. It follows the dose after a fixed delay, then rises gradually.

`verify_sim.py` runs 6 scenarios of one hour each: 3 patient variants (K = 70, 85 and 115, with delays of 60, 120 and 180 s) times 2 dosing policies. The *reactive* policy changes the dose after the pressure falls. The *twin* policy doses ahead, from the digital twin's prediction. The test compares all 21,606 seconds with the team's Python reference model, [lag_aware_sim.py](../reference/lag_aware_sim.py).

### Reference model results

`lag_aware_sim.py` compares the two dosing policies on the simulated patient.

| Result | Reactive dosing | Twin dosing |
|---|---|---|
| Time below 65 mmHg | 14.0 min | 6.0 min |
| Dose changes | 20 | 8 |
| Mean time outside 65 to 75 mmHg, 12 patient variants | 20.1 min | 4.7 min |

The target band is 65 to 75 mmHg, with 1 mmHg of measurement noise and a drug delay of about 2 minutes. Next, the team tests the twin against a patient model with a different structure and adds a PID controller (a standard feedback controller) as a second baseline.

## Command guard

The guard runs five checks in this order:

1. **Wrong session:** the command belongs to another session.
2. **Duplicate:** the command ID was seen before (a replay).
3. **Stale:** the command is older than 5 s.
4. **Out of limit:** the dose is outside 0 to 0.5 µg/kg/min.
5. **Step too large:** the change from the current dose is over 0.03 µg/kg/min.

`test_guard.py` sends 10,000 random commands plus 9 edge cases. Rejections by reason: wrong session 1,022, duplicate 1,014, stale 1,031, out of limit 958, step too large 1,005. The hardware watchdog and override switch are a separate layer: see [hardware](../hardware/README.md#safety-circuit-version-1).

## Run

```bash
cc -O2 -std=c99 -o patient_sim patient_sim.c
cc -O2 -std=c99 -o guard guard.c
python3 verify_sim.py
python3 test_guard.py
```

`verify_sim.py` needs numpy and matplotlib. It imports the reference model from `reference/`.
