(() => {
  const button = document.getElementById('run-walkthrough');
  if (!button) return;
  const badge = document.getElementById('walk-status');
  const result = document.getElementById('walk-result');
  const progress = document.getElementById('walk-progress');
  const copy = {
    verified: ['Connection confirmed', 'The recorded connection checks out.', 'This exact file matches a signed record connected to a demo provider. The linked credential is currently active in the demo registry.', 'You can inspect the recorded connection. This does not establish who wrote the report or whether its medical content is correct.'],
    unregistered: ['No matching record', 'We cannot confirm this copy’s connection.', 'The service has no registered provider connection for these exact file bytes.', 'A changed file does not inherit the original file’s result. No matching record is a limit on what we know, not an accusation of fraud.'],
    invalid_binding: ['Check failed', 'The recorded connection could not be verified.', 'The service could not validate the signed association for this report.', 'This result must remain unverified. An explanation from an AI model cannot override it.'],
    credential_unavailable: ['Credential not confirmed', 'The file matches, but the credential does not pass.', 'A registered report connection was found, but the linked credential could not be confirmed as current and active.', 'A matching document alone is not enough. Its linked credential must pass the current checks as well.'],
    denied: ['Access not allowed', 'This request is outside the permitted access.', 'The service did not authorize this check. No provider information was released.', 'Access is determined by the credential service, not by what a person or AI asks to see.'],
    unavailable: ['Check unavailable', 'We could not complete the check.', 'The verification service did not return a completed result. Please try again later.', 'The application does not display a successful result when it cannot finish the checks.'],
    not_configured: ['Service not connected', 'The verification service needs to be connected.', 'This instance of Report Genie has not been configured to run credential checks.', 'Start the complete local demo to see the live verification flow.'],
  };
  const labels = {report_digest:'File fingerprint',binding_signature:'Signed connection',credential_signature_and_time:'Credential signature and dates',credential_version:'Credential version',registry_status:'Registry status',license_validity:'Professional license validity',medical_accuracy:'Medical accuracy'};
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.hidden = true;
    badge.dataset.state = '';
    badge.textContent = 'Checking…';
    document.getElementById('walk-checks').replaceChildren();
    document.getElementById('walk-reference').textContent = '';
    progress.textContent = 'Contacting the verification service and recording the outcome…';
    let data;
    try {
      const response = await fetch('/credential-check', {method:'POST',headers:{'X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw Error('Incomplete check');
      data = await response.json();
    } catch { data = {status:'unavailable'}; }
    const state = Object.hasOwn(copy, data.status) ? data.status : 'unavailable';
    const [label, title, explanation, meaning] = copy[state];
    badge.textContent = label;
    badge.dataset.state = state;
    result.dataset.state = state;
    document.getElementById('walk-heading').textContent = title;
    document.getElementById('walk-explanation').textContent = explanation;
    document.getElementById('walk-meaning').textContent = meaning;
    const provider = document.getElementById('walk-provider');
    provider.textContent = state === 'verified' && data.public_metadata?.display_name ? `Recorded provider: ${data.public_metadata.display_name}` : '';
    provider.hidden = !provider.textContent;
    const checks = document.getElementById('walk-checks');
    for (const [key, labelText] of Object.entries(labels)) {
      if (typeof data.checks?.[key] !== 'string') continue;
      const row = document.createElement('div');
      const term = document.createElement('dt');
      const value = document.createElement('dd');
      term.textContent = labelText;
      value.textContent = data.checks[key].replaceAll('_',' ');
      row.append(term,value);checks.append(row);
    }
    if (data.request_id) document.getElementById('walk-reference').textContent = `Audit reference: ${data.request_id}`;
    progress.textContent = data.request_id ? 'The service returned a reference for this attempt. Expand the evidence details to inspect it.' : 'No completed verification has been established.';
    result.hidden = false;
    button.disabled = false;
    button.innerHTML = 'Run the check again <span aria-hidden="true">↻</span>';
  });
})();
