/* One-click public workspace launcher. */
(() => {
  'use strict';
  const button = document.querySelector('#hosted-open');
  const status = document.querySelector('#hosted-login-status');
  const error = document.querySelector('#hosted-login-error');
  if (!button || !status || !error) return;
  let busy = false;
  button.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    error.hidden = true;
    error.textContent = '';
    status.textContent = 'Launching your review workspace…';
    try {
      const response = await fetch('/api/hosted/login', {
        method: 'POST', credentials: 'same-origin', redirect: 'error',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify({})
      });
      if (!response.ok) {
        error.textContent = response.status === 429
          ? 'Too many attempts. Wait a little before trying again.'
          : 'Review access is temporarily unavailable. Refresh and try again.';
        error.hidden = false;
        status.textContent = '';
        return;
      }
      location.replace('/');
    } catch {
      error.textContent = 'The connection could not be confirmed. Refresh this page before trying again.';
      error.hidden = false;
      status.textContent = '';
    } finally {
      busy = false;
      button.disabled = false;
    }
  });
})();
