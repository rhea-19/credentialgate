# CredentialGate: project review and extensive build plan

Reviewed against the current source and tests on 2026-10-01. Features below are explicitly separated into implemented behavior and proposed work. This document is a development plan, not a claim that the proposed platform exists.

Update 2026-10-03: the first Report Genie integration is implemented locally: signed report-digest associations, an MCP verification tool, a session-scoped evidence panel, and integration tests. The remaining lifecycle/approval/deployment stages below are still proposals. See the current README for implemented behavior.

## Assessment

This is a good foundation for a substantial backend, security and applied-AI project. Its strongest feature is the separation between what an AI assistant can request and what the service actually authorizes. The implementation includes real MCP transport, signatures, policy enforcement and transactional auditing.

It is currently a small architecture prototype. Two fixture providers, three read tools and a scripted client do not yet demonstrate a full credential-management workflow. To make it a strong flagship project, build a coherent journey: issue a credential, inspect it, request restricted evidence, approve access, verify a report binding, revoke the credential, and explain what changes at each step.

The project's proposed expanded purpose is: **help an institution inspect a provider's credential evidence through an AI assistant while preserving field-level authorization and a traceable decision record.** All demonstrations should continue to use synthetic data.

## What happens today

### 1. Initialize a registry

`bootstrap.py` creates two synthetic providers in different institutions and four demo client identities. Each identity receives a randomly generated bearer token; the database stores the token digest. Identities have a server-assigned role, institution and expiry.

The script generates an Ed25519 signing key and signs each provider's public metadata together with issuer, provider ID, credential ID and validity dates. It exports the signed artifacts and a public-key trust bundle. The private signing key is discarded. This is why the runtime can verify existing fixtures but cannot yet issue or renew credentials.

### 2. Discover tools through MCP

The host starts the MCP adapter as a separate subprocess. The client establishes the MCP session and requests the tool list. It receives schemas for `get_provider_summary`, `verify_credential`, and `request_credential_fields`.

The deterministic demo calls these directly. The optional Claude client lets a model choose tools from those schemas, then routes the requested calls through the same MCP session. A real model call is optional and has not been validated with an account key.

MCP standardizes tool discovery and invocation. It is not the credential database, a signature scheme, or the component deciding who may see a birth date.

### 3. Execute a request

Consider an institution client requesting a license number:

```mermaid
sequenceDiagram
    participant C as MCP client
    participant M as MCP adapter
    participant S as Credential service
    participant D as SQLite registry and audit
    C->>M: request_credential_fields(provider_id, license_number)
    M->>S: HTTP request + provisioned client token
    S->>D: Begin transaction; look up identity and provider
    S->>S: Check role, institution, requested fields
    S->>S: Check signed metadata and registry status
    S->>D: Append audit event and commit
    alt Authorized and commit succeeds
        S-->>M: Requested field + request ID
    else Forbidden or storage failure
        S-->>M: Error; no credential fields
    end
    M-->>C: Structured MCP result
```

The role does not come from the model. It comes from the token's identity in the registry. A public caller requesting a license number is denied. An institution caller can receive it for its own institution's provider. A reviewer can request additional sensitive fixture fields within the same institution.

The service uses a database transaction so it can commit the audit event before responding. If audit insertion or commit fails, it returns no credential data. An audit event means the service committed a decision; it cannot prove that a remote client ultimately received the response.

### 4. Verify outside the service

The separate verifier accepts an artifact, an independently configured trust bundle and an expected provider ID. It verifies the signature, identity and validity period without importing the producer's verification helper. Both implementations use a maintained cryptographic library.

Offline verification cannot determine current revocation. Nor does a valid signature establish that a real licensing body checked the underlying claims. Issuer trust and business validation are additional decisions.

## Findings that should guide the next version

| Finding | Evidence in current code | Consequence / next change |
|---|---|---|
| Verification is narrower than license validity | `crypto.py` validates envelope expiry; `service.py` checks registry status. `license_expires_at` is an unsigned registry field. | Return separate signature, credential-expiry, registry-status and license-evidence results. Avoid a single unexplained green badge. |
| No credential lifecycle API | Signing occurs only in `bootstrap.py`; runtime endpoints are read-only. | Add authenticated issuance, renewal, revocation and version history through an issuer/admin interface. |
| Audit lacks disclosure detail | Events contain actor, time, operation, outcome, provider ID and request ID. | Add requested/released field names, credential version, policy version and reason code, without storing field values or tokens. Protect audit access too. |
| Audit protection assumes a trusted operator | SQLite triggers reject update/delete; the chain checker uses hashes in the same database. | Add an independently retained checkpoint and test rewritten/truncated history. Do not call the current log administrator-proof. |
| Client identity is provisioned statically | Four bootstrap identities, 30-day tokens, no account/membership management. | Add sessions, short-lived service credentials, tenant membership and explicit delegation. |
| Signature schema validation is minimal | Verifiers check selected identity/time fields, not a complete strict payload schema. | Validate required public fields and types, reject ambiguous/duplicate JSON keys, enforce size limits, and retain independent verifier conformance tests. |
| No visual explanation of decisions | CLI demo and API docs only. | Build a dashboard showing requests, authorized fields, verification checks and audit correlation. |
| Agent behavior remains unevaluated | Deterministic MCP integration passes; optional live model loop is not exercised. | Add model-independent malicious-tool-input tests and separately measured model evaluations. |
| Delivery evidence is incomplete | Docker and CI configurations exist but no local Docker execution or hosted CI result has been established. | Run both images and CI before claiming container isolation or release validation as demonstrated. |

A review probe used a temporary synthetic database, changed `license_expires_at` to `2000-01-01`, and called `/v1/verify`. It still returned `verified: true` with its documented signed-metadata scope. This is a semantic limitation, not evidence of a signature bypass. The next interface should make this distinction impossible to miss.

## The extensive version: six build stages

### Stage 1 — Complete verification semantics and credential lifecycle

Add issuer identities, provider creation, credential versions, trusted-key management, issuance, renewal, expiry and revocation. Keep provider IDs stable across credential versions. Issuance and revocation belong to an authenticated issuer/admin interface, not the general assistant's tools.

Return explicit verification checks: trusted issuer, signature integrity, expected subject, artifact validity, registry status, schema validity and separately evaluated license evidence. Represent unavailable evidence as unknown. Scope responses so restricted license details cannot be inferred through a public verification result.

**Done when:** an authorized issuer can issue version 1, renew to version 2 and revoke a credential; an unauthorized caller cannot. Restarting services preserves history. An old or revoked version cannot be silently treated as current. Invalid time windows, malformed claims and forged signatures have distinct tested outcomes.

### Stage 2 — A visual credential workbench

Build a React/TypeScript interface with four focused views:

- Provider directory and detail view: stable ID, institution-scoped records and credential history.
- Verification inspector: separate check results with concise reasons and source timestamps.
- Assistant console: visible MCP tool name, sanitized arguments, returned fields and request ID.
- Audit explorer: policy outcome, credential version, timestamps and disclosure field names.

The demo can offer separate pre-provisioned synthetic accounts. A role selector must switch between those accounts through host-controlled demo setup; it must not send `role=reviewer` as an authorization override. The UI should receive only authorized records, rather than hiding already-fetched private fields with CSS.

**Done when:** changing accounts changes what the API returns, browser requests never contain another account's private fields, and a user can follow one tool call to its audit event. The backend remains the sole disclosure authority.

### Stage 3 — Human-approved access and useful agent workflows

Add a workflow for a bounded access request: applicant, provider, requested fields, purpose, expiry, approving reviewer and final decision. A purpose string supplies context, not permission. An approver grants only capabilities they are entitled to delegate. The agent cannot approve its own request.

Give the assistant a useful task: prepare a credential-review checklist from authorized evidence, explicitly marking missing, expired or unverifiable evidence. Link each supported finding to a tool result/request ID. Keep the final institutional decision human-owned.

Potential additional tools are `list_credential_versions`, `get_verification_checks`, `submit_access_request` and `get_access_request_status`. All still go through service authorization. Submitting an access request is a write operation and must be described and handled as such by the client.

**Done when:** pending access returns no restricted data, a grant is bound to actor/provider/fields/expiry, expired or withdrawn grants stop access, and the model cannot manufacture a grant by changing arguments.

### Stage 4 — Report Genie integration with a verified report binding

Create a signed association between a synthetic report's digest, provider ID, credential version and attesting issuer. Hash the original bytes; do not rely on extracted names or filenames. Only an authorized attester can create the binding.

Report Genie can then verify the report binding, check the associated credential and summarize authorized document content with evidence references. A dashboard should show report integrity, provider credential status and content analysis as separate results. A signature from an institution attests to what that institution signed; it is not automatically proof of provider authorship.

**Done when:** changing one byte of a report fails binding verification; swapping provider IDs fails; unknown bindings remain unknown; unauthorized users cannot obtain protected reports. The integration cannot bypass the credential service by reading its database.

### Stage 5 — Operational and security depth

Use Postgres with migrations for the expanded relational model. Add request limits, connection management, idempotency for lifecycle mutations, short-lived identities, structured redacted logs, trace correlation and externally retained audit checkpoints. Use separate database permissions for application writes and audit administration.

Keep existing stdio MCP for local development. If a remote HTTP MCP endpoint is added, implement the applicable MCP authorization flow, discovery and audience checks rather than repurposing development tokens. Maintain a clear distinction between the requesting person and the agent acting for them.

**Done when:** interrupted mutations recover predictably, simultaneous requests preserve audit consistency, unauthorized writes fail, expired credentials are rejected, and tampered or truncated audit history is detectable against an independently trusted checkpoint.

### Stage 6 — Reproducible demonstration and measured evidence

Provide a one-command synthetic demo environment, CI test results, container boundary tests, a threat model and a short walkthrough video. Show both allowed requests and intentionally failed requests.

Measure performance under a documented workload: concurrency, dataset size, environment, latency percentiles, throughput, errors and audit-write impact. Record numbers only after measurement.

Build an evaluation set containing role spoofing, cross-institution access, missing data, expired/revoked credentials, altered artifacts, prompt injection in tool-returned text and requests to reconstruct hidden fields. Measure server-side disclosure independently from whether a model invents a plausible answer. A refusal prompt is not an authorization boundary.

**Done when:** a fresh checkout reproduces the documented demo; negative controls fail as expected; results identify the tested commit, configurations and actual limitations. Live-model evaluations record model ID and run date and do not claim deterministic guarantees.

## Proposed data model

Start with these entities as the workflows require them; do not add empty tables just for appearance:

| Entity | Purpose |
|---|---|
| Provider | Persistent subject identity |
| Organization / membership | Institution scope and user membership |
| Issuer / signing key | Trust configuration and key lifecycle |
| Credential / credential version | Signed evidence and immutable version identity |
| Credential status event | Revocation and lifecycle history |
| Access request / grant | Bounded human-approved disclosure |
| Report binding | Signed association of report bytes and provider evidence |
| Audit event / checkpoint | Access decision history and independent integrity checkpoint |

Keep the existing HTTP service as the domain authority and the MCP adapter as a separate process. A UI is another client. Introduce additional workers or services only when a specific workflow needs them.

## A demonstration worth building toward

1. Sign in as an issuer and issue a synthetic provider credential.
2. Sign in as an institution reviewer and ask the assistant for a credential-review checklist.
3. Inspect the MCP tools and evidence behind the answer.
4. Request a restricted field and see a denial or pending approval, with no value returned.
5. Approve a narrowly scoped grant through a separate authorized account; retry successfully.
6. Alter an exported artifact and see independent verification fail.
7. Verify a synthetic report binding, then alter the report and see the failure.
8. Revoke the credential and show the change in live verification while explaining offline limits.
9. Trace each operation through the authorized audit viewer.

Steps beyond the current summary/field/verification demo are proposed, not implemented.

## Suggested learning order

Read `policy.py`, then `service.py`, `crypto.py`, `storage.py`, `mcp_server.py`, `client.py`, and finally the tests. Trace an allowed field request, repeat it with a public token, and inspect the corresponding audit events. Then read the offline verifier and explain why it needs its own trusted key configuration.

The strongest technical story today is: “I built an MCP interface to a synthetic credential service with server-enforced disclosure rules, signed public metadata, independent verification and audit-before-response behavior.” After the new workflows are implemented and measured, the project can support a much broader claim.

## Public references

- [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization): distinguishes stdio environment credentials from authorization for HTTP MCP transports.
- [MCP security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices): guidance relevant to a future remote deployment and safe token handling.
- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/): useful context for issuer, subject, verifier and trust distinctions; the current custom artifact is not an implementation of this standard.
