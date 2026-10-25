/* Hosted restrictions complement server enforcement; the local app is unchanged. */
(() => {
  'use strict';
  const restricted = [
    '[data-action="ai-settings"]', '#sd-ai-connect-dialog', '#sd-ai-key', '#sd-ai-connect-button',
    '[data-action="ai-disconnect"]', '[data-action="ai-forget"]',
    '[data-aq-connect-form]', '.sr-connection', '[data-sr-action="search"]',
    '[data-aq="start"]', '[data-aq="preview"]', '[data-aq="export"]',
    '[data-aq="connect-observability"]', '[data-aq="forget-observability"]',
    '[data-aq="disconnect-observability"]', '#sd-evidence-evaluation', '#sd-ultra-diagnostic',
    '#sd-workflow-evaluation', '[data-action*="evaluation-start"]', '[data-action*="diagnostic-start"]'
  ].join(',');
  let mode = null, notice = null, logout = null, observer = null, ended = false;
  function restrict() {
    if (!mode?.hosted || !document.body) return;
    document.querySelectorAll(restricted).forEach(node => {
      if (!node.hidden) node.hidden = true;
      if ('disabled' in node && !node.disabled) node.disabled = true;
      if (!node.hasAttribute('data-hosted-restricted')) node.setAttribute('data-hosted-restricted', '');
      node.querySelectorAll?.('input,select,button').forEach(control => {if (!control.disabled) control.disabled = true;});
    });
    const storageLabel = document.querySelector('.sd-side-bottom > .sd-small');
    if (storageLabel && storageLabel.textContent !== 'Saved in this isolated hosted workspace') storageLabel.textContent = 'Saved in this isolated hosted workspace';
    if (mode.live_ai_enabled === false) {
      document.querySelectorAll('#sd-ai-start').forEach(node => {if (!node.disabled) node.disabled = true;node.title = 'Live inference is disabled for this hosted deployment.';});
    }
  }
  function expire() {
    if (ended || !mode?.hosted || !notice) return;
    ended = true;
    notice.textContent = 'Your review session has expired or been signed out. Refresh to enter the invitation code again.';
    notice.setAttribute('role', 'alert');
    document.documentElement.classList.add('sixd-hosted-expired');
    if (logout) logout.textContent = 'Return to sign in';
  }
  function install(value) {
    mode = value;
    document.documentElement.classList.add('sixd-hosted');
    const banner = document.createElement('aside');
    banner.className = 'sixd-hosted-banner';
    banner.setAttribute('aria-label', 'Hosted review session');
    notice = document.createElement('p');
    notice.className = 'sixd-hosted-notice';
    notice.setAttribute('role', 'status');
    notice.textContent = 'Isolated review workspace · ' + (value.live_ai_enabled === true ? 'AI runs only when explicitly requested, within server limits.' : 'Live AI is disabled for this deployment. Engineering calculations run locally on the hosted server.');
    const detail = document.createElement('p');
    detail.className = 'sixd-hosted-detail';
    detail.textContent = 'Constructed/public data only. Provider keys and administrative actions are managed by the demo owner. External searches and metrics uploads are unavailable here.';
    if (typeof value.expires_at === 'string' && Number.isFinite(Date.parse(value.expires_at))) detail.textContent += ' Session expires ' + new Date(value.expires_at).toLocaleString() + '.';
    const copy = document.createElement('div');copy.append(notice, detail);
    if (value.live_ai_enabled === true) {
      const budget = value.inference_budget;
      const remaining = ['total_remaining_usd','daily_remaining_usd','session_remaining_usd'];
      const budgetNote = document.createElement('p');
      budgetNote.className = 'sixd-hosted-detail sixd-hosted-budget';
      budgetNote.textContent = budget && remaining.every(key => typeof budget[key] === 'number' && Number.isFinite(budget[key]) && budget[key] >= 0)
        ? 'Inference allowance remaining at page load: cumulative $' + budget.total_remaining_usd.toFixed(4) + ' · UTC day $' + budget.daily_remaining_usd.toFixed(4) + ' · this session $' + budget.session_remaining_usd.toFixed(4) + '. Conservative reservations, not provider billed balance.'
        : 'Live inference uses server-controlled cumulative, UTC-day and session reservation limits. Remaining allowance could not be displayed.';
      copy.append(budgetNote);
    }
    logout = document.createElement('button');
    logout.type = 'button';logout.className = 'sixd-hosted-logout';logout.textContent = 'Sign out';
    logout.addEventListener('click', async () => {
      if (ended) {location.replace('/');return;}
      logout.disabled = true;
      try {
        const response = await fetch('/api/hosted/logout', {method:'POST',credentials:'same-origin',redirect:'error',headers:{'Content-Type':'application/json','Accept':'application/json'},body:'{}'});
        if (response.ok || response.status === 401) {location.replace('/');return;}
        notice.textContent = response.status === 409 ? 'Wait for the active investigation to finish before signing out.' : 'Sign-out could not be confirmed. Refresh and try again.';
      } catch {notice.textContent = 'Sign-out could not be confirmed. Refresh and try again.';}
      finally {logout.disabled = false;}
    });
    banner.append(copy, logout);document.body.prepend(banner);
    document.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target.closest(restricted) : null;
      if (target) {event.preventDefault();event.stopImmediatePropagation();}
    }, true);
    document.addEventListener('submit', event => {
      if (event.target instanceof Element && event.target.matches('[data-aq-connect-form],[data-sr-connect-form]')) {event.preventDefault();event.stopImmediatePropagation();}
    }, true);
    observer = new MutationObserver(restrict);observer.observe(document.body,{childList:true,subtree:true});restrict();
    const nativeFetch = window.fetch;
    window.fetch = async function (...args) {
      const response = await nativeFetch.apply(this,args);
      const input = args[0], address = typeof input === 'string' ? input : input?.url;
      if (response.status === 401 && typeof address === 'string') {
        try {if (new URL(address,location.href).origin === location.origin) expire();} catch {}
      }
      return response;
    };
  }
  async function start() {
    try {
      const response = await fetch('/api/hosted/status',{credentials:'same-origin',redirect:'error',headers:{'Accept':'application/json'}});
      if (!response.ok) return;
      const value = await response.json();
      if (value?.hosted === true && value.authenticated === true) install(value);
    } catch { /* Optional local-mode enhancement; server remains authoritative. */ }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start,{once:true});else void start();
})();
