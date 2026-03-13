import json
import os
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, Response, render_template, request, jsonify, send_file

# Copyright Daniel Lee Barren 2026
# Ensure the src/ directory (which contains generic_consultant_crew) is importable
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from generic_consultant_crew.crew import GenericConsultantCrew
from generic_consultant_crew.security_guard import (
    SecurityState,
    setup_security_listener,
    SecurityLimitError,
    describe_security_limits,
)

app = Flask(__name__)

DOCS_DIR = BASE_DIR / "docs"
OUTPUT_DIR = BASE_DIR / "output"
GENERATED_CODE_DIR = BASE_DIR / "generated_code"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_CODE_DIR.mkdir(parents=True, exist_ok=True)

_runs: dict[str, dict] = {}
_listener_initialized = False


def _init_security_once() -> None:
    global _listener_initialized
    if not _listener_initialized:
        SecurityState.reset()
        setup_security_listener()
        _listener_initialized = True


def _infer_industry_and_client_type(description: str) -> tuple[str, str]:
    """Infer industry and client_type from run description so YAML placeholders are filled."""
    if not description or not description.strip():
        return "General", "business"
    d = description.strip().lower()
    # Roofers / general contractors / construction
    if "roofer" in d or "roofers" in d or "general contractor" in d or "contractors" in d:
        return "Construction / Contracting", "roofers and general contractors"
    # SaaS / web app
    if "saas" in d or "web app" in d or "software" in d:
        if "hr " in d or "hr tech" in d:
            return "HR Technology", "mid-market companies"
        if "construction" in d or "contractor" in d:
            return "Construction / Contracting", "contractors and field teams"
        return "Software / SaaS", "B2B clients"
    # HVAC / field service
    if "hvac" in d or "maintenance" in d:
        return "Field Services", "regional service companies"
    # Default: use a short label so placeholders aren't literal "Example industry"
    return "General", "business"


def _start_crew_run(run_id: str, project_description: str) -> None:
    _init_security_once()
    from datetime import datetime

    now = datetime.now()
    # Explicitly instruct the Project Manager to coordinate dual outputs:
    # in-app summary + markdown + PDF report.
    instructions = (
        (project_description or "").strip()
        + "\n\n"
        "Project Manager: coordinate the team to produce (1) a concise in-app summary "
        "of key insights and recommendations, (2) a full markdown client package in "
        "./output, and (3) a professional PDF report suitable for direct client delivery."
    )

    env_industry = os.getenv("GENERIC_CONSULTANT_INDUSTRY", "").strip()
    env_client_type = os.getenv("GENERIC_CONSULTANT_CLIENT_TYPE", "").strip()
    inferred_industry, inferred_client_type = _infer_industry_and_client_type(project_description)
    industry = env_industry or inferred_industry
    client_type = env_client_type or inferred_client_type

    inputs = {
        "company_name": "Web UI Client",
        "industry": industry,
        "client_type": client_type,
        "market": f"{industry} market",
        "region": "US",
        "engagement_focus": instructions,
        "current_year": str(now.year),
        "current_date": now.strftime("%Y%m%d"),
    }

    _runs[run_id]["status"] = "running"
    _runs[run_id]["message"] = "Starting Generic Consultant Crew run..."
    _runs[run_id]["events"] = []

    def emit_event(kind: str, message: str, agent: str | None = None) -> None:
        from datetime import datetime as _dt

        entry = {
            "kind": kind,
            "time": _dt.now().strftime("%H:%M:%S"),
            "agent": agent or "system",
            "message": message,
        }
        _runs[run_id]["events"].append(entry)

    try:
        emit_event("progress", "Delegating work to agent team...", "Project Manager")
        out = GenericConsultantCrew().crew().kickoff(inputs=inputs)
        # After the crew finishes, ensure a beautiful PDF exists.
        try:
            _generate_beautiful_pdf()
        except Exception:
            # Do not fail the whole run if PDF generation has issues.
            pass
        _runs[run_id]["status"] = "completed"
        _runs[run_id]["message"] = "Run completed successfully."
        _runs[run_id]["result"] = str(out)
        emit_event("progress", "Run completed successfully.", "system")
    except SecurityLimitError as e:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["message"] = f"Security limit reached: {e.message}\n\n{describe_security_limits()}"
        print(f">>> [web-ui] Run {run_id} security limit: {e.message}")
    except Exception as e:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["message"] = f"Error during run: {e}"
        print(f">>> [web-ui] Run {run_id} failed: {e}", flush=True)
        import traceback
        traceback.print_exc()


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_well_known():
    """Avoid 404 in console when Chrome probes for DevTools config."""
    return "", 204


@app.route("/", methods=["GET"])
def index():
    output_files = []
    if OUTPUT_DIR.exists():
        output_files = sorted(
            [p.name for p in OUTPUT_DIR.iterdir() if p.is_file()],
        )
    return render_template("index.html", output_files=output_files)


@app.route("/upload", methods=["POST"])
def upload():
    print(">>> [web-ui] Received /upload request")
    files = request.files.getlist("files[]")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        if not f.filename:
            continue
        dest = DOCS_DIR / f.filename
        f.save(dest)
        saved.append(dest.name)
    print(f">>> [web-ui] Saved files: {saved}")
    return jsonify({"saved": saved})


@app.route("/run", methods=["POST"])
def run_team():
    print(">>> [web-ui] Received /run request")
    data = request.form or request.json or {}
    description = data.get("description", "")
    print(f">>> [web-ui] Run description: {description!r}")
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"status": "queued", "message": "Queued", "result": None}
    t = threading.Thread(target=_start_crew_run, args=(run_id, description), daemon=True)
    t.start()
    return jsonify({"run_id": run_id})


@app.route("/status/<run_id>", methods=["GET"])
def status(run_id: str):
    info = _runs.get(run_id)
    if not info:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(
        {
            "status": info.get("status"),
            "message": info.get("message"),
        }
    )


@app.route("/stream/<run_id>")
def stream(run_id: str):
    print(f">>> [web-ui] SSE /stream requested for run_id={run_id}")
    def event_stream():
        last_index = 0
        while True:
            info = _runs.get(run_id)
            if not info:
                yield "event: error\ndata: {}\n\n"
                break
            events = info.get("events", [])
            while last_index < len(events):
                ev = events[last_index]
                last_index += 1
                payload = (
                    "event: progress\ndata: "
                    + json.dumps(
                        {
                            "time": ev["time"],
                            "agent": ev["agent"],
                            "message": ev["message"],
                        }
                    )
                    + "\n\n"
                )
                yield payload
            if info.get("status") in {"completed", "error"}:
                # send summary stub
                summary_html = (
                    "Run finished. Download the full markdown and PDF reports for client-ready output."
                )
                yield (
                    "event: summary\ndata: "
                    + json.dumps({"html": summary_html})
                    + "\n\n"
                )
                yield (
                    "event: done\ndata: "
                    + json.dumps({"status": info.get("status")})
                    + "\n\n"
                )
                break
            import time

            # Keepalive so the client connection does not time out
            yield ": keepalive\n\n"
            time.sleep(1.5)

    resp = Response(event_stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        return (
            "Report not generated yet. Run the agent team and wait for completion, or check that the run finished successfully.",
            404,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    return send_file(path, as_attachment=True)


@app.route("/stop/<run_id>", methods=["POST"])
def stop_run(run_id: str):
    info = _runs.get(run_id)
    if not info:
        return jsonify({"error": "Run not found"}), 404
    info["status"] = "stopping"
    info.setdefault("events", []).append(
        {
            "kind": "progress",
            "time": "",
            "agent": "system",
            "message": "Stop requested by user.",
        }
    )
    # Trigger guardrail-based stop on next LLM call
    SecurityState.cost_limit_hit = True  # type: ignore[attr-defined]
    return jsonify({"ok": True})


def _generate_beautiful_pdf() -> Path:
    """Render the main HTML report as a PDF using WeasyPrint and the HTML template."""
    from datetime import datetime
    from flask import render_template as _render

    try:
        from weasyprint import HTML
    except Exception as e:
        raise RuntimeError(
            "WeasyPrint is not available. On Windows, install GTK3 runtime or use WSL. "
            "See https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        ) from e

    html_report_path = OUTPUT_DIR / "client_report.html"
    markdown_package = OUTPUT_DIR / "client_package.md"

    # Fallback: if the dedicated HTML report is not present, wrap the markdown.
    if html_report_path.exists():
        html_body = html_report_path.read_text(encoding="utf-8")
    elif markdown_package.exists():
        html_body = f"<pre>{markdown_package.read_text(encoding='utf-8')}</pre>"
    else:
        html_body = "<p>No report content available.</p>"

    rendered_html = _render(
        "report_template.html",
        company_name="Web UI Client",
        industry=os.getenv("GENERIC_CONSULTANT_INDUSTRY", "Example industry"),
        client_type=os.getenv("GENERIC_CONSULTANT_CLIENT_TYPE", "Example client type"),
        generated_date=datetime.now().strftime("%Y-%m-%d"),
        executive_summary="",
        market_research="",
        competitor_overview="",
        competitor_table="",
        solution_architecture="",
        business_model_pricing="",
        notes_and_next_steps=html_body,
    )

    ts = datetime.now().strftime("%Y%m%d")
    pdf_path = OUTPUT_DIR / f"client_report_{ts}.pdf"
    try:
        HTML(string=rendered_html).write_pdf(str(pdf_path))
    except Exception as e:
        raise RuntimeError(f"WeasyPrint PDF render failed: {e}") from e
    return pdf_path


@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    """Generate (if needed) and return the latest beautiful PDF report."""
    try:
        pdf_path = _generate_beautiful_pdf()
    except RuntimeError as exc:
        err_msg = str(exc)
        if "WeasyPrint" in err_msg or "GTK" in err_msg:
            err_msg = (
                "PDF generation is unavailable: WeasyPrint requires GTK3 on Windows. "
                "Download the Markdown or HTML report from the Outputs panel instead, "
                "or see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
            )
        return jsonify({"error": err_msg, "fallback": "html"}), 503
    except Exception as exc:
        return jsonify({"error": f"Failed to generate PDF: {exc}"}), 500
    if not pdf_path.exists():
        return jsonify({"error": "PDF not found"}), 404
    return send_file(pdf_path, as_attachment=True)


def run():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)


if __name__ == "__main__":
    run()

