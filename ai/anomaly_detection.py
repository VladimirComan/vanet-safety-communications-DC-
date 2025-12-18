#!/usr/bin/env python3
"""
anomaly_detection.py
====================

AI-based anomaly detection for VANET broadcast storms and misconfigurations.

This module implements multiple anomaly detection approaches:
1. Isolation Forest - efficient unsupervised anomaly detection
2. One-Class SVM - boundary-based outlier detection
3. Autoencoder - reconstruction error-based detection

The models are trained on normal VANET behavior and detect anomalies
such as:
- Broadcast storms (excessive transmission rates)
- Misconfigured nodes (wrong beacon sizes, rates, or alert patterns)
- Duplicate packet storms
- Isolated/deaf nodes

Author: VANET Project Team
Course: Data Communications and Computer Networks
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging
import pickle
import json
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
    roc_auc_score, roc_curve
)
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from feature_extraction import (
    extract_all_features, inject_broadcast_storm_anomaly,
    inject_misconfigured_node_anomaly, preprocess_features,
    normalize_features, split_train_test
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MODEL CLASSES
# ============================================================================

class IsolationForestDetector:
    """
    Isolation Forest-based anomaly detector.

    Isolation Forest works by randomly partitioning data points.
    Anomalies are easier to isolate and thus have shorter average path lengths.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        max_samples: Union[str, float] = 'auto',
        random_state: int = 42
    ):
        """
        Initialize Isolation Forest detector.

        Args:
            contamination: Expected fraction of anomalies
            n_estimators: Number of trees
            max_samples: Samples to train each tree
            random_state: Random seed
        """
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, feature_names: List[str] = None):
        """
        Fit the model on training data (assumed normal).

        Args:
            X: Training feature matrix
            feature_names: Names of features
        """
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.feature_names = feature_names
        self.is_fitted = True
        logger.info(f"Isolation Forest fitted on {len(X)} samples")

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict anomalies.

        Args:
            X: Feature matrix

        Returns:
            Binary predictions (0=normal, 1=anomaly)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)

        # Convert: 1 -> 0 (normal), -1 -> 1 (anomaly)
        return (predictions == -1).astype(int)

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        """
        Get anomaly scores (higher = more anomalous).

        Args:
            X: Feature matrix

        Returns:
            Anomaly scores
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)
        # score_samples returns negative anomaly scores
        # More negative = more anomalous
        scores = -self.model.score_samples(X_scaled)
        return scores

    def save(self, path: str):
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, f)
        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.is_fitted = True
        logger.info(f"Model loaded from {path}")


class OneClassSVMDetector:
    """
    One-Class SVM anomaly detector.

    Learns a decision boundary around normal data points.
    Points outside the boundary are considered anomalies.
    """

    def __init__(
        self,
        nu: float = 0.05,
        kernel: str = 'rbf',
        gamma: str = 'scale'
    ):
        """
        Initialize One-Class SVM detector.

        Args:
            nu: Upper bound on fraction of margin errors / support vectors
            kernel: Kernel type
            gamma: Kernel coefficient
        """
        self.model = OneClassSVM(
            nu=nu,
            kernel=kernel,
            gamma=gamma
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, feature_names: List[str] = None):
        """Fit the model on training data."""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.feature_names = feature_names
        self.is_fitted = True
        logger.info(f"One-Class SVM fitted on {len(X)} samples")

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict anomalies."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        return (predictions == -1).astype(int)

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        """Get anomaly scores."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)
        # decision_function: positive = normal, negative = anomaly
        scores = -self.model.decision_function(X_scaled)
        return scores

    def save(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, f)

    def load(self, path: str):
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.is_fitted = True


class AutoencoderDetector:
    """
    Autoencoder-based anomaly detector.

    Uses reconstruction error to detect anomalies.
    Normal patterns can be reconstructed well, anomalies cannot.
    """

    def __init__(
        self,
        encoding_dim: int = 8,
        hidden_dims: List[int] = None,
        threshold_percentile: float = 95.0
    ):
        """
        Initialize Autoencoder detector.

        Args:
            encoding_dim: Dimension of encoded representation
            hidden_dims: Hidden layer dimensions
            threshold_percentile: Percentile for anomaly threshold
        """
        self.encoding_dim = encoding_dim
        self.hidden_dims = hidden_dims or [32, 16]
        self.threshold_percentile = threshold_percentile
        self.scaler = StandardScaler()
        self.model = None
        self.threshold = None
        self.feature_names = None
        self.is_fitted = False

        # Try to import TensorFlow/Keras
        self._keras_available = False
        try:
            import tensorflow as tf
            from tensorflow import keras
            self._keras_available = True
            self.tf = tf
            self.keras = keras
        except ImportError:
            logger.warning("TensorFlow not available. Using simple autoencoder.")

    def _build_model(self, input_dim: int):
        """Build the autoencoder model."""
        if not self._keras_available:
            return None

        keras = self.keras

        # Encoder
        input_layer = keras.layers.Input(shape=(input_dim,))
        encoded = input_layer

        for dim in self.hidden_dims:
            encoded = keras.layers.Dense(dim, activation='relu')(encoded)
            encoded = keras.layers.Dropout(0.1)(encoded)

        encoded = keras.layers.Dense(self.encoding_dim, activation='relu')(encoded)

        # Decoder
        decoded = encoded
        for dim in reversed(self.hidden_dims):
            decoded = keras.layers.Dense(dim, activation='relu')(decoded)
            decoded = keras.layers.Dropout(0.1)(decoded)

        output_layer = keras.layers.Dense(input_dim, activation='linear')(decoded)

        model = keras.models.Model(input_layer, output_layer)
        model.compile(optimizer='adam', loss='mse')

        return model

    def fit(
        self,
        X: np.ndarray,
        feature_names: List[str] = None,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.1
    ):
        """Fit the autoencoder on training data."""
        X_scaled = self.scaler.fit_transform(X)
        self.feature_names = feature_names

        if self._keras_available:
            self.model = self._build_model(X_scaled.shape[1])
            self.model.fit(
                X_scaled, X_scaled,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=validation_split,
                verbose=0
            )

            # Calculate reconstruction errors and threshold
            reconstructed = self.model.predict(X_scaled, verbose=0)
            errors = np.mean(np.square(X_scaled - reconstructed), axis=1)
            self.threshold = np.percentile(errors, self.threshold_percentile)

            logger.info(f"Autoencoder fitted. Threshold: {self.threshold:.4f}")
        else:
            # Fallback: use simple PCA-based reconstruction
            from sklearn.decomposition import PCA
            self.model = PCA(n_components=min(self.encoding_dim, X_scaled.shape[1]))
            X_encoded = self.model.fit_transform(X_scaled)
            X_reconstructed = self.model.inverse_transform(X_encoded)

            errors = np.mean(np.square(X_scaled - X_reconstructed), axis=1)
            self.threshold = np.percentile(errors, self.threshold_percentile)

            logger.info(f"PCA fallback fitted. Threshold: {self.threshold:.4f}")

        self.is_fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict anomalies based on reconstruction error."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        scores = self.predict_scores(X)
        return (scores > self.threshold).astype(int)

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        """Get reconstruction errors as anomaly scores."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)

        if self._keras_available:
            reconstructed = self.model.predict(X_scaled, verbose=0)
        else:
            X_encoded = self.model.transform(X_scaled)
            reconstructed = self.model.inverse_transform(X_encoded)

        errors = np.mean(np.square(X_scaled - reconstructed), axis=1)
        return errors

    def save(self, path: str):
        """Save model (without Keras model for simplicity)."""
        with open(path, 'wb') as f:
            pickle.dump({
                'scaler': self.scaler,
                'threshold': self.threshold,
                'feature_names': self.feature_names,
                'encoding_dim': self.encoding_dim,
                'hidden_dims': self.hidden_dims
            }, f)

        # Save Keras model separately if available
        if self._keras_available and self.model is not None:
            keras_path = path.replace('.pkl', '_keras.h5')
            self.model.save(keras_path)

    def load(self, path: str):
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.scaler = data['scaler']
        self.threshold = data['threshold']
        self.feature_names = data['feature_names']
        self.encoding_dim = data['encoding_dim']
        self.hidden_dims = data['hidden_dims']
        self.is_fitted = True


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_detector(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray = None,
    detector_name: str = "Detector"
) -> Dict:
    """
    Evaluate detector performance.

    Args:
        y_true: True labels (0=normal, 1=anomaly)
        y_pred: Predicted labels
        scores: Anomaly scores (for ROC AUC)
        detector_name: Name for logging

    Returns:
        Dictionary with evaluation metrics
    """
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    results = {
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'true_positives': int(tp),
        'true_negatives': int(tn),
        'false_positives': int(fp),
        'false_negatives': int(fn),
        'accuracy': (tp + tn) / (tp + tn + fp + fn)
    }

    if scores is not None and len(np.unique(y_true)) > 1:
        try:
            roc_auc = roc_auc_score(y_true, scores)
            results['roc_auc'] = roc_auc
        except:
            results['roc_auc'] = None

    logger.info(f"\n{detector_name} Evaluation:")
    logger.info(f"  Precision: {precision:.3f}")
    logger.info(f"  Recall:    {recall:.3f}")
    logger.info(f"  F1 Score:  {f1:.3f}")
    logger.info(f"  Accuracy:  {results['accuracy']:.3f}")
    if 'roc_auc' in results and results['roc_auc'] is not None:
        logger.info(f"  ROC AUC:   {results['roc_auc']:.3f}")

    return results


def compare_detectors(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str] = None,
    output_dir: str = None
) -> pd.DataFrame:
    """
    Compare multiple anomaly detection approaches.

    Args:
        X_train: Training features (normal data)
        X_test: Test features
        y_test: Test labels
        feature_names: Feature names
        output_dir: Directory to save results

    Returns:
        DataFrame with comparison results
    """
    results = []

    # 1. Isolation Forest
    logger.info("Training Isolation Forest...")
    if_detector = IsolationForestDetector(contamination=0.1)
    if_detector.fit(X_train, feature_names)
    if_pred = if_detector.predict(X_test)
    if_scores = if_detector.predict_scores(X_test)
    if_results = evaluate_detector(y_test, if_pred, if_scores, "Isolation Forest")
    if_results['model'] = 'Isolation Forest'
    results.append(if_results)

    # 2. One-Class SVM
    logger.info("Training One-Class SVM...")
    svm_detector = OneClassSVMDetector(nu=0.1)
    svm_detector.fit(X_train, feature_names)
    svm_pred = svm_detector.predict(X_test)
    svm_scores = svm_detector.predict_scores(X_test)
    svm_results = evaluate_detector(y_test, svm_pred, svm_scores, "One-Class SVM")
    svm_results['model'] = 'One-Class SVM'
    results.append(svm_results)

    # 3. Autoencoder
    logger.info("Training Autoencoder...")
    ae_detector = AutoencoderDetector(threshold_percentile=90)
    ae_detector.fit(X_train, feature_names, epochs=50)
    ae_pred = ae_detector.predict(X_test)
    ae_scores = ae_detector.predict_scores(X_test)
    ae_results = evaluate_detector(y_test, ae_pred, ae_scores, "Autoencoder")
    ae_results['model'] = 'Autoencoder'
    results.append(ae_results)

    # Create comparison DataFrame
    comparison_df = pd.DataFrame(results)

    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save models
        if_detector.save(str(output_dir / "isolation_forest.pkl"))
        svm_detector.save(str(output_dir / "one_class_svm.pkl"))
        ae_detector.save(str(output_dir / "autoencoder.pkl"))

        # Save comparison
        comparison_df.to_csv(output_dir / "model_comparison.csv", index=False)

        # Generate plots
        plot_roc_curves(
            y_test,
            {'Isolation Forest': if_scores, 'One-Class SVM': svm_scores, 'Autoencoder': ae_scores},
            str(output_dir / "roc_curves.png")
        )

        plot_score_distributions(
            y_test,
            {'Isolation Forest': if_scores, 'One-Class SVM': svm_scores, 'Autoencoder': ae_scores},
            str(output_dir / "score_distributions.png")
        )

    return comparison_df


# ============================================================================
# VISUALIZATION
# ============================================================================

def plot_roc_curves(
    y_true: np.ndarray,
    scores_dict: Dict[str, np.ndarray],
    output_path: str
):
    """Plot ROC curves for multiple detectors."""
    plt.figure(figsize=(10, 8))

    for name, scores in scores_dict.items():
        if len(np.unique(y_true)) > 1:
            try:
                fpr, tpr, _ = roc_curve(y_true, scores)
                auc = roc_auc_score(y_true, scores)
                plt.plot(fpr, tpr, label=f'{name} (AUC = {auc:.3f})', linewidth=2)
            except:
                continue

    plt.plot([0, 1], [0, 1], 'k--', label='Random', alpha=0.5)
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curves - Anomaly Detection')
    plt.legend(loc='lower right')
    plt.grid(True, alpha=0.3)

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved ROC curves to {output_path}")


def plot_score_distributions(
    y_true: np.ndarray,
    scores_dict: Dict[str, np.ndarray],
    output_path: str
):
    """Plot anomaly score distributions."""
    n_models = len(scores_dict)
    fig, axes = plt.subplots(1, n_models, figsize=(5 * n_models, 5))

    if n_models == 1:
        axes = [axes]

    for ax, (name, scores) in zip(axes, scores_dict.items()):
        normal_scores = scores[y_true == 0]
        anomaly_scores = scores[y_true == 1]

        ax.hist(normal_scores, bins=50, alpha=0.7, label='Normal', density=True)
        ax.hist(anomaly_scores, bins=50, alpha=0.7, label='Anomaly', density=True)
        ax.set_xlabel('Anomaly Score')
        ax.set_ylabel('Density')
        ax.set_title(f'{name}')
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved score distributions to {output_path}")


def plot_feature_importance(
    detector,
    output_path: str
):
    """Plot feature importance for Isolation Forest."""
    if not hasattr(detector, 'model') or detector.feature_names is None:
        return

    if hasattr(detector.model, 'feature_importances_'):
        importances = detector.model.feature_importances_
    else:
        return

    # Sort by importance
    indices = np.argsort(importances)[::-1]

    plt.figure(figsize=(12, 6))
    plt.bar(range(len(importances)), importances[indices])
    plt.xticks(range(len(importances)),
               [detector.feature_names[i] for i in indices],
               rotation=45, ha='right')
    plt.xlabel('Feature')
    plt.ylabel('Importance')
    plt.title('Feature Importance (Isolation Forest)')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_anomaly_detection_pipeline(
    packet_log_path: str,
    output_dir: str,
    window_size: float = 5.0,
    anomaly_ratio: float = 0.05,
    test_ratio: float = 0.3
) -> Dict:
    """
    Run complete anomaly detection pipeline.

    Args:
        packet_log_path: Path to packet log CSV
        output_dir: Output directory
        window_size: Feature extraction window size
        anomaly_ratio: Fraction of synthetic anomalies to inject
        test_ratio: Fraction of data for testing

    Returns:
        Dictionary with pipeline results
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("VANET Anomaly Detection Pipeline")
    logger.info("=" * 60)

    # 1. Load packet log
    logger.info(f"Loading packet log from {packet_log_path}")
    packet_log = pd.read_csv(packet_log_path)
    logger.info(f"Loaded {len(packet_log)} packets")

    # 2. Extract features
    logger.info("Extracting features...")
    features_df = extract_all_features(packet_log, window_size=window_size)

    if features_df.empty:
        logger.error("No features extracted")
        return None

    logger.info(f"Extracted {len(features_df)} feature vectors")

    # Save raw features
    features_df.to_csv(output_dir / "raw_features.csv", index=False)

    # 3. Inject synthetic anomalies
    logger.info("Injecting synthetic anomalies...")
    features_with_anomalies, labels = inject_broadcast_storm_anomaly(
        features_df, anomaly_ratio=anomaly_ratio
    )

    # Also inject some misconfigured node anomalies
    features_with_anomalies, labels2 = inject_misconfigured_node_anomaly(
        features_with_anomalies, anomaly_ratio=anomaly_ratio/2
    )

    # Combine labels
    labels = np.maximum(labels, labels2)

    logger.info(f"Total anomalies: {np.sum(labels)} ({np.mean(labels)*100:.1f}%)")

    # 4. Preprocess features
    X, feature_names = preprocess_features(features_with_anomalies)
    logger.info(f"Feature matrix shape: {X.shape}")

    # 5. Split data
    # For training, we want mostly normal data
    normal_indices = np.where(labels == 0)[0]
    anomaly_indices = np.where(labels == 1)[0]

    np.random.shuffle(normal_indices)
    n_train = int(len(normal_indices) * (1 - test_ratio))

    train_indices = normal_indices[:n_train]
    test_indices = np.concatenate([normal_indices[n_train:], anomaly_indices])
    np.random.shuffle(test_indices)

    X_train = X[train_indices]
    X_test = X[test_indices]
    y_test = labels[test_indices]

    logger.info(f"Training set: {len(X_train)} samples (all normal)")
    logger.info(f"Test set: {len(X_test)} samples ({np.sum(y_test)} anomalies)")

    # 6. Compare detectors
    logger.info("Comparing anomaly detection models...")
    comparison_df = compare_detectors(
        X_train, X_test, y_test,
        feature_names=feature_names,
        output_dir=str(output_dir)
    )

    print("\n" + "=" * 60)
    print("MODEL COMPARISON RESULTS")
    print("=" * 60)
    print(comparison_df[['model', 'precision', 'recall', 'f1_score', 'accuracy']].to_string(index=False))
    print("=" * 60)

    # Save final report
    report = {
        'timestamp': datetime.now().isoformat(),
        'packet_log': packet_log_path,
        'total_packets': len(packet_log),
        'feature_vectors': len(features_df),
        'anomaly_ratio': anomaly_ratio,
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'test_anomalies': int(np.sum(y_test)),
        'best_model': comparison_df.loc[comparison_df['f1_score'].idxmax(), 'model'],
        'best_f1_score': float(comparison_df['f1_score'].max()),
        'results': comparison_df.to_dict('records')
    }

    with open(output_dir / "pipeline_report.json", 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"\nResults saved to {output_dir}")
    logger.info(f"Best model: {report['best_model']} (F1={report['best_f1_score']:.3f})")

    return report


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="VANET Anomaly Detection"
    )
    parser.add_argument(
        "packet_log",
        help="Path to packet log CSV file"
    )
    parser.add_argument(
        "--output", "-o",
        default="./ai_results",
        help="Output directory"
    )
    parser.add_argument(
        "--window", "-w",
        type=float, default=5.0,
        help="Feature window size (seconds)"
    )
    parser.add_argument(
        "--anomaly-ratio",
        type=float, default=0.05,
        help="Synthetic anomaly ratio"
    )

    args = parser.parse_args()

    results = run_anomaly_detection_pipeline(
        args.packet_log,
        args.output,
        window_size=args.window,
        anomaly_ratio=args.anomaly_ratio
    )

    if results:
        print(f"\nPipeline completed successfully!")
        print(f"Best model: {results['best_model']}")
        print(f"Best F1 Score: {results['best_f1_score']:.3f}")
