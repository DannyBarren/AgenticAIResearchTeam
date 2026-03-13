#!/usr/bin/env python
# Copyright Daniel Lee Barren 2026
# Generic Consultant Crew entrypoint – OpenAI gpt-4o-mini by default
import os
import shutil
import sys
import threading
import warnings
from pathlib import Path

from datetime import datetime, date

from generic_consultant_crew.crew import GenericConsultantCrew
from generic_consultant_crew.security_guard import (
    SecurityLimitError,
    SecurityState,
    setup_security_listener,
    describe_security_limits,
)

print("✅ Generic Consultant Crew – Using only ./docs folder for all client materials. Security features fully retained.")

# === CHROMA + ENV SETUP - RUNS FIRST EVERY TIME ===
# 1. Delete global CrewAI cache (old embeddings)
global_cache = os.path.expanduser(r"~\AppData\Local\CrewAI\generic_consultant_crew")
if os.path.exists(global_cache):
    shutil.rmtree(global_cache, ignore_errors=True)

# 2. Force local chroma inside project
local_chroma_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db"))
if os.path.exists(local_chroma_path):
    shutil.rmtree(local_chroma_path, ignore_errors=True)
os.makedirs(local_chroma_path, exist_ok=True)

# 3. Ensure an OpenAI API key exists (required for OpenAI models and some tools)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-your-openai-key-here"

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

MAX_RUNTIME_SECONDS = 25 * 60  # 25 minutes
_security_listener_initialized: bool = False

# === Runtime configuration for industry and client type ===
# These can be overridden via environment variables or by editing defaults here.
INDUSTRY = os.getenv("GENERIC_CONSULTANT_INDUSTRY", "Example industry")
CLIENT_TYPE = os.getenv("GENERIC_CONSULTANT_CLIENT_TYPE", "Example client type")


def clear_memory_cache() -> None:
    """
    Development helper: clear CrewAI memories so each run starts fresh.
    Safe to remove in production once testing is complete.
    """
    try:
        import subprocess

        # Reset all CrewAI memories (short-term, long-term, entity, knowledge)
        subprocess.run(
            ["crewai", "reset-memories", "-a"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # Best-effort only; do not block runs if the CLI is unavailable.
        pass


def _load_docs_summary() -> str:
    """Summarize all .md and .txt files in ./docs once for crew-wide context."""
    docs_dir = Path("docs")
    if not docs_dir.exists():
        return "No ./docs directory found; no client materials are available."

    parts: list[str] = []
    for path in sorted(docs_dir.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            parts.append(f"\n---\n[ERROR READING: {path.name}] {exc}\n---\n")
            continue
        parts.append(
            f"\n---\n[START DOCUMENT: {path.name}]\n\n{text.strip()}\n\n[END DOCUMENT: {path.name}]\n---\n"
        )

    docs_summary = "".join(parts) if parts else "No .md or .txt reference docs found in ./docs."
    return docs_summary


def _default_inputs() -> dict:
    """Default inputs for a generic consulting engagement."""
    now = datetime.now()
    docs_summary = _load_docs_summary()
    return {
        "company_name": "Example Client",
        "industry": INDUSTRY,
        "client_type": CLIENT_TYPE,
        "market": f"{INDUSTRY} market",
        "region": "US",
        "engagement_focus": (
            f"Consulting engagement for a {CLIENT_TYPE} in the {INDUSTRY} industry, "
            "covering market research, competitor analysis, and solution design."
        ),
        "current_year": str(now.year),
        "current_date": now.strftime("%Y%m%d"),
        "reference_docs_summary": docs_summary,
    }


def run():
    """
    Run the Generic Consultant Crew end-to-end for a consulting engagement.
    The crew runs with a 25-minute max runtime and all security guards enabled.
    """
    global _security_listener_initialized

    # For development/testing: start from a clean memory state each run.
    clear_memory_cache()

    Path("docs").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    SecurityState.reset()
    if not _security_listener_initialized:
        setup_security_listener()
        _security_listener_initialized = True

    inputs = _default_inputs()
    result_holder: list = []
    exc_holder: list = []

    def run_crew():
        try:
            out = GenericConsultantCrew().crew().kickoff(inputs=inputs)
            result_holder.append(out)
        except Exception as e:
            exc_holder.append(e)

    thread = threading.Thread(target=run_crew, daemon=True)
    thread.start()
    thread.join(timeout=MAX_RUNTIME_SECONDS)
    if thread.is_alive():
        raise Exception(
            f"Crew run exceeded maximum runtime ({MAX_RUNTIME_SECONDS // 60} minutes). "
            "Check ./logs/security_log_*.txt and consider splitting work."
        )
    if exc_holder:
        e = exc_holder[0]
        if isinstance(e, SecurityLimitError):
            # Interactive security handler: let human decide to quit or restart.
            print("\n[Security] A safety limit was reached during this run.")
            print(f"Reason: {e.message}\n")
            print(describe_security_limits())
            while True:
                choice = input(
                    "Type 'quit' to stop, or 'continue' to restart this run from scratch: "
                ).strip().lower()
                if choice in ("quit", "q"):
                    raise Exception(
                        f"Security limit reached and user chose to quit: {e.message}"
                    )
                if choice in ("continue", "c"):
                    print("Restarting Generic Consultant Crew from scratch with the same inputs...")
                    SecurityState.reset()
                    result_holder.clear()
                    exc_holder.clear()
                    thread = threading.Thread(target=run_crew, daemon=True)
                    thread.start()
                    thread.join(timeout=MAX_RUNTIME_SECONDS)
                    if thread.is_alive():
                        raise Exception(
                            f"Crew run exceeded maximum runtime ({MAX_RUNTIME_SECONDS // 60} minutes). "
                            "Check ./logs/security_log_*.txt and consider splitting work."
                        )
                    if exc_holder:
                        raise Exception(
                            f"An error occurred while running the crew after continue: {exc_holder[0]}"
                        )
                    if result_holder:
                        return result_holder[0]
                    raise Exception("Crew finished without a result after continue.")
                print("Please type 'quit' or 'continue'.")
        raise Exception(f"An error occurred while running the crew: {e}")
    if result_holder:
        return result_holder[0]


def train():
    """
    Train the Generic Consultant Crew for a given number of iterations.
    """
    clear_memory_cache()
    inputs = _default_inputs()
    try:
        GenericConsultantCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        clear_memory_cache()
        GenericConsultantCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the Generic Consultant Crew execution and returns the results.
    """
    clear_memory_cache()
    inputs = _default_inputs()

    try:
        GenericConsultantCrew().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    clear_memory_cache()
    now = datetime.now()
    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "company_name": trigger_payload.get("company_name", ""),
        "industry": trigger_payload.get("industry", INDUSTRY),
        "client_type": trigger_payload.get("client_type", CLIENT_TYPE),
        "market": trigger_payload.get("market", f"{INDUSTRY} market"),
        "region": trigger_payload.get("region", ""),
        "engagement_focus": trigger_payload.get(
            "engagement_focus",
            f"Consulting engagement for a {CLIENT_TYPE} in the {INDUSTRY} industry.",
        ),
        "current_year": str(now.year),
        "current_date": now.strftime("%Y%m%d"),
    }

    Path("docs").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    SecurityState.reset()
    global _security_listener_initialized
    if not _security_listener_initialized:
        setup_security_listener()
        _security_listener_initialized = True

    result_holder: list = []
    exc_holder: list = []

    def run_crew_trigger():
        try:
            out = GenericConsultantCrew().crew().kickoff(inputs=inputs)
            result_holder.append(out)
        except Exception as e:
            exc_holder.append(e)

    thread = threading.Thread(target=run_crew_trigger, daemon=True)
    thread.start()
    thread.join(timeout=MAX_RUNTIME_SECONDS)
    if thread.is_alive():
        raise Exception(f"Crew run exceeded maximum runtime ({MAX_RUNTIME_SECONDS // 60} minutes).")
    if exc_holder:
        e = exc_holder[0]
        if isinstance(e, SecurityLimitError):
            raise Exception(f"Security limit reached: {e.message}")
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
    if result_holder:
        return result_holder[0]

