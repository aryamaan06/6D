/* Keep an explicitly opened disclosure at its reading position.
 * Native details, focus and scroll anchoring remain in charge outside the two
 * layout frames immediately following a summary activation. No navigation,
 * calculation, DOM replacement or persistent state is performed here. */
(function(global){
  'use strict';
  const controllers=new WeakMap();
  function install(root){
    if(!root?.addEventListener)return()=>{};
    if(controllers.has(root))return controllers.get(root);
    const doc=root.ownerDocument||root,view=doc.defaultView;
    if(!view?.requestAnimationFrame)return()=>{};
    let pending=null;
    function release(){
      if(!pending)return;
      const old=pending;pending=null;
      view.clearTimeout(old.timer);
      for(const frame of old.frames)view.cancelAnimationFrame(frame);
      for(const item of old.scrollers){
        for(const [name,stored] of Object.entries(item.styles)){
          if(stored.value)item.node.style.setProperty(name,stored.value,stored.priority);
          else item.node.style.removeProperty(name);
        }
      }
    }
    function scrollChain(summary){
      const found=[];let fixed=false;
      for(let node=summary.parentElement;node;node=node.parentElement){
        const style=view.getComputedStyle(node);
        if(/auto|scroll|overlay/.test(style.overflowY))found.push(node);
        if(style.position==='fixed'){fixed=true;break;}
      }
      if(!fixed&&doc.scrollingElement&&!found.includes(doc.scrollingElement))found.push(doc.scrollingElement);
      return found;
    }
    function summaryFor(event){
      const summary=event.target?.closest?.('summary');
      if(!summary||!root.contains(summary)||summary.parentElement?.tagName!=='DETAILS')return null;
      const detail=summary.parentElement;
      if(Array.from(detail.children).find(node=>node.tagName==='SUMMARY')!==summary)return null;
      const interactive=event.target.closest?.('a,button,input,select,textarea,[contenteditable="true"]');
      return interactive&&interactive!==summary?null:summary;
    }
    function begin(event){
      if(event.defaultPrevented||event.type==='click'&&event.button!==0)return;
      if(event.type==='keydown'&&(!['Enter',' '].includes(event.key)||event.repeat))return;
      const summary=summaryFor(event);if(!summary)return;
      if(pending?.summary===summary&&pending.wasOpen===summary.parentElement.open)return;
      release();
      const scrollers=scrollChain(summary).map(node=>{
        const styles={};
        for(const name of ['overflow-anchor','scroll-behavior'])styles[name]={value:node.style.getPropertyValue(name),priority:node.style.getPropertyPriority(name)};
        node.style.setProperty('overflow-anchor','none','important');
        node.style.setProperty('scroll-behavior','auto','important');
        return{node,styles};
      });
      const rect=summary.getBoundingClientRect();
      pending={summary,detail:summary.parentElement,wasOpen:summary.parentElement.open,top:rect.top,scrollers,frames:[],timer:null};
      // A prevented native activation must also release the temporary styles.
      pending.timer=view.setTimeout(release,180);
    }
    function stabilize(event){
      const current=pending;
      if(!current||event.target!==current.detail||current.detail.open===current.wasOpen)return;
      function correct(){
        if(pending!==current||!current.summary.isConnected)return release();
        for(const item of current.scrollers){
          const delta=current.summary.getBoundingClientRect().top-current.top;
          if(Math.abs(delta)<.5)break;
          item.node.scrollTop+=delta;
        }
      }
      correct();
      current.frames.push(view.requestAnimationFrame(()=>{
        if(pending!==current)return;
        correct();
        current.frames.push(view.requestAnimationFrame(()=>{if(pending===current){correct();release();}}));
      }));
    }
    function interrupt(event){
      if(!pending)return;
      // A second intentional interaction owns the viewport immediately.
      if(event.type==='keydown'&&['Enter',' '].includes(event.key)&&summaryFor(event)===pending.summary)return;
      release();
    }
    root.addEventListener('click',begin,true);
    root.addEventListener('keydown',begin,true);
    root.addEventListener('toggle',stabilize,true);
    for(const name of ['wheel','touchstart','pointerdown','keydown'])doc.addEventListener(name,interrupt,{capture:true,passive:true});
    function destroy(){
      release();root.removeEventListener('click',begin,true);root.removeEventListener('keydown',begin,true);root.removeEventListener('toggle',stabilize,true);
      for(const name of ['wheel','touchstart','pointerdown','keydown'])doc.removeEventListener(name,interrupt,true);
      controllers.delete(root);
    }
    controllers.set(root,destroy);return destroy;
  }
  global.SixDDisclosureScroll={install};
})(window);
