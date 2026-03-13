# Copyright Daniel Lee Barren 2026
from crewai.tools import tool
import os
import re
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("./output")
DOCS_DIR = Path("./docs")


def get_website_search_tool_base():
    """Return a WebsiteSearchTool with local Chroma in project (main.py cleans chroma_db at startup)."""
    from crewai_tools import WebsiteSearchTool

    chroma_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "chroma_db")
    )
    return WebsiteSearchTool(
        config=dict(
            embedder=dict(
                provider="sentence-transformers",
                config=dict(model_name="all-MiniLM-L6-v2"),
            ),
            collection_name=f"generic_consultant_rag_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            persist_directory=chroma_path,
            summarize=False,
        )
    )


@tool("save_to_notes")
def save_to_notes(content: str, filename_prefix: str = "notes") -> str:
    """Persist structured consulting notes to a timestamped text file in ./output.
    Parameters: content (text to write), filename_prefix (optional, default 'notes').
    Returns the path to the written file."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Failed to create output directory at '{OUTPUT_DIR}': {exc}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = re.sub(r"[^\w\-]", "_", (filename_prefix.strip() or "notes")[:64]) or "notes"
    filename = OUTPUT_DIR / f"{safe_prefix}_{timestamp}.txt"
    try:
        with filename.open("w", encoding="utf-8") as f:
            f.write(f"Notes created at {datetime.now().isoformat()}\n\n")
            f.write(content.rstrip() + "\n")
    except OSError as exc:
        return f"Failed to write notes file at '{filename}': {exc}"
    return f"Notes successfully saved to '{filename.resolve()}'"


@tool("read_reference_docs")
def read_reference_docs(directory: str = "") -> str:
    """Read all .md and .txt reference files from ./docs (or optional directory) and return their contents.
    Parameter: directory (optional override; leave empty for ./docs)."""
    if directory and str(directory).strip():
        base_dir = (Path.cwd() / directory).resolve()
        if not str(base_dir).startswith(str(Path.cwd().resolve())):
            return "Invalid input: directory must stay under the project directory."
    else:
        base_dir = DOCS_DIR.resolve()
    if not base_dir.exists():
        return f"No reference docs directory found at '{base_dir}'."
    doc_paths = sorted(
        p for p in base_dir.glob("*") if p.suffix.lower() in {".md", ".txt"} and p.is_file()
    )
    if not doc_paths:
        return f"No .md or .txt reference docs found in '{base_dir}'."
    parts: list[str] = []
    for path in doc_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            parts.append(f"\n---\n[ERROR READING: {path.name}] {exc}\n---\n")
            continue
        parts.append(
            f"\n---\n[START DOCUMENT: {path.name}]\n\n{text.strip()}\n\n[END DOCUMENT: {path.name}]\n---\n"
        )
    return "".join(parts)


