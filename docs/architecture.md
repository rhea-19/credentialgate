# Architecture decisions and next steps

## Threat model

A caller or model may submit arbitrary tool arguments, ask for a stronger role, request another institution's record or try to retrieve sensitive fields. Artifacts may be modified, expired or signed by an untrusted key. The audit store may fail. We trust the service process, configured trust store, token provisioning, host administrator and cryptographic library.

Authorization applies regardless of what the model says. Possession of a stronger token does grant stronger access, so provisioning and host isolation remain essential. Prompt instructions are usability guidance, not an authorization control.

## Decisions

| Choice | Reason | Limitation |
|---|---|---|
| Separate HTTP service | Tools need no database access or schema knowledge | Local processes do not isolate a hostile host user |
| stdio MCP | Real protocol with a small deployment surface | No hosted multi-user MCP/OAuth flow |
| Server-provisioned identities | Tool arguments cannot assign a role | Static tokens need replacement for deployment |
| Exact-byte Ed25519 envelope | Small signing surface; portable verification | Custom demo format, no VC interoperability claim |
| Public-only artifact | Offline verification cannot expose private fields | Restricted fields require registry trust |
| Transactional SQLite audit | Clear fail-closed behavior | Serialized access limits throughput |
| Separate verifier implementation | Does not just call producer verification code | Shares the cryptographic library and format assumptions |

## Containers

`Dockerfile` provides `api` and `mcp` targets. Both run as UID 10001. The API starts on port 8010 and expects an initialized writable `/data` volume. The MCP target contains only adapter/client source; never mount the database volume in it.

```bash
docker volume create credentialgate-data
docker run --rm -v credentialgate-data:/data credentialgate-api \
  python -m credentialgate.bootstrap --data-dir /data
docker run --rm -p 127.0.0.1:8010:8010 -v credentialgate-data:/data credentialgate-api
```

Named volumes inherit the image's `/data` ownership on first use. For other mounts, ensure UID 10001 can write. Bootstrap is one-time. The volume's `clients.json` is operator provisioning material, never an agent-readable tool resource.

Run the MCP image with stdin attached (`docker run --rm -i ...`) from an MCP host. Provision its URL and one token through environment variables. A private container HTTP network needs `CREDENTIALGATE_ALLOW_INTERNAL_HTTP=1`; use HTTPS outside local development.

No cloud resources, public endpoint, release signing or security certification is created by this starter.

## Next milestones

1. **Lifecycle:** authenticated issuance, revocation and renewal, key rotation, issuer onboarding, schema migrations. Keep issuance out of the agent tool set.
2. **Report binding:** signed report digest plus provider ID before adding a Report Genie connector. Tests must reject changed reports and provider associations.
3. **Disclosure assurance:** decide whether registry-authorized fields suffice or whether separately signed field claims/standard disclosure formats are needed.
4. **Deployment identity:** short-lived credentials, membership management, TLS, audience restrictions and rotation. Remote MCP would require its applicable authorization flow; do not forward unrelated bearer tokens.
5. **Operations:** Postgres, request/rate limits, denial metrics, backups, external audit checkpoints, dependency scans and image digest pinning.

Real sensitive records, clinical use, compliance claims and institutional integration are outside this prototype's scope.
