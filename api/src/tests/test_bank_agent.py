import json
from pathlib import Path

import pytest

from src.voice.agent.documents import (
    DocumentToolError,
    execute_document_tool,
    list_documents,
    read_document,
)
from src.voice.agent.protocol import parse_agent_decision

QUESTIONS_PATH = (
    Path(__file__).resolve().parents[3] / "bank" / "demo_bank_questions.json"
)


def test_demo_bank_document_tools_list_and_read_allowlisted_files():
    documents = list_documents()

    assert [document["name"] for document in documents] == [
        "account.md",
        "atm_card.md",
        "loan.md",
        "money_transfer.md",
        "safety.md",
    ]
    assert all(document["title"] for document in documents)
    assert all(document["description"] for document in documents)
    content = read_document("account.md")
    assert "Demo Bank" in content
    assert "## Overview" in content


@pytest.mark.parametrize("name", ["../account.md", "/etc/passwd", "unknown.md", ""])
def test_demo_bank_document_tools_reject_unknown_or_path_names(name):
    with pytest.raises(DocumentToolError):
        read_document(name)


def test_demo_bank_document_tool_returns_structured_results():
    listing = execute_document_tool("list_docs", {})
    assert len(listing["documents"]) == 5

    result = execute_document_tool(
        "read_doc",
        {"name": "safety.md"},
    )
    assert result["name"] == "safety.md"
    assert "Demo Bank" in result["content"]


def test_structured_agent_actions_are_parsed_without_guessing():
    tool = parse_agent_decision(
        json.dumps(
            {
                "action": "tool",
                "tool": "read_doc",
                "name": "atm_card.md",
                "notice": "Ek minute, documents check kar raha hoon.",
            }
        )
    )
    assert tool.action == "tool"
    assert tool.tool == "read_doc"
    assert tool.name == "atm_card.md"

    answer = parse_agent_decision('{"action":"answer"}')
    assert answer.action == "answer"

    with pytest.raises(ValueError):
        parse_agent_decision('{"action":"tool","tool":"shell"}')


def test_demo_bank_question_set_is_multilingual_and_covers_required_documents():
    cases = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    assert len(cases) == 12
    assert {case["language"] for case in cases} == {"en", "hi", "hinglish"}
    assert {
        document
        for case in cases
        for document in case["expected_docs"]
    } == {
        "account.md",
        "atm_card.md",
        "loan.md",
        "money_transfer.md",
        "safety.md",
    }
    assert any("balance" in case["question"].lower() for case in cases)
    assert any("OTP" in case["question"] for case in cases)
    assert any(case["id"] == "en_unknown" for case in cases)
