/* Shared light dismissal for native dialogs and floating action menus only.
 * Close requests retain native cancel/close hooks; no form is submitted here. */
(() => {
  'use strict';
  const menuSelector='details.sd-project-actions, details.sd-tool-menu, details[data-overlay-menu]';
  const reasons=new WeakMap();
  let press=null, menuPress=null, draggedMenus=[], suppressPointerClick=false;

  function inside(dialog,event) {
    if (event.target !== dialog && dialog.contains(event.target)) return true;
    const bounds=dialog.getBoundingClientRect();
    return event.clientX>=bounds.left && event.clientX<=bounds.right &&
      event.clientY>=bounds.top && event.clientY<=bounds.bottom;
  }
  function currentDialog(event) {
    const containing=event.target?.closest?.('dialog[open]');
    if (containing) return containing;
    const open=[...document.querySelectorAll('dialog[open]')];
    return open.reverse().find(dialog=>dialog.matches(':modal')) || open[0] || null;
  }
  function requestClose(dialog,reason='outside-pointer') {
    if (!(dialog instanceof HTMLDialogElement) || !dialog.open) return false;
    reasons.set(dialog,reason);
    try {
      if (typeof dialog.requestClose === 'function') dialog.requestClose();
      else if (dialog.dispatchEvent(new Event('cancel',{cancelable:true}))) dialog.close();
    } finally {reasons.delete(dialog);}
    return !dialog.open;
  }
  // Capture gives workspace guards a chance to veto before module-specific
  // cancel listeners perform cleanup (including spreadsheet import teardown).
  document.addEventListener('cancel',event=>{
    const dialog=event.target;
    if (!(dialog instanceof HTMLDialogElement)) return;
    const allowed=dialog.dispatchEvent(new CustomEvent('sixd:before-dismiss',{
      bubbles:true,cancelable:true,detail:{reason:reasons.get(dialog)||'escape'}
    }));
    if (!allowed) {event.preventDefault();event.stopImmediatePropagation();}
  },true);

  document.addEventListener('pointerdown',event=>{
    suppressPointerClick=false;press=null;menuPress=null;draggedMenus=[];
    if (event.button!==0 || event.isPrimary===false) return;
    menuPress={id:event.pointerId,menus:[...document.querySelectorAll(menuSelector)].filter(menu=>menu.open&&menu.contains(event.target))};
    const dialog=currentDialog(event);
    if (dialog && !inside(dialog,event)) press={dialog,id:event.pointerId};
  },true);
  document.addEventListener('pointerup',event=>{
    if(menuPress?.id===event.pointerId)draggedMenus=menuPress.menus.filter(menu=>menu.open&&!menu.contains(event.target));
    menuPress=null;
    const start=press;press=null;
    if (!start || event.button!==0 || event.pointerId!==start.id ||
        !start.dialog.open || inside(start.dialog,event)) return;
    // Do not let the same completed outside click activate a control behind
    // the dialog, even when an unsaved-edit guard refuses the close request.
    suppressPointerClick=true;
    event.preventDefault();
    requestClose(start.dialog);
  },true);
  document.addEventListener('pointercancel',()=>{press=null;menuPress=null;draggedMenus=[];},true);
  document.addEventListener('click',event=>{
    if (suppressPointerClick && event.detail>0) {
      suppressPointerClick=false;event.preventDefault();event.stopImmediatePropagation();
    }
  },true);
  document.addEventListener('click',event=>{
    const protectedMenus=new Set(draggedMenus);draggedMenus=[];
    document.querySelectorAll(menuSelector).forEach(menu=>{
      if (!menu.open || protectedMenus.has(menu)) return;
      const summary=menu.querySelector(':scope > summary');
      if (!menu.contains(event.target) ||
          (!summary?.contains(event.target) && event.target?.closest?.('button,a,[role="menuitem"]')))
        menu.open=false;
    });
  });
  document.addEventListener('keydown',event=>{
    if (event.key!=='Escape' || document.querySelector('dialog[open]')) return;
    const open=[...document.querySelectorAll(menuSelector)].filter(menu=>menu.open);
    if (!open.length) return;
    event.preventDefault();
    open.forEach(menu=>{menu.open=false;});
    open.at(-1).querySelector(':scope > summary')?.focus();
  });
  window.SixDOverlayDismiss=Object.freeze({requestClose});
})();
