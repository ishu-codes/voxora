"""Five-question classifier metrics shared by clean and noisy STT runs."""

from __future__ import annotations

from typing import Any

from classification.classifier import Classifier
from classification.schema import NoulAnswer, NoulQuestion
from bench.providers.base import BenchmarkProviderError


def _probability(
    classifier_client: Classifier,
    state: str,
    questions: list[NoulQuestion],
) -> dict[str, float]:
    answers = classifier_client.classify(state, questions)
    result: dict[str, float] = {}
    for question in questions:
        answer = answers.get(question.name)
        if not isinstance(answer, NoulAnswer):
            raise BenchmarkProviderError(
                f"Classifier returned non-boolean answer for {question.name}."
            )
        result[question.name] = float(answer.noul)
    return result


def classify_stt_records(
    classifier_client: Classifier,
    records: list[dict[str, Any]],
) -> None:
    """Add semantic and entity metrics using at most five questions per call."""
    for start in range(0, len(records), 5):
        batch = records[start : start + 5]
        lines = []
        questions = []
        for index, record in enumerate(batch):
            item = f"ITEM{index}"
            lines.extend(
                [
                    item,
                    f"REFERENCE: {record['reference']}",
                    f"HYPOTHESIS: {record['raw_hypothesis']}",
                ]
            )
            questions.append(
                NoulQuestion(
                    name=f"semantic_{index}",
                    instructions=(
                        f"For {item}, do the reference and hypothesis say the "
                        "same thing? Ignore Devanagari or Roman script, spelling "
                        "variants, and punctuation."
                    ),
                )
            )
        probabilities = _probability(
            classifier_client,
            "Compare each reference with its hypothesis.\n\n" + "\n".join(lines),
            questions,
        )
        for index, record in enumerate(batch):
            value = probabilities[f"semantic_{index}"]
            record["semantic_match"] = value >= 0.5
            record["semantic_probability"] = value

    entity_items: list[tuple[dict[str, Any], dict[str, str]]] = []
    for record in records:
        for entity in record.get("entities", []):
            entity_items.append((record, entity))
    for start in range(0, len(entity_items), 5):
        batch = entity_items[start : start + 5]
        lines = []
        questions = []
        for index, (record, entity) in enumerate(batch):
            item = f"ENTITY{index}"
            lines.extend(
                [
                    item,
                    f"TYPE: {entity['type']}",
                    f"REFERENCE VALUE: {entity['value']}",
                    f"HYPOTHESIS: {record['raw_hypothesis']}",
                ]
            )
            questions.append(
                NoulQuestion(
                    name=f"contains_{index}",
                    instructions=(
                        f"Does the hypothesis for {item} contain the "
                        f"{entity['type']} value {entity['value']!r}, including "
                        "digits, spoken words, spelling variants, or any script?"
                    ),
                )
            )
        probabilities = _probability(
            classifier_client,
            "Check whether each hypothesis contains its reference entity.\n\n"
            + "\n".join(lines),
            questions,
        )
        for index, (record, entity) in enumerate(batch):
            value = probabilities[f"contains_{index}"]
            record.setdefault("entity_checks", []).append(
                {
                    "type": entity["type"],
                    "reference_value": entity["value"],
                    "matched": value >= 0.5,
                    "probability": value,
                }
            )

    for record in records:
        checks = record.get("entity_checks", [])
        record["entity_accuracy"] = (
            sum(item["matched"] for item in checks) / len(checks)
            if checks
            else None
        )
        record["classifier_question_batches"] = {
            "semantic": "one call per up to five utterances",
            "entity": "one call per up to five entity questions",
        }


__all__ = ["classify_stt_records"]
