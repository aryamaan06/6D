/* Explicit live qualification and optional metrics export. No credentials are retained here. */
(() => {
  'use strict';
  let mounted = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const items = value => Array.isArray(value) ? value : [];
  const money = value => typeof value === 'number' && Number.isFinite(value) ? '$' + value.toFixed(4) : 'Not recorded';
  const valueText = value => value === null || value === undefined ? 'Not recorded' : String(value);
  const idOf = record => record?.qualification_id || record?.id || null;
  const running = record => ['queued','running'].includes(record?.state || record?.status);
  const label = value => ({queued:'Queued',running:'Running',completed:'Completed',failed:'Stopped',stopped:'Stopped',interrupted:'Interrupted',skipped:'Not tested',untested:'Not tested',not_run:'Not tested',not_tested:'Not tested',passed:'Contract checks passed',pass:'Contract checks passed',met:'Meets criterion',not_met:'Criterion unmet',not_assessed:'Not assessed',accepted_by_api:'Accepted by API',unknown:'Delivery unknown'}[value] || String(value || 'Not recorded').replaceAll('_',' '));
  const button = (action, title, disabled = false, primary = false) => '<button type="button" class="sd-button' + (primary ? ' sd-primary' : '') + '" data-aq="' + esc(action) + '"' + (disabled ? ' disabled' : '') + '>' + esc(title) + '</button>';
  const badge = value => '<span class="aq-badge aq-' + (['completed','passed','pass','failed','running','queued','skipped'].includes(value) ? value : 'neutral') + '">' + esc(label(value)) + '</span>';

  function unmount() { mounted?.dispose(); }

  function mount(host, ctx) {
    unmount();
    if (!host || typeof ctx?.api !== 'function') throw new Error('AI quality requires a host and API client.');
    const state = {closed:false, generation:0, status:null, receipt:null, receiptId:null, receiptError:false, loading:true, busy:'', error:'', notice:'', preview:null, uploadAttempted:new Set(), controllers:new Set(), timer:null};
    mounted = state;
    const live = () => !state.closed && mounted === state;
    const select = selector => host.querySelector(selector);
    const q = () => state.status?.qualification || {};
    const latest = () => q().latest || null;
    const selectedReceipt = () => state.receiptId && state.receipt ? state.receipt : null;
    const exportId = () => idOf(selectedReceipt());
    const locked = () => !!state.busy || state.loading;
    const obs = () => state.status?.observability || {};
    const canStart = () => {
      const c = state.status?.connection || {}, qualification = q();
      return !locked() && !running(latest()) && c.key_present === true && !!(c.model || c.model_id) && c.configured !== false && c.restart_required !== true && qualification.can_start !== false && qualification.available !== false && Number(qualification.batch_cap_usd) === .8;
    };

    async function request(url, body) {
      const controller = new AbortController();
      state.controllers.add(controller);
      try { return await ctx.api(url, body, {signal:controller.signal}); }
      finally { state.controllers.delete(controller); }
    }

    function message() {
      const box = select('[data-aq-message]');
      if (!box) return;
      box.replaceChildren();
      if (!state.error && !state.notice) return;
      const node = document.createElement('p');
      node.className = state.error ? 'aq-error' : 'aq-notice';
      node.setAttribute('role', state.error ? 'alert' : 'status');
      node.textContent = state.error || state.notice;
      box.append(node);
    }

    function renderConnection() {
      const connection = state.status?.connection || {}, budget = connection.budget || {};
      select('[data-aq-connection]').innerHTML = '<div class="aq-inline"><span class="aq-dot ' + (connection.key_present ? 'aq-connected' : '') + '" aria-hidden="true"></span><strong>' + (connection.key_present ? 'Nebius key connected' : 'Nebius key not connected') + '</strong><span class="aq-muted">' + esc(connection.model || connection.model_id || 'No model configured') + '</span></div>' +
        '<p class="aq-caption">The configured Nemotron model performs these live investigations. Local calculators supply numerical evidence. Connecting a key makes no inference call.</p>' +
        (budget.allowance_usd !== undefined || budget.cap_usd !== undefined || budget.reserved_usd !== undefined ? '<p class="aq-caption">Cumulative application ceiling: ' + money(budget.allowance_usd ?? budget.cap_usd ?? budget.ceiling_usd) + ' · Reserved: ' + money(budget.reserved_usd) + '. Reservations are not billed charges.</p>' : '') +
        (connection.restart_required ? '<p class="aq-warning">The server needs a restart before live checks can run.</p>' : '') +
        (!connection.key_present ? '<p class="aq-caption">Open Owner settings → Manage Nebius connection to connect your key privately.</p>' : '');
    }

    function renderCases() {
      const cases = items(q().cases);
      select('[data-aq-cases]').innerHTML = cases.length ? '<ol class="aq-case-plan">' + cases.map(row => '<li><strong>' + esc(row.title || row.id) + '</strong><p>' + esc(row.focus || '') + '</p><span class="aq-caption">Expected evidence finding: ' + esc(label(row.expected_status)) + '</span></li>').join('') + '</ol>' : '<p class="aq-muted">Loading the fixed qualification cases…</p>';
    }

    function renderQualification() {
      renderCases();
      const record = latest(), id = idOf(record), receipt = selectedReceipt(), target = select('[data-aq-result]');
      const start = select('[data-aq="start"]');
      start.disabled = !canStart();
      start.textContent = state.busy === 'start' ? 'Starting live checks…' : 'Run four live checks · $0.80 ceiling';
      const startState = select('[data-aq-start-state]'), connection = state.status?.connection || {};
      startState.textContent = state.loading ? 'Reading configuration and the recorded allowance…' : running(record) ? 'A qualification is already running. No second batch can start here.' : !connection.key_present ? 'Connect your Nebius key privately using Connect AI to enable this batch.' : !connection.model || connection.configured === false ? 'The Assistant configuration must be available before starting.' : connection.restart_required ? 'Restart the updated local server before starting.' : Number(q().batch_cap_usd) !== .8 ? 'The fixed qualification ceiling is unavailable. Refresh status.' : 'Starting this batch uses the connected account inside the displayed ceiling.';
      const sourceMatch = q().current_sources_match;
      if (!id) {
        target.innerHTML = '<div class="aq-empty"><strong>No qualification receipt recorded.</strong><p>The existing Assistant remains available. This panel will not call Nebius until you explicitly start the fixed batch.</p></div>';
        return;
      }
      const result = receipt || record;
      const resultState = result.state || result.status || record.state || record.status;
      const requestCount = result.request_attempts ?? result.request_reservations ?? result.summary?.request_attempts ?? result.summary?.request_reservations;
      const reserved = result.reserved_usd ?? result.summary?.reserved_usd ?? result.spending?.reserved_usd;
      const seconds = result.duration_seconds ?? result.elapsed_seconds ?? result.summary?.duration_seconds;
      const scorecard = q().scorecard || {}, rows = items(scorecard.rows || result.rows || result.cases || result.results || result.case_results);
      const mode = result.provider_mode || record.provider_mode;
      target.innerHTML = '<div class="aq-receipt-heading"><div><strong>Latest qualification</strong><p class="aq-caption aq-mono">' + esc(id) + '</p></div>' + badge(resultState) + '</div>' +
        '<p class="aq-caption">Recorded model: ' + esc(result.model || record.model || 'Not recorded') + ' · Execution: ' + esc(mode === 'live_token_factory' || mode === 'live' ? 'Live Nebius inference' : mode ? 'Offline / injected provider (' + mode + ')' : 'Not recorded') + '</p>' +
        '<p class="aq-context ' + (sourceMatch === true ? '' : 'aq-warning') + '">' + (sourceMatch === true ? 'This receipt matches the current application sources.' : sourceMatch === false ? 'Historical receipt: application sources have changed. This is not a current-build qualification.' : 'Source match has not been confirmed for this receipt.') + '</p>' +
        '<dl class="aq-metrics"><div><dt>Requests / reservations</dt><dd>' + esc(valueText(requestCount)) + '</dd></div><div><dt>Reserved</dt><dd>' + money(reserved) + '</dd></div><div><dt>Elapsed</dt><dd>' + (seconds === undefined ? 'Not recorded' : esc(String(seconds)) + ' s') + '</dd></div></dl>' +
        (running(record) ? '<p class="aq-caption" role="status">Checking status locally. Leaving this page stops polling; it does not cancel a request already accepted by the server.</p>' : '') +
        (state.receiptError ? '<p class="aq-warning">The complete receipt could not be loaded. Refresh to inspect it; no live request is retried.</p>' : '') +
        (rows.length ? '<div class="aq-table-wrap"><table class="aq-results-table"><caption>Recorded case outcomes</caption><thead><tr><th scope="col">Constructed case</th><th scope="col">Execution and checks</th><th scope="col">Recorded explanation and metrics</th></tr></thead><tbody>' + rows.map(row => {
          const info = items(q().cases).find(item => item.id === (row.case_id || row.id)), rowState = row.state || row.status, gate = row.workflow_gate_pass ?? row.score?.workflow_gate_pass;
          const summary = row.summary || row.receipt?.summary || row.reason || row.error_code || row.quality_status || 'Inspect the exact receipt for recorded checks.';
          const rawRow=items(receipt?.report?.rows || receipt?.rows).find(item=>item.case_id===row.case_id);
          const httpStatus=(rawRow?.receipt || row.receipt)?.provider_diagnostic?.http_status;
          const guidance=(rawRow?.receipt || row.receipt)?.guidance;
          const steps=items(guidance?.review_actions), missing=items(guidance?.missing_information);
          const guidanceMarkup=steps.length || missing.length ? '<details class="aq-guidance"><summary>Concrete next checks and missing evidence</summary>'+steps.map(item=>'<p><strong>'+esc(item.title)+'</strong><br>'+esc(item.action)+'</p>').join('')+missing.map(item=>'<p><strong>Missing: '+esc(item.item)+'</strong><br>'+esc(item.why)+'</p>').join('')+'<p class="aq-caption">Application guidance captured with this receipt; these are proposed checks, not new results.</p></details>' : '';
          const nextStep=httpStatus===401 || httpStatus===403 ? 'Nebius rejected authentication (HTTP '+httpStatus+'). Reconnect an active Token Factory key through Connect AI before deliberately starting a fresh batch.' : httpStatus===429 ? 'Nebius reported a service or account limit (HTTP 429). Check the provider console before deliberately starting another batch.' : rowState==='failed' ? 'Inspect the exact retained receipt before another deliberate attempt; no retry was made.' : '';
          return '<tr><th scope="row">' + esc(row.title || info?.title || row.case_id || row.id) + '</th><td>' + badge(rowState) + '<p class="aq-caption">' + (rowState === 'not_run' || rowState === 'skipped' ? 'Untested; no quality conclusion.' : gate === true ? 'Bounded workflow checks passed.' : gate === false ? 'Workflow checks did not pass.' : 'Workflow check outcome not recorded.') + '</p></td><td><p>' + esc(summary) + '</p>' + (nextStep?'<p class="aq-warning">'+esc(nextStep)+'</p>':'') + '<p class="aq-caption">Requests: ' + esc(valueText(row.request_reservations)) + ' · Live responses: ' + esc(valueText(row.live_model_calls)) + ' · Reserved: ' + money(row.reserved_usd) + ' · Time: ' + esc(valueText(row.elapsed_seconds)) + ' s</p>' + (row.source_context_captured ? '<p class="aq-caption">Supplemental source context captured.</p>' : '') + guidanceMarkup + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
        '<div class="aq-inline aq-receipt-actions"><a class="aq-link" href="/api/ai-quality/runs/' + encodeURIComponent(id) + '" target="_blank" rel="noopener">Open exact receipt ↗</a>' + (receipt ? button('receipt-json','Show recorded JSON') : '') + '</div><pre class="aq-json" data-aq-receipt-json hidden></pre>' +
        '<p class="aq-caption">' + esc(scorecard.semantic_review || 'Independent human review pending') + '. Completed means the workflow finished. Contract checks are bounded checks, not proof of semantic accuracy or an independent engineering review. Skipped cases remain untested. This batch does not select or activate a model.</p>';
    }

    function renderObservability() {
      const status = obs(), record = selectedReceipt(), id = exportId();
      const connectionState = status.credential_error ? (status.key_present ? 'Connected for this server session. Saved-key storage state is unavailable.' : 'No LangSmith key is connected. Saved-key storage state is unavailable.') : status.key_present ? (status.key_remembered ? (status.key_source === 'remembered' ? 'Remembered key connected locally.' : 'Session connected; an encrypted key copy is saved on this device.') : 'Connected for this server session only. No key is saved on this device.') : status.key_remembered ? 'A saved key is present, but no key is connected.' : 'No LangSmith key is connected or saved.';
      select('[data-aq-observability-status]').innerHTML = '<div class="aq-inline"><span class="aq-dot ' + (status.key_present ? 'aq-connected' : '') + '" aria-hidden="true"></span><strong>' + (status.key_present ? 'LangSmith key connected' : 'LangSmith is optional') + '</strong>' + (status.key_present ? '<span class="aq-muted">' + esc(String(status.region || 'region not recorded').toUpperCase()) + '</span>' : '') + '</div><p class="aq-caption" role="status">' + esc(connectionState) + '</p>' + (status.key_remembered ? '<p class="aq-caption">The saved key, region and workspace restore on server startup. Restoring or connecting makes no LangSmith request and does not validate the key.</p>' : '<p class="aq-caption">Connecting makes no LangSmith request and does not validate the key.</p>') + (status.credential_error ? '<p class="aq-warning" role="alert">The saved key could not be restored or updated. Re-enter it privately, or forget the saved copy. No LangSmith request was made.</p>' : '') + (status.workspace_id ? '<p class="aq-caption aq-mono">Workspace: ' + esc(status.workspace_id) + '</p>' : '') + '<p class="aq-caption">This sends qualification metrics only: no prompts, engineering data or API keys. Preview the exact payload, then upload it once to your private LangSmith account. It is not a public post. LangSmith account usage is separate from the Nebius dollar ceiling.</p>';
      select('[data-aq="connect-observability"]').disabled = locked();
      select('[data-aq="forget-observability"]').disabled = locked() || (!status.key_remembered && !status.credential_error);
      select('[data-aq="disconnect-observability"]').disabled = locked() || (!status.key_present && !status.key_remembered && !status.credential_error);
      host.querySelectorAll('[data-aq-key],[data-aq-region],[data-aq-workspace]').forEach(node => node.disabled = locked());
      const remember = select('[data-aq-remember]');
      remember.disabled = locked() || status.remember_supported !== true;
      if (status.remember_supported !== true) remember.checked = false;
      select('[data-aq-remember-note]').textContent = status.remember_supported === true ? 'Optional: save an encrypted copy for this Windows account and restore it when 6D starts. Leaving this unchecked removes any previous saved key when you connect.' : 'Remembering is unavailable on this device. A connection stays in server memory only.';
      select('[data-aq="preview"]').disabled = locked() || !id || running(record);
      const preview = state.preview;
      const panel = select('[data-aq-export-preview]');
      if (preview && preview.qualificationId === id) {
        panel.innerHTML = '<div class="aq-preview-heading"><strong>Exact metrics preview</strong><span class="aq-caption aq-mono">' + esc(preview.digest) + '</span></div><pre class="aq-json" data-aq-preview-json></pre><div class="aq-inline">' + button('export',state.busy === 'export' ? 'Uploading metrics…' : 'Upload these metrics once',locked() || !status.key_present || preview.attempted || running(record),true) + '<span class="aq-caption">' + (preview.attempted ? 'An upload was attempted. There is no automatic retry.' : 'Bound to the captured receipt and preview digest.') + '</span></div>';
        select('[data-aq-preview-json]').textContent = JSON.stringify(preview.payload,null,2);
      } else panel.replaceChildren();
      const attempts = items(status.attempts);
      select('[data-aq-export-history]').innerHTML = attempts.length ? '<details><summary>Recorded upload attempts (' + attempts.length + ')</summary><ul class="aq-attempts">' + attempts.slice(0,20).map(row => '<li>' + esc(row.qualification_id || row.export_id || row.attempt_id || 'Metrics export') + ' · ' + esc(label(row.state || row.status)) + (row.created_at ? ' · ' + esc(row.created_at) : '') + '</li>').join('') + '</ul></details>' : typeof status.attempts === 'number' ? '<p class="aq-caption">Recorded upload attempts: ' + esc(status.attempts) + ' of ' + esc(status.maximum_attempts ?? status.export_limit ?? 'the local limit') + '. An API acceptance records delivery only; it is not an independent evaluation.</p>' : '';
    }

    function renderResearch() {
      const research = state.status?.research || {};
      select('[data-aq-research]').innerHTML = '<div class="aq-inline"><span class="aq-dot ' + (research.key_present ? 'aq-connected' : '') + '" aria-hidden="true"></span><strong>' + (research.key_present ? 'Tavily key connected' : 'Tavily connection is optional') + '</strong></div><p>Search and inspect external references in Source library. Each search is explicit; a result never changes a numerical finding or becomes verified engineering evidence automatically.</p>' + button('sources','Open Source library for explicit search',typeof ctx.onSources !== 'function');
    }

    function render() {
      if (!live()) return;
      host.setAttribute('aria-busy',String(state.loading || !!state.busy));
      select('[data-aq="refresh"]').disabled = locked();
      renderConnection();renderQualification();renderObservability();renderResearch();message();
    }

    function schedule() {
      clearTimeout(state.timer);
      if (live() && running(latest()) && !state.error) state.timer = setTimeout(() => { if (live()) void refresh(true); },1000);
    }

    async function refresh(poll = false) {
      if (!live() || (state.busy && !poll)) return;
      const generation = ++state.generation;
      if (!poll) { state.loading = true;state.error = '';render(); }
      try {
        const status = await request('/api/ai-quality/status');
        if (!live() || generation !== state.generation) return;
        if (status?.schema !== 'sixd.ai-quality-status.v1') throw new Error('Unexpected status contract');
        if (state.status && (status.observability?.region !== obs().region || status.observability?.workspace_id !== obs().workspace_id)) state.preview = null;
        const previousObservability = state.status?.observability;
        state.status = status;
        if (!previousObservability || status.observability?.region !== previousObservability.region || status.observability?.workspace_id !== previousObservability.workspace_id) {
          select('[data-aq-region]').value = status.observability?.region === 'eu' ? 'eu' : 'us';
          select('[data-aq-workspace]').value = status.observability?.workspace_id || '';
        }
        const id = idOf(status.qualification?.latest);
        if (id !== state.receiptId) { state.receipt = null;state.receiptId = id;state.preview = null; }
        state.receiptError = false;
        if (id) {
          try {
            const receipt = await request('/api/ai-quality/runs/' + encodeURIComponent(id));
            if (!live() || generation !== state.generation) return;
            if (idOf(receipt) !== id) throw new Error('Receipt mismatch');
            state.receipt = receipt;
          } catch (error) {
            if (error.name === 'AbortError') throw error;
            if (!live() || generation !== state.generation) return;
            state.receipt = null;state.receiptError = true;state.preview = null;
          }
        }
      } catch (error) {
        if (live() && generation === state.generation && error.name !== 'AbortError') {
          state.error = 'AI quality status could not be refreshed. No live request was started or retried. Refresh to try reading status again.';
          state.status = null;state.receipt = null;state.receiptId = null;state.preview = null;
        }
      } finally {
        if (live() && generation === state.generation) { state.loading = false;render();schedule(); }
      }
    }

    async function mutate(action, work) {
      if (!live() || locked()) return;
      clearTimeout(state.timer);
      state.generation++;
      state.busy = action;state.error = '';state.notice = '';render();
      try { await work(); }
      catch (error) { if (live() && error.name !== 'AbortError') state.error = ({start:'The live batch could not be started or confirmed. Refresh status before deciding what to do next. No automatic retry will run.',connect:'The private LangSmith connection could not be confirmed. Check the key, region and workspace, then reconnect explicitly.',forget:'Removing the saved LangSmith key could not be confirmed. Refresh status to check it.',disconnect:'The LangSmith disconnect and saved-key removal could not be confirmed. Refresh status to check it.',preview:'The metrics preview could not be prepared. Refresh the receipt and try previewing again.',export:'The metrics upload failed or could not be confirmed. The attempt is retained; no automatic retry will run.'}[action] || 'The requested operation could not be completed.'); }
      finally { if (live()) { state.busy = '';render();schedule(); } }
    }

    async function start() {
      if (!canStart()) return;
      await mutate('start',async() => {
        await request('/api/ai-quality/start',{allow_spend:true,allowance_usd:.8});
        if (!live()) return;
        state.notice = 'The explicit live batch was accepted. Its receipt records requests, outcomes and reservations.';
        await refresh(true);
      });
    }

    async function connect() {
      const input = select('[data-aq-key]'), key = input.value.trim();
      input.value = '';
      if (!key) { state.error = 'Enter the LangSmith key privately in this form.';message();return; }
      const region = select('[data-aq-region]').value, workspace = select('[data-aq-workspace]').value.trim();
      const remember = obs().remember_supported === true && select('[data-aq-remember]').checked;
      select('[data-aq-remember]').checked = false;
      await mutate('connect',async() => {
        const status = await request('/api/observability/connect',{api_key:key,region,workspace_id:workspace || null,remember});
        if (!live()) return;
        state.preview = null;
        state.notice = status.key_remembered ? 'LangSmith connected and remembered on this device. No LangSmith request was made; the key has not been validated.' : 'LangSmith connected for this server session. No LangSmith request was made; the key has not been validated.';
        await refresh(true);
      });
    }

    async function clearConnection(action) {
      const input = select('[data-aq-key]');if (input) input.value = '';
      select('[data-aq-remember]').checked = false;
      await mutate(action,async() => {
        const status = await request('/api/observability/' + action,{});
        if (!live()) return;
        if (action === 'disconnect') state.preview = null;
        state.notice = action === 'forget' ? (status.key_present ? 'Saved LangSmith key forgotten. The current server session remains connected.' : 'Saved LangSmith key forgotten. No key is connected.') : 'LangSmith disconnected and the saved key removed. Existing local receipts remain available.';
        await refresh(true);
      });
    }

    async function preview() {
      const id = exportId();
      if (!id || running(selectedReceipt())) return;
      await mutate('preview',async() => {
        state.preview = null;
        const result = await request('/api/observability/preview',{qualification_id:id});
        if (!live() || exportId() !== id) return;
        if (typeof result.preview_digest !== 'string' || !result.preview_digest || result.payload === undefined) throw new Error('Invalid preview');
        if (result.qualification_id && result.qualification_id !== id) throw new Error('Preview receipt mismatch');
        state.preview = {qualificationId:id,digest:result.preview_digest,payload:result.payload,attempted:state.uploadAttempted.has(id)};
        state.notice = 'Inspect the exact metrics below. Previewing has not uploaded anything.';
      });
    }

    async function upload() {
      const p = state.preview, id = exportId();
      if (!p || p.attempted || p.qualificationId !== id || !obs().key_present || running(selectedReceipt())) return;
      p.attempted = true;state.uploadAttempted.add(id);
      await mutate('export',async() => {
        const result = await request('/api/observability/export',{qualification_id:id,preview_digest:p.digest,allow_upload:true});
        if (!live()) return;
        const resultState = result.state || result.status || result.attempt?.state || result.attempt?.status;
        state.notice = resultState === 'accepted_by_api' ? 'LangSmith accepted the metrics upload. This confirms API acceptance, not display or independent evaluation.' : resultState === 'failed' ? 'The upload attempt was recorded as failed. It will not be retried automatically.' : 'Metrics delivery is unconfirmed. The recorded attempt will not be retried automatically.';
        await refresh(true);
      });
    }

    host.innerHTML = '<article class="aq-workspace" aria-label="AI quality and connections"><header class="aq-header"><div><span class="aq-eyebrow">AI quality</span><h1>Evidence before confidence.</h1><p>Inspect the configured Assistant, run a bounded live qualification and keep its receipts visible.</p></div>' + button('refresh','Refresh status',true) + '</header><div data-aq-message aria-live="polite"></div><section class="aq-section aq-connection" aria-label="Nemotron connection"><div data-aq-connection></div></section><section class="aq-section" aria-labelledby="aq-qualification-title"><div class="aq-section-heading"><div><h2 id="aq-qualification-title">Live Nemotron qualification</h2><p>Four constructed evidence cases. This is a small application workflow check, not a broad model benchmark.</p></div></div><div data-aq-cases></div><div class="aq-start"><div><strong>A deliberate, bounded batch</strong><p>Up to $0.80 and 24 request reservations inside the existing cumulative allowance. No automatic retry, model selection or numerical verdict edits.</p><p class="aq-caption" data-aq-start-state></p></div>' + button('start','Run four live checks · $0.80 ceiling',true,true) + '</div><div data-aq-result></div></section><section class="aq-section" aria-labelledby="aq-observability-title"><div class="aq-section-heading"><div><h2 id="aq-observability-title">Optional metrics in LangSmith</h2><p>Preview first. Upload only after checking the captured metrics.</p></div></div><div data-aq-observability-status></div><form class="aq-private-form" data-aq-connect-form autocomplete="off"><label>LangSmith API key<input type="password" data-aq-key autocomplete="new-password" spellcheck="false" aria-describedby="aq-private-note"></label><label>Region<select data-aq-region><option value="us">US</option><option value="eu">EU</option></select></label><label>Workspace UUID <span class="aq-muted">(optional)</span><input type="text" data-aq-workspace autocomplete="off" spellcheck="false" placeholder="Leave blank for account default"></label><label class="aq-remember"><input type="checkbox" data-aq-remember aria-describedby="aq-remember-note" disabled>Remember on this device</label><p id="aq-remember-note" data-aq-remember-note class="aq-caption"></p><div class="aq-inline">' + button('connect-observability','Connect privately',true) + button('forget-observability','Forget saved key',true) + button('disconnect-observability','Disconnect and forget',true) + '</div><p id="aq-private-note" class="aq-caption">The key is cleared from this field on submission and never saved in browser storage or included in the preview. Forget removes the saved key and keeps the current session connected. Disconnect and forget removes both.</p></form><div class="aq-inline aq-export-actions">' + button('preview','Preview metrics for LangSmith',true) + '<span class="aq-caption">Available after a complete receipt is loaded.</span></div><div data-aq-export-preview></div><div data-aq-export-history></div></section><section class="aq-section" aria-labelledby="aq-research-title"><h2 id="aq-research-title">External source research</h2><div data-aq-research></div></section><footer class="aq-footer"><p>Local status reads are free of inference calls. Nemotron investigations and optional external service actions require their own explicit buttons. Qualification results do not certify a design or guarantee mission success.</p></footer></article>';

    host.onclick = event => {
      const element = event.target.closest('[data-aq]');
      if (!element || !host.contains(element) || element.disabled || !live()) return;
      const action = element.dataset.aq;
      if (action === 'refresh') void refresh();
      else if (action === 'start') void start();
      else if (action === 'connect-observability') void connect();
      else if (action === 'forget-observability') void clearConnection('forget');
      else if (action === 'disconnect-observability') void clearConnection('disconnect');
      else if (action === 'preview') void preview();
      else if (action === 'export') void upload();
      else if (action === 'sources') ctx.onSources?.();
      else if (action === 'receipt-json' && selectedReceipt()) { const pre = select('[data-aq-receipt-json]');pre.hidden = !pre.hidden;if (!pre.hidden) pre.textContent = JSON.stringify(selectedReceipt(),null,2);element.textContent = pre.hidden ? 'Show recorded JSON' : 'Hide recorded JSON'; }
    };
    host.onsubmit = event => { if (event.target.matches('[data-aq-connect-form]')) { event.preventDefault();if (!locked()) void connect(); } };
    state.dispose = () => {
      if (state.closed) return;
      state.closed = true;state.generation++;
      clearTimeout(state.timer);
      for (const controller of state.controllers) controller.abort();
      state.controllers.clear();
      const key = select('[data-aq-key]');if (key) key.value = '';
      host.onclick = null;host.onsubmit = null;host.replaceChildren();host.removeAttribute('aria-busy');
      state.preview = null;state.receipt = null;state.status = null;
      if (mounted === state) mounted = null;
    };
    render();void refresh();
    return state.dispose;
  }
  window.SixDAIQuality = Object.freeze({mount,unmount});
})();
