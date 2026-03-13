<!-- Copyright Daniel Lee Barren 2026 -->

✅ All ChromaDB issues fixed — now 100% local in ./chroma_db. Global cache auto-deleted on every run.

## Generic Consultant Crew – Market Research + Consulting Template

This project is a reusable CrewAI setup for solo consultants in any industry
({industry}, {client_type}). It performs market research, competitor analysis,
solution/architecture design, and note capture using only documents in the
`./docs` folder as context.

The crew performs:

- **Docs summarization** – reads and summarizes all files in `./docs` to
  understand the client's current situation and requirements.
- **Market research** for the specified `industry` and `client_type`.
- **Competitor analysis** of relevant products, services, or platforms.
- **Solution / architecture design** based on the client's materials and goals.
- **Human approval gates** before major decision points and before generating
  the final client package.
- **Notes capture and packaging** into a client-ready deliverable under `output/`.

The team also includes a dedicated Code Writer / Technical Architect agent and a
Business Model & Pricing Strategist to support deeper technical and commercial
work when needed.
One-click beautiful PDF reports are included — professional enough to send
directly to clients.

### Security and cost control (invisible until triggered)

- **Rate limits**: max 15 Serper/search calls and 30 OpenAI LLM calls per run.
- **Cost guardrail**: run stops and asks for human approval if estimated cost exceeds $2.00.
- **Max runtime**: 25 minutes per crew run.
- **Logging**: every tool call and LLM use is recorded in `logs/security_log_YYYYMMDD.txt`.
- No automatic external actions (emails, payments, posts) without human confirmation.

### Installation

- Ensure you have Python >=3.10 <3.14 available.
- Install dependencies (you can use `pip` or `uv`):

```bash
pip install -r requirements.txt
```

- Set your LLM and API keys in `.env` (e.g. `OPENAI_API_KEY`, `MODEL=openai/gpt-4o-mini`, and optional `SERPER_API_KEY` for web search).

### How to Use for Any Client

- **Set industry and client_type**
  - Option 1 (environment variables):
    - `GENERIC_CONSULTANT_INDUSTRY="Roofing"`, `GENERIC_CONSULTANT_CLIENT_TYPE="SaaS startup"`
    - Or any other combination such as HVAC, plumbing, landscaping, SaaS, etc.
  - Option 2 (edit defaults):
    - Open `src/generic_consultant_crew/main.py` and update the `INDUSTRY` and
      `CLIENT_TYPE` defaults near the top of the file.

- **Provide client materials**
  - Drop all client documents, notes, PDFs, requirements, and background
    materials into the `./docs` folder. The crew will use ONLY this folder for
    context.
  - Common files: `docs/app_description.md`, `docs/requirements.txt`,
    `docs/background_notes.md`, exported emails or reports as `.md` or `.txt`.

- **Run for a new client**
  - From the project root:
    ```bash
    crewai run
    ```
  - Or using the script entry point (after install):
    ```bash
    generic_consultant_crew
    ```
  - The run will:
    - Ensure `docs/` and `logs/` exist.
    - Reset security state and start the security listener.
    - Summarize all docs in `./docs`.
    - Execute the consulting workflow with approval gates and rate/cost limits.
    - Write results to `output/` (`reference_docs_summary.md`,
      `market_research.md`, `competitor_analysis.md`,
      `solution_architecture.md`, `client_package.md`, and timestamped
      `notes_*.txt`).

### Providing Your Real App or Business Documentation

- Place your internal app or business documents as `.md` or `.txt` files in the
  **`docs/`** folder.
- At minimum, replace `docs/app_description.md` with your client's internal app
  or business description. The crew will use whatever is here (plus any other
  files in `./docs`) as its only context.

### Running the Flask Web UI

- Install additional web UI dependencies:
  ```bash
  pip install -r web_ui/requirements.txt
  ```

- Start the web interface (this is also the default script entry point):
  ```bash
  generic_consultant_crew
  ```

- Then open `http://localhost:8000` in your browser. From there you can:
  - Describe your consulting project or research goal in a large textarea.
  - Drag and drop client documents; they are saved into `./docs` automatically.
  - Click **Run Agent Team** to launch the full consulting crew.
  - Watch live status updates as the crew progresses.
  - Download individual markdown outputs from the output panel.
  - Click **Download Full Report as PDF** to render `client_package.md` as a
    PDF via WeasyPrint.
