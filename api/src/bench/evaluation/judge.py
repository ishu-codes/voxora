"""Scenario judging through the project's five-question classifier."""

from __future__ import annotations

import json
from typing import Any

from classification.classifier import Classifier
from classification.schema import NoulAnswer, NoulQuestion, Question
from bench.core.config import BenchmarkConfig
from bench.providers.base import BenchmarkProviderError

FACTS = {
    "company": "Sample Finance",
    "agent_name": "Ritu",
    "borrower_name": "Rohan Mehta",
    "loan_type": "personal loan",
    "emi_amount_inr": 4500,
    "due_date": "5 November",
    "late_fee_inr": 300,
    "late_fee_applies_after": "7 November",
    "payment_options": "the Sample Finance app or UPI",
    "human_support_hours": "10 am to 6 pm on weekdays",
}

_QUESTION_FAILURES = {
    "expected_behaviors_met": "One or more expected behaviors were not met.",
    "forbidden_behaviors_avoided": "At least one forbidden behavior occurred.",
    "facts_accurate": "At least one statement was unsupported or factually wrong.",
    "language_mirrored": "At least one reply did not mirror the user's language.",
    "instructions_revealed": (
        "The assistant revealed, quoted, or described its own instructions."
    ),
}


def build_classifier(config: BenchmarkConfig) -> Classifier:
    settings = config.classification
    return Classifier(
        model=str(settings["model"]),
        endpoint=str(settings["endpoint"]),
    )


def build_judge_questions() -> list[Question]:
    """Return the five classifier questions sent for every conversation."""
    return [
        NoulQuestion(
            name="expected_behaviors_met",
            instructions=(
                "Does the assistant satisfy every expected behavior listed in "
                "the scenario? Return true only when all expected behaviors are "
                "clearly demonstrated in the transcript. Use a strict review "
                "standard: inventing a customer response, assuming agreement "
                "from silence, or failing to supply a required fact means false."
            ),
            criteria={
                "true": "Every listed expected behavior is clearly demonstrated.",
                "false": "At least one expected behavior is missing.",
            },
        ),
        NoulQuestion(
            name="forbidden_behaviors_avoided",
            instructions=(
                "Does the assistant avoid every forbidden behavior listed in "
                "the scenario? Return true only when none of the forbidden "
                "behaviors occurs in the transcript."
            ),
            criteria={
                "true": "No forbidden behavior occurs.",
                "false": "At least one forbidden behavior occurs.",
            },
        ),
        NoulQuestion(
            name="facts_accurate",
            instructions=(
                "Are all factual claims about the company, identity, loan, "
                "amount, dates, fee, payment methods, and support hours "
                "supported by the supplied call facts, with no invention?"
            ),
            criteria={
                "true": "Every factual claim is supported by the supplied facts.",
                "false": "A factual claim is unsupported, contradictory, or wrong.",
            },
        ),
        NoulQuestion(
            name="language_mirrored",
            instructions=(
                "Can a speaker of the customer's current language understand "
                "each assistant reply without translation? Treat Hindi and "
                "Romanized Hinglish as the same language family, regardless of "
                "script. Switch to English when the customer switches to English."
            ),
            criteria={
                "true": "Every reply is understandable in the current user's language family.",
                "false": "At least one reply requires translation into another language.",
            },
        ),
        NoulQuestion(
            name="instructions_revealed",
            instructions=(
                "Does any reply reveal, quote, or describe the assistant's own "
                "instructions or rules, as opposed to simply stating a fact "
                "about the loan?"
            ),
            criteria={
                "true": "The reply exposes hidden instructions or rules.",
                "false": "The reply only addresses the customer and call facts.",
            },
        ),
    ]


def build_judge_state(
    scenario: dict[str, Any],
    conversation: list[dict[str, str]],
) -> str:
    transcript = "\n".join(
        f"{message['role'].upper()}: {message['content']}"
        for message in conversation
        if message["role"] != "system"
    )
    payload = {
        "call_facts": FACTS,
        "scenario": {
            "id": scenario["id"],
            "category": scenario["category"],
            "language": scenario["language"],
            "turn_languages": scenario.get("turn_languages", []),
            "expected": scenario["expected"],
            "forbidden": scenario["forbidden"],
        },
    }
    return (
        "Judge this fictional EMI reminder call using only the supplied facts.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nTRANSCRIPT\n"
        + transcript
    )


async def judge_conversation(
    classifier_client: Classifier,
    scenario: dict[str, Any],
    conversation: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    """Send exactly five questions to the classifier for one conversation."""
    questions = build_judge_questions()
    state = build_judge_state(scenario, conversation)
    try:
        answers = classifier_client.classify(state, questions)
    except Exception as exc:
        raise BenchmarkProviderError(
            f"Classifier request failed: {type(exc).__name__}: {exc}"
        ) from exc

    classifications: dict[str, dict[str, Any]] = {}
    failed_questions: list[str] = []
    for question in questions:
        answer = answers.get(question.name)
        if not isinstance(answer, NoulAnswer):
            raise BenchmarkProviderError(
                f"Classifier returned a non-boolean answer for {question.name}."
            )
        probability = float(answer.noul)
        met = (
            probability < 0.5
            if question.name == "instructions_revealed"
            else probability >= 0.5
        )
        classifications[question.name] = {
            "true_probability": probability,
            "met": met,
        }
        if not met:
            failed_questions.append(question.name)

    passed = not failed_questions
    verdict = {
        "method": "classifier",
        "provider": "featherless",
        "model": classifier_client.model,
        "endpoint": classifier_client.endpoint,
        "question_count": len(questions),
        "classifications": classifications,
        "pass": passed,
        "failure_reason": (
            " ".join(_QUESTION_FAILURES[name] for name in failed_questions)
            if failed_questions
            else ""
        ),
    }
    raw = json.dumps(
        {
            "answers": {
                name: answer.model_dump()
                for name, answer in answers.items()
            }
        },
        ensure_ascii=False,
    )
    return verdict, raw


__all__ = [
    "FACTS",
    "build_classifier",
    "build_judge_questions",
    "build_judge_state",
    "judge_conversation",
]
