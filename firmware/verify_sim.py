"""Dry-run verification of the simulator firmware logic against the team's reference model.

DI-02 (simulator fidelity): firmware output matches the desktop reference within ±0.5 mmHg
on scripted scenarios.
DI-01 (MAP responds to dose): MAP starts to respond within the configured delay ±5 s.

The reference is lag_aware_sim.py, imported unchanged. Its noise-free MAP (true_map) is the
comparison target. Scenarios reuse the dose histories the reference itself produced.
"""
import json, subprocess, sys, pathlib
import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "reference"))
import lag_aware_sim as ref  # noqa: E402

BIN = HERE / "patient_sim"


def run_fw(doses, k, td, tau, d_max=ref.D_MAX, d_start=ref.D_START, d_ramp=ref.D_RAMP):
    args = [str(BIN), str(k), str(int(td)), str(tau), str(ref.P0), str(ref.U0), str(d_max), str(d_start), str(d_ramp)]
    out = subprocess.run(args, input="\n".join(f"{d:.6f}" for d in doses), capture_output=True, text=True, check=True).stdout
    return np.array([float(l.split(",")[1]) for l in out.strip().splitlines()])


results = {"DI-02": [], "DI-01": []}
# DI-02: 6 scripted scenarios = 3 patient variants x 2 dosing policies
for k, td in ((70, 60), (85, 120), (115, 180)):
    for policy in ("reactive", "twin"):
        t, true_map, u_hist, _ = ref.simulate(policy, k=k, td=td, tau=ref.TAU_TRUE, seed=7)
        fw = run_fw(u_hist, k, td, ref.TAU_TRUE)
        err = float(np.max(np.abs(fw - true_map)))
        results["DI-02"].append({"K": k, "delay_s": td, "policy": policy, "seconds": len(fw), "max_abs_err_mmHg": err, "pass": err <= 0.5})

# DI-01: dose step with no disturbance, measure response onset against the configured delay
for td in (60, 120, 180):
    n, step_at = 1200, 300
    doses = [ref.U0] * step_at + [ref.U0 + 0.10] * (n - step_at)
    fw = run_fw(doses, ref.K_TRUE, td, ref.TAU_TRUE, d_max=0.0)
    base = fw[step_at - 1]
    onset = next(i for i in range(step_at, n) if fw[i] - base > 0.01)
    measured = onset - step_at
    results["DI-01"].append({"configured_delay_s": td, "measured_onset_s": int(measured), "error_s": int(measured - td), "pass": abs(measured - td) <= 5})

summary = {
    "DI-02": {"scenarios": len(results["DI-02"]), "all_pass": all(r["pass"] for r in results["DI-02"]),
              "worst_err_mmHg": max(r["max_abs_err_mmHg"] for r in results["DI-02"]),
              "seconds_compared": sum(r["seconds"] for r in results["DI-02"])},
    "DI-01": {"cases": len(results["DI-01"]), "all_pass": all(r["pass"] for r in results["DI-01"]),
              "worst_error_s": max(abs(r["error_s"]) for r in results["DI-01"])},
}
(HERE / "verify_sim_results.json").write_text(json.dumps({"summary": summary, "detail": results}, indent=2))
print(json.dumps(summary, indent=2))
