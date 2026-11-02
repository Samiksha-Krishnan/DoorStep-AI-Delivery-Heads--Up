"""Delay-risk model: synthetic data -> train LogReg + RandomForest -> keep best by F1."""
import os
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.joblib")
COURIERS = ["amazon", "flipkart", "delhivery", "blue dart", "ecom express", "india post", "ekart"]
COURIER_BAD = {"amazon": .10, "flipkart": .15, "delhivery": .25, "blue dart": .15,
               "ecom express": .28, "india post": .45, "ekart": .22}


def make_synthetic(n=4000, seed=42):
    """Simulated delivery history. Replace with real logged deliveries to improve accuracy."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "courier": rng.choice(COURIERS, n),
        "weekday": rng.integers(0, 7, n),          # Mon=0 .. Sun=6
        "start_hour": rng.integers(8, 20, n),
        "window_len": rng.choice([1, 2, 3, 4, 6, 12], n),
        "rain_mm": rng.exponential(2, n).round(1),
    })
    p = (df.courier.map(COURIER_BAD) + (df.weekday == 6) * .12 + (df.start_hour >= 17) * .10
         + (df.window_len <= 2) * .06 + np.clip(df.rain_mm / 40, 0, .25) + rng.normal(0, .05, n))
    df["delayed"] = (rng.random(n) < np.clip(p, .02, .95)).astype(int)
    return df


def train(verbose=True):
    df = make_synthetic()
    X, y = df.drop(columns="delayed"), df["delayed"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.2, random_state=1, stratify=y)
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), ["courier"])], remainder="passthrough")
    models = {"logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
              "random_forest": RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced", random_state=1)}
    best, best_f1, best_name = None, -1, ""
    for name, clf in models.items():
        pipe = Pipeline([("pre", pre), ("clf", clf)]).fit(Xtr, ytr)
        pred = pipe.predict(Xte)
        f1 = f1_score(yte, pred)
        if verbose:
            print(f"\n== {name}  F1={f1:.3f}")
            print(confusion_matrix(yte, pred))
            print(classification_report(yte, pred))
        if f1 > best_f1:
            best, best_f1, best_name = pipe, f1, name
    joblib.dump(best, MODEL_PATH)
    print(f"Saved best model: {best_name} (F1={best_f1:.3f})")
    return best


_model = None
def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else train()
    return _model


def predict_risk(courier, start, end, rain_mm=0.0):
    c = (courier or "").lower()
    row = pd.DataFrame([{"courier": c if c in COURIERS else "delhivery", "weekday": start.weekday(),
                         "start_hour": start.hour,
                         "window_len": max(1, round((end - start).total_seconds() / 3600)),
                         "rain_mm": float(rain_mm)}])
    p = float(get_model().predict_proba(row)[0][1])
    score = int(round(min(max(p, .03), .95) * 100))
    return score, ("Low" if score < 25 else "Medium" if score < 50 else "High")


def explain(courier, start, end, rain_mm=0.0):
    """Human-readable reasons shown next to the score."""
    c = (courier or "").lower()
    why = [f"{(courier or 'Unknown courier').title()}: past delay rate about {int(COURIER_BAD.get(c, .3) * 100)}%"]
    if start.weekday() == 6: why.append("Sunday deliveries slip more often")
    if start.hour >= 17: why.append("evening slot, rush hour")
    if (end - start).total_seconds() <= 2 * 3600: why.append("narrow window")
    if rain_mm >= 5: why.append("rain expected")
    return why


if __name__ == "__main__":
    train()
