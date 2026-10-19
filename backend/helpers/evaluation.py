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


def markdown_report(report):
    metrics = report["metrics"]
    lines = [
        f"# {report['title']}",
        "",
        f"Evaluation status: **{report['evaluation_status']}**.",
        "",
        f"Checkpoint SHA-256: `{report['checkpoint_sha256']}`",
        f"Dataset fingerprint: `{report['dataset_fingerprint']}`",
        "",
        f"Partition: `{report['split']}`; photos: {metrics['count']}; duplicate groups: {report['groups']}.",
        "",
    ]
    for warning in report["limitations"]:
        lines += [f"- {warning}"]
    lines += [
        "",
        "## Metrics",
        "",
        f"Accuracy: {metrics['accuracy']:.3%}; macro F1: {metrics['macro_f1']:.4f}; balanced accuracy: {metrics['balanced_accuracy']:.3%}.",
        "",
        f"Brier score: {metrics['brier_score']:.4f} (lower is better; this alone does not establish calibration).",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in metrics["per_class"].items():
        lines.append(
            f"| {name} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['support']} |"
        )
    matrix = metrics["confusion_matrix"]["counts"]
    lines += [
        "",
        "## Confusion matrix",
        "",
        "Rows are folder labels; columns are predictions.",
        "",
        "| Actual / predicted | Non-Smiski | Smiski |",
        "| --- | ---: | ---: |",
        f"| Non-Smiski | {matrix[0][0]} | {matrix[0][1]} |",
        f"| Smiski | {matrix[1][0]} | {matrix[1][1]} |",
        "",
        "## Highest-score mistakes",
        "",
        "Review these before changing labels: some folder labels may be wrong. Scores are uncalibrated.",
        "",
        "| Image (relative to dataset root) | Folder label | Prediction | Score | Source |",
        "| --- | --- | --- | ---: | --- |",
    ]
    failures = sorted(
        (row for row in report["predictions"] if row["label"] != row["prediction"]),
        key=lambda row: -row["score"],
    )
    for row in failures[:20]:
        source = (
            f"[source]({row['source_page']})"
            if (row.get("source_page") or "").startswith("https://")
            else "unknown"
        )
        lines.append(
            f"| `{row['path']}` | {LABEL_NAMES[row['label']]} | {LABEL_NAMES[row['prediction']]} | {row['score']:.3%} | {source} |"
        )
    if not failures:
        lines.append("| No mistakes in this partition | | | | |")
    return "\n".join(lines) + "\n"
