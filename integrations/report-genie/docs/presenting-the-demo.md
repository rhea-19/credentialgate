> Bundled checkout: the simplest setup is the repository-root command `python scripts/run_report_genie.py`. See [the integration README](../README.md).

# Showing Report Genie to a nontechnical reviewer

## What to show

Open `/walkthrough` on the running local demo. It presents two examples with plain-language outcomes. Technical details stay collapsed until requested. The original upload and report summary remain available.

This is a working, locally runnable prototype, not a deployed institutional product. The PDF examples and provider are synthetic. File fingerprints, digital signatures, MCP requests, current credential checks and audit writes are real. The walkthrough does not run an AI model or evaluate medical content.

## A two-minute presentation

**0:00–0:20 — Explain the problem.**

“Report Genie helps explain reports. I wanted to explore a related question: what evidence can we check about a report's recorded provider connection before relying on an AI explanation?”

**0:20–0:50 — Show the original.**

Choose **Original sample**, then **Check this report**.

“For this synthetic example, an operator registered a signed connection between the exact document and a demo provider credential. The application checks that connection and the credential's current registry status.”

Wait for the actual result. If it passes, point to **Connection confirmed**. If the service is unavailable, explain the failure honestly and restart the demo rather than describing it as a success.

**0:50–1:20 — Show the changed copy.**

Choose **Changed copy**, then **Check this report**.

“Here I changed a small piece of text. It creates a different file, so the earlier record does not automatically apply. The application says it cannot confirm this copy's connection. That does not mean the document is fraudulent; it means we do not have matching evidence.”

**1:20–1:45 — Explain the design.**

“Report Genie asks a separate service to check the evidence. That service controls access and records its decision before returning a result. The same interface can be used by an AI assistant through MCP.”

MCP in one sentence: “It is a standard way for an AI application to ask another system to perform a specific operation.” The walkthrough itself is button-driven, so it does not pretend an AI model made these choices.

**1:45–2:00 — State the scope and invite a useful conversation.**

“This checks a registered connection, not medical accuracy, professional license validity or actual authorship. I built it to understand the engineering hands-on. The next substantial steps are credential lifecycle management and a real issuer onboarding process.”

A useful discussion question: “In a real workflow, which pieces of evidence would someone need to see before acting on a report?”

## How to present it

- **Live conversation:** share your browser window, open the walkthrough and follow the two examples. The other person does not need Python, GitHub access or technical knowledge.
- **Asynchronous review:** share a short recording of the actual walkthrough along with the scope statement above. A recording demonstrates the interaction but does not let the recipient operate the application.
- **Self-service public demo:** host both Report Genie and the credential service with supervised processes and an appropriate synthetic-only configuration. A localhost address works only on your own computer; it is not a link you can send him to try remotely. This implementation has not been publicly deployed.

## Running it

From the Report Genie folder:

```bash
source .venv-mcp/bin/activate
python scripts/run_evidence_demo.py --credentialgate "/path/to/credentialgate"
```

The default walkthrough address is `http://127.0.0.1:5002/walkthrough`. If the launcher is given another `--port`, use that port instead. Restarting the launcher creates a new browser session secret; refresh the page if a previous session no longer works.

The walkthrough is enabled only in synthetic demo mode. It makes no changes to credential permissions, does not issue new credentials, and does not auto-register the changed example. Each example is still verified through the existing MCP integration.

## How to describe the originality

“This extends my existing report-explanation project with a separate evidence-checking service. It explores how AI applications can use signed records and controlled access.”

Discuss your own implementation, decisions and test results. Do not present another company's internal implementation as your source material or claim equivalence with their infrastructure. A focused working prototype is a defensible demonstration of initiative; individual feedback cannot be predicted.
