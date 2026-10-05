# CredentialGate: the project in plain language

## The question

An AI application can explain what a report says. What can it independently check about the report's recorded connection to a provider?

CredentialGate is an independent prototype built to explore that question. It extends the local Report Genie application with a separate evidence service. The project uses synthetic providers and reports and does not represent a hospital deployment.

## A concrete example

An operator registers a signed connection between a synthetic PDF and a provider credential. Report Genie later checks that exact file against the record. It can display the checked connection and the credential's status, together with a reference to the service's audit event.

Change a small piece of text in the PDF and its bytes change. That copy no longer has a matching registered record. The correct result is “connection not established,” not “fraud detected.” The application distinguishes what it can confirm from what it cannot.

## Why it is useful to explore

- A viewer can inspect the evidence separately from an AI-generated explanation.
- The AI application receives only the operations and fields its service identity is allowed to access.
- A completed access decision has an audit reference.
- Signature or storage failures do not become successful verification results.

These are demonstrated software properties. They are not measured claims of time savings, fraud reduction, clinical accuracy or regulatory compliance.

## The demonstration

The local Report Genie integration provides `/walkthrough` with two examples:

1. Select **Original sample**, run the check, and inspect the recorded connection.
2. Select **Changed copy**, run the same check, and see that no matching record is found.
3. Expand the details to see the checks and audit reference.

File fingerprinting, MCP communication, signature validation and audit recording are real. Provider identities and reports are synthetic. This walkthrough is button-driven; a language model does not choose these tool calls. A separate optional Claude client exists, but live model behavior has not been validated with an account key.

The Report Genie integration and its walkthrough are bundled under `integrations/report-genie`. The existing public Report Genie repository is separate and its default branch has not been changed. This repository runs the complete synthetic demo with `python scripts/run_report_genie.py` after setup.

## A concise introduction

“I extended my report-explanation project with an evidence-checking service. It lets the application inspect a signed record connecting an exact report to a provider credential, while keeping access decisions in a separate service. I built a working prototype and tested both successful checks and cases where the system must refuse to confirm a result.”

## What the project does not claim

The operator is the trust anchor in this prototype. A signed record does not establish that a real authority vetted a provider. The project does not establish report authorship, current professional license validity, or medical correctness. Restricted fields are registry assertions rather than independently signed disclosures. The audit chain has no external checkpoint and is not administrator-proof.

The next substantial milestones are issuer onboarding, credential lifecycle management, bounded access approvals and operational deployment. Those are roadmap items, not existing functionality.

## How to explore the source

| Concern | Implementation |
|---|---|
| Who can see which fields? | [`policy.py`](../src/credentialgate/policy.py) |
| When is a result returned? | [`service.py`](../src/credentialgate/service.py) |
| What report evidence is checked? | [`reports.py`](../src/credentialgate/reports.py) |
| How does the client call it? | [`mcp_server.py`](../src/credentialgate/mcp_server.py) |
| How are signatures checked independently? | [`verify_artifact.py`](../tools/verify_artifact.py) |
| What breaks when the system is tampered with? | [Tests](../tests) |
