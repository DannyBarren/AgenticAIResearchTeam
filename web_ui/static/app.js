// Copyright Daniel Lee Barren 2026
console.log("app.js script started");

document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ app.js loaded and DOM ready");

  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileList = document.getElementById("file-list");
  const runButton = document.getElementById("run-button");
  const stopButton = document.getElementById("stop-button");
  const statusText = document.getElementById("status-text");
  const progressFeed = document.getElementById("progress-feed");
  const statusPill = document.getElementById("status-pill");
  const summary = document.getElementById("summary");
  const downloadMd = document.getElementById("download-md");
  const downloadPdfBtn = document.getElementById("download-pdf");
  const runSpinner = document.getElementById("run-spinner");
  const clearAllBtn = document.getElementById("clear-all");
  const sidebarEngagement = document.getElementById("sidebar-engagement");
  const newEngagementBtn = document.getElementById("new-engagement");
  const outputFiles = document.getElementById("output-files");

  let currentRunId = null;
  let currentSource = null;

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function setStatusPill(state) {
    const base =
      "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] transition-colors";
    if (!statusPill) return;
    if (state === "running" || state === "queued") {
      statusPill.className = `${base} border-cyan-400/60 text-cyan-200`;
      statusPill.textContent = state === "running" ? "Running" : "Queued";
    } else if (state === "completed") {
      statusPill.className = `${base} border-emerald-400/60 text-emerald-200`;
      statusPill.textContent = "Completed";
    } else if (state === "error") {
      statusPill.className = `${base} border-rose-400/60 text-rose-200`;
      statusPill.textContent = "Error";
    } else if (state === "stopped") {
      statusPill.className = `${base} border-amber-400/60 text-amber-200`;
      statusPill.textContent = "Stopped";
    } else {
      statusPill.className = `${base} border-slate-600 text-slate-300`;
      statusPill.textContent = "Idle";
    }
  }

  function handleFiles(files) {
    if (!files || files.length === 0) return;
    const formData = new FormData();
    Array.from(files).forEach((f) => formData.append("files[]", f));
    fetch("/upload", {
      method: "POST",
      body: formData,
    })
      .then((r) => r.json())
      .then((data) => {
        (data.saved || []).forEach((name) => {
          const li = document.createElement("li");
          li.textContent = name;
          if (fileList) fileList.appendChild(li);
        });
      })
      .catch((err) => {
        console.error(err);
        alert("Error uploading files.");
      });
  }

  function refreshOutputList() {
    fetch("/")
      .then((r) => r.text())
      .then((html) => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        const newList = doc.getElementById("output-files");
        if (newList && outputFiles) outputFiles.innerHTML = newList.innerHTML;
      })
      .catch((err) => console.error(err));
  }

  function startEventStream(runId) {
    if (!runId) return;
    if (currentSource) currentSource.close();
    const source = new EventSource(`/stream/${runId}`);
    currentSource = source;
    if (progressFeed) progressFeed.textContent = "";

    source.addEventListener("progress", (event) => {
      const data = JSON.parse(event.data);
      const line = `[${data.time}] [${data.agent || "system"}] ${data.message}\n`;
      if (progressFeed) {
        progressFeed.textContent += line;
        progressFeed.scrollTop = progressFeed.scrollHeight;
      }
    });

    source.addEventListener("summary", (event) => {
      const data = JSON.parse(event.data);
      if (summary) summary.innerHTML = `<div class="text-xs text-slate-200">${data.html}</div>`;
    });

    source.addEventListener("done", (event) => {
      const data = JSON.parse(event.data);
      if (statusText) statusText.textContent = data.status || "completed";
      if (data.status === "error") {
        setStatusPill("error");
        if (currentRunId && summary) {
          fetch("/status/" + currentRunId)
            .then((r) => r.json())
            .then((info) => {
              const msg = (info.message && typeof info.message === "string") ? info.message : "Run failed.";
              if (msg.indexOf("Security limit reached:") === 0) {
                summary.innerHTML =
                  '<div class="text-xs text-slate-200">' +
                  "<p class='mb-2 text-amber-300 font-semibold'>Security threshold reached.</p>" +
                  "<p class='mb-2 text-slate-300'>The agent team has paused to avoid exceeding your configured rate and cost limits.</p>" +
                  "<p class='mb-1 text-slate-400'>You can either:</p>" +
                  "<ul class='list-disc list-inside text-slate-300 mb-2'>" +
                  "<li>Click <span class='font-semibold'>Stop Crew</span> to end this run.</li>" +
                  "<li>Or adjust limits and click <span class='font-semibold'>Run Agent Team</span> again to restart with the same context.</li>" +
                  "</ul></div>";
              } else {
                summary.innerHTML =
                  '<div class="text-xs text-slate-200">' +
                  "<p class='mb-2 text-rose-300 font-semibold'>Run failed</p>" +
                  "<p class='text-slate-300 whitespace-pre-wrap'>" + escapeHtml(msg) + "</p>" +
                  "<p class='mt-2 text-slate-400'>Check the server console for details. Fix the issue (e.g. set OPENAI_API_KEY in .env) and try again.</p></div>";
              }
            })
            .catch((err) => {
              console.error(err);
              if (summary) summary.innerHTML = "<p class='text-slate-300 text-xs'>Run failed. Check the server console.</p>";
            });
        }
      } else {
        setStatusPill("completed");
      }
      if (runSpinner) runSpinner.classList.add("hidden");
      if (runButton) runButton.disabled = false;
      refreshOutputList();
      source.close();
    });

    source.addEventListener("error", () => {
      setStatusPill("error");
      if (runSpinner) runSpinner.classList.add("hidden");
      if (runButton) runButton.disabled = false;
      source.close();
    });
  }

  // —— Run Agent Team
  if (runButton) {
    runButton.addEventListener("click", () => {
      console.log("🚀 Run Agent Team clicked");
      const descriptionEl = document.getElementById("description");
      const description = descriptionEl ? descriptionEl.value : "";
      if (sidebarEngagement)
        sidebarEngagement.textContent = description || "Describe your consulting goal to begin.";

      const formData = new FormData();
      formData.append("description", description);

      if (statusText) statusText.textContent = "queued";
      if (progressFeed) progressFeed.textContent = "Submitting run...";
      setStatusPill("queued");
      if (runSpinner) runSpinner.classList.remove("hidden");
      runButton.disabled = true;

      fetch("/run", {
        method: "POST",
        body: formData,
      })
        .then((r) => r.json())
        .then((data) => {
          currentRunId = data.run_id;
          if (statusText) statusText.textContent = "running";
          if (progressFeed) progressFeed.textContent = "Run started...";
          setStatusPill("running");
          startEventStream(currentRunId);
        })
        .catch((err) => {
          console.error(err);
          if (statusText) statusText.textContent = "error";
          if (progressFeed) progressFeed.textContent = "Failed to start run.";
          setStatusPill("error");
          if (runSpinner) runSpinner.classList.add("hidden");
          runButton.disabled = false;
        });
    });
  }

  // —— Stop Crew
  if (stopButton) {
    stopButton.addEventListener("click", (e) => {
      e.preventDefault();
      console.log("🛑 Stop Crew clicked");
      if (!currentRunId) return;
      fetch("/stop/" + currentRunId, { method: "POST" }).catch((err) => console.error(err));
      setStatusPill("stopped");
      if (statusText) statusText.textContent = "Stopped";
      if (progressFeed) progressFeed.textContent += "\n[system] Run stopped by you. You can start a new run anytime.\n";
      if (runSpinner) runSpinner.classList.add("hidden");
      if (runButton) runButton.disabled = false;
      currentRunId = null;
    });
  }

  // —— Drag-and-drop
  if (dropZone) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, preventDefaults, false);
    });
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => dropZone.classList.add("highlight"), false);
    });
    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => dropZone.classList.remove("highlight"), false);
    });
    dropZone.addEventListener("drop", (e) => {
      console.log("📁 File dropped");
      const files = e.dataTransfer.files;
      handleFiles(files);
    });
    if (fileInput) {
      dropZone.addEventListener("click", () => fileInput.click());
    }
  }
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      console.log("📁 File(s) selected");
      handleFiles(e.target.files);
    });
  }

  // —— Download Markdown
  if (downloadMd) {
    downloadMd.addEventListener("click", (e) => {
      e.preventDefault();
      window.open("/download/client_package.md", "_blank");
      refreshOutputList();
    });
  }

  // —— Download HTML report (fallback when PDF unavailable, e.g. Windows without WeasyPrint/GTK)
  const downloadHtml = document.getElementById("download-html");
  if (downloadHtml) {
    downloadHtml.addEventListener("click", (e) => {
      e.preventDefault();
      window.open("/download/client_report.html", "_blank");
      refreshOutputList();
    });
  }

  // —— Download PDF
  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener("click", (e) => {
      e.preventDefault();
      fetch("/download_pdf", { method: "POST" })
        .then((response) => {
          if (!response.ok)
            return response
              .json()
              .catch(() => response.text())
              .then((body) => {
                const msg = typeof body === "object" && body && body.error ? body.error : String(body || "Failed to generate PDF.");
                throw new Error(msg);
              });
          return response.blob();
        })
        .then((blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "client_report.pdf";
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        })
        .catch((err) => {
          console.error(err);
          const msg = err && err.message ? err.message : "Error generating PDF.";
          if (msg.indexOf("WeasyPrint") !== -1 || msg.indexOf("GTK") !== -1) {
            alert(
              "PDF is not available on this system (WeasyPrint needs GTK3 on Windows).\n\n" +
                "Use the Outputs panel to download the Markdown or HTML report instead."
            );
          } else {
            alert("Error generating PDF: " + msg);
          }
        });
    });
  }

  // —— Clear All
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const desc = document.getElementById("description");
      if (desc) desc.value = "";
      if (sidebarEngagement) sidebarEngagement.textContent = "Describe your consulting goal to begin.";
      if (fileList) fileList.innerHTML = "";
      if (statusText) statusText.textContent = "Idle";
      if (progressFeed) progressFeed.textContent = "";
      setStatusPill("idle");
      if (summary)
        summary.innerHTML =
          '<p class="text-slate-400 text-xs">Once the run completes, a concise engagement summary will appear here.</p>';
      if (outputFiles) outputFiles.innerHTML = "";
      if (currentSource) {
        currentSource.close();
        currentSource = null;
      }
      currentRunId = null;
    });
  }

  // —— New Engagement
  if (newEngagementBtn) {
    newEngagementBtn.addEventListener("click", (e) => {
      e.preventDefault();
      if (clearAllBtn) clearAllBtn.click();
    });
  }
});
