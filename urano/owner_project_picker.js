/* Montara Owner private project picker. Reusable, not another editor. */
(() => {
  'use strict';
  if (window.MontaraProjectPicker) return;
  const isEditor = /^\/urano\/v1\/editor\/projects\/[0-9a-f-]{36}\//i.test(location.pathname);
  const state = { scope: isEditor ? 'stage' : 'all', projects:[], open:false, busy:false };
  const labels = {all:'All projects',video:'Video projects',music:'Music projects',
    stage:'Stage projects',push:'Push projects',show:'Show projects'};
  const modes = {stage:'Stage',push:'Push',show:'Show'};
  const oldHeader = document.querySelector('header.top');
  if (!oldHeader) return;
  const trigger = document.createElement('button');
  trigger.type='button';trigger.className='btn ghost small';trigger.id='montaraOwnerProjectsButton';
  trigger.setAttribute('aria-haspopup','dialog');
  const dialog = document.createElement('dialog');
  dialog.id='montaraOwnerProjectsDialog';
  dialog.className='montara-owner-dialog';
  dialog.setAttribute('aria-label','My projects');
  const heading = document.createElement('h2');
  heading.id='montaraOwnerProjectsHeading';
  const close = document.createElement('button');
  close.type='button';close.className='btn ghost small';close.textContent='Close';
  const top = document.createElement('div');top.className='montara-owner-top';
  top.append(heading,close);
  const search = document.createElement('input');
  search.type='search';search.placeholder='Search projects';search.setAttribute('aria-label','Search projects');
  const list = document.createElement('ul');list.className='montara-owner-list';
  const hint = document.createElement('p');
  hint.className='hint';hint.setAttribute('role','status');hint.setAttribute('aria-live','polite');
  const form = document.createElement('form');form.className='montara-owner-new';
  const name = document.createElement('input');name.required=true;name.maxLength=120;
  name.placeholder='Project name';name.setAttribute('aria-label','New project name');
  const create = document.createElement('button');create.type='submit';create.className='btn primary small';create.textContent='Create Stage';
  const modeSelect = document.createElement('select');modeSelect.setAttribute('aria-label','Project type');
  for(const mode of ['stage','push','show']){const o=document.createElement('option');o.value=mode;o.textContent=modes[mode];modeSelect.append(o)}
  form.append(modeSelect,name,create);
  dialog.append(top,search,list,hint,form);
  document.body.append(dialog);
  oldHeader.querySelector('#newVideo, #ownerLogout, #sharePreview')?.before(trigger);
  if(!trigger.isConnected) oldHeader.append(trigger);
  function modeOf(p) {
    const value=p.mode || p.recipe?.montara_beta_workspace?.mode;
    return ['stage','push','show'].includes(value)?value:'legacy';
  }
  function visible(p) {
    const m=modeOf(p);
    return state.scope==='all'||state.scope==='video'&&m!=='music'||
      state.scope==='music'&&m==='music'||m===state.scope;
  }
  function setScope(scope) {
    if(!labels[scope])return;
    state.scope=scope;
    trigger.textContent=labels[scope];
    heading.textContent=labels[scope];
    modeSelect.value=['stage','push','show'].includes(scope)?scope:'stage';
    modeSelect.hidden=state.scope==='stage'||state.scope==='push'||state.scope==='show';
    create.textContent='Create '+modes[modeSelect.value];
    form.hidden=state.scope==='music';
    if(state.open)render();
  }
  function message(value){hint.textContent=value||'';}
  async function api(path,opts={}) {
    const res=await fetch('/urano/v1/'+path,{credentials:'same-origin',cache:'no-store',...opts});
    const body=await res.json().catch(()=>({}));
    if(!res.ok)throw Error(typeof body.error==='string'?body.error:body.error?.message||'Request failed ('+res.status+')');
    return body;
  }
  async function csrf(){
    return (await api('session/refresh',{method:'POST'})).csrf;
  }
  function openProject(p,newProject=false){
    const mode=modeOf(p);
    if(mode!=='stage') {message('This project type is not yet available in the Owner beta.');return;}
    if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(p.id))throw Error('Invalid project ID');
    if(isEditor) {
      const current=location.pathname.match(/\/projects\/([0-9a-f-]{36})\//i)?.[1];
      if(current===p.id){dialog.close();return;}
    }
    location.assign('/urano/v1/editor/projects/'+encodeURIComponent(p.id)+'/'+
      (newProject?'?start=stage':'?resume=footage'));
  }
  function render() {
    list.replaceChildren();
    const term=search.value.trim().toLocaleLowerCase();
    const filtered=state.projects.filter(p=>visible(p)&&
      (!term||(p.title||'').toLocaleLowerCase().includes(term)));
    for(const [i,p] of filtered.entries()){
      const li=document.createElement('li');
      const button=document.createElement('button');button.type='button';button.className='montara-owner-choice';
      const strong=document.createElement('strong');strong.textContent=p.title || 'Untitled project';
      const meta=document.createElement('small');
      meta.textContent=(modes[modeOf(p)]||'Legacy')+(i===0?' · Latest':'');
      button.append(strong,meta);button.addEventListener('click',()=>openProject(p));
      li.append(button);list.append(li);
    }
    message(filtered.length?'':'No projects in this area yet.');
  }
  async function open(scope){
    if(scope)setScope(scope);
    if(!dialog.open)dialog.showModal();
    state.open=true;search.value='';message('Loading projects…');
    try { state.projects=(await api('projects')).projects||[];render(); }
    catch(error){message(error.message)}
  }
  trigger.addEventListener('click',()=>open());
  close.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{state.open=false});
  search.addEventListener('input',render);
  modeSelect.addEventListener('change',()=>{create.textContent='Create '+modes[modeSelect.value]});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(state.busy)return;
    state.busy=true;create.disabled=true;message('Creating project…');
    try {
      const mode=modeSelect.value;
      if(mode!=='stage') {message('Only Stage editing is enabled in this beta.');return;}
      const result=await api('editor/projects',{method:'POST',
        headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf()},
        body:JSON.stringify({title:name.value,mode})});
      openProject(result.project,true);
    }catch(error){message(error.message)}
    finally{state.busy=false;create.disabled=false}
  });
  document.addEventListener('click',event=>{
    if(isEditor)return;
    const intent=event.target.closest('[data-intent]');
    if(intent)setScope(intent.dataset.intent);
    const card=event.target.closest('[data-platform]');
    if(card)setScope(({youtube:'stage',reel:'push',show:'show'})[card.dataset.platform]);
    const task=event.target.closest('[data-audio-task]');
    if(task)setScope('music');
  });
  setScope(state.scope);
  window.MontaraProjectPicker=Object.freeze({open,setScope});
})();
