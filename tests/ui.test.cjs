// Pure UI rendering tests; no claim of real-browser visual coverage.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=new Map();
// Stubs only what app.js actually touches; a real browser layout is still not covered here.
function node(selector){if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',value:'',scrollTop:0,scrollHeight:1000,clientHeight:400,removed:false,dataset:{},attributes:{},style:{values:{},setProperty(name,value){this.values[name]=value;},getPropertyValue(name){return this.values[name];}},setAttribute(name,value){this.attributes[name]=value;},getAttribute(name){return this.attributes[name];},getBoundingClientRect(){return {left:0,right:1400,top:0,bottom:900,width:1400,height:900};},insertAdjacentHTML(_,html){this.innerHTML+=html;},remove(){this.removed=true;}});return nodes.get(selector);}
const listeners={},stored={};
const fire=(type,event)=>(listeners[type]||[]).forEach(fn=>fn(event));
const gutterEvent=(side,extra={})=>{const handle={dataset:{side},closest:s=>s==='.gutter'?handle:null};return {target:handle,preventDefault(){},...extra};};
// A press on the collapse button reports both the button and the handle it sits inside.
const buttonEvent=(side,extra={})=>{const handle={dataset:{side}},toggle={dataset:{side,act:'panel'},closest:s=>s==='.gutter'?handle:s==='[data-act]'?toggle:null};return {target:toggle,preventDefault(){},...extra};};
const context=vm.createContext({console,Date,JSON,Number,String,Map,FormData:class{},document:{querySelector:node,addEventListener(type,fn){(listeners[type]=listeners[type]||[]).push(fn);},removeEventListener(type,fn){listeners[type]=(listeners[type]||[]).filter(f=>f!==fn);},activeElement:null},window:{},localStorage:{setItem(key,value){stored[key]=String(value);},getItem(key){return key in stored?stored[key]:null;}},setTimeout,clearTimeout,fetch(){throw Error('Unexpected network in pure rendering tests');}});
let source=fs.readFileSync(require('node:path').join(__dirname,'../vibeguild/web/app.js'),'utf8').replace(/welcome\(\);\s*$/,'');
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);
run(`state={config:{project:{name:'Test',goal:'Build <parser>'},humans:[{id:'human',name:'Jonathan'}],general_context:'Shared context',policy:{},lead_agent_id:'a'},agents:{a:{id:'a',handle:'atlas',owner_id:'human',color:'#61d8bb',role:'lead',provider:'test',token_estimate:0,last_seen:Date.now()/1000,status:'ready',direct_room:'dm'}},control:{paused:false},rooms:{agent_chat:{id:'agent_chat',name:'agent_chat',kind:'global',members:[]}},tasks:{},votes:{},usage:{},activity:[]};project='test';`);
test('untrusted message text cannot introduce executable markup',()=>{
  const html=run('bodyHTML('+JSON.stringify('<img src=x onerror=alert(1)>\n`<script>`\n\n@atlas')+')');
  assert(!html.includes('<img'));
  assert(!html.includes('<script>'));
  assert(html.includes('&lt;img'));
  assert(html.includes('class="mention"'));
  assert(run(`bodyHTML('@Jonathan please review')`).includes('class="mention"'));
});
test('human identity is distinct and replies refer to durable IDs',()=>{
  const html=run(`message({id:'m',actor:'human',body:'Hello',room:'agent_chat',at:1,reply_to:'parent-uuid'})`);
  assert(html.includes('HUMAN'));
  assert(html.includes('data-id="parent-uuid"'));
  assert(html.includes('data-act="reply"'));
});
test('message labels resolve through the current UUID roster after a rename',()=>{
  const html=run(`message({id:'m',actor:'a',sender_name:'old-name',body:'Hello',room:'agent_chat',at:1})`);
  assert(html.includes('atlas'));
  assert(!html.includes('old-name'));
});
test('human messages show agent-session acknowledgment without claiming comprehension',()=>{
  let html=run(`message({id:'m',actor:'human',body:'Please review',room:'agent_chat',at:1,receipts:[{agent_id:'a',acknowledged:false}]})`);
  assert(html.includes('Awaiting @atlas'));
  html=run(`message({id:'m',actor:'human',body:'Please review',room:'agent_chat',at:1,receipts:[{agent_id:'a',acknowledged:true}]})`);
  assert(html.includes('@atlas acknowledged'));
  assert(html.includes('does not prove comprehension'));
});
test('feed previews expose full-message retrieval',()=>{
  assert(run(`message({id:'m',actor:'a',at:1,data:{room:'agent_chat',body:'preview',truncated:true}},true)`).includes('Read full message'));
});
test('render keeps drafts attached to original room when switching',()=>{
  node('#message-input').value='Unsent original draft';
  run(`renderedRoom='agent_chat';view='room:other';render()`);
  assert.equal(run(`drafts.agent_chat`),'Unsent original draft');
  assert.equal(run(`drafts.other`),undefined);
});
test('workspace has activity, conversations, tabs, pause and reported-usage distinctions',()=>{
  const html=node('#app').innerHTML;
  for(const label of ['Activity Feed','All Chats','OPEN TABS','Pause all','Unknown coverage'])assert(html.includes(label),label);
  assert(html.includes('Build &lt;parser&gt;'));
});
test('channels lists every room with the two coordination rooms pinned first',()=>{
  run(`state.rooms={
    agent_chat:{id:'agent_chat',name:'agent_chat',kind:'global',members:[]},
    zeta:{id:'zeta',name:'Zeta planning',kind:'group',members:[]},
    agent_scratch:{id:'agent_scratch',name:'agent_scratch',kind:'scratch',members:[]},
    alpha:{id:'alpha',name:'Alpha review',kind:'group',members:[]}
  };view='activity'`);
  node('.sidebar-bottom').innerHTML='';
  run(`render()`);
  const pinned=node('#app').innerHTML,additional=node('.sidebar-bottom').innerHTML;
  assert(pinned.indexOf('data-view="room:agent_chat"')<pinned.indexOf('data-view="room:agent_scratch"'));
  assert(additional.includes('data-view="room:alpha"'));
  assert(additional.includes('data-view="room:zeta"'));
  assert(additional.indexOf('Alpha review')<additional.indexOf('Zeta planning'));
  assert(!additional.includes('room:agent_chat'));
  assert(!additional.includes('room:agent_scratch'));
});
test('unread chat counts appear in the activity navigation and open tabs',()=>{
  run(`state.unread={agent_chat:{count:3,latest_seq:8}};tabs=['room:agent_chat'];render()`);
  const html=node('#app').innerHTML;
  assert(html.includes('notification-badge'));
  assert(html.includes('Activity · 3'));
});
test('reply mode has a cancel control that preserves the draft',()=>{
  run(`view='room:agent_chat';drafts.agent_chat='unfinished response';reply={id:'message-123456',room:'agent_chat'};composer('agent_chat')`);
  assert(node('#composer-slot').innerHTML.includes('Cancel reply'));
  node('#message-input').value='unfinished response';
  run(`cancelReply()`);
  assert.equal(run('reply'),null);
  assert.equal(node('#message-input').value,'unfinished response');
});
test('explicit preparing-response state renders only while fresh',()=>{
  run(`state.agents.a.responding_room='agent_chat';state.agents.a.responding_expires_at=Date.now()/1000+60;state.agents.a.last_seen=Date.now()/1000`);
  assert(run(`typingHTML('agent_chat')`).includes('@atlas'));
  run(`state.agents.a.responding_expires_at=Date.now()/1000-1`);
  assert.equal(run(`typingHTML('agent_chat')`),'');
});
test('mention sound detection requires the enabled setting and explicit human UUID mention',()=>{
  run(`state.config.notifications={human_mention_sound:true}`);
  context.nextState=run(`({...state,seq:12,activity:[{seq:12,kind:'message',actor:'a',data:{human_mentions:['human']}}]})`);
  assert.equal(run(`humanPingSince(nextState,11)`),true);
  run(`nextState.config.notifications.human_mention_sound=false`);
  assert.equal(run(`humanPingSince(nextState,11)`),false);
});
test('agent registration leads with agent and names the owning human',async()=>{
  await run(`state.activity=[{kind:'register',actor:'human',at:1,data:{agent_id:'a',name:'old-handle'}}];view='activity';renderContent()`);
  assert(node('#stream').innerHTML.includes('atlas (Jonathan) joined the project'));
  assert(!node('#stream').innerHTML.includes('Jonathan joined the project'));
});
test('vote does not present human silence as abstention',()=>{
  const html=run(`voteCard({id:'v',question:'Which?',options:['A','B'],electorate:['a','human'],ballots:{a:{option:0}},closes_at:Date.now()/1000+60,status:'open'})`);
  assert(html.includes('Your vote is pending'));
  assert(html.includes('0 abstained'));
  assert(html.includes('1/2 participated'));
});
test('cancelling folder selection preserves typed path and other form fields',async()=>{
  const input=node('#f-workspace');input.value='original workspace';
  node('#f-name').value='Unsubmitted project name';
  context.pickerTrigger={innerHTML:'Browse',disabled:false};
  context.fetch=async()=>({ok:true,json:async()=>({path:null,cancelled:true})});
  await run(`pickFolder('#f-workspace','Workspace',pickerTrigger)`);
  assert.equal(input.value,'original workspace');
  assert.equal(node('#f-name').value,'Unsubmitted project name');
  assert.equal(context.pickerTrigger.disabled,false);
  assert.equal(context.pickerTrigger.innerHTML,'Browse');
});
test('folder choice populates only the requested field',async()=>{
  const input=node('#f-workspace');input.dispatchEvent=()=>{};
  context.Event=class {};
  context.fetch=async()=>({ok:true,json:async()=>({path:'C:\\Projects\\Clé',cancelled:false})});
  await run(`pickFolder('#f-workspace','Workspace',pickerTrigger)`);
  assert.equal(input.value,'C:\\Projects\\Clé');
  assert.equal(node('#f-name').value,'Unsubmitted project name');
});
test('expired owner session refreshes once and retries the identical project form',async()=>{
  const requests=[];
  context.fetch=async(url,options)=>{
    requests.push({url,options});
    if(requests.length===1)return {ok:false,status:401,json:async()=>({code:'owner_session_required'})};
    if(url==='/api/session')return {ok:true};
    return {ok:true,json:async()=>({project:'new-project'})};
  };
  const result=await run(`api('create',{name:'Draft project',workspace:'C:/Projects/Clé'})`);
  assert.equal(result.project,'new-project');
  assert.deepEqual(requests.map(r=>r.url),['/api/create','/api/session','/api/create']);
  assert.equal(requests[0].options.body,requests[2].options.body);
  assert.equal(node('#f-name').value,'Unsubmitted project name');
});
test('ordinary permission failures are not retried as expired sessions',async()=>{
  let requests=0;
  context.fetch=async()=>{requests++;return {ok:false,status:403,json:async()=>({error:'Access denied'})};};
  await assert.rejects(run(`api('create',{name:'Draft project'})`),/Access denied/);
  assert.equal(requests,1);
});
test('default coordination path appends a subfolder without JSON-escaping the field',()=>{
  context.testWorkspace='C:\\Users\\black\\Jonathan\\DEV\\non-git\\SPARK_PLAN\\';
  assert.equal(run('defaultCoordinationPath(testWorkspace)'),context.testWorkspace+'.vibeguild');
  context.testWorkspace='\\\\server\\share\\code\\';
  assert.equal(run('defaultCoordinationPath(testWorkspace)'),context.testWorkspace+'.vibeguild');
  assert.equal(run(`defaultCoordinationPath('/projects/code/')`),'/projects/code/.vibeguild');
});
test('agent checkpoint pane exposes its emergency file',async()=>{
  await run(`view='agent:a';selectedAgentPane='checkpoint';state.agents.a.recovery_file='C:/project/.vibeguild/vibeguild_files/agents/a/RECOVERY.md';state.agents.a.master_memory='C:/project/.vibeguild/vibeguild_files/agents/a/MEMORY.md';state.agents.a.memory_folder='C:/project/.vibeguild/vibeguild_files/agents/a/memory';state.agents.a.heartbeat_file='C:/project/.vibeguild/vibeguild_files/agents/a/HEARTBEAT.json';renderContent()`);
  assert(node('#stream').innerHTML.includes('data-act="rename-agent"'));
  assert(node('#agent-content').innerHTML.includes('Copy master memory path'));
  assert(node('#agent-content').innerHTML.includes('Copy memory folder path'));
  assert(node('#agent-content').innerHTML.includes('Copy heartbeat file path'));
  assert(node('#agent-content').innerHTML.includes('Copy recovery file path'));
  assert(node('#agent-content').innerHTML.includes('C:/project/.vibeguild/vibeguild_files/agents/a/RECOVERY.md'));
  assert(node('#agent-content').innerHTML.includes('Agent-authored recovery claim'));
});
test('project pause is distinguished from an individual agent pause',()=>{
  assert.equal(run(`state.control={paused:true,revision:4};state.agents.a.status='working';state.agents.a.last_seen=Date.now()/1000;state.agents.a.paused=false;state.agents.a.budget_paused=false;presence(state.agents.a)`),'Working · pause pending');
  assert.equal(run(`state.control.paused=false;state.agents.a.paused=true;presence(state.agents.a)`),'Working · pause requested');
  assert(run(`state.agents.a.paused=false;state.agents.a.status='disconnected';presence(state.agents.a)`).startsWith('Disconnected · last seen'));
});
test('global rooms present agent chat as summaries and scratch as technical detail',()=>{
  run(`state.rooms.agent_scratch={id:'agent_scratch',name:'agent_scratch',kind:'scratch',members:[]};view='room:agent_chat';composer('agent_chat')`);
  assert(node('#composer-slot').innerHTML.includes('SUMMARY CHANNEL'));
  assert(node('#composer-slot').innerHTML.includes('Concise coordination summary'));
  run(`composer('agent_scratch')`);
  assert(node('#composer-slot').innerHTML.includes('DETAIL CHANNEL'));
  assert(node('#composer-slot').innerHTML.includes('Technical detail'));
});
test('stale working agents are warned while explicit disconnect is a clean signoff',()=>{
  run(`state.control={paused:false,revision:4};state.agents.a.status='working';state.agents.a.last_seen=Date.now()/1000-180;delete state.agents.a.signed_off_at;render()`);
  assert(node('#app').innerHTML.includes('1 LOST CONTACT'));
  assert(node('#app').innerHTML.includes('Lost contact while working'));
  assert.equal(run(`presence(state.agents.a)`).startsWith('Lost contact'),true);
  run(`state.agents.a.status='disconnected';state.agents.a.signed_off_at=Date.now()/1000`);
  assert.equal(run(`presence(state.agents.a)`).startsWith('Signed off'),true);
});
const css=fs.readFileSync(require('node:path').join(__dirname,'../vibeguild/web/style.css'),'utf8');
test('every workspace shell child holds an explicit grid column',()=>{
  // A collapsed panel is display:none, which leaves the grid entirely. Without explicit
  // placement the remaining children shift one column left and the conversation lands in
  // a 5px resize track -- the regression that hid the centre chat window.
  for(const [selector,column] of [['.sidebar','1'],['.gutter[data-side="left"]','2'],['.main','3'],['.gutter[data-side="right"]','4'],['.details','5']])
    assert(css.includes(selector+'{grid-column:'+column+'}'),selector+' must be placed in column '+column);
  for(const rule of css.match(/grid-template-columns:[^;}]*/g).filter(r=>r.includes('--sidebar-w')||r.includes('64px')))
    assert.equal(rule.split(/\s+/).length,5,'the shell grid always has five columns: '+rule);
});
test('the side panels and the conversation share one scrollbar treatment',()=>{
  assert(css.includes('--scroll-thumb:'),'the thumb colour is declared once as a token');
  for(const selector of ['.stream','.sidebar','.details']){
    // A selector carries several rules (placement, responsive); the scrolling one must use the token.
    const rules=[...css.matchAll(new RegExp('\\'+selector+'\\{[^}]*\\}','g'))].map(m=>m[0]);
    assert(rules.some(rule=>rule.includes('scrollbar-color:var(--scroll-thumb) transparent')),selector+' must use the shared scrollbar token');
  }
  assert(!/scrollbar-color:#/.test(css),'no scrollbar colour is hardcoded past the token');
});
test('both side panels offer a collapse button and a resize handle',()=>{
  run(`render()`);
  const html=node('#app').innerHTML;
  for(const side of ['left','right']){
    assert(html.includes(`<div class="gutter" data-side="${side}" role="separator" aria-orientation="vertical" tabindex="0"`),side+' handle');
    assert(html.includes(`class="panel-collapse" data-act="panel" data-side="${side}"`),side+' collapse button');
  }
  assert(html.includes('<div class="gutter" data-side="left"')&&html.indexOf('<main class="main">')>html.indexOf('data-side="left"'));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'238px');
  assert.equal(node('.workspace').style.getPropertyValue('--details-w'),'260px');
});
test('the collapse button lives inside its handle and never starts a drag',()=>{
  const html=node('#app').innerHTML;
  const handle=html.slice(html.indexOf('<div class="gutter" data-side="left"'));
  assert(handle.indexOf('panel-collapse')<handle.indexOf('</div>'),'button is nested in the handle');
  run(`resetPanel('left')`);
  fire('pointerdown',buttonEvent('left'));
  assert.equal(run(`dragSide`),null,'pressing the button must not begin a resize');
  assert.equal(node('.workspace').dataset.resizing,undefined);
});
test('clicking a collapse button collapses and reopens at the same width',()=>{
  run(`resizePanel('right',300);togglePanel('right')`);
  assert.equal(node('.workspace').style.getPropertyValue('--details-w'),'0px');
  assert.equal(node('.workspace').dataset.right,'closed');
  assert.equal(node('.panel-collapse[data-side="right"]').getAttribute('aria-expanded'),'false');
  assert.equal(JSON.parse(stored.panels).right.open,false);
  run(`togglePanel('right')`);
  assert.equal(node('.workspace').style.getPropertyValue('--details-w'),'300px');
  assert.equal(node('.workspace').dataset.right,'open');
  run(`resetPanel('right')`);
});
test('the arrow points the way the panel will move so a collapsed panel offers a way back',()=>{
  run(`resetPanel('left');resetPanel('right')`);
  assert.equal(run(`collapseArrow('left')`),'chevronLeft');
  assert.equal(run(`collapseArrow('right')`),'chevronRight');
  run(`togglePanel('left');togglePanel('right')`);
  assert.equal(run(`collapseArrow('left')`),'chevronRight');
  assert.equal(run(`collapseArrow('right')`),'chevronLeft');
  assert(node('.panel-collapse[data-side="left"]').innerHTML.includes(run(`paths.chevronRight`)));
  run(`resetPanel('left');resetPanel('right')`);
});
test('dragging a handle only ever resizes, never collapses',()=>{
  fire('pointerdown',gutterEvent('left'));
  assert.equal(node('.workspace').dataset.resizing,'left');
  fire('pointermove',gutterEvent('left',{clientX:300}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'300px');
  fire('pointermove',gutterEvent('left',{clientX:1100}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'430px');
  fire('pointermove',gutterEvent('left',{clientX:-200}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'170px','a drag past the minimum clamps, it does not hide the panel');
  assert.equal(node('.workspace').dataset.left,'open');
  fire('pointerup',gutterEvent('left'));
  assert.equal(node('.workspace').dataset.resizing,undefined);
  fire('pointermove',gutterEvent('left',{clientX:900}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'170px','a released handle stops tracking the pointer');
  run(`resetPanel('left')`);
});
test('a panel can never squeeze the conversation column below its minimum',()=>{
  run(`resetPanel('left');resetPanel('right')`);
  // 1400px viewport - 260px right panel - 10px handles - 400px conversation minimum.
  assert.equal(run(`fitPanel('left',430,1400)`),430);
  assert.equal(run(`fitPanel('left',430,1000)`),330);
  assert.equal(run(`fitPanel('left',430,600)`),170);
});
test('a focused handle resizes with the arrow keys',()=>{
  run(`resetPanel('left')`);
  fire('keydown',gutterEvent('left',{key:'ArrowRight'}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'254px');
  fire('keydown',gutterEvent('left',{key:'ArrowLeft'}));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'238px');
  fire('keydown',gutterEvent('right',{key:'ArrowLeft'}));
  assert.equal(node('.workspace').style.getPropertyValue('--details-w'),'276px');
  run(`resetPanel('left');resetPanel('right')`);
});
test('double-clicking a handle restores the preset width, but the button only toggles',()=>{
  run(`view='activity';resizePanel('left',400)`);
  fire('dblclick',gutterEvent('left'));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'238px');
  assert.equal(run(`view`),'activity');
  run(`resizePanel('left',400)`);
  fire('dblclick',buttonEvent('left'));
  assert.equal(node('.workspace').style.getPropertyValue('--sidebar-w'),'400px','the button must not reset the width');
  run(`resetPanel('left')`);
});
test('saved panel geometry is restored and clamped on load',()=>{
  stored.panels=JSON.stringify({left:{open:false,width:9999},right:{open:true,width:12}});
  assert.equal(run(`JSON.stringify(readPanels())`),'{"left":{"open":false,"width":430},"right":{"open":true,"width":210}}');
  delete stored.panels;
  assert.equal(run(`JSON.stringify(readPanels())`),'{"left":{"open":true,"width":238},"right":{"open":true,"width":260}}');
});
