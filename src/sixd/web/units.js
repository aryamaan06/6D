/* Display notation only. Stored unit strings and technical evidence stay exact. */
(function () {
  'use strict';
  const superscripts = {'-':'⁻','+':'⁺','0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'};
  const tokens = ['kg','km','cm','mm','µm','μm','nm','m','ms','µs','μs','s','K','kN','N','GPa','MPa','kPa','Pa','MJ','kJ','J','MW','kW','W','kV','mV','V','mA','A','GHz','MHz','kHz','Hz','mol','cd','rad','deg','g'];
  const power = new RegExp('(^|[^A-Za-z0-9_µμ])(' + tokens.join('|') + ')\\^([+-]?\\d+)(?![A-Za-z0-9_^]|\\.\\d)', 'g');
  const excluded = 'blockquote,.sl-source-meta,.sl-preserve,.si-metadata,input,textarea,select,option,datalist,pre,code,script,style,noscript,kbd,samp,[contenteditable]:not([contenteditable="false"]),[data-raw],[data-json],[data-provenance],[data-preserve-notation],[data-technical],.sd-receipt,[class*="identity"],[class*="provenance"],[class*="raw-json"],[class*="source-code"]';

  function technical(text) {
    if (/https?:\/\/|www\.|mailto:|`|[A-Za-z]:\\/.test(text)) return true;
    if (/['"][^'"\n]+['"]\s*:/.test(text)) return true;
    const trimmed = text.trim();
    if (/^[{[]/.test(trimmed)) {
      try { JSON.parse(trimmed); return true; } catch (_) { /* A unit label may use brackets. */ }
    }
    return false;
  }

  function format(value) {
    if (typeof value !== 'string' || !value.includes('^') || technical(value)) return value;
    return value.replace(power, (_, boundary, unit, exponent) => boundary + unit + Array.from(exponent, char => superscripts[char]).join(''));
  }

  // Presentation only: never coerce input text or round a value used by a calculation.
  // Significant digits preserve tiny nonzero values; fixed decimal places do not.
  function number(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
    if (value === 0) return '0';
    const magnitude = Math.abs(value);
    return magnitude < 1e-4 || magnitude >= 1e7
      ? value.toExponential(5)
      : value.toLocaleString('en-US', {maximumSignificantDigits:7});
  }

  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function value(amount, unit = '') {
    const valid = typeof amount === 'number' && Number.isFinite(amount);
    const suffix = typeof unit === 'string' && unit ? ' ' + unit : '';
    const exact = valid ? 'Exact: ' + String(amount) + suffix : 'Numeric value unavailable';
    return '<span class="sd-number" title="' + escape(exact) + '">' + escape(number(amount) + format(suffix)) + '</span>';
  }

  function eligible(node) {
    const parent = node.parentElement;
    return parent && !parent.closest(excluded) && !parent.closest('[hidden],[aria-hidden="true"]');
  }

  function decorate(root) {
    if (!root) return;
    if (root.nodeType === 3) {
      if (eligible(root)) {
        const next = format(root.nodeValue);
        if (next !== root.nodeValue) root.nodeValue = next;
      }
      return;
    }
    if (root.nodeType === 1 && root.matches(excluded)) return;
    const document = root.ownerDocument || root;
    const walker = document.createTreeWalker(root, 4);
    let node;
    while ((node = walker.nextNode())) decorate(node);
  }

  function observe(root) {
    decorate(root);
    if (!root) return {disconnect() {}};
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'characterData' || record.type === 'attributes') decorate(record.target);
        else for (const node of record.addedNodes) decorate(node);
      }
    });
    // A retained panel may become visible without replacing any of its text.
    observer.observe(root, {subtree:true, childList:true, characterData:true, attributes:true,
      attributeFilter:['hidden','aria-hidden','class','style','contenteditable']});
    return observer;
  }

  window.SixDUnits = {format, number, value, decorate, observe};
})();
