(() => {
  const button = document.getElementById('check-evidence');
  if (!button) return;
  const badge = document.getElementById('evidence-badge');
  const message = document.getElementById('evidence-message');
  const result = document.getElementById('evidence-result');
  const statuses = {
    verified: ['Association verified', 'The registered report association matches. Signed provider metadata and the current registry status passed their checks.'],
    unregistered: ['No association found', 'These PDF bytes have no registered association. No provider identity can be established from this check.'],
    invalid_binding: ['Association failed', 'The registered association could not be verified. Treat it as unverified.'],
    credential_unavailable: ['Credential unavailable', 'The report association matched, but its provider credential could not be confirmed as current and active.'],
    denied: ['Access denied', 'The credential service did not authorize this request. No provider fields were returned.'],
    unavailable: ['Check unavailable', 'The credential service could not complete the check. No verified status has been established. Try again later.'],
    not_configured: ['Not connected', 'Credential verification is not configured on this Report Genie server.'],
  };
  const labels = {
    report_digest: 'Original report bytes', binding_signature: 'Association signature',
    credential_signature_and_time: 'Credential signature & time', credential_version: 'Credential version',
    registry_status: 'Registry status', license_validity: 'License validity', medical_accuracy: 'Medical accuracy',
  };
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.hidden = true;
    badge.textContent = 'Checking…';
    badge.dataset.state = '';
    message.textContent = 'Checking through MCP and recording the access decision…';
    try {
      const response = await fetch('/credential-check', {
        method: 'POST', headers: { 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content },
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) throw new Error('Request failed');
      const data = await response.json();
      const state = Object.hasOwn(statuses, data.status) ? data.status : 'unavailable';
      [badge.textContent, message.textContent] = statuses[state];
      badge.dataset.state = state;
      document.getElementById('evidence-provider').textContent = data.public_metadata?.display_name || '';
      const checks = document.getElementById('evidence-checks');
      checks.replaceChildren();
      Object.entries(labels).forEach(([key, label]) => {
        if (!data.checks?.[key]) return;
        const row = document.createElement('div');
        const name = document.createElement('dt');
        const value = document.createElement('dd');
        name.textContent = label;
        value.textContent = data.checks[key].replaceAll('_', ' ');
        row.append(name, value);
        checks.append(row);
      });
      document.getElementById('evidence-request').textContent = data.request_id ? `Audit reference: ${data.request_id}` : '';
      result.hidden = !(data.request_id || data.checks);
    } catch {
      [badge.textContent, message.textContent] = statuses.unavailable;
      badge.dataset.state = 'unavailable';
    } finally { button.disabled = false; }
  });
})();
