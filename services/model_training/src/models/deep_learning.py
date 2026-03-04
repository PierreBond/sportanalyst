from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .base_model import BaseModel, ModelMeta

logger = logger = __import__("structlog").get_logger(__name__)


class CNN1DModel(BaseModel):
    """1D CNN for spatial pattern recognition in match features."""

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._model: nn.Module | None = None
        self._feature_names: list[str] = []
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_dim: int) -> nn.Module:
        """Build CNN architecture."""
        return nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.MaxPool1d(2),
            nn.Dropout(0.3),
            nn.Conv1d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 3),
            nn.Softmax(dim=-1),
        )

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train CNN model."""
        self._feature_names = X_train.columns.tolist()

        X = torch.FloatTensor(X_train.values).unsqueeze(1)

        label_map = {"home_win": 0, "draw": 1, "away_win": 2}
        y = torch.LongTensor([label_map.get(str(v), 1) for v in y_train])

        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        input_dim = X_train.shape[1]
        self._model = self._build_model(input_dim).to(self._device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        for epoch in range(50):
            total_loss = 0
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

        logger.info("cnn_model_trained", epochs=50)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities."""
        if self._model is None:
            return np.array([[0.33, 0.34, 0.33]] * len(X))

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).unsqueeze(1).to(self._device)
            outputs = self._model(X_tensor).cpu().numpy()

        return outputs

    def save(self, path: Path) -> None:
        """Save model."""
        if self._model:
            torch.save({
                "model_state": self._model.state_dict(),
                "feature_names": self._feature_names,
                "meta": {
                    "name": self.meta.name,
                    "version": self.meta.version,
                    "hyperparameters": self.meta.hyperparameters,
                },
            }, path)

    def load(self, path: Path) -> None:
        """Load model."""
        checkpoint = torch.load(path, map_location=self._device)
        self._feature_names = checkpoint["feature_names"]
        input_dim = len(self._feature_names)
        self._model = self._build_model(input_dim).to(self._device)
        self._model.load_state_dict(checkpoint["model_state"])


class LSTMModel(BaseModel):
    """LSTM for sequential pattern recognition in time-series features."""

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._model: nn.Module | None = None
        self._feature_names: list[str] = []
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_dim: int) -> nn.Module:
        """Build LSTM architecture."""
        return nn.Sequential(
            nn.LSTM(input_dim, 64, batch_first=True, num_layers=2, dropout=0.2),
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 3),
            nn.Softmax(dim=-1),
        )

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train LSTM model."""
        self._feature_names = X_train.columns.tolist()

        X = torch.FloatTensor(X_train.values).unsqueeze(1)

        label_map = {"home_win": 0, "draw": 1, "away_win": 2}
        y = torch.LongTensor([label_map.get(str(v), 1) for v in y_train])

        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        input_dim = X_train.shape[1]
        self._model = self._build_model(input_dim).to(self._device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        for epoch in range(50):
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        logger.info("lstm_model_trained", epochs=50)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities."""
        if self._model is None:
            return np.array([[0.33, 0.34, 0.33]] * len(X))

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).unsqueeze(1).to(self._device)
            outputs = self._model(X_tensor).cpu().numpy()

        return outputs

    def save(self, path: Path) -> None:
        """Save model."""
        if self._model:
            torch.save({
                "model_state": self._model.state_dict(),
                "feature_names": self._feature_names,
            }, path)

    def load(self, path: Path) -> None:
        """Load model."""
        checkpoint = torch.load(path, map_location=self._device)
        self._feature_names = checkpoint["feature_names"]
        input_dim = len(self._feature_names)
        self._model = self._build_model(input_dim).to(self._device)
        self._model.load_state_dict(checkpoint["model_state"])


class CNNLSTMModel(BaseModel):
    """Combined CNN-LSTM for spatial-temporal pattern recognition."""

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._model: nn.Module | None = None
        self._feature_names: list[str] = []
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_dim: int) -> nn.Module:
        """Build CNN-LSTM architecture."""
        return nn.Sequential(
            nn.Conv1d(input_dim, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.LSTM(64, 32, batch_first=True, num_layers=2, dropout=0.2),
            nn.Flatten(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(16, 3),
            nn.Softmax(dim=-1),
        )

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train CNN-LSTM model."""
        self._feature_names = X_train.columns.tolist()

        X = torch.FloatTensor(X_train.values).unsqueeze(1)

        label_map = {"home_win": 0, "draw": 1, "away_win": 2}
        y = torch.LongTensor([label_map.get(str(v), 1) for v in y_train])

        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        input_dim = X_train.shape[1]
        self._model = self._build_model(input_dim).to(self._device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        for epoch in range(50):
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        logger.info("cnn_lstm_model_trained", epochs=50)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities."""
        if self._model is None:
            return np.array([[0.33, 0.34, 0.33]] * len(X))

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).unsqueeze(1).to(self._device)
            outputs = self._model(X_tensor).cpu().numpy()

        return outputs

    def save(self, path: Path) -> None:
        """Save model."""
        if self._model:
            torch.save({
                "model_state": self._model.state_dict(),
                "feature_names": self._feature_names,
            }, path)

    def load(self, path: Path) -> None:
        """Load model."""
        checkpoint = torch.load(path, map_location=self._device)
        self._feature_names = checkpoint["feature_names"]
        input_dim = len(self._feature_names)
        self._model = self._build_model(input_dim).to(self._device)
        self._model.load_state_dict(checkpoint["model_state"])


class TransformerModel(BaseModel):
    """Transformer attention model for feature interactions."""

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._model: nn.Module | None = None
        self._feature_names: list[str] = []
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_dim: int) -> nn.Module:
        """Build Transformer architecture."""
        class TransformerClassifier(nn.Module):
            def __init__(self, input_dim: int):
                super().__init__()
                self.embedding = nn.Linear(input_dim, 64)
                self.pos_encoder = nn.Parameter(torch.randn(1, 10, 64))
                encoder_layer = nn.TransformerEncoderLayer(d_model=64, nhead=4, batch_first=True)
                self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
                self.classifier = nn.Sequential(
                    nn.Linear(64, 32),
                    nn.ReLU(),
                    nn.Dropout(0.3),
                    nn.Linear(32, 3),
                    nn.Softmax(dim=-1),
                )

            def forward(self, x):
                x = self.embedding(x)
                x = x + self.pos_encoder[:, :x.size(1), :]
                x = self.transformer(x)
                x = x.mean(dim=1)
                return self.classifier(x)

        return TransformerClassifier(input_dim)

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train Transformer model."""
        self._feature_names = X_train.columns.tolist()

        X = torch.FloatTensor(X_train.values).unsqueeze(1)

        label_map = {"home_win": 0, "draw": 1, "away_win": 2}
        y = torch.LongTensor([label_map.get(str(v), 1) for v in y_train])

        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        input_dim = X_train.shape[1]
        self._model = self._build_model(input_dim).to(self._device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        for epoch in range(50):
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        logger.info("transformer_model_trained", epochs=50)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities."""
        if self._model is None:
            return np.array([[0.33, 0.34, 0.33]] * len(X))

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).unsqueeze(1).to(self._device)
            outputs = self._model(X_tensor).cpu().numpy()

        return outputs

    def save(self, path: Path) -> None:
        """Save model."""
        if self._model:
            torch.save({
                "model_state": self._model.state_dict(),
                "feature_names": self._feature_names,
            }, path)

    def load(self, path: Path) -> None:
        """Load model."""
        checkpoint = torch.load(path, map_location=self._device)
        self._feature_names = checkpoint["feature_names"]
        input_dim = len(self._feature_names)
        self._model = self._build_model(input_dim).to(self._device)
        self._model.load_state_dict(checkpoint["model_state"])


class TabNetModel(BaseModel):
    """TabNet model for tabular data with attention-based feature selection."""

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._model: nn.Module | None = None
        self._feature_names: list[str] = []
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_model(self, input_dim: int) -> nn.Module:
        """Build TabNet-like architecture."""

        class TabNetBlock(nn.Module):
            def __init__(self, input_dim: int, shared_dim: int = 32):
                super().__init__()
                self.fc = nn.Linear(input_dim, shared_dim)
                self.bn = nn.BatchNorm1d(shared_dim)
                self.attention = nn.Linear(shared_dim, input_dim)

            def forward(self, x):
                h = torch.relu(self.bn(self.fc(x)))
                mask = torch.softmax(self.attention(h), dim=-1)
                return h * mask

        return nn.Sequential(
            TabNetBlock(input_dim, 64),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 3),
            nn.Softmax(dim=-1),
        )

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train TabNet model."""
        self._feature_names = X_train.columns.tolist()

        X = torch.FloatTensor(X_train.values)

        label_map = {"home_win": 0, "draw": 1, "away_win": 2}
        y = torch.LongTensor([label_map.get(str(v), 1) for v in y_train])

        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        input_dim = X_train.shape[1]
        self._model = self._build_model(input_dim).to(self._device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        for epoch in range(50):
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)

                optimizer.zero_grad()
                outputs = self._model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        logger.info("tabnet_model_trained", epochs=50)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities."""
        if self._model is None:
            return np.array([[0.33, 0.34, 0.33]] * len(X))

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).to(self._device)
            outputs = self._model(X_tensor).cpu().numpy()

        return outputs

    def save(self, path: Path) -> None:
        """Save model."""
        if self._model:
            torch.save({
                "model_state": self._model.state_dict(),
                "feature_names": self._feature_names,
            }, path)

    def load(self, path: Path) -> None:
        """Load model."""
        checkpoint = torch.load(path, map_location=self._device)
        self._feature_names = checkpoint["feature_names"]
        input_dim = len(self._feature_names)
        self._model = self._build_model(input_dim).to(self._device)
        self._model.load_state_dict(checkpoint["model_state"])


def create_cnn_model(hidden_dims: list[int] | None = None) -> CNN1DModel:
    """Factory for CNN model."""
    meta = ModelMeta(
        name="cnn_1d",
        version="1.0",
        hyperparameters={"hidden_dims": hidden_dims or [64, 128, 256]},
    )
    return CNN1DModel(meta)


def create_lstm_model(hidden_size: int = 64) -> LSTMModel:
    """Factory for LSTM model."""
    meta = ModelMeta(
        name="lstm",
        version="1.0",
        hyperparameters={"hidden_size": hidden_size},
    )
    return LSTMModel(meta)


def create_cnn_lstm_model() -> CNNLSTMModel:
    """Factory for CNN-LSTM model."""
    meta = ModelMeta(
        name="cnn_lstm",
        version="1.0",
        hyperparameters={},
    )
    return CNNLSTMModel(meta)


def create_transformer_model(n_heads: int = 4) -> TransformerModel:
    """Factory for Transformer model."""
    meta = ModelMeta(
        name="transformer",
        version="1.0",
        hyperparameters={"n_heads": n_heads},
    )
    return TransformerModel(meta)


def create_tabnet_model() -> TabNetModel:
    """Factory for TabNet model."""
    meta = ModelMeta(
        name="tabnet",
        version="1.0",
        hyperparameters={},
    )
    return TabNetModel(meta)
