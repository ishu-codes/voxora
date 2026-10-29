from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, Field, TypeAdapter

# -------------------- Question --------------------


class QuestionType(BaseModel):
    name: str
    instructions: str


class ChoiceQuestion(QuestionType):
    type: ClassVar[Literal["choice"]] = "choice"
    criteria: dict[str, Any]


class ScoreQuestion(QuestionType):
    type: ClassVar[Literal["score"]] = "score"
    criteria: list[str]


class NoulQuestion(QuestionType):
    type: ClassVar[Literal["noul"]] = "noul"
    criteria: dict[Literal["true", "false"], Any] | None = None


Question = Annotated[
    ChoiceQuestion | ScoreQuestion | NoulQuestion,
    Field(discriminator="type"),
]

# -------------------- Answer --------------------


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: float
    probabilities: dict[str, float]


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    confidence: float
    probabilities: dict[str, float]
    score: float
    legend: dict[str, str]


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: float


Answer = Annotated[
    ChoiceAnswer | ScoreAnswer | NoulAnswer,
    Field(discriminator="type"),
]

answer_adapter = TypeAdapter(Answer)
