/* Actual chart/app code, isolated from a browser, exchange, engine and orders. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),controls=[];
function check(id,fn){fn();controls.push(id);}
let fixtures;
if(process.argv[2])fixtures=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
else{
  const python=process.env.NAUTILUS_TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python';
  const made=spawnSync(python,['-c','import json; from tests.tool_rack.test_looking_glass_patterns import construct_fixtures; print(json.dumps(construct_fixtures()))'],{cwd:root,encoding:'utf8'});
  assert.equal(made.status,0,made.stderr);fixtures=JSON.parse(made.stdout);
}
const chartSource=fs.readFileSync(path.join(root,'strategy_core/nautilus/chart.js'),'utf8');
function environment(){
  const paint=[],style={};
  const context=new Proxy(style,{get:(target,key)=>key in target?target[key]:(...args)=>{paint.push({method:key,args,color:target.strokeStyle,width:target.lineWidth});},set:(target,key,value)=>(target[key]=value,true)});
  const sandbox={window:{},console,Date,Math,Number,Intl,localStorage:{getItem:()=>null,setItem(){}},
    ResizeObserver:class{observe(){}},requestAnimationFrame:()=>1};
  vm.runInNewContext(chartSource,sandbox);
  const canvas={getContext:()=>context,parentElement:{getBoundingClientRect:()=>({width:1400,height:800})},
    addEventListener(){},style:{},focus(){},setPointerCapture(){},releasePointerCapture(){}};
  const chart=new sandbox.window.NautilusChart(canvas,{classList:{add(){},remove(){}},style:{}},()=>{});
  return {chart,sandbox,paint,canvas};
}
function withFixture(name='rail'){const value=structuredClone(fixtures[name]),env=environment();env.chart.setData(value);return {...env,value};}
for(const [name,kind]of [['rail','UP_RAIL'],['mountain','ALTERNATING_MOUNTAIN'],['sprout','FRESH_LEG'],['release','RELEASE'],['forming','RELEASE_FORMING']]){
  check('pattern_'+name,()=>{const {chart}=withFixture(name);assert.equal(chart.scenarioView().active.kind,kind);});
}
check('featured_weight_and_alternatives',()=>{
  const {chart,paint,value}=withFixture(),original=JSON.stringify(value);chart.draw();
  assert.ok(paint.some(row=>row.method==='stroke'&&row.color==='#bcffb0ff'&&row.width===3));
  assert.ok(paint.some(row=>row.method==='stroke'&&row.color.endsWith('45')&&row.width<3));
  assert.ok(paint.some(row=>row.method==='fillText'&&String(row.args[0]).includes('ACTIVE · UP RAIL')));
  assert.equal(JSON.stringify(value),original,'Drawing cannot alter data or forecasts');
});
check('finite_shape_horizon',()=>{const {chart,paint}=withFixture('finite');const view=chart.scenarioView();assert.ok(view.active.horizon_ts<view.glass.close_ts);chart.draw();assert.ok(paint.some(row=>row.method==='fillText'&&row.args[0].startsWith('SHAPE ENDS ')));});
for(const [name,alter] of [
  ['stale_source',v=>{v.server_now+=4;}],['wrong_ticker',v=>{v.looking_glass.ticker='PREVIOUS';}],
  ['wrong_expiry',v=>{v.looking_glass.close_ts+=900;}],['stopped',v=>{v.run.stopped=true;}],
  ['authoritative',v=>{v.looking_glass.execution_authority=true;}],['physical_stale',v=>{v.market.fresh=false;}]
])check('withheld_'+name,()=>{const {chart,value}=withFixture();alter(value);const view=chart.scenarioView();assert.equal(view.paths.length,0);assert.equal(view.active,null);assert.equal(view.issued,null);});
check('disconnected_and_review',()=>{const {chart}=withFixture();chart.sourceConnected=()=>false;assert.equal(chart.scenarioView().paths.length,0);chart.sourceConnected=()=>true;chart.reviewMode=true;assert.equal(chart.scenarioView().paths.length,0);});
for(const [name,alter]of [
  ['wrong_active_source',g=>{g.active_pattern.source_ts-=1;}],
  ['unknown_active_id',g=>{g.active_pattern.path_id='INVENTED';}],
  ['active_authority',g=>{g.active_pattern.execution_authority=true;}]
])check('unfeatured_'+name,()=>{const {chart,value}=withFixture();alter(value.looking_glass);assert.equal(chart.scenarioView().active,null);});
for(const [name,alter]of [
  ['future_reference',p=>{p.reference_end_ts=3901;}],['stretch',p=>{p.time_stretched=true;}],
  ['repeat',p=>{p.repeated=true;}],['wrong_horizon',p=>{p.horizon_ts+=1;}],
  ['cross_expiry',p=>{p.points.at(-1).time=4501;p.horizon_ts=4501;}]
])check('finite_reject_'+name,()=>{const {chart,value}=withFixture('finite');const g=value.looking_glass,p=g.paths.find(p=>p.id===g.active_pattern.path_id);alter(p);assert.equal(chart.scenarioView().active,null);});
function issuedFixture(){
  const env=withFixture(),g=env.value.looking_glass,a=g.active_pattern,p=structuredClone(g.paths.find(p=>p.id===a.path_id));
  p.points[0].time-=60;p.points[0].btc-=12;p.points[0].e9-=8;
  g.research={as_issued:[{id:'SYNTHETIC_FIRST_ISSUED',run_id:env.value.run.run_id,ticker:g.ticker,close_ts:g.close_ts,
    pattern_key:a.key,continuity_generation:a.continuity_generation,source_ts:g.source_ts-60,issued_at_ts:g.source_ts-60,
    conditional:true,execution_authority:false,frozen:true,anchor:structuredClone(p.points[0]),path:p}]};
  return env;
}
check('as_issued_paints_original_anchor',()=>{const {chart,paint,value}=issuedFixture(),before=JSON.stringify(value);assert.ok(chart.scenarioView().issued);chart.draw();assert.ok(paint.some(row=>row.method==='stroke'&&row.color==='#d1e2ef82'));assert.ok(paint.some(row=>row.method==='fillText'&&row.args[0].includes('· FIXED')));assert.equal(JSON.stringify(value),before);});
for(const [name,alter]of [
  ['future',s=>{s.source_ts=4000;}],['wrong_run',s=>{s.run_id='OTHER';}],['wrong_contract',s=>{s.ticker='OLD';}],
  ['wrong_generation',s=>{s.continuity_generation=9;}],['reanchored',s=>{s.path.points[0].btc+=1;}],
  ['future_issued',s=>{s.issued_at_ts=4000;}],['not_frozen',s=>{s.frozen=false;}]
])check('as_issued_reject_'+name,()=>{const {chart,value}=issuedFixture();alter(value.looking_glass.research.as_issued[0]);assert.equal(chart.scenarioView().issued,null);});

// Minimal DOM adapter runs the shipped app.js functions. It is a functional
// readout check, not a browser-layout or screenshot claim.
class Node{
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.style={};this.attributes={};this.value='';this._text='';this._classes=new Set();this.classList={add:(...v)=>v.forEach(x=>this._classes.add(x)),remove:(...v)=>v.forEach(x=>this._classes.delete(x)),contains:v=>this._classes.has(v),toggle:(v,on)=>{if(on===undefined)on=!this._classes.has(v);on?this._classes.add(v):this._classes.delete(v);return on;}};}
  set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent||'').join(' ');}
  set className(v){this._classes=new Set(String(v).split(/\s+/));}get className(){return [...this._classes].join(' ');}
  append(...v){this.children.push(...v);}replaceChildren(...v){this._text='';this.children=[...v];}setAttribute(k,v){this.attributes[k]=String(v);}getAttribute(k){return this.attributes[k];}
  addEventListener(){}closest(){return this.parentElement||this;}querySelector(selector){return this.children.find(n=>selector.startsWith('.')&&n.classList.contains(selector.slice(1)))||null;}querySelectorAll(){return [];}focus(){}get options(){return this.children;}
}
async function appControls(){
  const nodes=new Map(),html=fs.readFileSync(path.join(root,'strategy_core/nautilus/index.html'),'utf8');
  for(const match of html.matchAll(/id="([^"]+)"/g)){const n=new Node();n.id=match[1];nodes.set(n.id,n);}
  for(const cls of ['glass-continuation','glass-rotation','glass-reversal']){const n=new Node();n.classList.add(cls);nodes.get('lookingGlassLegend').append(n);}
  nodes.get('lookingGlassLegend').append(nodes.get('lookingGlassActive'),nodes.get('lookingGlassIssued'));
  nodes.get('spanSelect').append(...['15','45','90','180'].map(value=>Object.assign(new Node('option'),{value})));
  nodes.get('feedFilter').value='all';
  const env=environment(),nodeCanvas=nodes.get('marketChart');Object.assign(nodeCanvas,env.canvas);
  const selectors=new Map(),document={getElementById:id=>nodes.get(id)||null,createElement:tag=>new Node(tag),createDocumentFragment:()=>new Node(),
    querySelector:selector=>{if(!selectors.has(selector))selectors.set(selector,new Node());return selectors.get(selector);},querySelectorAll:()=>[],dispatchEvent(){},addEventListener(){}};
  let elapsed=1000,tick;
  const payload=structuredClone(fixtures.dashboard),sandbox=env.sandbox;
  Object.assign(sandbox,{document,NautilusChart:sandbox.window.NautilusChart,performance:{now:()=>elapsed},AbortController,
    Event:class{},CustomEvent:class{},setInterval:fn=>{tick=fn;return 1;},setTimeout:()=>1,clearTimeout(){},fetch:async()=>({ok:true,json:async()=>payload})});
  vm.runInNewContext(fs.readFileSync(path.join(root,'strategy_core/nautilus/reliability-ui.js'),'utf8'),sandbox);
  sandbox.NautilusReliability=sandbox.window.NautilusReliability;
  vm.runInNewContext(fs.readFileSync(path.join(root,'strategy_core/nautilus/app.js'),'utf8'),sandbox);
  await new Promise(setImmediate);
  check('app_publishes_complete_readout',()=>{assert.equal(sandbox.window.__nautilus.state,payload,nodes.get('errorBanner').textContent);assert.ok(nodes.get('errorBanner').classList.contains('hidden'));});
  check('app_active_label_and_legend',()=>{assert.match(nodes.get('lookingGlassStatus').textContent,/Up rail continuation · conditional/);assert.equal(nodes.get('lookingGlassBar').dataset.featured,'true');assert.equal(nodes.get('lookingGlassActive').classList.contains('hidden'),false);});
  check('app_briefing_bounded_and_read_only',()=>{assert.match(nodes.get('details').textContent,/ACTIVE PATTERN/);assert.match(nodes.get('details').textContent,/Dimmer paths are alternative outcomes/);assert.match(nodes.get('details').textContent,/Restarting the engine clears/);});
  check('app_stale_clears_active_caption',()=>{elapsed+=4000;tick();assert.equal(nodes.get('lookingGlassBar').dataset.featured,'false');assert.equal(nodes.get('lookingGlassActive').classList.contains('hidden'),true);assert.match(nodes.get('lookingGlassStatus').textContent,/stale/i);});
}
appControls().then(()=>console.log(JSON.stringify({passed:true,check_count:controls.length,controls,renderer:'ACTUAL_CHART_AND_APP_CODE_WITH_TEST_ADAPTERS',browser_layout_verified:false}))).catch(error=>{console.error(error);process.exitCode=1;});
