import hashlib
import io
import os
import secrets
import tempfile
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, session

import credential_client
import report_store

ROOT = Path(__file__).resolve().parent


def demo_pdf(scenario="registered"):
    """Two real PDFs with distinct bytes; the altered example is never auto-registered."""
    raw = (ROOT / "resources/credential-demo.pdf").read_bytes()
    if scenario == "changed":
        # Equal-length text replacement preserves the PDF's byte offsets and stream length.
        raw = raw.replace(b"software testing only", b"software testing ONLY")
    return raw


def process_pdf(*args):
    # Defer heavyweight model imports so evidence verification works without local model weights.
    from tokenizer import process_pdf as process

    return process(*args)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("REPORTGENIE_SECRET_KEY") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REPORT_DATA_DIR=os.environ.get("REPORTGENIE_DATA_DIR", str(ROOT / "var")),
        DEMO_MODE=os.environ.get("REPORTGENIE_DEMO") == "1",
    )
    if config:
        app.config.update(config)

    def current_report():
        return report_store.get(app.config["REPORT_DATA_DIR"], session.get("report_id"))

    @app.before_request
    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            token = request.headers.get("X-CSRF-Token") or request.form.get(
                "csrf_token", ""
            )
            if not secrets.compare_digest(token, session["csrf"]):
                return jsonify(error="Refresh the page and try again."), 400

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.context_processor
    def template_config():
        return {
            "csrf_token": session.get("csrf", ""),
            "demo_mode": app.config["DEMO_MODE"],
        }

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/upload")
    def upload_file():
        file = request.files.get("pdf-upload")
        if not file or not file.filename.lower().endswith(".pdf"):
            return "Please choose a PDF report.", 400
        raw = file.read()
        if not raw.startswith(b"%PDF-"):
            return "The uploaded file is not a PDF.", 400
        digest = hashlib.sha256(raw).hexdigest()
        if app.config["DEMO_MODE"]:
            result = {
                "tokens": [],
                "notes": "Evidence-only demo: this upload was not sent to an AI model.",
                "filename": "Uploaded synthetic report",
            }
        else:
            with tempfile.TemporaryDirectory(prefix="report-genie-") as folder:
                path = Path(folder) / "report.pdf"
                path.write_bytes(raw)
                try:
                    result = process_pdf(
                        str(path),
                        request.form.get("report-type", "other"),
                        request.form.get("notes", ""),
                    )
                except Exception:
                    app.logger.error(
                        "Report extraction failed; check model configuration."
                    )
                    return (
                        "Report processing is unavailable. Check the model configuration and retry.",
                        503,
                    )
        session["report_id"] = report_store.save(
            app.config["REPORT_DATA_DIR"], result, digest
        )
        return redirect("/summary")

    @app.post("/demo")
    def demo():
        if not app.config["DEMO_MODE"]:
            return "Demo is disabled", 404
        scenario = request.form.get("scenario", "registered")
        if scenario not in {"registered", "changed"}:
            return "Unknown demonstration example", 400
        raw = demo_pdf(scenario)
        result = {
            "tokens": [
                {
                    "name": "Example report",
                    "value": "Synthetic fixture",
                    "description": "This sample demonstrates report evidence checks. No medical interpretation is generated.",
                }
            ],
            "notes": "Prepared fixture for the integration walkthrough; no patient data.",
            "filename": "credential-demo.pdf",
            "demo_scenario": scenario,
        }
        session["report_id"] = report_store.save(
            app.config["REPORT_DATA_DIR"], result, hashlib.sha256(raw).hexdigest()
        )
        return redirect(
            "/walkthrough" if request.form.get("view") == "walkthrough" else "/summary"
        )

    @app.get("/walkthrough")
    def walkthrough():
        if not app.config["DEMO_MODE"]:
            return "Demo is disabled", 404
        report = current_report()
        scenario = report["summary"].get("demo_scenario") if report else None
        return render_template(
            "walkthrough.html",
            scenario=scenario,
            report_digest=report["sha256"] if scenario else None,
        )

    @app.get("/demo-report.pdf")
    def demo_download():
        if not app.config["DEMO_MODE"]:
            return "Demo is disabled", 404
        scenario = request.args.get("scenario", "registered")
        if scenario not in {"registered", "changed"}:
            return "Unknown demonstration example", 400
        return send_file(
            io.BytesIO(demo_pdf(scenario)),
            as_attachment=True,
            download_name=f"credential-demo-{scenario}.pdf",
            mimetype="application/pdf",
        )

    @app.get("/summary")
    def summary():
        report = current_report()
        if not report:
            return redirect("/")
        return render_template(
            "summary.html", summary=report["summary"], report_digest=report["sha256"]
        )

    @app.post("/credential-check")
    def credential_check():
        report = current_report()
        if not report:
            return jsonify(error="Upload a report before checking its evidence."), 404
        # Browser-supplied provider IDs, hashes and roles are never used for the check.
        return jsonify(credential_client.verify_report(report["sha256"]))

    @app.post("/ask")
    def ask_question():
        if not current_report():
            return jsonify(error="Upload a report first."), 404
        question = request.form.get("question", "").strip()
        if not question or len(question) > 2000:
            return jsonify(error="Enter a question of up to 2,000 characters."), 400
        if app.config["DEMO_MODE"]:
            return jsonify(
                answer="This evidence demo does not run an AI model. Use Check report evidence to inspect the live MCP verification results."
            )
        try:
            from generator import generate_answer
            from retriever import retrieve_hybrid

            answer = generate_answer(question, "\n".join(retrieve_hybrid(question)))
            return jsonify(answer=answer)
        except Exception:
            return jsonify(error="The question-answering model is unavailable."), 503

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
