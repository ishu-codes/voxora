import time
from typing import Any

import requests

from .schema import (
    Answer,
    Question,
    ScoreAnswer,
    answer_adapter,
)

CLASSIFICATION_URL = "https://simple-jev-demo-api.featherless.ai/v1/classifier"
CLASSIFICATION_MODEL = "featherless-ai/gemma-4-26B-A4B-classifier"


class Classifier:
    """
    Classifier class to choose/suggest best path based on the situation.

    Usage example:

    classifier = Classifier()
    answers = classifier.classify(
        "Mia has a beautiful cycle. It's color is same as fresh ripe tomatoes?",
        [
            ChoiceQuestion(
                name="color",
                instructions="what's her cycle's color",
                criteria={"red": None, "green": None, "blue": None},
            ),
            ScoreQuestion(
                name="probabilities",
                instructions="what's her cycle's color",
                criteria=["red", "green", "blue"],
            ),
            NoulQuestion(name="checker", instructions="is her cycle's color blue"),
            NoulQuestion(
                name="checker2",
                instructions="is her cycle's color red",
                criteria={
                    "true": "if it's deninitely red",
                    "false": "if it's definitely not red",
                },
            ),
        ],
    )

    for key, val in answers.items():
        print(f"{key}: {val}")
    """

    def __init__(
        self,
        model: str = CLASSIFICATION_MODEL,
        endpoint: str = CLASSIFICATION_URL,
    ) -> None:
        self.model = model
        self.endpoint = endpoint

    def classify(self, state: str, questions: list[Question]) -> dict[str, Answer]:
        all_questions = self._combine_questions(questions)
        last_response: requests.Response | None = None
        for attempt in range(6):
            response = requests.post(
                self.endpoint,
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "state": state,
                    "questions": all_questions,
                },
                timeout=30,
            )
            last_response = response
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(2**attempt, 20))
                continue
            response.raise_for_status()
            return self._combine_answers(response.json()["answers"])
        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("Classifier request failed without a response.")

    def _combine_questions(self, questions: list[Question]) -> dict[str, Any]:
        all_questions: dict[str, Any] = {
            q.name: {**q.model_dump(exclude={"name"}), "type": q.type}
            for q in questions
        }
        return all_questions

    def _combine_answers(self, answers: dict[str, Any]) -> dict[str, Answer]:
        final_answers: dict[str, Any] = {}

        for name, value in answers.items():
            answer = answer_adapter.validate_python(value)

            if isinstance(answer, ScoreAnswer):
                answer.probabilities = {
                    answer.legend[key]: probability
                    for key, probability in answer.probabilities.items()
                }

            final_answers[name] = answer

        return final_answers


classifier = Classifier()
