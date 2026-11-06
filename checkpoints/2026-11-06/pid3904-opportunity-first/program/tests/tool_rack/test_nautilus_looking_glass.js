/* Isolated chart acceptance: conditional paths never become observed history. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const storage=new Map(),paint=[];
const context=new Proxy({}, {get:(target,key)=>key in target?target[key]:(...args)=>paint.push([key,...args]),set:(target,key,value)=>(target[key]=value,true)});
const sandbox={window:{},console,Date,Math,Number,Intl,
  localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
  ResizeObserver:class{observe(){}},requestAnimationFrame:()=>1};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../strategy_core/nautilus/chart.js'),'utf8'),sandbox);
const Chart=sandbox.window.NautilusChart;
function fixture(){
  const source=1700000000,close=source+600;
  return {server_now:source,run:{fresh:true,stopped:false},
    market:{ticker:'KX_CURRENT',time:source,close_ts:close,btc:80000,e9:79995,e30:79980,target:80010,fresh:true},
    candles:Array.from({length:46},(_,index)=>({time:Math.floor(source/60)*60-(45-index)*60,
      open:79990,high:80003,low:79980,close:80000,complete:index<45,quality:'observed'})),
    emas:[],targets:[],quotes:[],trades:[],
    looking_glass:{status:'READY',source_ts:source,valid_until:source+3,ticker:'KX_CURRENT',close_ts:close,
      execution_authority:false,probabilities_calibrated:false,
      paths:['CONTINUATION','ROTATION_STALL','REVERSAL'].map((family,index)=>({id:family,family,conditional:true,
        points:[{time:source,btc:80000,e9:79995},{time:source+300,btc:80000+(1-index)*30,e9:79995+(1-index)*20},
          {time:close,btc:80000+(1-index)*60,e9:79995+(1-index)*40}]}))}};
}
function chart(data=fixture()){
  const canvas={getContext:()=>context,parentElement:{getBoundingClientRect:()=>({width:900,height:700})},
    addEventListener(){},style:{},focus(){},setPointerCapture(){},releasePointerCapture(){}};
  const tooltip={classList:{add(){},remove(){}},style:{},textContent:''};
  const c=new Chart(canvas,tooltip,()=>{});c.setLookingGlass(true);c.setData(data);return c;
}

const data=fixture(),original=JSON.stringify(data),c=chart(data);
assert.equal(c.scenarioView().paths.length,3);
assert.equal(c.end-c.viewSpan(),c.historyEnd()-c.span,'Adding future space preserves the selected amount of past history');
assert.ok(c.end>=data.market.close_ts,'Current expiry remains visible');
c.draw();
assert.ok(paint.some(call=>call[0]==='fillText'&&call[1]==='NOW'));
assert.ok(paint.some(call=>call[0]==='fillText'&&call[1]==='CONDITIONAL PATHS'));
assert.equal(JSON.stringify(data),original,'Rendering cannot mutate published observations or scenarios');

c.manualY={low:79960,high:80040};const manual=c.manualY;
c.setLookingGlass(false);c.draw();assert.equal(c.range,manual,'Hiding paths does not reset the manual price scale');
assert.equal(c.scenarioView().status,'OFF');
assert.equal(c.scenarioView({ignorePreference:true}).paths.length,3,'The chart visibility preference does not manufacture missing model evidence');
c.setLookingGlass(true);c.draw();assert.equal(c.range,manual);
c.reviewMode=true;assert.equal(c.scenarioView().status,'REVIEW');assert.equal(c.scenarioView().paths.length,0);
c.reviewMode=false;c.inspect({entry_ts:data.market.time-500,exit_ts:data.market.time-400});
assert.equal(c.scenarioView().status,'REVIEW','A selected historical trade cannot show a current forecast');
c.selected=null;c.toLive();const selectedHistory=c.span;c.freezeViewport();const frozen=[c.end,c.viewSpan()];
c.setData(fixture());assert.deepEqual([c.end,c.viewSpan()],frozen,'A manually inspected time window does not jump on a refresh');
assert.equal(c.scenarioView().status,'PAUSED','Manual historical inspection suppresses current scenario paths');
assert.equal(c.scenarioView({ignoreViewport:true}).paths.length,3,'Current model evidence remains separate from the chart viewport');
c.toLive();assert.equal(c.span,selectedHistory,'Returning live does not add forecast time repeatedly to the selected history span');

for(const alter of [
  view=>{view.looking_glass.ticker='KX_PREVIOUS';},
  view=>{view.looking_glass.close_ts+=900;},
  view=>{view.looking_glass.execution_authority=true;},
  view=>{view.looking_glass.probabilities_calibrated=true;},
  view=>{view.market.time-=30;}
]){const value=fixture();alter(value);assert.equal(chart(value).scenarioView().paths.length,0,'An incompatible scenario snapshot is withheld');}
for(const alter of [
  point=>{point.time-=1;},point=>{point.btc+=1;},point=>{point.e9=NaN;}
]){const value=fixture();value.looking_glass.paths.forEach(p=>alter(p.points[0]));assert.equal(chart(value).scenarioView().paths.length,0,'The future path must be anchored to the current observed price and time');}
for(const alter of [
  points=>{points.at(-1).time+=1;},points=>{points[1].time=points[0].time;},points=>{points[1].btc=Infinity;}
]){const value=fixture();value.looking_glass.paths.forEach(p=>alter(p.points));assert.equal(chart(value).scenarioView().paths.length,0,'Invalid or cross-expiry path points are withheld');}
const stale=chart();stale.sourceClock=()=>stale.data.looking_glass.valid_until+.01;
assert.equal(stale.scenarioView().status,'STALE');assert.equal(stale.scenarioView().paths.length,0);
const disconnected=chart();disconnected.sourceConnected=()=>false;
assert.equal(disconnected.scenarioView().status,'STALE');
const stopped=fixture();stopped.run.stopped=true;assert.equal(chart(stopped).scenarioView().status,'STALE');
const missing=fixture();delete missing.looking_glass;assert.equal(chart(missing).scenarioView().status,'UNAVAILABLE');

console.log('Looking Glass chart boundary checks passed');
