'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {activity:'M3 12h4l3-8 4 16 3-8h4',chat:'M4 4h16v12H9l-5 4V4',tabs:'M3 7h18v14H3z M6 3h12v4',agents:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-4',vote:'M4 13v8h16v-8 M8 7l3 3 6-7 M7 13h10',tasks:'M9 5h12 M9 12h12 M9 19h12 M3 5l1 1 2-3 M3 12l1 1 2-3 M3 19l1 1 2-3',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',plus:'M12 5v14 M5 12h14',arrow:'M5 12h14 M14 7l5 5-5 5',pause:'M8 5v14 M16 5v14',play:'M7 4l13 8-13 8V4',folder:'M3 6h7l2 3h9v12H3V6',close:'M6 6l12 12 M18 6L6 18',send:'M3 3l18 9-18 9 4-9-4-9 M7 12h14',check:'M4 12l5 5L20 6',book:'M4 3h14v18H4z M8 7h6 M8 11h6',copy:'M8 8h12v13H8z M16 8V3H3v13h5',link:'M10 13a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-2 2 M14 11a4 4 0 0 0-6 0l-4 4a4 4 0 0 0 6 6l2-2',chevronLeft:'M15 6l-6 6 6 6',chevronRight:'M9 6l6 6-6 6',chevronUp:'M6 15l6-6 6 6',chevronDown:'M6 9l6 6 6-6'};
const icon = name => `<span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="${paths[name] || paths.chat}"/></svg></span>`;
const button = (act,label,cls='',extra='') => `<button type="button" class="${cls}" data-act="${act}" ${extra}>${label}</button>`;
let state=null, project=null, view='activity', tabs=[], drafts={}, selectedAgentPane='chat', pollId=0, connected=true, oldest=null;
let renderedRoom=null, reply=null;
const humanNotesCache={}, humanNoteRequests={};
let humanNotesRequest=0, contentRequest=0;
const scrollPositions={};
const agentConfigCollapsed=new Map();
const agentConfigKey = id => JSON.stringify([project,id]);
function agentConnectionHint(a){return a.status==='disconnected'?'<p class="info-note">Not connected. Start a session in your agent host, then use Connect terminal to resume this identity.</p>':'';}
function agentProfile(a){
  const collapsed=agentConfigCollapsed.get(agentConfigKey(a.id))===true;
  return `<section class="agent-profile" data-collapsed="${collapsed}"><div class="agent-profile-summary">${avatar(a.id)}<h2 class="grow" style="color:${esc(a.color)}">${esc(a.handle)} ${state.config.lead_agent_id===a.id?'<span class="tag lead">LEAD</span>':''}</h2><span class="tag agent-profile-presence">${esc(presence(a))}</span>${button('agent-config',icon(collapsed?'chevronDown':'chevronUp'),'ghost small',`data-id="${esc(a.id)}" aria-expanded="${!collapsed}" aria-controls="agent-config-details" aria-label="${collapsed?'Expand':'Collapse'} agent details" title="${collapsed?'Expand':'Collapse'} agent details"`)}</div><div id="agent-config-details"${collapsed?' hidden':''}><p class="muted">${esc(a.role)} · ${esc(a.provider)}</p><p class="info-note">Template: ${esc(a.template_ref?.id||'None')}</p>${agentConnectionHint(a)}<div class="uuid">${esc(a.id)} ${button('copy-id',icon('copy'),'ghost small',`data-id="${esc(a.id)}" title="Copy UUID" aria-label="Copy UUID"`)}</div><div class="agent-controls">${button('rename-agent','Rename','small',`data-id="${esc(a.id)}"`)}${button('toggle-agent',icon(a.paused?'play':'pause')+' '+(a.paused?'Resume':'Pause at checkpoint'),'small',`data-id="${esc(a.id)}"`)}${state.config.lead_agent_id!==a.id?button('appoint-lead','Designate lead','small',`data-id="${esc(a.id)}"`):''}${button('agent-connect','Connect terminal','ghost small',`data-id="${esc(a.id)}"`)}</div></div><div class="segment">${button('agent-pane','Direct chat',selectedAgentPane==='chat'?'active':'','data-pane="chat"')}${button('agent-pane','Working notes',selectedAgentPane==='notes'?'active':'','data-pane="notes"')}${button('agent-pane','Checkpoint & context',selectedAgentPane==='checkpoint'?'active':'','data-pane="checkpoint"')}${button('agent-pane','Template',selectedAgentPane==='template'?'active':'','data-pane="template"')}</div></section>`;
}
function toggleAgentConfig(id){
  if(view!=='agent:'+id)return;
  const stream=$('#stream'),details=$('#agent-config-details'),profile=$('#profile-slot .agent-profile'),toggle=$('#profile-slot [data-act="agent-config"]');
  if(!stream||!details||!profile||!toggle)return;
  const top=stream.scrollTop,bottom=stream.scrollHeight-stream.clientHeight-top<50;
  const collapsed=agentConfigCollapsed.get(agentConfigKey(id))!==true;
  agentConfigCollapsed.set(agentConfigKey(id),collapsed);
  if(collapsed&&details.contains(document.activeElement))toggle.focus();
  details.hidden=collapsed;profile.dataset.collapsed=String(collapsed);
  toggle.innerHTML=icon(collapsed?'chevronDown':'chevronUp');
  toggle.setAttribute('aria-expanded',String(!collapsed));
  toggle.setAttribute('aria-label',(collapsed?'Expand':'Collapse')+' agent details');
  toggle.setAttribute('title',(collapsed?'Expand':'Collapse')+' agent details');
  stream.scrollTop=bottom?stream.scrollHeight:top;
  rememberScroll();
}

const PANEL_SIDES=['left','right'];
const PANEL_INFO={left:{name:'chats panel',variable:'--sidebar-w',preset:238,min:170,max:430},right:{name:'agents panel',variable:'--details-w',preset:260,min:210,max:470}};
const GUTTER=5, MAIN_MIN=400;
const clampPanel = (side,px) => Math.round(Math.min(PANEL_INFO[side].max,Math.max(PANEL_INFO[side].min,px)));
const panelLabel = side => (panels[side].open?'Hide the ':'Show the ')+PANEL_INFO[side].name;
function readPanels(){
  let saved={};
  try{saved=JSON.parse(localStorage.getItem('panels')||'null')||{};}catch{saved={};}
  return Object.fromEntries(PANEL_SIDES.map(side=>[side,{open:saved[side]?.open!==false,width:clampPanel(side,Number(saved[side]?.width)||PANEL_INFO[side].preset)}]));
}
let panels=readPanels(), dragSide=null;
function savePanels(){try{localStorage.setItem('panels',JSON.stringify(panels));}catch{}}
// However far a handle is dragged, neither panel may squeeze the conversation below MAIN_MIN.
function fitPanel(side,px,available){
  const other=panels[side==='left'?'right':'left'];
  return Math.min(clampPanel(side,px),clampPanel(side,available-(other.open?other.width:0)-2*GUTTER-MAIN_MIN));
}
function applyPanels(){
  const workspace=$('.workspace');
  if(!workspace)return;
  for(const side of PANEL_SIDES){
    const panel=panels[side];
    workspace.style.setProperty(PANEL_INFO[side].variable,(panel.open?panel.width:0)+'px');
    workspace.dataset[side]=panel.open?'open':'closed';
    const toggle=$(`.panel-collapse[data-side="${side}"]`);
    if(toggle){toggle.innerHTML=icon(collapseArrow(side));toggle.setAttribute('aria-expanded',String(panel.open));toggle.setAttribute('title',panelLabel(side));toggle.setAttribute('aria-label',panelLabel(side));}
  }
}
function togglePanel(side){panels[side].open=!panels[side].open;savePanels();applyPanels();}
function resetPanel(side){panels[side]={open:true,width:PANEL_INFO[side].preset};savePanels();applyPanels();}
// Dragging only ever resizes. Collapsing is the explicit button, so no drag can hide a panel.
function resizePanel(side,px){
  const available=$('.workspace')?.getBoundingClientRect?.().width;
  panels[side]={open:true,width:available?fitPanel(side,px,available):clampPanel(side,px)};
  savePanels();applyPanels();
}
// The arrow always points the way the panel will move, so a collapsed panel offers a way back.
const collapseArrow = side => panels[side].open===(side==='left')?'chevronLeft':'chevronRight';
const panelToggle = side => button('panel',icon(collapseArrow(side)),'panel-collapse',`data-side="${side}" aria-expanded="${panels[side].open}" title="${panelLabel(side)}" aria-label="${panelLabel(side)}"`);
const gutter = side => `<div class="gutter" data-side="${side}" role="separator" aria-orientation="vertical" tabindex="0" aria-label="Resize the ${PANEL_INFO[side].name}" title="Drag to resize · double-click to reset">${panelToggle(side)}</div>`;
const nameOf = id => state?.agents[id]?.handle || state?.config.humans.find(h=>h.id===id)?.name || (id==='system'?'Vibeguild':'Participant');
const colorOf = id => state?.agents[id]?.color || '#9be4be';
const avatar = (id,cls='') => `<span class="avatar ${cls}" style="--agent-color:${esc(colorOf(id))}">${esc(nameOf(id).slice(0,2))}</span>`;
const timeLabel = n => new Date(n*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
const compact = n => Number(n||0).toLocaleString();
const isHuman = id => state?.config.humans.some(h=>h.id===id);
const ownId = () => state.config.humans[0].id;
const fresh = a => Date.now()/1000-a.last_seen<120;
const lostWhileWorking = a => a.status==='working'&&!fresh(a);
function presence(a){
  const status=String(a.status||'unknown'),label=status.charAt(0).toUpperCase()+status.slice(1),seen=timeLabel(a.last_seen);
  if(status==='disconnected')return a.signed_off_at?'Signed off · last seen '+seen:'Disconnected · last seen '+seen;
  if(lostWhileWorking(a))return 'Lost contact '+seen+' · was working';
  if(!fresh(a))return 'Last seen '+seen+' · was '+status;
  if(a.budget_paused)return label+' · token budget paused';
  if(a.paused)return status==='paused'&&a.pause_ack_agent_revision===(a.pause_revision||0)?'Paused · checkpointed':label+' · pause requested';
  if(state.control.paused)return status==='paused'&&a.pause_ack_revision===state.control.revision?'Paused · checkpointed':label+' · pause pending';
  if(status==='paused')return 'Paused · awaiting resume';
  return label;
}
const roomForView = () => view.startsWith('human:')?null:view.startsWith('room:')?view.slice(5):view.startsWith('agent:')?state.agents[view.slice(6)]?.direct_room:'agent_chat';
const unreadRoom = room => Number(state?.unread?.[room]?.count||0);
const unreadView = key => key.startsWith('room:')?unreadRoom(key.slice(5)):key.startsWith('agent:')?unreadRoom(state.agents[key.slice(6)]?.direct_room):0;
const unreadTotal = () => Object.values(state?.unread||{}).reduce((n,r)=>n+Number(r.count||0),0);
const respondersFor = room => Object.values(state?.agents||{}).filter(a=>a.responding_room===room&&Number(a.responding_expires_at||0)>Date.now()/1000&&fresh(a));
const typingHTML = room => respondersFor(room).map(a=>`<div class="typing-indicator" style="--response-life:${Math.max(.1,a.responding_expires_at-Date.now()/1000)}s">${avatar(a.id,'tiny')}<span><strong>@${esc(a.handle)}</strong> is preparing a response</span><span class="typing-dots"><i></i><i></i><i></i></span></div>`).join('');
const humanHandle = config => config.humans[0].handle||config.humans[0].name.toLowerCase().replace(/[^a-z0-9_-]+/g,'-').replace(/^-|-$/g,'')||'human';
const humanPingSince = (next,after) => Boolean(state&&next.config.notifications?.human_mention_sound&&next.activity.some(e=>e.seq>after&&e.kind==='message'&&e.actor!==next.config.humans[0].id&&e.data?.human_mentions?.includes(next.config.humans[0].id)));
function playMentionSound(){try{const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;const ctx=new Audio(),gain=ctx.createGain(),tone=ctx.createOscillator();tone.type='sine';tone.frequency.setValueAtTime(620,ctx.currentTime);tone.frequency.exponentialRampToValueAtTime(880,ctx.currentTime+.16);gain.gain.setValueAtTime(.0001,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.12,ctx.currentTime+.02);gain.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.34);tone.connect(gain);gain.connect(ctx.destination);tone.start();tone.stop(ctx.currentTime+.36);tone.onended=()=>ctx.close();}catch{}}

let renewingSession=null;
async function renewSession(){
  if(!renewingSession)renewingSession=(async()=>{const r=await fetch('/api/session',{credentials:'same-origin',headers:{'X-Vibeguild-UI':'1'}});if(!r.ok)throw new Error('Could not reconnect to Vibeguild. Refresh this page and try again.');})().finally(()=>renewingSession=null);
  return renewingSession;
}
async function api(route, data){
  const opts=data?{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{credentials:'same-origin'};
  for(let attempt=0;attempt<2;attempt++){
    const r=await fetch('/api/'+route,opts);const j=await r.json();
    if(r.ok)return j;
    if(attempt===0&&r.status===401&&j.code==='owner_session_required'){await renewSession();continue;}
    throw new Error(j.error||'Request failed');
  }
}
async function command(action,args={}){const result=await api('command',{project,action,args,request_id:crypto.randomUUID()});await refresh(true);return result;}
async function markCurrentRoomRead(){
  if((!view.startsWith('room:')&&!view.startsWith('agent:'))||document.visibilityState==='hidden')return;
  const room=roomForView();if(!room||unreadRoom(room)<1)return;
  const currentProject=project,currentView=view;
  const result=await api('command',{project,action:'human_read',args:{room},request_id:crypto.randomUUID()});
  if(project!==currentProject||view!==currentView)return;
  state.unread[room]={count:0,latest_seq:result.through};state.seq=Math.max(state.seq,result.seq||0);
  rememberScroll();render();await renderContent();
}
function toast(message,error=false){const el=$('#toast');el.textContent=message;el.className='show'+(error?' error':'');clearTimeout(el.timer);el.timer=setTimeout(()=>el.className='',6500);}
function modal(title,sub,content,submit,label='Save'){
  $('#modal-content').innerHTML=`<form id="modal-form"><div class="modal-head"><h2>${esc(title)}</h2>${button('close-modal',icon('close'),'ghost small','aria-label="Close dialog"')}</div><p class="modal-subtitle">${esc(sub)}</p>${content}<div class="form-error" id="modal-error"></div><div class="modal-actions">${button('close-modal','Cancel','ghost')}<button class="primary" type="submit">${esc(label)}</button></div></form>`;
  $('#modal').showModal();$('#modal-form').onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;try{await submit(new FormData(e.target));$('#modal').close();}catch(err){$('#modal-error').textContent=err.message;}finally{btn.disabled=false;}};
}
const field=(label,name,value='',type='text')=>`<label for="f-${name}">${esc(label)}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" required>`;
const folderField=(label,name,value='')=>`<label for="f-${name}">${esc(label)}</label><div class="folder-field"><input id="f-${name}" name="${name}" value="${esc(value)}" required>${button('pick-folder',icon('folder')+' Browse','',`data-target="f-${name}" data-title="${esc(label)}" data-allow-new="${name==='path'}" aria-label="Browse for ${esc(label)}"`)}</div>${name==='path'?'<p class="info-note">Choose an empty folder, or enter a new folder path. Vibeguild creates it when you submit this form.</p>':''}`;
function defaultCoordinationPath(workspace){const value=workspace.trim();if(!value)return '';return value.replace(/[\\/]+$/,'')+(value.includes('\\')||/^[a-z]:/i.test(value)?'\\':'/')+'.vibeguild';}
function bindProjectFolders(){
  const workspace=$('#f-workspace'),coordination=$('#f-path');let suggested='';
  workspace.addEventListener('input',()=>{const next=defaultCoordinationPath(workspace.value);if(!coordination.value||coordination.value===suggested)coordination.value=next;suggested=next;});
}
async function pickFolder(selector,title,trigger){
  const input=$(selector);if(!input)return;
  const original=trigger.innerHTML;trigger.disabled=true;trigger.textContent='Choosing…';
  try{const result=await api('pick-folder',{path:input.value,title,allow_new:trigger.dataset?.allowNew==='true'});if(result.path){input.value=result.path;input.dispatchEvent(new Event('input',{bubbles:true}));}}
  finally{trigger.disabled=false;trigger.innerHTML=original;}
}
const area=(label,name,value='')=>`<label for="f-${name}">${esc(label)}</label><textarea id="f-${name}" name="${name}">${esc(value)}</textarea>`;
function bodyHTML(body){return String(body||'').split('```').map((part,i)=>i%2?`<pre>${esc(part.replace(/^\w+\n/,''))}</pre>`:esc(part).replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/(^|\s)(@[a-z][\w-]*)/gi,'$1<span class="mention">$2</span>').replace(/\n/g,'<br>')).join('');}
function empty(title,desc,act,label){return `<div class="empty">${icon('chat')}<h3>${esc(title)}</h3><p>${esc(desc)}</p>${act?button(act,label,'primary'):''}</div>`;}

async function welcome(){
  project=null;state=null;pollId++;let rec=[];try{rec=(await api('recent')).paths;}catch(e){toast(e.message,true);}
  $('#app').innerHTML=`<div class="welcome"><header class="welcome-head"><div class="row"><span class="logo-mark"></span><span class="brand">vibeguild</span></div><span class="eyebrow">LOCAL FIRST / HUMAN LED</span></header><div class="welcome-content"><section><div class="eyebrow">THE SHARED ROOM</div><h1>Independent minds.<br><em>Shared momentum.</em></h1><p class="intro">A place for your agents to think together, share their work, and keep you in the conversation.</p><div class="entry-facts"><span>01 / Bring your agents</span><span>02 / Keep your context</span></div></section><section><div class="entry-card"><div class="eyebrow">START A CONVERSATION</div><div class="spacer"></div><h2>Open your project</h2><p class="muted">Choose a coordination folder containing <code>vibeguild.json</code>.</p><label for="project-path">Project folder</label><div class="row"><input id="project-path" placeholder="C:\\Projects\\my-vibeguild-room" autocomplete="off">${button('browse',icon('folder'),'','aria-label="Browse project folders"')}</div>${button('open-project','Open project '+icon('arrow'),'primary')}${button('create-project','Create a new project','secondary-action')}</div>${rec.length?`<div class="recent"><div class="eyebrow">RECENT PROJECTS</div>${rec.slice(0,4).map(p=>button('recent',`${icon('folder')} <span>${esc(p.split(/[\\/]/).pop())}</span><span class="recent-path">${esc(p)}</span>`,'recent-item',`data-path="${esc(p)}"`)).join('')}</div>`:''}</section></div><footer class="welcome-foot"><span>ONE HUMAN. MANY PERSPECTIVES.</span><span>VIBEGUILD / v0.1</span></footer></div>`;
}
async function openProject(path){const result=await api('open',{path});project=result.project;view='activity';drafts={};reply=null;try{tabs=JSON.parse(localStorage.getItem('tabs:'+project)||'[]');if(!Array.isArray(tabs))tabs=[];}catch{tabs=[];}await refresh(true);startPoll();}
function rememberScroll(){const stream=$('#stream');if(stream)scrollPositions[project+view+selectedAgentPane]={top:stream.scrollTop,bottom:stream.scrollHeight-stream.clientHeight-stream.scrollTop<50};}
async function refresh(force=false){if(!project)return;const pid=project,after=state?.seq||0;const next=await api('state?project='+encodeURIComponent(pid));if(pid!==project)return;const ping=humanPingSince(next,after);state=next;connected=true;if(view==='settings'&&!force)return;rememberScroll();render();await renderContent();if(ping)playMentionSound();await markCurrentRoomRead();}
function saveTabs(){localStorage.setItem('tabs:'+project,JSON.stringify(tabs));}
function roomView(id){const a=state.rooms[id]?.kind==='direct'?Object.values(state.agents).find(a=>a.direct_room===id):null;return a?'agent:'+a.id:'room:'+id;}
async function go(next){rememberScroll();if(next.startsWith('room:'))next=roomView(next.slice(5));if(next.startsWith('room:')||next.startsWith('agent:')||next.startsWith('human:')){if(!tabs.includes(next))tabs.push(next);saveTabs();}view=next;oldest=null;render();await renderContent();await markCurrentRoomRead();}
function tabName(key){return key.startsWith('human:')?nameOf(key.slice(6)):key.startsWith('room:')?'# '+(state.rooms[key.slice(5)]?.name||'chat'):'@'+(state.agents[key.slice(6)]?.handle||'agent');}
function nav(key,label,ico,count=''){return button('nav',`${icon(ico)}<span class="nav-text">${label}</span>${count?`<span class="count">${count}</span>`:''}`,'nav-item '+(view===key?'selected':''),`data-view="${key}" title="${label}"`);}
const PINNED_CHANNELS=['agent_chat','agent_scratch'];
function additionalChannelNav(){
  return Object.values(state.rooms)
    .filter(room=>!PINNED_CHANNELS.includes(room.id))
    .sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),undefined,{sensitivity:'base'}))
    .map(room=>{const target=roomView(room.id);return button(
      'nav',
      `${room.kind==='direct'?'':'<span class="mono">#</span>'}<span class="nav-text">${esc(room.name||room.id)}</span>${unreadRoom(room.id)?`<span class="notification-badge">${unreadRoom(room.id)}</span>`:''}`,
      'nav-item channel '+(view===target?'selected':''),
      `data-view="${esc(target)}" title="${esc(room.name||room.id)}"`,
    );}).join('');
}
function render(){
  if(!state)return;
  const normalized=[...new Set(tabs.map(t=>t.startsWith('room:')?roomView(t.slice(5)):t))];if(normalized.length!==tabs.length||normalized.some((t,i)=>t!==tabs[i])){tabs=normalized;saveTabs();}
  window.restoreAgentConfigFocus=document.activeElement?.dataset?.act==='agent-config'&&document.activeElement.dataset.id===view.slice(6)?view:null;
  const active=$('#message-input'),sel=active&&document.activeElement===active?{start:active.selectionStart,end:active.selectionEnd}:null;
  if(active&&renderedRoom)drafts[renderedRoom]=active.value;
  renderedRoom=null;
  const openVotes=Object.values(state.votes).filter(v=>v.status==='open');
  const totalTokens=Object.values(state.agents).reduce((n,a)=>n+a.token_estimate,0);
  const working=Object.values(state.agents).filter(a=>a.status==='working'&&fresh(a)).length;
  const lost=Object.values(state.agents).filter(lostWhileWorking);
  const runStatus=(state.control.paused?'PAUSED · CHECKPOINT CONTROL':working+' WORKING · RECENT CONTACT')+(lost.length?' · ⚠ '+lost.length+' LOST CONTACT':'');
  const unread=unreadTotal();
  $('#app').innerHTML=`<div class="workspace"><header class="topbar"><div class="row"><span class="logo-mark"></span><span class="brand">vibeguild</span></div><div class="project-switch"><span class="tag">PROJECT</span><strong class="truncate">${esc(state.config.project.name)}</strong>${button('home',icon('folder'),'ghost small','title="Switch project" aria-label="Switch project"')}</div><div class="top-actions"><div class="link-state ${connected?'':'off'}"><span class="dot ${connected?'':'off'}"></span><span class="connection-text">${connected?'COORDINATOR CONNECTED':'RECONNECTING…'}</span></div><div class="run-state ${lost.length?'warning':''}"><span class="dot ${state.control.paused?'off':''}"></span>${runStatus}</div>${button('toggle-all',icon(state.control.paused?'play':'pause')+' '+(state.control.paused?'Resume all':'Pause all'),'small')}${button('nav',avatar(ownId(),'tiny'),'ghost small profile-shortcut',`data-view="human:${ownId()}" title="Open your profile" aria-label="Open your profile"`)}${button('nav',icon('settings'),'ghost small','data-view="settings" title="Project settings" aria-label="Project settings"')}</div></header><aside class="sidebar"><div class="eyebrow" style="padding:0 13px 14px">WORKSPACE</div>${nav('activity','Activity Feed','activity',unread||'')}${nav('rooms','All Chats','chat',unread||Object.keys(state.rooms).length)}${nav('tasks','Tasks','tasks',Object.values(state.tasks).filter(t=>t.status!=='done').length)}${nav('votes','Votes','vote',openVotes.length)}${nav('agents','Agents','agents',Object.keys(state.agents).length)}<div class="section-label">OPEN TABS <span>${tabs.length}</span></div>${tabs.map(t=>`<div class="tab-nav ${view===t?'active':''}">${icon(t.startsWith('agent:')||t.startsWith('human:')?'agents':'chat')}<button data-act="nav" data-view="${t}">${esc(tabName(t))}${unreadView(t)?` <span class="notification-badge">${unreadView(t)}</span>`:''}</button>${button('close-tab','×','close',`data-tab="${t}" aria-label="Close ${esc(tabName(t))}"`)}</div>`).join('')}${!tabs.length?'<p class="info-note" style="padding:8px 14px">Open a chat to keep it here.</p>':''}<div class="section-label">CHANNELS ${button('new-room','+','ghost small','title="Create chat"')}</div>${['agent_chat','agent_scratch'].map(r=>button('nav',`<span class="mono">#</span><span class="nav-text">${r}</span>${unreadRoom(r)?`<span class="notification-badge">${unreadRoom(r)}</span>`:''}`,'nav-item channel',`data-view="room:${r}"`)).join('')}<div class="sidebar-bottom">${button('nav',`${avatar(ownId(),'tiny')}<span class="truncate">${esc(nameOf(ownId()))}</span><span class="tag human">HUMAN</span>`,'human-profile-link row',`data-view="human:${ownId()}" title="Open your profile" aria-label="Open your profile"`)}</div></aside>${gutter('left')}<main class="main"><div class="tabstrip">${button('nav','Activity'+(unread?' · '+unread:''),' '+(view==='activity'?'active':''),'data-view="activity"')}${tabs.map(t=>button('nav',esc(tabName(t))+(unreadView(t)?' · '+unreadView(t):''),view===t?'active':'',`data-view="${t}"`)).join('')}</div><div id="channel-head"></div><div id="profile-slot"></div><div class="stream" id="stream"></div><div id="composer-slot"></div></main>${gutter('right')}<aside class="details"><div class="goal-card"><div class="eyebrow">SHARED OBJECTIVE</div><p>${esc(state.config.project.goal)}</p></div><div class="row between"><div class="eyebrow" style="margin:0">IN THIS PROJECT</div>${button('new-agent','+','ghost small','aria-label="Add agent"')}</div>${lost.length?`<div class="agent-alert"><strong>⚠ Lost contact while working</strong><span>${lost.map(a=>'@'+esc(a.handle)).join(', ')}</span></div>`:''}<div class="roster">${Object.values(state.agents).map(a=>`<div class="roster-item ${lostWhileWorking(a)?'attention':''}" tabindex="0" role="button" data-act="nav" data-view="agent:${a.id}">${avatar(a.id)}<div class="grow"><div class="name">${esc(a.handle)} ${state.config.lead_agent_id===a.id?'<span class="tag lead">LEAD</span>':''}</div><div class="role">${esc(a.role)}</div></div>${unreadRoom(a.direct_room)?`<span class="notification-badge">${unreadRoom(a.direct_room)}</span>`:''}<span class="presence-label">${esc(presence(a))}</span></div>`).join('')||'<p class="info-note">No agents yet. Add a profile or join from a terminal.</p>'}</div>${button('connect-help','Connect an agent '+icon('arrow'),'ghost small')}<div class="details-rule"></div><div class="eyebrow">CONTEXT ECONOMY</div><div class="metric"><span>Text supplied · est. tokens</span><strong>${compact(totalTokens)}</strong></div><div class="metric"><span>Provider-reported input</span><strong>${Object.keys(state.usage).length?compact(Object.values(state.usage).reduce((n,u)=>n+u.input,0)):'—'}</strong></div><div class="metric"><span>Provider-reported output</span><strong>${Object.keys(state.usage).length?compact(Object.values(state.usage).reduce((n,u)=>n+u.output,0)):'—'}</strong></div><p class="info-note">Payload estimates are separate from provider usage. Unknown coverage is never counted as zero.</p><div class="details-rule"></div><div class="eyebrow">DECISION AUTHORITY</div><p style="font-size:12px;color:#a6b5b0">${state.config.lead_agent_id?'@'+esc(nameOf(state.config.lead_agent_id))+' leads this project.':'No lead appointed yet.'}<br>You always have final say.</p></aside></div>`;
  const sidebarBottom=$('.sidebar-bottom');
  if(sidebarBottom)sidebarBottom.insertAdjacentHTML('beforebegin',additionalChannelNav());
  applyPanels();
  if(sel)window.restoreComposer=sel;
}
function header(title,description,ico='chat',actions=''){ $('#channel-head').innerHTML=`<div class="channel-head"><span class="channel-icon">${icon(ico)}</span><div><h2>${esc(title)}</h2><p>${esc(description)}</p></div><div class="channel-actions">${actions}</div></div>`;}
function composer(room){
  renderedRoom=room;
  const replying=reply&&reply.room===room;
  const scratch=room==='agent_scratch';
  const purpose=scratch?'Technical detail, logs, excerpts, tests, and review evidence':'Concise coordination summary, decision, blocker, or request';
  $('#composer-slot').innerHTML=`<div class="composer-wrap">${replying?`<div class="reply-context" id="reply-context"><span>Replying to message <code>${esc(reply.id.slice(0,8))}</code></span>${button('cancel-reply','× Cancel reply','ghost small')}</div>`:''}<div id="mention-menu"></div><form id="message-form" class="composer"><textarea id="message-input" aria-label="Message ${esc(state.rooms[room]?.name)}" placeholder="${esc(purpose)}">${esc(drafts[room]||'')}</textarea><div class="composer-footer"><div class="composer-tools">${button('mention','@','ghost small','title="Mention an agent"')}${button('new-vote',icon('vote'),'ghost small','title="Create a vote" aria-label="Create a vote"')}<small>AS ${esc(nameOf(ownId()).toUpperCase())} · HUMAN</small></div><button type="submit" class="primary send-btn">Send ${icon('send')}</button></div></form><p class="composer-hint">${scratch?'DETAIL CHANNEL · cite this message UUID from a concise chat summary':'SUMMARY CHANNEL · put supporting technical detail in #agent_scratch'} · Enter to send · Shift + Enter for a new line${state.control.paused?' · Agents are paused; your messages remain available.':''}</p></div>`;
  if(reply&&reply.room===room)$('#message-input').placeholder='Replying to '+reply.id.slice(0,8)+' · write your message';
  $('#message-form').onsubmit=async e=>{e.preventDefault();const input=$('#message-input');if(!input.value.trim())return;const body=input.value;const reply_to=reply&&reply.room===room?reply.id:null;drafts[room]='';input.value='';reply=null;try{await command('send',{room,body,reply_to});}catch(err){drafts[room]=body;input.value=body;toast(err.message,true);}};
  $('#message-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#message-form').requestSubmit();}};
  $('#message-input').oninput=e=>{drafts[room]=e.target.value;if(/@[\w-]*$/.test(e.target.value.slice(0,e.target.selectionStart)))showMentions();else $('#mention-menu').innerHTML='';};
  if(window.restoreComposer){const s=window.restoreComposer;delete window.restoreComposer;$('#message-input').focus();$('#message-input').setSelectionRange(s.start,s.end);}
}
const humanDraftKey = id => `human:${project}:${id}`;
function humanNoteHTML(m){return `<article class="notes-block human-note"><div class="row between"><time class="eyebrow">${esc(new Date(m.at*1000).toLocaleString())}</time>${button('copy-id',icon('copy'),'ghost small',`data-id="${esc(m.id)}" title="Copy note ID" aria-label="Copy note ID"`)}</div><div class="message-body">${bodyHTML(m.body)}</div>${m.has_more_body?button('full-message','Read full note','ghost small',`data-id="${esc(m.id)}"`):''}</article>`;}
function mergeHumanNotes(key,messages,older=false){
  const cache=humanNotesCache[key]||(humanNotesCache[key]={rows:[],more:false,loaded:false});
  // A full page without overlap may hide a gap of unseen notes; restart paging.
  if(!older&&cache.loaded&&messages.length===50&&cache.rows.length&&messages[0].seq>cache.rows.at(-1).seq){cache.rows=[];cache.loaded=false;}
  if(older||!cache.loaded)cache.more=messages.length===50;
  cache.rows=[...new Map([...cache.rows,...messages].map(m=>[m.id,m])).values()].sort((a,b)=>a.seq-b.seq);
  cache.loaded=true;return cache;
}
function drawHumanNotes(id,key){
  const cache=humanNotesCache[key];
  $('#human-notes-list').innerHTML=(cache.more&&cache.rows.length?button('older-human-notes','Load earlier notes','ghost small',`data-human="${esc(id)}" data-before="${cache.rows[0].seq}"`):'')+(cache.rows.map(humanNoteHTML).join('')||empty('A place for your own notes','Save thoughts here without sending them to agents.'));
}
function humanNotesComposer(id){
  const key=humanDraftKey(id);renderedRoom=key;
  const busy=humanNoteRequests[key]?.busy;
  $('#composer-slot').innerHTML=`<div class="composer-wrap"><form id="human-note-form" class="composer"><textarea id="message-input" aria-label="Personal note" placeholder="Write a note to yourself">${esc(drafts[key]||'')}</textarea><div class="composer-footer"><small>PERSONAL NOTES</small><button id="save-human-note" class="primary send-btn" type="submit" ${busy?'disabled':''}>${busy?'Saving…':'Save note'}</button></div></form><p class="composer-hint">Saved to this project. Not sent to agents. You can ask an agent to read a note by its ID.</p></div>`;
  $('#message-input').oninput=e=>{drafts[key]=e.target.value;};
  $('#human-note-form').onsubmit=async e=>{
    e.preventDefault();const input=$('#message-input'),body=input.value;if(!body.trim()||humanNoteRequests[key]?.busy)return;
    const targetProject=project;
    const request=humanNoteRequests[key]?.body===body?humanNoteRequests[key]:{body,request_id:crypto.randomUUID()};
    humanNoteRequests[key]=request;request.busy=true;drafts[key]=body;$('#save-human-note').disabled=true;$('#save-human-note').textContent='Saving…';
    let saved=false;
    try{
      await api('command',{project:targetProject,action:'note',args:{body},request_id:request.request_id});saved=true;delete humanNoteRequests[key];
      if(drafts[key]===body){drafts[key]='';if(project===targetProject&&renderedRoom===key)$('#message-input').value='';}
      if(project===targetProject)await refresh();
    }catch(err){toast(saved?'Note saved; refresh failed: '+err.message:err.message,true);}
    finally{request.busy=false;if(project===targetProject&&renderedRoom===key){$('#save-human-note').disabled=false;$('#save-human-note').textContent='Save note';}}
  };
  // Enter inserts a newline in personal notes; saving is always explicit.
  if(window.restoreComposer){const s=window.restoreComposer;delete window.restoreComposer;$('#message-input').focus();$('#message-input').setSelectionRange(s.start,s.end);}
}
async function loadHumanNotes(id){
  const currentProject=project,key=humanDraftKey(id),request=++humanNotesRequest;
  humanNotesComposer(id);
  const result=await api('history?project='+encodeURIComponent(currentProject)+'&human_id='+encodeURIComponent(id));
  if(project!==currentProject||view!=='human:'+id||request!==humanNotesRequest)return;
  const first=!humanNotesCache[key]?.loaded;mergeHumanNotes(key,result.messages);drawHumanNotes(id,key);
  if(first)$('#stream').scrollTop=$('#stream').scrollHeight;
}
function cancelReply(){reply=null;$('#reply-context')?.remove();const input=$('#message-input'),room=roomForView();if(input)input.placeholder=room==='agent_scratch'?'Technical detail, logs, excerpts, tests, and review evidence':'Concise coordination summary, decision, blocker, or request';}
function showMentions(){const input=$('#message-input');if(!input)return;const term=(input.value.slice(0,input.selectionStart).match(/@([\w-]*)$/)||['',''])[1];$('#mention-menu').innerHTML=`<div class="mention-menu">${Object.values(state.agents).filter(a=>a.handle.startsWith(term)).map(a=>button('pick-mention',avatar(a.id,'tiny')+esc(a.handle),'',`data-name="${a.handle}"`)).join('')||'<p class="info-note" style="padding:12px">Add an agent first.</p>'}</div>`;}
function receiptHTML(m){if(!isHuman(m.actor)||!Array.isArray(m.receipts)||!m.receipts.length)return '';const seen=m.receipts.filter(r=>r.acknowledged);const summary=m.receipts.length===1?(seen.length?'✓ @'+nameOf(m.receipts[0].agent_id)+' acknowledged':'○ Awaiting @'+nameOf(m.receipts[0].agent_id)):`${seen.length===m.receipts.length?'✓':'○'} ${seen.length}/${m.receipts.length} agent sessions acknowledged`;return `<details class="read-receipts"><summary>${esc(summary)}</summary>${m.receipts.map(r=>`<div>${r.acknowledged?'✓ Acknowledged':'○ Awaiting'} · @${esc(nameOf(r.agent_id))}</div>`).join('')}<p>Acknowledgment confirms the session consumed its inbox batch; it does not prove comprehension or agreement.</p></details>`;}
function message(m,feed=false){const id=m.actor;const body=m.body??m.data?.body??'';const room=m.room??m.data?.room;const mid=m.id;const parent=m.reply_to??m.data?.reply_to;return `<article class="message" data-message="${mid}">${avatar(id)}<div class="message-content"><div class="message-meta"><span class="sender" style="color:${esc(colorOf(id))}">${esc(nameOf(id))}</span>${isHuman(id)?'<span class="tag human">HUMAN</span>':state.config.lead_agent_id===id?'<span class="tag lead">LEAD</span>':''}<time>${timeLabel(m.at)}</time>${feed?button('nav','# '+esc(state.rooms[room]?.name||room),'room-label',`data-view="room:${room}"`):''}</div>${parent?button('full-message','↳ Reply to '+esc(parent.slice(0,8)),'ghost small',`data-id="${esc(parent)}"`):''}<div class="message-body">${bodyHTML(body)}</div>${m.has_more_body||m.data?.truncated?button('full-message','Read full message','ghost small',`data-id="${mid}"`):''}${receiptHTML(m)}</div><div class="message-tools">${button('reply',icon('chat'),'small',`data-id="${mid}" data-room="${room}" title="Reply" aria-label="Reply"`)}${button('copy-id',icon('link'),'small',`data-id="${mid}" title="Copy message ID" aria-label="Copy message ID"`)}</div></article>`;}
function voteCard(v){const counts=v.options.map((_,i)=>Object.values(v.ballots).filter(b=>b.option===i).length);const chosen=v.ballots[ownId()]?.option;const left=Math.max(0,Math.ceil((v.closes_at-Date.now()/1000)/60));return `<article class="vote-card"><div class="row between"><span class="eyebrow">${icon('vote')} ADVISORY VOTE</span><span class="tag">${v.status==='open'?left+' MIN LEFT':v.close_reason==='everyone_voted'?'EVERYONE VOTED':'CLOSED'}</span></div><h3>${esc(v.question)}</h3>${v.options.map((o,i)=>`<button class="vote-option ${chosen===i?'chosen':''}" data-act="ballot" data-id="${v.id}" data-option="${i}" ${v.status!=='open'?'disabled':''}><span class="fill" style="width:${100*counts[i]/Math.max(1,v.electorate.length)}%"></span><span>${chosen===i?'✓ ':''}${esc(o)}</span><span class="votes-count">${counts[i]}</span></button>`).join('')}<div class="vote-foot">${button('ballot',chosen==='abstain'?'✓ Abstained':'Abstain','small',`data-id="${v.id}" data-option="abstain" ${v.status!=='open'?'disabled':''}`)}<small>${Object.keys(v.ballots).length}/${v.electorate.length} participated · ${Object.values(v.ballots).filter(b=>b.option==='abstain').length} abstained</small></div><p class="info-note" style="margin-top:12px">${v.status==='open'&&!v.ballots[ownId()]?'Your vote is pending. This stays open for you until the deadline.':v.status==='closed'?`${v.electorate.length-Object.keys(v.ballots).length} did not vote. Result informs judgment; it does not authorize action.`:'Your ballot is recorded. You can change it while the vote is open.'}</p><details style="margin-top:10px;font-size:11px;color:#81958f"><summary>Participants & ballots</summary>${v.electorate.map(id=>`<div class="row" style="margin-top:8px">${avatar(id,'tiny')}<span>${esc(nameOf(id))}</span><span class="grow"></span><span>${v.ballots[id]?v.ballots[id].option==='abstain'?'Abstain':esc(v.options[v.ballots[id].option]):v.status==='open'?'Pending':'Did not vote'}</span></div>`).join('')}</details></article>`;}
async function renderContent(){
  if(!state)return;const stream=$('#stream');if(!stream)return;const thisView=view,thisProject=project,request=++contentRequest;
  const current=()=>request===contentRequest&&view===thisView&&project===thisProject;
  $('#profile-slot').innerHTML='';
  const newChat=button('new-room',icon('plus')+' <span class="label">New chat</span>','small');
  if(view==='activity'){
    header('Activity Feed','Every conversation. One shared perspective.','activity',button('new-vote',icon('vote')+' <span class="label">Start vote</span>','small'));
    const recent=state.activity.filter(e=>e.kind!=='ballot');
    stream.innerHTML=`<div class="date-separator">PROJECT TIMELINE</div>${recent.map(e=>{if(e.kind==='message')return message(e,true);if(e.kind==='vote')return state.votes[e.data.vote_id]?voteCard(state.votes[e.data.vote_id]):'';if(e.kind==='decision')return `<div class="decision-card"><div class="eyebrow">${isHuman(e.actor)?'HUMAN':'LEAD'} DECISION · ${esc(nameOf(e.actor))}</div><div class="spacer"></div><div class="message-body">${bodyHTML(e.data.body)}</div></div>`;if(e.kind==='register'){const joined=state.agents[e.data.agent_id];const owner=nameOf(joined?.owner_id||e.actor);return `<div class="system-entry">${icon('agents')}<span>${esc(joined?.handle||e.data.name)} (${esc(owner)}) joined the project</span><time>${timeLabel(e.at)}</time></div>`;}const descriptions={project_created:'Project created',agent_update:'renamed an agent',human_update:'renamed the human',room:'created a conversation',control:e.data.paused?'paused collaboration':'resumed collaboration',lead:'updated the project lead',settings:'updated project context/settings',settings_updated:'updated settings',task:'created a task',task_update:'updated a task',votes_closed:'A vote reached its deadline',resume:'resumed their identity',join_room:'joined a conversation'};return `<div class="system-entry">${icon(e.kind==='task'?'tasks':'activity')}<span>${e.kind==='project_created'?'':esc(nameOf(e.actor))+' '}${esc(descriptions[e.kind]||e.kind.replaceAll('_',' '))}${e.kind==='human_update'?' · '+esc(e.data.old_name)+' → '+esc(e.data.name):e.kind==='agent_update'?' · @'+esc(e.data.old_handle)+' → @'+esc(e.data.handle):e.data.title?' · '+esc(e.data.title):e.data.name?' · '+esc(e.data.name):''}</span><time>${timeLabel(e.at)}</time></div>`;}).join('')}`;
    composer('agent_chat');stream.scrollTop=stream.scrollHeight;
  }else if(view==='rooms'){
    header('All Chats','Double-click a conversation to open it in a new tab.','chat',newChat);
    stream.innerHTML=`<div class="filterbar"><input id="room-filter" aria-label="Filter chats" placeholder="Find a conversation…"></div><div class="table-head"><span>CONVERSATION</span><span>MEMBERS</span><span>VIEW</span></div><div id="room-list">${Object.values(state.rooms).map(r=>`<div class="room-row" tabindex="0" role="button" data-room="${r.id}" data-name="${esc(r.name.toLowerCase())}"><div><strong><span style="color:#6e9281">#</span> ${esc(r.name)} ${unreadRoom(r.id)?`<span class="notification-badge">${unreadRoom(r.id)} new</span>`:''}</strong><p>${r.kind==='global'?'Short results, status, decisions, blockers & requests':r.kind==='scratch'?'Technical analysis, logs, excerpts, tests & review evidence':r.kind==='direct'?'Human ↔ agent conversation':'Agent collaboration'}</p></div><span class="room-count">${r.kind==='global'||r.kind==='scratch'?Object.keys(state.agents).length+1:r.members.length+1}</span><span class="open-label">${tabs.includes('room:'+r.id)?'OPEN TAB':'↗ OPEN'}</span></div>`).join('')}</div>`;
    $('#room-filter').oninput=e=>document.querySelectorAll('.room-row').forEach(r=>r.hidden=!r.dataset.name.includes(e.target.value.toLowerCase()));
  }else if(view.startsWith('room:')){
    const r=state.rooms[view.slice(5)];if(!r)return go('rooms');header(r.name,r.kind==='scratch'?'Technical record · cite scratch message UUIDs from concise coordination summaries':r.kind==='global'?'Coordination summaries · route supporting technical detail to agent_scratch':'A shared conversation · human contributions are always distinct','chat',button('new-vote',icon('vote'),'small','title="Start a vote" aria-label="Start a vote"'));
    const result=await api('history?project='+project+'&room='+encodeURIComponent(r.id));if(!current())return;
    stream.innerHTML=(result.messages.length===50?button('older','Load earlier messages','ghost small',`data-before="${result.messages[0].seq}" data-room="${r.id}"`):'')+(result.messages.length?result.messages.map(m=>message(m)).join(''):empty('The conversation starts here','Share a brief, ask a question, or mention an agent.'))+typingHTML(r.id);composer(r.id);stream.scrollTop=stream.scrollHeight;
  }else if(view==='votes'){
    header('Votes','Gather perspectives. The result is advisory.','vote',button('new-vote',icon('plus')+' New vote','small'));
    stream.innerHTML=Object.values(state.votes).reverse().map(voteCard).join('')||empty('Make room for every perspective','Start a timed vote. Agents can choose an option or abstain.','new-vote','Start a vote');
  }else if(view==='tasks'){
    header('Tasks','Clear ownership. Explicit evidence. Shared progress.','tasks',button('new-task',icon('plus')+' New task','small'));
    stream.innerHTML=Object.values(state.tasks).map(t=>`<article class="task-card"><div class="row between"><span class="tag">${esc(t.status)}</span><span class="muted" style="font-size:11px">${t.owner?'@'+esc(nameOf(t.owner)):'Unclaimed'}</span></div><h3>${esc(t.title)}</h3><p>${esc(t.description)}</p>${t.result?`<pre>${esc(t.result)}</pre>`:''}<div class="task-controls">${button('task-status','Update status','small',`data-id="${t.id}"`)}${button('copy-id','Copy ID','ghost small',`data-id="${t.id}"`)}</div></article>`).join('')||empty('A goal becomes work, one task at a time','Agents claim a task before editing and record evidence when it is done.','new-task','Create a task');
  }else if(view==='agents'){
    header('Agents','Independent sessions. Durable identities.','agents',button('new-agent',icon('plus')+' Add agent','small'));
    stream.innerHTML=Object.values(state.agents).map(a=>`<article class="task-card ${lostWhileWorking(a)?'attention':''}"><div class="row">${avatar(a.id,'large')}<div class="grow"><h3 style="margin:0;color:${esc(a.color)}">${esc(a.handle)} ${state.config.lead_agent_id===a.id?'<span class="tag lead">LEAD</span>':''}</h3><p>${esc(a.role)} · ${esc(a.provider)}</p></div>${button('nav','Open agent '+icon('arrow'),'small',`data-view="agent:${a.id}"`)}</div><div class="uuid">${a.id}</div><div class="task-controls"><span class="tag">${esc(presence(a))}</span></div></article>`).join('')||empty('Bring your first agent into the room','Start a terminal yourself, load the Vibeguild skill, and join this project.','connect-help','Connection instructions');
  }else if(view.startsWith('human:')){
    const h=state.config.humans.find(h=>h.id===view.slice(6));if(!h)return go('activity');
    $('#composer-slot').innerHTML='';
    header(h.name,'Your profile in this project.','agents');
    stream.innerHTML=`<div class="agent-sticky human-profile"><div class="agent-header">${avatar(h.id,'large')}<div class="human-heading"><h2>${esc(h.name)} <span class="tag human">HUMAN</span></h2><p class="muted">Mention handle: @${esc(humanHandle(state.config))}</p><div class="uuid">${esc(h.id)} ${button('copy-id',icon('copy'),'ghost small',`data-id="${esc(h.id)}" title="Copy UUID" aria-label="Copy UUID"`)}</div></div></div><div class="agent-controls">${button('rename-human','Rename','small',`data-id="${esc(h.id)}"`)}</div><h3 class="human-notes-title">Personal notes</h3></div><div id="human-notes-list"></div>`;
    await loadHumanNotes(h.id);
  }else if(view.startsWith('agent:')){
    const a=state.agents[view.slice(6)];if(!a)return go('agents');header('@'+a.handle,'Your direct line to this agent, with visible working notes.','agents');
    $('#profile-slot').innerHTML=agentProfile(a);
    stream.innerHTML='<div id="agent-content"></div>';
    if(window.restoreAgentConfigFocus===view){delete window.restoreAgentConfigFocus;$('#profile-slot [data-act="agent-config"]').focus();}
    if(selectedAgentPane==='chat'){const res=await api('history?project='+project+'&room='+a.direct_room);if(!current())return;$('#agent-content').innerHTML=(res.messages.map(m=>message(m)).join('')||empty('A direct conversation','Messages here reach this agent.'))+typingHTML(a.direct_room);composer(a.direct_room);}
    else if(selectedAgentPane==='notes'){const res=await api('history?project='+project+'&agent_id='+a.id);if(!current())return;$('#agent-content').innerHTML=res.messages.map(m=>`<div class="notes-block"><div class="eyebrow">WORKING NOTE · ${timeLabel(m.at)}</div><div class="message-body">${bodyHTML(m.body)}</div></div>`).join('')||empty('No working notes yet','The skill teaches agents to record useful decisions, blockers, and findings here.');}
    else if(selectedAgentPane==='template'){
      $('#composer-slot').innerHTML='';
      $('#agent-content').innerHTML='<p class="info-note" role="status">Loading template…</p>';
      try{
        const info=a.template_ref?await api('agent-template?project='+encodeURIComponent(project)+'&agent='+encodeURIComponent(a.id)):{state:'none'};
        if(!current())return;
        $('#agent-content').innerHTML=templateHTML(info);
      }catch(err){if(!current())return;$('#agent-content').innerHTML=templateHTML({state:'unavailable',template_ref:a.template_ref,error:err.message});}
    }
    else $('#agent-content').innerHTML=`<div class="notes-block"><div class="eyebrow">PROJECT MEMORY / START HERE</div>${a.master_memory ? `<p class="info-note">Master memory: ${esc(a.master_memory)}</p>${button('copy-id','Copy master memory path','ghost small',`data-id="${esc(a.master_memory)}"`)}${button('copy-id','Copy memory folder path','ghost small',`data-id="${esc(a.memory_folder)}"`)}` : ''}</div><div class="notes-block"><div class="eyebrow">SESSION HEARTBEAT</div><p class="info-note">${esc(presence(a))} · Recent contact means the watch loop reached Vibeguild; it is not proof that work continues.</p>${a.heartbeat_file?button('copy-id','Copy heartbeat file path','ghost small',`data-id="${esc(a.heartbeat_file)}"`):''}</div><div class="notes-block"><div class="eyebrow">EMERGENCY RECOVERY / CHECKPOINT</div>${a.recovery_file ? `<p class="info-note">Recovery file: ${esc(a.recovery_file)}</p>${button('copy-id','Copy recovery file path','ghost small',`data-id="${esc(a.recovery_file)}"`)}` : ''}<p class="checkpoint-caveat">Agent-authored recovery claim. Verify task revisions, changed files, and test evidence before relying on it.</p><div class="checkpoint-text">${esc(a.checkpoint||'No checkpoint recorded yet.')}</div></div><div class="metric"><span>Vibeguild payload estimate</span><strong>${compact(a.token_estimate)} tokens</strong></div><div class="notes-block"><div class="eyebrow">GENERAL PROJECT CONTEXT</div><div class="checkpoint-text">${esc(state.config.general_context||'Add shared context in project settings.')}</div></div>`;
  }else if(view==='settings'){
    header('Project settings','Shared context, guardrails, and the place your code lives.','settings');
    const p=state.config.project,policy=state.config.policy,notifications=state.config.notifications||{};
    stream.innerHTML=`<form class="settings-form" id="settings-form">${field('Project name','name',p.name)}${area('Overarching goal','goal',p.goal)}${area('General context · every agent reads this on join/resume','general_context',state.config.general_context)}${folderField('External code workspace','workspace',p.workspace)}<p class="info-note" style="margin-top:8px">Coordination lives separately at ${esc(state.path)}</p><h3>Notifications</h3><label class="check-row"><input type="checkbox" name="mention_sound" ${notifications.human_mention_sound?'checked':''}> Play a sound when an agent explicitly mentions @${esc(humanHandle(state.config))}</label><p class="info-note">The browser tab must be open. Audio may require one prior interaction with this page.</p><h3>Operating guardrails</h3><div class="form-columns">${field('Incoming inactivity · minutes','inactivity',policy.agent_inactivity_minutes,'number')}${field('Working status interval · minutes','status_interval',policy.working_status_interval_minutes,'number')}</div><label for="f-mode">Code coordination</label><select id="f-mode" name="mode"><option value="worktrees" ${policy.coordination_mode==='worktrees'?'selected':''}>Separate Git worktrees (default)</option><option value="shared" ${policy.coordination_mode==='shared'?'selected':''}>Shared directory · sequential work</option></select><label for="f-budget">Optional per-agent token pause budget · Vibeguild payload estimate</label><input id="f-budget" name="budget" type="number" min="1" value="${policy.token_budget??''}" placeholder="Disabled — leave blank"><p class="info-note">This measures text supplied by Vibeguild, not total model usage or provider spend. Pauses are cooperative at the next checkpoint.</p><button class="primary" type="submit">Save project settings</button><div class="spacer"></div><div class="notes-block"><div class="eyebrow">PILOT REFERENCE</div><div class="checkpoint-text">${esc(p.reference||'No reference document linked.')}</div></div></form>`;
    $('#settings-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);try{await command('settings',{name:f.get('name'),goal:f.get('goal'),general_context:f.get('general_context'),workspace:f.get('workspace'),notifications:{human_mention_sound:f.get('mention_sound')==='on'},policy:{agent_inactivity_minutes:Number(f.get('inactivity')),working_status_interval_minutes:Number(f.get('status_interval')),coordination_mode:f.get('mode'),token_budget:f.get('budget')?Number(f.get('budget')):null}});toast('Project settings saved. Agents receive changed context on their next read.');}catch(err){toast(err.message,true);}};
  }
  const saved=scrollPositions[project+view+selectedAgentPane];if(saved)stream.scrollTop=saved.bottom?stream.scrollHeight:saved.top;
  if(view!=='settings'&&!view.startsWith('human:'))$('#channel-head .channel-actions')?.insertAdjacentHTML('afterbegin',button('search','Search','ghost small'));
}
function startPoll(){const id=++pollId;(async()=>{while(project&&id===pollId){try{const p=project;const changes=await api('changes?project='+p+'&after='+state.seq);if(id!==pollId)return;if(changes.seq!==state.seq)await refresh();if(!connected){connected=true;render();}}catch(e){if(connected){connected=false;render();}toast('Connection interrupted. Retrying the local coordinator…',true);await new Promise(r=>setTimeout(r,4000));}}})();}

async function browse(path){const data=await api('browse',{path});modal('Choose a project folder',data.path,`<div class="row">${button('browse-up','↑ Parent folder','small',`data-path="${esc(data.parent)}"`)}<input id="browse-path" value="${esc(data.path)}" aria-label="Folder path">${button('browse-go','Go','small')}</div><div class="folder-list">${data.folders.map(f=>button('browse-folder',icon('folder')+`<span class="grow">${esc(f.name)}</span>`+(f.project?'<span class="tag">VIBEGUILD</span>':''),'folder-row',`data-path="${esc(f.path)}"`)).join('')}</div><p class="info-note">${data.project?'This folder contains vibeguild.json.':'Navigate to a folder containing vibeguild.json.'}</p>`,async()=>openProject(data.path),'Open this project');}
function templateHTML(info){
  if(info.state==='none')return empty('No template assigned','This agent uses the base Vibeguild skill and its free-text role.');
  const labels={saved:'Verified saved copy',assigned:'Assigned; saved copy not available',unavailable:'Bound instructions unavailable'};
  const visible=['saved','assigned'].includes(info.state)&&typeof info.body==='string';
  return `<section class="template-detail"><div class="eyebrow">AGENT TEMPLATE</div><h3>${esc(info.title||info.template_ref?.id||'Template')}</h3><p class="tag">${labels[info.state]||labels.unavailable}</p><p class="info-note">${info.state==='assigned'?'These packaged instructions match the assigned version. A saved copy is not available.':info.state==='saved'?'This saved copy matches the assigned version.':'The assigned instructions could not be verified. Ask the agent to check its saved copy.'} This does not confirm that a model has loaded or followed the instructions.</p><details class="template-version"><summary>Assigned version</summary><code>${esc(info.template_ref?.sha256)}</code>${info.error?`<p>${esc(info.error)}</p>`:''}</details>${visible?`<pre class="template-body">${esc(info.body)}</pre>`:''}</section>`;
}
async function addAgentProfile(){
  const targetProject=project;
  const {templates}=await api('templates');
  if(project!==targetProject)return;
  const selector=`<label for="f-template">Template · optional</label><select id="f-template" name="template"><option value="" selected>None · base skill only</option>${templates.map(t=>`<option value="${esc(t.id)}">${esc(t.title)} — ${esc(t.summary)}</option>`).join('')}</select><p class="info-note">A template adds working instructions to the base skill. Choose once when creating the profile; the role label stays independent.</p>`;
  const providerField=`<label for="f-provider">Provider</label><select id="f-provider" name="provider" required><option value="" selected disabled>Choose a provider</option><option value="codex">Codex</option><option value="claude-code">Claude Code</option><option value="other">Other · custom name</option></select><div id="provider-custom-fields" hidden><label for="f-provider-custom">Provider name</label><input id="f-provider-custom" name="provider_custom" maxlength="80" placeholder="e.g. Gemini CLI" disabled></div><p class="info-note">A label for the agent host you plan to use. It does not configure an API, run a script, or launch a terminal.</p>`;
  modal('Add an agent','Create a saved identity here, then connect it from an agent session you start separately.',field('Short name','handle')+field('Role','role','contributor')+providerField+selector,async f=>{
    if(project!==targetProject)throw Error('Project changed. Reopen Add agent in the intended project.');
    const args={...Object.fromEntries(f),dormant:true};if(!args.template)delete args.template;
    if(!['codex','claude-code','other'].includes(args.provider))throw Error('Choose a provider.');
    if(args.provider==='other'){
      args.provider=String(args.provider_custom||'').trim();
      if(!args.provider||args.provider.length>80)throw Error('Enter a provider name of 1 to 80 characters.');
    }
    delete args.provider_custom;
    await command('register',args);toast('Agent added. Start its terminal separately, then use Connect terminal to resume this identity.');
  },'Add agent');
  const provider=$('#f-provider'),custom=$('#f-provider-custom');
  provider.onchange=()=>{const other=provider.value==='other';$('#provider-custom-fields').hidden=!other;custom.disabled=!other;custom.required=other;};
  provider.onchange();
}
function connectHelp(a){const cmd=a?`python -m vibeguild resume --project "${state.path}" --agent ${a.id}`:`python -m vibeguild join --project "${state.path}" --handle builder --role implementer --provider claude`;modal(a?'Connect @'+a.handle:'Connect your agent','Start a terminal separately, then have its agent connect to this identity.',`<p class="info-note">Vibeguild does not open a terminal or launch a model. Start Claude Code, Codex, or another agent host yourself, then have it load the Vibeguild skill and run the command below. For an existing identity, resume its UUID rather than joining again.</p><div class="spacer"></div><pre class="join-code">${esc(cmd)}</pre><p class="info-note">Run these commands from the Vibeguild source folder, using the Python installation that runs the coordinator. Use the same coordinator home as the running server. For a custom home, insert <code>--home &lt;coordinator-home&gt;</code> before <code>${a?'resume':'join'}</code>.</p>${a?.template_ref?`<p class="info-note">Assigned template: <strong>${esc(a.template_ref.id)}</strong>. After resuming, read the bootstrap and controls, then follow the skill’s template-loading instructions to verify the saved copy or save the matching bound version. Wait while paused.</p>`:''}<p class="muted">Load the skill directly from the source checkout, or install it into your agent host’s skills folder. Then tell that agent to load this project and connect.</p><pre class="join-code">python -m vibeguild install-skill --dest &lt;your-skills-folder&gt;</pre><p class="info-note">Use .agents/skills for Codex or .claude/skills for Claude Code. The coordinator stays running while your terminal watches for messages. A closed terminal cannot be woken by the skill alone.</p>`,async()=>{},'Done');}
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-act]');if(!el)return;const act=el.dataset.act;
 try{
  if(act==='close-modal')return $('#modal').close();
  if(act==='home')return welcome();
  if(act==='panel')return togglePanel(el.dataset.side);
  if(act==='open-project')return await openProject($('#project-path').value);
  if(act==='recent')return await openProject(el.dataset.path);
  if(act==='nav')return await go(el.dataset.view);
  if(act==='close-tab'){tabs=tabs.filter(t=>t!==el.dataset.tab);saveTabs();if(view===el.dataset.tab)view='activity';render();return await renderContent();}
  if(act==='browse')return await pickFolder('#project-path','Open a Vibeguild project folder',el);
  if(act==='pick-folder')return await pickFolder('#'+el.dataset.target,el.dataset.title,el);
  if(act==='browse-folder'||act==='browse-up'){ $('#modal').close();return await browse(el.dataset.path);}
  if(act==='browse-go'){const p=$('#browse-path').value;$('#modal').close();return await browse(p);}
  if(act==='toggle-all')return await command('control',{paused:!state.control.paused});
  if(act==='toggle-agent')return await command('control',{agent_id:el.dataset.id,paused:!state.agents[el.dataset.id].paused});
  if(act==='rename-human'){const h=state.config.humans.find(h=>h.id===el.dataset.id);if(!h)return;return modal('Rename yourself',`Your mention handle stays @${humanHandle(state.config)}. Your identity, messages and ownership stay attached to you.`,field('Display name','name',h.name),async f=>{const result=await command('human_update',{human_id:h.id,name:f.get('name')});toast(result.unchanged?'You already have that name.':'Your display name is now '+result.name+'.');},'Rename');}
  if(act==='rename-agent'){const a=state.agents[el.dataset.id];return modal('Rename @'+a.handle,'The immutable UUID, session, messages, tasks, and chat memberships stay attached to this agent. Historical message text is not rewritten.',field('New short name','handle',a.handle)+`<p class="info-note">New mentions use the new @name. The journal records this rename from @${esc(a.handle)} without changing earlier events.</p>`,async f=>{const old=a.handle;const result=await command('agent_update',{agent_id:a.id,handle:f.get('handle')});toast(result.unchanged?'The agent already has that name.':'@'+old+' is now @'+result.handle+'. UUID unchanged.');},'Rename agent');}
  if(act==='appoint-lead'){await command('lead',{agent_id:el.dataset.id});return toast('@'+nameOf(el.dataset.id)+' is now the project lead.');}
  if(act==='copy-id'){await navigator.clipboard.writeText(el.dataset.id);return toast('Copied to clipboard');}
  if(act==='reply'){reply={id:el.dataset.id,room:el.dataset.room};await go('room:'+reply.room);$('#message-input').focus();return;}
  if(act==='cancel-reply'){cancelReply();return;}
  if(act==='full-message'){const result=await api('message?project='+project+'&id='+encodeURIComponent(el.dataset.id));return modal('Message detail',el.dataset.id,`<pre id="full-body">${esc(result.body)}</pre>${result.total>result.next?button('more-body','Load next section','small',`data-id="${el.dataset.id}" data-start="${result.next}"`):''}`,async()=>{},'Done');}
  if(act==='more-body'){const result=await api('message?project='+project+'&id='+encodeURIComponent(el.dataset.id)+'&start='+el.dataset.start);$('#full-body').textContent+=result.body;el.dataset.start=result.next;if(result.next>=result.total)el.remove();return;}
  if(act==='search')return modal('Search conversations','Search message text across the project.',field('Search text','query'),async f=>{const res=await api('history?project='+project+'&q='+encodeURIComponent(f.get('query')));$('#stream').innerHTML=res.messages.map(m=>message(m,true)).join('')||empty('No matches','Try another search term.');},'Search');
  if(act==='older-human-notes'){
    const id=el.dataset.human,currentProject=project,key=humanDraftKey(id);el.disabled=true;
    try{const result=await api('history?project='+encodeURIComponent(currentProject)+'&human_id='+encodeURIComponent(id)+'&before='+el.dataset.before);
      if(project!==currentProject||view!=='human:'+id)return;
      const stream=$('#stream'),height=stream.scrollHeight;mergeHumanNotes(key,result.messages,true);drawHumanNotes(id,key);stream.scrollTop+=stream.scrollHeight-height;
    }finally{el.disabled=false;}return;
  }
  if(act==='older'){const res=await api('history?project='+project+'&room='+encodeURIComponent(el.dataset.room)+'&before='+el.dataset.before);const stream=$('#stream'),height=stream.scrollHeight;el.insertAdjacentHTML('afterend',res.messages.map(m=>message(m)).join(''));if(res.messages.length===50)el.dataset.before=res.messages[0].seq;else el.remove();stream.scrollTop+=stream.scrollHeight-height;return;}
  if(act==='agent-config')return toggleAgentConfig(el.dataset.id);
  if(act==='agent-pane'){rememberScroll();selectedAgentPane=el.dataset.pane;render();return await renderContent();}
  if(act==='connect-help')return connectHelp();
  if(act==='agent-connect')return connectHelp(state.agents[el.dataset.id]);
  if(act==='mention'){const input=$('#message-input');input.focus();input.value+='@';return showMentions();}
  if(act==='pick-mention'){const input=$('#message-input'),pos=input.selectionStart;input.value=input.value.slice(0,pos).replace(/@[\w-]*$/,'@'+el.dataset.name+' ')+input.value.slice(pos);drafts[roomForView()]=input.value;$('#mention-menu').innerHTML='';input.focus();return;}
  if(act==='ballot')return await command('ballot',{vote_id:el.dataset.id,option:el.dataset.option==='abstain'?'abstain':Number(el.dataset.option)});
  if(act==='create-project'){modal('Create a project','Choose your code workspace. Vibeguild creates a .vibeguild subfolder for its chats and project context.',field('Project name','name')+folderField('Workspace folder (your code)','workspace')+folderField('Coordination folder (created automatically)','path')+field('Your name','human','Jonathan')+area('Project goal','goal')+area('General context for joining agents','general_context'),async f=>{const result=await api('create',Object.fromEntries(f));project=result.project;view='activity';tabs=[];await refresh();startPoll();},'Create project');bindProjectFolders();return;}
  if(act==='new-agent')return await addAgentProfile();
  if(act==='new-room')return modal('New conversation','Visible to you and the agents you include.',field('Chat name','name')+'<label>Participants</label>'+Object.values(state.agents).map(a=>`<label class="check-row"><input type="checkbox" name="members" value="${a.id}" checked>${avatar(a.id,'tiny')}${esc(a.handle)}</label>`).join(''),async f=>{const r=await command('room',{name:f.get('name'),members:f.getAll('members')});await go('room:'+r.room_id);},'Create chat');
  if(act==='new-task')return modal('Create a task','Give one coherent piece of work a clear endpoint.',field('Task title','title')+area('Scope and acceptance criteria','description'),async f=>{await command('task',Object.fromEntries(f));},'Create task');
  if(act==='task-status'){const t=state.tasks[el.dataset.id];return modal('Update task',t.title,'<label>Status</label><select name="status">'+['open','working','blocked','review','done'].map(s=>`<option ${s===t.status?'selected':''}>${s}</option>`).join('')+'</select>'+area('Evidence / blocker / result','result',t.result),async f=>{await command('task_update',{...Object.fromEntries(f),task_id:t.id,revision:t.revision});});}
  if(act==='new-vote')return modal('Ask the room','Everyone, including you, has until the deadline to vote or abstain.',field('Question','question')+area('Options · one per line','options','Option A\nOption B')+field('Open for · minutes','minutes','10','number'),async f=>{await command('vote',{question:f.get('question'),options:f.get('options').split('\n').map(s=>s.trim()).filter(Boolean),minutes:Number(f.get('minutes')),room:roomForView()});},'Open advisory vote');
 }catch(err){toast(err.message,true);}
});
document.addEventListener('dblclick',e=>{const handle=e.target.closest('.gutter');if(handle){if(!e.target.closest('[data-act]'))resetPanel(handle.dataset.side);return;}const row=e.target.closest('[data-room]');if(row)go('room:'+row.dataset.room);});
// The drag lives on the document so a re-render replacing the handle mid-drag cannot strand it.
const dragPanel=e=>{if(!dragSide)return;e.preventDefault();const rect=$('.workspace').getBoundingClientRect();resizePanel(dragSide,dragSide==='left'?e.clientX-rect.left:rect.right-e.clientX);};
const endPanelDrag=()=>{if(!dragSide)return;dragSide=null;const workspace=$('.workspace');if(workspace)delete workspace.dataset.resizing;document.removeEventListener('pointermove',dragPanel);document.removeEventListener('pointerup',endPanelDrag);document.removeEventListener('pointercancel',endPanelDrag);};
document.addEventListener('pointerdown',e=>{if(e.target.closest('[data-act]'))return;const handle=e.target.closest('.gutter');if(!handle)return;e.preventDefault();dragSide=handle.dataset.side;const workspace=$('.workspace');if(workspace)workspace.dataset.resizing=dragSide;document.addEventListener('pointermove',dragPanel);document.addEventListener('pointerup',endPanelDrag);document.addEventListener('pointercancel',endPanelDrag);});
document.addEventListener('keydown',e=>{
 const handle=e.target.closest('.gutter');
 if(handle&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();const side=handle.dataset.side;return resizePanel(side,(panels[side].open?panels[side].width:0)+(e.key==='ArrowRight'?16:-16)*(side==='left'?1:-1));}
 if(e.key==='Enter'){const row=e.target.closest('[data-room]');if(row){e.preventDefault();go('room:'+row.dataset.room);}else if(e.target.id==='project-path')openProject(e.target.value).catch(err=>toast(err.message,true));}});
welcome();
