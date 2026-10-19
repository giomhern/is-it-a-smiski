"""Binary metrics with fixed label ordering; no threshold tuning on test data."""

import math

LABEL_NAMES = ["Non-Smiski", "Smiski"]


def calculate_metrics(labels, predictions, probabilities):
    if (
        not labels
        or len(labels) != len(predictions)
        or len(labels) != len(probabilities)
    ):
        raise ValueError(
            "Expected nonempty, equally sized labels, predictions and scores"
        )
    matrix = [[0, 0], [0, 0]]
    for actual, predicted, probability in zip(labels, predictions, probabilities):
        if (
            actual not in (0, 1)
            or predicted not in (0, 1)
            or not math.isfinite(probability)
            or not 0 <= probability <= 1
        ):
            raise ValueError("Invalid binary labels, predictions or probabilities")
        matrix[actual][predicted] += 1
    per_class = {}
    for index, name in enumerate(LABEL_NAMES):
        true_positive = matrix[index][index]
        predicted_count = sum(row[index] for row in matrix)
        support = sum(matrix[index])
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        per_class[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return {
        "count": len(labels),
        "accuracy": sum(matrix[index][index] for index in (0, 1)) / len(labels),
        "macro_f1": sum(row["f1"] for row in per_class.values()) / 2,
        "balanced_accuracy": sum(row["recall"] for row in per_class.values()) / 2,
        "brier_score": sum(
            (score - label) ** 2 for score, label in zip(probabilities, labels)
        )
        / len(labels),
        "confusion_matrix": {
            "rows": LABEL_NAMES,
            "columns": LABEL_NAMES,
            "counts": matrix,
        },
        "per_class": per_class,
    }
