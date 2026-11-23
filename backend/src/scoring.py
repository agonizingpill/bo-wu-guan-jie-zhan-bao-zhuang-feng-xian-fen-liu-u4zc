import hashlib
import json
from functools import lru_cache

import numpy as np
import scipy
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, TargetEncoder

SEED = 2611
THRESHOLD = 0.58
SMOOTHING = 12
VERSION = 'crate-target-logit-v1'
COLUMNS = ('material', 'packing', 'route_type', 'max_rh', 'transfers')


def synthetic_inspections():
    rng = np.random.default_rng(SEED)
    rows, labels = [], []
    for _ in range(960):
        material = str(rng.choice(['bronze', 'paper', 'porcelain']))
        packing = str(rng.choice(['foam', 'suspension', 'double_wall']))
        route = str(rng.choice(['direct', 'transfer', 'mountain']))
        rh = int(rng.integers(38, 83))
        transfers = int(rng.integers(0, 5))
        latent = (-3.8 + {'bronze': 0, 'paper': 0.85, 'porcelain': 1.65}[material]
                  + {'foam': 1.25, 'suspension': 0, 'double_wall': 0.5}[packing]
                  + {'direct': 0, 'transfer': 0.75, 'mountain': 1.25}[route]
                  + 0.052 * (rh - 48) + 0.39 * transfers)
        rows.append([material, packing, route, rh, transfers])
        labels.append(int(rng.random() < 1 / (1 + np.exp(-latent))))
    return np.asarray(rows, dtype=object), np.asarray(labels)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=1)
def trained_model():
    inputs, labels = synthetic_inspections()
    x_train, x_test, y_train, y_test = train_test_split(
        inputs, labels, test_size=0.25, random_state=SEED, stratify=labels)
    features = ColumnTransformer([
        ('categories', TargetEncoder(target_type='binary', smooth=SMOOTHING, cv=5, random_state=SEED), [0, 1, 2]),
        ('measurements', StandardScaler(), [3, 4]),
    ])
    model = make_pipeline(features, LogisticRegression(solver='lbfgs', C=1.0, max_iter=500, random_state=SEED))
    model.fit(x_train, y_train)
    predictions = model.predict_proba(x_test)[:, 1]
    statistics = {
        'model_version': VERSION, 'random_seed': SEED, 'risk_threshold': THRESHOLD,
        'smoothing': SMOOTHING, 'cross_fit_folds': 5, 'test_ratio': 0.25,
        'train_count': len(y_train), 'test_count': len(y_test), 'training_source': 'synthetic',
        'roc_auc': round(float(roc_auc_score(y_test, predictions)), 4),
        'brier_score': round(float(brier_score_loss(y_test, predictions)), 4),
        'training_sha256': sha([inputs.tolist(), labels.tolist()]),
        'solver': 'lbfgs', 'regularization_c': 1.0, 'scikit_learn': sklearn.__version__,
        'numpy': np.__version__, 'scipy': scipy.__version__,
    }
    return model, statistics


def score(snapshot):
    model, statistics = trained_model()
    values = np.asarray([[snapshot[column] for column in COLUMNS]], dtype=object)
    probability = float(model.predict_proba(values)[0, 1])
    transformed = model.named_steps['columntransformer'].transform(values)[0]
    evidence = {**statistics, 'input_sha256': sha(snapshot),
                'encoded_features': dict(zip(COLUMNS, map(float, transformed), strict=True))}
    return probability, 'high' if probability >= THRESHOLD else 'low', evidence
