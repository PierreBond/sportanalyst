from __future__ import annotations

from .base_model import BaseModel, ModelMeta
from .poisson import PoissonModel
from .bayesian import BayesianTeamModel as BayesianModel
from .gradient_boosting import XGBoostModel, RandomForestModel
from .injury_risk import InjuryRiskModel

try:
    from .deep_learning import (
        CNN1DModel as CNNModel,
        LSTMModel,
        CNNLSTMModel,
        TransformerModel,
        TabNetModel,
    )
except ImportError:
    CNNModel = None
    LSTMModel = None
    CNNLSTMModel = None
    TransformerModel = None
    TabNetModel = None

__all__ = [
    "BaseModel",
    "ModelMeta",
    "PoissonModel",
    "BayesianModel",
    "XGBoostModel",
    "RandomForestModel",
    "InjuryRiskModel",
]

if CNNModel is not None:
    __all__.extend([
        "CNNModel",
        "LSTMModel",
        "CNNLSTMModel",
        "TransformerModel",
        "TabNetModel",
    ])
