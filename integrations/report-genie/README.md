# Report Genie integration

This directory contains the Report Genie application source, MCP connector, guided walkthrough, synthetic PDF and tests. It is an integration snapshot maintained within the CredentialGate project; the existing public Report Genie repository is a separate project.

## Run the working walkthrough

From the **CredentialGate repository root**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements.lock -e '.[dev,web]'
python scripts/run_report_genie.py
```

Open http://127.0.0.1:5002/walkthrough. Both services run locally; Ctrl+C stops them. Use `--port 5003 --api-port 8012` if the default ports are already occupied.

Choose the original example and check it, then choose the changed copy and run the same check. The results come from the actual MCP-connected service. Synthetic content is used and no external model calls are made.

See [the presentation guide](docs/presenting-the-demo.md) and [integration details](docs/credential-integration.md).

## Source and asset boundaries

The original extraction/retrieval/generation Python modules are included for reference and future model-backed integration. That mode requires the separate legacy dependencies, configured model access and generated retrieval indexes; it has not been validated as part of this demo.

Historical uploaded PDFs, extracted report data, generated model logs, serialized retrieval indexes, old report screenshots and model weights are intentionally not included. The knowledge-base descriptions and bundled demonstration PDF are sufficient for the implemented evidence walkthrough, which does not load the legacy model pipeline.

The original Report Genie MIT license is retained in this directory. The credential-service implementation at the repository root is a separate component.
