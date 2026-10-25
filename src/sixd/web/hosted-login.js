/* Invitation login only. Credentials never enter URLs or browser storage. */
(() => {
  'use strict';
  const form = document.querySelector('#hosted-login');
  const input = document.querySelector('#hosted-access-code');
  const button = document.querySelector('#hosted-open');
  const status = document.querySelector('#hosted-login-status');
  const error = document.querySelector('#hosted-login-error');
  if (!form || !input || !button || !status || !error) return;
  let busy = false;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    const accessCode = input.value;
    input.value = '';
    busy = true;
    button.disabled = true;
    error.hidden = true;
    error.textContent = '';
    status.textContent = 'Opening your isolated review workspace…';
    try {
      const response = await fetch('/api/hosted/login', {
        method: 'POST', credentials: 'same-origin', redirect: 'error',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify({access_code: accessCode})
      });
      if (!response.ok) {
        error.textContent = response.status === 429 ? 'Too many attempts. Wait a little before trying again.' : response.status === 503 ? 'Review access is temporarily unavailable. Contact the demo owner.' : 'The invitation could not be accepted. Check the code or contact the demo owner.';
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
      input.value = '';
      if (!error.hidden) input.focus();
    }
  });
})();
