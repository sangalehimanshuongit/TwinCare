"""ONNX toolchain check (not a forecaster): train toy models on VitalDB MAP,
export to ONNX, check ONNX Runtime matches scikit-learn, report file size."""
import glob, json, os, sys, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from skl2onnx import to_onnx
import onnxruntime as ort, onnx

src, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(src, "*.parquet")))[:120]
X, y, case = [], [], []
for ci, f in enumerate(files):
    d = pd.read_parquet(f)
    if "ART_MBP" not in d: continue
    m = d["ART_MBP"].where((d["ART_MBP"] > 20) & (d["ART_MBP"] < 200))
    mm = m.groupby(d["t_s"] // 60).median()           # 1-min medians
    mm = mm.reindex(range(int(mm.index.max()) + 1))
    v = mm.to_numpy(dtype=float)
    for t in range(10, len(v) - 10):
        hist, fut = v[t-10:t], v[t:t+10]
        if np.isnan(hist).any() or np.isnan(fut).all() or hist[-1] < 65:
            continue
        X.append(hist); y.append(int(np.nanmin(fut) < 65)); case.append(ci)
X, y, case = np.asarray(X, np.float32), np.asarray(y), np.asarray(case)
train, test = case < 90, case >= 90                     # split by case
res = {"cases": len(files), "rows": int(len(y)), "positive_rate": float(y.mean())}
models = {
    "logreg": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
    "mlp16": make_pipeline(StandardScaler(), MLPClassifier((16,), max_iter=300, random_state=0)),
}
for name, mdl in models.items():
    mdl.fit(X[train], y[train])
    onx = to_onnx(mdl, X[:1], options={"zipmap": False}, target_opset=17)
    path = os.path.join(out, f"{name}.onnx"); open(path, "wb").write(onx.SerializeToString())
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    p_onnx = sess.run(None, {sess.get_inputs()[0].name: X[test]})[1][:, 1]
    p_skl = mdl.predict_proba(X[test])[:, 1]
    n_par = sum(np.size(a) for a in [getattr(mdl[-1], k, None) for k in ("coef_", "intercept_")] if a is not None)
    if name == "mlp16": n_par = sum(w.size for w in mdl[-1].coefs_) + sum(b.size for b in mdl[-1].intercepts_)
    res[name] = {"onnx_bytes": os.path.getsize(path), "nodes": len(onx.graph.node),
                 "ops": sorted({n.op_type for n in onx.graph.node}),
                 "parameters": int(n_par + 2 * X.shape[1]),     # + scaler mean/scale
                 "max_abs_prob_diff": float(np.max(np.abs(p_onnx - p_skl))),
                 "test_rows": int(test.sum())}
json.dump(res, open(os.path.join(out, "onnx_check.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
