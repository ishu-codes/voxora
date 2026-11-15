"""Safe access to the Demo Bank knowledge documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

BANK_DOCS_DIR = Path(__file__).resolve().parents[4] / "bank" / "demo_bank"


class DocumentToolError(ValueError):
    """A document name or document file cannot be used by the agent."""


@dataclass(frozen=True)
class DocumentInfo:
    name: str
    title: str
    description: str

    def public(self) -> dict[str, str]:
        return asdict(self)


def _front_matter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentToolError(f"Unable to read {path.name}.") from exc
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DocumentToolError(f"{path.name} is missing front matter.")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    raise DocumentToolError(f"{path.name} has unterminated front matter.")


@lru_cache(maxsize=1)
def _documents() -> dict[str, DocumentInfo]:
    documents: dict[str, DocumentInfo] = {}
    for path in sorted(BANK_DOCS_DIR.glob("*.md")):
        front = _front_matter(path)
        title = front.get("title", "").strip()
        description = front.get("description", "").strip()
        if not title or not description:
            raise DocumentToolError(
                f"{path.name} needs title and description front matter."
            )
        documents[path.name] = DocumentInfo(
            name=path.name,
            title=title,
            description=description,
        )
    if not documents:
        raise DocumentToolError(f"No Demo Bank documents found in {BANK_DOCS_DIR}.")
    return documents


def list_documents() -> list[dict[str, str]]:
    return [document.public() for document in _documents().values()]


def read_document(name: str) -> str:
    if not isinstance(name, str) or name != Path(name).name:
        raise DocumentToolError("Invalid document name.")
    documents = _documents()
    if name not in documents:
        raise DocumentToolError("Unknown document name.")
    path = BANK_DOCS_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentToolError(f"Unable to read {name}.") from exc


def execute_document_tool(
    tool: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool == "list_docs":
        return {"documents": list_documents()}
    if tool == "read_doc":
        name = arguments.get("name")
        content = read_document(str(name or ""))
        return {
            "name": name,
            "title": _documents()[str(name)].title,
            "content": content,
        }
    raise DocumentToolError(f"Unknown tool {tool!r}.")


__all__ = [
    "BANK_DOCS_DIR",
    "DocumentInfo",
    "DocumentToolError",
    "execute_document_tool",
    "list_documents",
    "read_document",
]
