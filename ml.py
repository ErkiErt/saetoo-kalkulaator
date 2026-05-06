import streamlit as st
import pandas as pd
from history import HISTORY_FILE

ML_MIN_ROWS_TO_TRAIN  = 10
ML_MIN_ROWS_TO_DECIDE = 20
ML_MAX_ACCEPTABLE_MAE_SEC = 180

try:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

FEATURES = ["materjal_paksus_mm", "toorik_laius_mm", "toorik_pikkus_mm",
            "detail_laius_mm", "detail_pikkus_mm", "detailide_arv",
            "ketas", "avatud_plaadid"]
TARGET = "tegelik_aeg_sek"


@st.cache_resource
def get_trained_model():
    if not SKLEARN_AVAILABLE or not HISTORY_FILE.exists():
        return None, None, None
    try:
        df = pd.read_csv(HISTORY_FILE).dropna(subset=FEATURES + [TARGET])
    except Exception:
        return None, None, None
    if len(df) < ML_MIN_ROWS_TO_TRAIN:
        return None, None, None

    X, y = df[FEATURES], df[TARGET]
    cat_cols = ["ketas"]
    num_cols = [c for c in FEATURES if c not in cat_cols]
    pipeline = Pipeline([
        ("prep", ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ])),
        ("model", RandomForestRegressor(n_estimators=100, random_state=42)),
    ])
    if len(df) >= 20:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        pipeline.fit(X_tr, y_tr)
        mae = mean_absolute_error(y_te, pipeline.predict(X_te))
    else:
        pipeline.fit(X, y)
        mae = None
    return pipeline, mae, len(df)


def predict_result_time(result):
    if not SKLEARN_AVAILABLE:
        return None
    model, mae, n_rows = get_trained_model()
    if model is None:
        return None
    if n_rows < ML_MIN_ROWS_TO_DECIDE:
        return None
    if mae is not None and mae > ML_MAX_ACCEPTABLE_MAE_SEC:
        return None
    try:
        row = pd.DataFrame([{
            "materjal_paksus_mm": result["blade"]["max_stack_mm"],
            "toorik_laius_mm":    result["raw_width_mm"],
            "toorik_pikkus_mm":   result["raw_length_mm"],
            "detail_laius_mm":    result["detail_width_mm"],
            "detail_pikkus_mm":   result["detail_length_mm"],
            "detailide_arv":      result["detail_count"],
            "ketas":              result["blade"]["blade"],
            "avatud_plaadid":     result["opened_sheet_count"],
        }])
        pred = float(model.predict(row)[0])
        low  = result["total_sec"] * 0.25
        high = result["total_sec"] * 3.0
        return max(low, min(high, pred))
    except Exception:
        return None
