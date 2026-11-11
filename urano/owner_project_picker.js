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
  // One consistent layout: Montara + Projects left, editor steps centre, Account right.
  const brand = oldHeader.querySelector('.brand');
  if (brand) brand.after(trigger);
  else oldHeader.prepend(trigger);
  if (isEditor) {
    const account = document.createElement('button');
    account.type = 'button'; account.className = 'btn ghost small';
    account.id = 'montaraOwnerAccount'; account.textContent = 'Account';
    const accountDialog = document.createElement('dialog');
    accountDialog.className = 'montara-owner-dialog montara-owner-account';
    const accountTitle = document.createElement('h2'); accountTitle.textContent = 'Account';
    const signOut = document.createElement('button');
    signOut.type = 'button'; signOut.className = 'btn ghost small';
    signOut.textContent = 'Sign out';
    const cancel = document.createElement('button');
    cancel.type = 'button'; cancel.className = 'btn ghost small';
    cancel.textContent = 'Close';
    const accountStatus = document.createElement('p');
    accountStatus.setAttribute('role', 'alert');
    const closeEngine = document.createElement('button');
    closeEngine.type = 'button'; closeEngine.className = 'btn ghost small';
    closeEngine.textContent = 'Close idle Engine';
    const actions = document.createElement('div'); actions.className = 'actions';
    actions.append(closeEngine, signOut, cancel);
    accountDialog.append(accountTitle, actions, accountStatus);
    closeEngine.addEventListener('click', async () => {
      const ownProject = location.pathname.match(/\/projects\/([0-9a-f-]{36})\//i)?.[1];
      if(!ownProject) return;
      closeEngine.disabled = true;
      accountStatus.textContent = 'Checking current project activity…';
      try {
        // The Owner-bound bridge retrieves only this project's state.
        // Refuse to stop on any unavailable or uncertain status.
        const token = await csrf();
        const admission = await api('projects/'+encodeURIComponent(ownProject)+'/ensure',{
          method:'POST',headers:{'X-Urano-CSRF':token,Origin:location.origin}
        });
        if(admission.state!=='ready' || !Number.isSafeInteger(admission.generation))
          throw Error('Private Engine verification failed. Nothing was stopped.');
        const current = await fetch('/urano/v1/media/'+encodeURIComponent(ownProject)+'/wizard/status', {
          credentials:'same-origin',cache:'no-store',
          headers:{'X-Urano-CSRF':token,
                   'X-Montara-Engine-Generation':String(admission.generation)}
        });
        if(!current.ok) throw Error('Project status is not verified. Nothing has been stopped.');
        const state = await current.json();
        if(state.status !== 'idle')
          throw Error('Project is not idle ('+String(state.status||'unknown')+'). Finish or cancel its work first.');
        if(!window.confirm('Close the idle Engine for this project? Project files will remain saved.')) {
          accountStatus.textContent = 'Engine was not closed.';
          return;
        }
        const result=await api('projects/'+encodeURIComponent(ownProject)+'/close',{
          method:'POST',headers:{'X-Urano-CSRF':token,Origin:location.origin}
        });
        if(result.state!=='stopped')throw Error('Engine closure was not confirmed.');
        accountStatus.textContent='Engine closed. Project files remain saved. Returning to projects…';
        location.replace('/urano/v1/entry');
      }catch(error){accountStatus.textContent=error.message}
      finally{closeEngine.disabled=false}
    });
    document.body.append(accountDialog);
    oldHeader.append(account);
    account.addEventListener('click', () => accountDialog.showModal());
    cancel.addEventListener('click', () => accountDialog.close());
    signOut.addEventListener('click', async () => {
      signOut.disabled = true;
      try {
        await api('logout', {method:'POST',
          headers:{'X-Urano-CSRF':await csrf(),Origin:location.origin}});
        location.replace('/urano/v1/google/start');
      } catch (error) {
        accountStatus.textContent = error.message;
        signOut.disabled = false;
      }
    });
  }
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
  function syncEditorScope() {
    if(!isEditor) return;
    const byId = id => document.getElementById(id);
    const home = byId('home');
    const mode = byId('mode');
    if (home && !home.hidden) {setScope('all');return;}
    if (mode && !mode.hidden) {
      setScope(byId('videoChoices') && !byId('videoChoices').hidden ? 'video' :
               byId('musicChoices') && !byId('musicChoices').hidden ? 'music' : 'all');
      return;
    }
    // The same Chema Footage screen is used by Stage and by all Music
    // actions. URL alone must never label an audio task "Stage projects".
    const label = byId('modeLabel')?.textContent?.trim().toLowerCase() || '';
    const musicTask = ['mix a song','mix a full session','master a mix']
      .some(value => label.includes(value));
    setScope(musicTask ? 'music' : 'stage');
  }
  if(isEditor) {
    const watched = ['home','mode','videoChoices','musicChoices','footage'];
    const observer = new MutationObserver(syncEditorScope);
    for(const id of watched){
      const node = document.getElementById(id);
      if(node) observer.observe(node,{attributes:true,attributeFilter:['hidden']});
    }
    // Mode label changes after selecting an audio task, often without
    // leaving Footage; track those text updates as well as screen changes.
    const taskLabel = document.getElementById('modeLabel');
    if(taskLabel) observer.observe(taskLabel,{
      childList:true,characterData:true,subtree:true
    });
    window.addEventListener('popstate',syncEditorScope);
    document.addEventListener('click',event=>{
      if(event.target.closest('.brand, #modeQuestionBack, [data-intent]'))
        queueMicrotask(syncEditorScope);
    });
    queueMicrotask(syncEditorScope);
  }
  async function api(path,opts={}) {
    const res=await fetch('/urano/v1/'+path,{credentials:'same-origin',cache:'no-store',...opts});
    const body=await res.json().catch(()=>({}));
    if(!res.ok)throw Error(typeof body.error==='string'?body.error:body.error?.message||'Request failed ('+res.status+')');
    return body;
  }
  let localCsrfJob = null;
  function getLocalCsrf() {
    if(!localCsrfJob) {
      localCsrfJob = api('session/refresh',{
        method:'POST',headers:{Origin:location.origin}
      }).then(body=>{
        if(!/^[a-f0-9]{64}$/.test(body.csrf||''))throw Error('Private session unavailable');
        return body.csrf;
      }).catch(error=>{localCsrfJob=null;throw error});
    }
    return localCsrfJob;
  }
  if(!window.MontaraOwnerCsrf) {
    window.MontaraOwnerCsrf = Object.freeze({get:getLocalCsrf});
  }
  async function csrf(){return window.MontaraOwnerCsrf.get();}

  async function openProject(p,newProject=false){
    const mode=modeOf(p);
    if(mode!=='stage') {message('This project type is not yet available in the Owner beta.');return;}
    if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(p.id))
      throw Error('Invalid project ID');
    try {sessionStorage.setItem('montara-owner-selected-stage',p.id);}catch {}
    if(isEditor) {
      const current=location.pathname.match(/\/projects\/([0-9a-f-]{36})\//i)?.[1];
      if(current===p.id){
        dialog.close();
        // Same Owner project, but the native Chema Home/Mode screen is
        // showing: re-enter Stage instead of silently doing nothing.
        const home=document.getElementById('home');
        const mode=document.getElementById('mode');
        if((home&&!home.hidden)||(mode&&!mode.hidden)){
          location.assign('/urano/v1/editor/projects/'+encodeURIComponent(p.id)+'/?start=stage');
        }
        return;
      }
    }
    // A project switch must be admitted BEFORE navigating into Chema's
    // recovery UI. A 409 stays in this readable modal; never stop an
    // existing Engine or pretend the network disconnected.
    if(!newProject) {
      message('Opening private project…');
      try {
        await api('projects/'+encodeURIComponent(p.id)+'/ensure', {
          method:'POST',
          headers:{'X-Urano-CSRF':await csrf(),Origin:location.origin}
        });
      } catch (error) {
        message(error.message === 'Engine already busy'
          ? 'Another project has an active Engine. Open that Stage, then use Account → Close idle Engine after finishing its work. Nothing has been stopped.'
          : error.message);
        return;
      }
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
      button.append(strong,meta);button.addEventListener('click',()=>{openProject(p).catch(error=>message(error.message))});
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
      await openProject(result.project,true);
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
