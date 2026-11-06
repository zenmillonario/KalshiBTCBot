/* Optional real-browser acceptance: no exchange connections and no strategy run.
 * Uses the actual Dashboard HTTP/assets/CSP and actual executor/projection fixtures.
 * Run with NODE_PATH pointing to playwright-core and NAUTILUS_BROWSER_EXECUTABLE
 * pointing to an installed Chromium/headless-shell. Python-only CHECK stays portable.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {chromium} = require('playwright-core');

const root = path.resolve(__dirname, '../..');
const python = process.env.NAUTILUS_TEST_PYTHON || process.env.CODEX_PRIMARY_RUNTIME_PYTHON || 'python';
const executablePath = process.env.NAUTILUS_BROWSER_EXECUTABLE;
assert.ok(executablePath && fs.existsSync(executablePath), 'Set NAUTILUS_BROWSER_EXECUTABLE to a Chromium executable');
const fixtureCode = String.raw`
import json, math, tempfile, time
from pathlib import Path
from strategy_core.nautilus_projection import NautilusProjection
from strategy_core.paper_execution import FloorPolicy, PaperExecutioner
from strategy_core.types import Action
from tests.tool_rack.test_nautilus_projection import native, status
from tests.tool_rack.test_paper_execution import decision
t=time.time()
minute=int(t//60)*60
# A synthetic, minute-aligned contract with ample time remaining. Completed
# reference profiles use the same boundaries as every current-contract book.
current_close=minute+660
p=NautilusProjection()
with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory)/'fixture') as e:
    b=native(t-900,ticker='KX_FIXTURE_OLD',close=t-100)
    e.execute(decision(t-900,opportunity='OLD',ticker=b.ticker),b,now_ts=t-900,command_id='OLD')
    p.observe(status(e,ts=t-900,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-120,close=current_close)
    e.execute(decision(t-120,opportunity='EDGE1'),b,now_ts=t-120,command_id='ENTRY1')
    p.observe(status(e,ts=t-120,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-90,bid=.27,quantity=50,close=current_close)
    e.execute(decision(t-90,action=Action.EXIT),b,now_ts=t-90,command_id='PARTIAL',position_id='2')
    p.observe(status(e,ts=t-90,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-89,bid=.30,close=current_close)
    e.execute(decision(t-89,action=Action.EXIT),b,now_ts=t-89,command_id='EXIT',position_id='2')
    p.observe(status(e,ts=t-89,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-70,close=current_close)
    e.execute(decision(t-70,opportunity='EDGE2'),b,now_ts=t-70,command_id='ENTRY2')
    p.observe(status(e,ts=t-70,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-65,ticker='KX_FIXTURE_LOSS',close=current_close)
    e.execute(decision(t-65,opportunity='LOSS',ticker=b.ticker),b,now_ts=t-65,command_id='LOSS_ENTRY')
    p.observe(status(e,ts=t-65,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-60,ticker='KX_FIXTURE_LOSS',bid=.12,close=current_close)
    e.execute(decision(t-60,action=Action.EXIT,ticker=b.ticker),b,now_ts=t-60,command_id='LOSS_EXIT',position_id='4')
    p.observe(status(e,ts=t-60,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-59,ticker='KX_FIXTURE_ZERO',close=current_close)
    e.execute(decision(t-59,opportunity='ZERO',ticker=b.ticker,budget=.18),b,now_ts=t-59,command_id='ZERO_ENTRY')
    p.observe(status(e,ts=t-59,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-58,ticker='KX_FIXTURE_ZERO',bid=.20,close=current_close)
    e.execute(decision(t-58,action=Action.EXIT,ticker=b.ticker),b,now_ts=t-58,command_id='ZERO_EXIT',position_id='5')
    p.observe(status(e,ts=t-58,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t-50,bid=.30,close=current_close)
    e.observe_floors(b,now_ts=t-50,policies={'3':FloorPolicy(.5,.05)})
    p.observe(status(e,ts=t-50,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE'))
    b=native(t,bid=.29,close=current_close)
    s=status(e,ts=t,book=b,run='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE')
    s['market'].update(target=80040,target_source='KALSHI_MARKET_FLOOR_STRIKE')
    candles=[]
    baseline=80012-60*math.sin(90/8)
    e9=e30=None
    for i in range(91):
        ts=minute-(90-i)*60
        close=baseline+60*math.sin(i/8)
        e9=close if e9 is None else e9+2/10*(close-e9)
        e30=close if e30 is None else e30+2/31*(close-e30)
        candles.append({'time':ts,'open':close-8,'high':close+13,'low':close-17,
            'close':close,'quality':'coinbase-completed' if i<90 else 'coinbase-developing',
            'complete':i<90,'source':'SYNTHETIC_BROWSER_FIXTURE',
            'e9':e9 if i>=8 and i!=50 else None,
            'e30':e30 if i>=29 and i!=50 else None})
    s['latest_geometry'].update(btc_price=candles[-1]['close'],ema9=e9,ema30=e30)
    chart={'candles':candles,'history':{'status':'READY','requested_minutes':90,
        'completed_minutes':90,'developing_status':'OBSERVED_TRADES'}}
    view=p.project(s,[s['latest_geometry']],chart_data=chart,now_ts=t)
    assert len(view['positions'])==2 and len(view['trades'])==5,view
    assert view['trades'][1]['partial_exits']==1,view['trades']
    assert view['positions'][1]['mark_valid'],view['positions']
    assert view['looking_glass']['status']=='READY',view['looking_glass']
    assert len(view['looking_glass']['paths'])==6,view['looking_glass']
    print(json.dumps(view))
`;
const built = spawnSync(python, ['-c', fixtureCode], {cwd: root, encoding: 'utf8'});
assert.equal(built.status, 0, built.stderr || built.stdout);
let view = JSON.parse(built.stdout.trim().split('\n').at(-1));
const initialFeed = view.feed.length;
const expectedNet = view.accounting.realized_net;
const originalStamp = view.server_now;

// This fixture advances a single synthetic observation during UI checks. Shift
// its entire Looking Glass clock uniformly: refreshing only market.time would
// conceal an invalid source/expiry mismatch instead of exercising live paths.
function shiftGlassTimes(value, delta) {
  if (Array.isArray(value)) {value.forEach(item=>shiftGlassTimes(item,delta));return;}
  if (!value || typeof value!=='object') return;
  for (const [key,item] of Object.entries(value)) {
    if (Number.isFinite(item) && (key.endsWith('_ts') ||
        ['time','known_at','observed_at','valid_until','entry_time','exit_time'].includes(key))) value[key]=item+delta;
    else if (key==='missing_close_times' && Array.isArray(item)) value[key]=item.map(time=>time+delta);
    else shiftGlassTimes(item,delta);
  }
}

function freshView() {
  const result = structuredClone(view), now = Date.now()/1000, delta=now-view.server_now;
  shiftGlassTimes(result.looking_glass,delta);
  if(Number.isFinite(result.market.close_ts))result.market.close_ts+=delta;
  if(Number.isFinite(result.clock.close_ts))result.clock.close_ts+=delta;
  for(const target of result.targets||[])if(target.ticker===result.market.ticker)shiftGlassTimes(target,delta);
  result.server_now=now; result.run.updated=now; result.run.fresh=true;
  result.market.time=now; result.market.fresh=true;
  result.quote.observed_wall=now; result.quote.time=now; result.quote.valid_until=now+3;
  result.quote.last_verified.verified_at=now; result.quote.exchange_age_sec=0;
  result.clock.valid_until=now+5;
  for(const key of ['engine','price','quotes','physical','commander'])result.health[key].updated=now;
  for(const p of result.positions)if(p.ticker===result.market.ticker){
    if(Number.isFinite(p.close_ts))p.close_ts+=delta;
    p.valid_until=now+3; p.mark_valid=true; p.protection.fresh=true;
    if(p.last_verified_mark)p.last_verified_mark.verified_at=now;
  }
  return result;
}

const serverCode = String.raw`
import tempfile
from pathlib import Path
from strategy_core.paper_dashboard import Dashboard
with tempfile.TemporaryDirectory() as directory:
    d=Dashboard(Path(directory))
    try:
        print(d.start(),flush=True)
        input()
    finally:d.close()
`;
const server=spawn(python,['-u','-c',serverCode],{cwd:root,stdio:['pipe','pipe','pipe']});
let stderr=''; server.stderr.on('data',chunk=>stderr+=chunk);
const urlReady=new Promise((resolve,reject)=>{
  let stdout='';
  const timer=setTimeout(()=>reject(Error('Dashboard startup timeout '+stderr)),15000);
  server.stdout.on('data',chunk=>{stdout+=chunk;const line=stdout.split('\n').find(s=>s.startsWith('http://'));
    if(line){clearTimeout(timer);resolve(line.trim());}});
  server.once('exit',code=>{clearTimeout(timer);reject(Error('Dashboard exited '+code+' '+stderr));});
});

(async()=>{
  let browser;
  try{
    const url=await urlReady;
    browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox']});
    const context=await browser.newContext({viewport:{width:1884,height:1050}});
    const page=await context.newPage();
    const canvasLabels=()=>page.evaluate(()=>{
      const chart=window.__nautilus.chart,labels=[],text=chart.text;
      chart.text=function(label,...args){labels.push(label);return text.call(this,label,...args);};
      try{chart.draw();}finally{chart.text=text;}
      return labels;
    });
    const observeGlassPaint=()=>page.evaluate(()=>{
      const chart=window.__nautilus.chart,draw=chart.drawLookingGlass;
      chart.drawLookingGlass=function(view){window.__nautilusPaintedPaths=view.paths.length;return draw.call(this,view);};
      chart.requestDraw();
    });
    const errors=[],external=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    page.on('request',request=>{if(!request.url().startsWith(url))external.push(request.url());});
    await page.goto(url);
    await page.waitForFunction(()=>document.getElementById('sourceStatus').textContent.includes('first Tool Rack'));
    assert.equal(await page.locator('#errorBanner').isVisible(),false,'Cold start should show loading, not an error');
    let frozen=null,holdPolling=false;
    const heldRequests=[];
    await page.route('**/api/nautilus',route=>{
      if(holdPolling){heldRequests.push(route);return;}
      return route.fulfill({contentType:'application/json',body:JSON.stringify(frozen||freshView())});
    });
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE');
    assert.equal(await page.locator('#spanSelect').inputValue(),'45');
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.ratio),.83);
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.price(null)),'—','Unknown seed EMA cannot display zero');
    assert.ok(await page.evaluate(()=>{const c=window.__nautilus.chart,ctx=c.ctx,ys=[],move=ctx.moveTo,line=ctx.lineTo;ctx.moveTo=function(x,y){ys.push(y);return move.call(this,x,y);};ctx.lineTo=function(x,y){ys.push(y);return line.call(this,x,y);};try{c.draw();}finally{ctx.moveTo=move;ctx.lineTo=line;}return ys.every(y=>Number.isFinite(y)&&Math.abs(y)<c.h*2);}), 'Null seed EMAs cannot draw fake zero-price line segments');
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='ready');
    assert.deepEqual(await page.evaluate(()=>{
      const chart=window.__nautilus.chart,view=chart.scenarioView(),glass=view.glass;
      return {count:view.paths.length,refs:glass.reference_window.completed_prior_contracts,
        readOnly:glass.execution_authority===false&&glass.can_order===false&&glass.can_veto===false,
        uncalibrated:glass.probabilities_calibrated===false,
        endpoints:view.paths.every(path=>path.points[0].time===glass.source_ts&&path.points.at(-1).time===glass.close_ts),
        leftPreserved:Math.abs((chart.end-chart.viewSpan())-(chart.historyEnd()-chart.span))<1e-6,
        expiryVisible:chart.end>glass.close_ts&&chart.end-chart.viewSpan()<glass.source_ts};
    }),{count:6,refs:2,readOnly:true,uncalibrated:true,endpoints:true,leftPreserved:true,expiryVisible:true},
      'Looking Glass uses real projected prior-contract paths, keeps the selected history and reaches exact expiry');
    assert.equal(await page.locator('#lookingGlassLegend').isVisible(),true);
    assert.match(await page.locator('#lookingGlassLegend').innerText(),/Continuation[\s\S]*Rotation \/ stall[\s\S]*Return \/ reversal[\s\S]*Dashed BTC · dotted EMA9 analogue · conditional/);
    let labels=await canvasLabels();
    assert.ok(labels.includes('NOW')&&labels.some(label=>label.startsWith('CLOSE ')),'Canvas separates observed history from conditional future through close');
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-looking-glass-synthetic-1884.png'),fullPage:true});
    await page.locator('#lookingGlassToggle').click();
    assert.equal(await page.locator('#lookingGlassBar').getAttribute('data-state'),'off');
    assert.equal(await page.locator('#lookingGlassLegend').isVisible(),false);
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.scenarioView().paths.length),0);
    assert.equal((await canvasLabels()).some(label=>label==='NOW'||label.startsWith('CLOSE ')),false,'Hidden paths leave no future annotations on the canvas');
    await page.reload();
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE');
    assert.equal(await page.locator('#lookingGlassToggle').getAttribute('aria-pressed'),'false','Looking Glass preference survives reload');
    await page.locator('#lookingGlassToggle').click();
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='ready');
    await page.locator('#briefingTab').click();
    const glassBriefing=await page.locator('#lookingGlassBriefing').innerText();
    assert.match(glassBriefing,/OBSERVATION ONLY/);
    assert.match(glassBriefing,/2 prior contracts/);
    assert.match(glassBriefing,/not win probabilities or official settlement values/);
    assert.match(glassBriefing,/40% gross return on entry/);
    assert.match(glassBriefing,/not a take-profit or an instruction to sell/);
    assert.match(glassBriefing,/no entry, exit or veto authority/);
    const yesSwing=page.locator('#lookingGlassBriefing .glass-swing-card').first();
    assert.match(await yesSwing.innerText(),/Ask now\s*0\.300/);
    assert.match(await yesSwing.innerText(),/Review bid\s*0\.420/,'40% means sale bid divided by entry ask, before fees');
    assert.match(await yesSwing.innerText(),/Future swing unassessed/,'Quote arithmetic cannot become a forecast of available future profit');
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-looking-glass-briefing-synthetic-1884.png'),fullPage:true});
    await page.locator('button[data-right="positions"]').click();
    await page.locator('#marketChart').focus();
    await page.keyboard.press('ArrowLeft');
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='paused');
    const frozenViewport=await page.evaluate(()=>({end:window.__nautilus.chart.end,span:window.__nautilus.chart.viewSpan()}));
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.scenarioView().paths.length),0,'Manually inspected history hides current paths');
    assert.equal((await canvasLabels()).some(label=>label==='NOW'||label.startsWith('CLOSE ')),false);
    const panStamp=await page.evaluate(()=>window.__nautilus.getState().server_now);
    await page.waitForFunction(stamp=>window.__nautilus.getState().server_now>stamp,panStamp);
    assert.deepEqual(await page.evaluate(()=>({end:window.__nautilus.chart.end,span:window.__nautilus.chart.viewSpan()})),frozenViewport,'Fresh observations cannot move a manually inspected viewport');
    await page.locator('#liveEdge').click();
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='ready');
    await page.locator('#spanSelect').selectOption('45');
    // Observe scheduled paints without forcing a redraw. The overlay must
    // disappear even when polling is stuck and no newer payload arrives.
    await observeGlassPaint();
    await page.waitForFunction(()=>window.__nautilusPaintedPaths===6);
    holdPolling=true;
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='stale',null,{timeout:6500});
    assert.ok(heldRequests.length>0,'Stale-overlay check must include an outstanding poll without a response');
    assert.equal(await page.evaluate(()=>window.__nautilusPaintedPaths),0,'Stale future lines are cleared by the UI clock without another API response');
    assert.equal(await page.locator('#lookingGlassLegend').isVisible(),false);
    holdPolling=false;
    for(const route of heldRequests.splice(0))await route.fulfill({contentType:'application/json',body:JSON.stringify(freshView())});
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='ready');
    await page.waitForFunction(()=>window.__nautilusPaintedPaths===6);
    assert.equal(await page.locator('#toolRackPrimary').innerText(),'MOUNTAIN');
    assert.equal(await page.locator('#targetValue').innerText(),'$80,040.00');
    assert.match(await page.locator('#distanceValue').innerText(),/28\.00/);
    assert.match(await page.locator('#realizedValue').innerText(),new RegExp(Math.abs(expectedNet).toFixed(2).replace('.','\\.')));
    assert.match(await page.locator('#positionCount').innerText(),/1 active · 1 awaiting/);
    assert.match(await page.locator('#positions').innerText(),/AWAITING OFFICIAL RESULT/);
    assert.match(await page.locator('#positions').innerText(),/FULL-LOT BID/);
    assert.match(await page.locator('#positions').innerText(),/MAX @ \$1/);
    assert.match(await page.locator('#positions .position-card').first().innerText(),/#3/,'Active inventory is shown first');
    assert.equal(await page.locator('#protectionPanel').count(),0,'Standalone bottom protection panel is removed');
    assert.match(await page.locator('#positions .position-card').first().innerText(),/FLOOR/i,'Protection stays attached to the exact active position');
    assert.equal(await page.locator('#engineFeed .feed-line').count(),initialFeed);
    assert.match(await page.locator('#engineFeed').innerText(),/ET ·/);
    const tradeHeaders=await page.locator('#tableArea th').allTextContents();
    const netPercentColumn=tradeHeaders.indexOf('NET %');
    assert.ok(netPercentColumn>=0,'Recorded Trades exposes the fee-inclusive NET %');
    assert.ok(tradeHeaders.includes('NET P&L')&&tradeHeaders.includes('GROSS P&L'),'Both dollar P&L columns remain available');
    const tradeRow=id=>page.locator('#tableArea tbody tr').filter({hasText:'#'+id+'  '});
    // These are committed executor receipts: a partial sale followed by final
    // close, a losing close, and one contract with exactly zero after fees.
    assert.equal(await tradeRow('2').locator('td').nth(netPercentColumn).innerText(),'+52.68%');
    assert.equal(await tradeRow('4').locator('td').nth(netPercentColumn).innerText(),'-37.45%');
    assert.equal(await tradeRow('5').locator('td').nth(netPercentColumn).innerText(),'0.00%');
    assert.equal(await tradeRow('3').locator('td').nth(netPercentColumn).innerText(),'OPEN','An open position does not display a zero realized return');
    assert.equal(await tradeRow('2').locator('td').nth(tradeHeaders.indexOf('NET P&L')).innerText(),'+$13.08');
    assert.equal(await tradeRow('2').locator('td').nth(tradeHeaders.indexOf('GROSS P&L')).innerText(),'+$16.44');
    const winningTrade=view.trades.find(t=>t.trade_id==='2');
    const savedNetRoi=winningTrade.net_roi,savedNetBasis=winningTrade.net_return_basis;
    winningTrade.net_roi=null;winningTrade.net_return_basis=null;
    await page.waitForFunction(()=>{const table=document.getElementById('tableArea'),index=[...table.querySelectorAll('th')].findIndex(n=>n.textContent==='NET %'),row=[...table.querySelectorAll('tbody tr')].find(n=>n.textContent.startsWith('#2  '));return row?.children[index]?.textContent==='—';});
    assert.equal(await tradeRow('2').locator('td').nth(netPercentColumn).innerText(),'—','Missing verified net basis cannot fall back to gross return');
    winningTrade.net_roi=savedNetRoi;winningTrade.net_return_basis=savedNetBasis;
    await page.waitForFunction(()=>document.getElementById('tableArea').textContent.includes('+52.68%'));
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-net-roi-1884.png'),fullPage:true});

    await page.locator('#feedFilter').selectOption('trade');
    assert.ok(await page.locator('#engineFeed .feed-line').count()<initialFeed);
    await page.locator('#feedFilter').selectOption('all');
    await page.locator('#pauseFeed').click();
    view.feed.push({id:'FIXTURE:NEW',time:originalStamp+1,text:'WAIT: fixture source stale <script>unsafe()</script>',category:'warning'});
    await page.waitForFunction(()=>document.getElementById('newLines').textContent.includes('1 new'));
    assert.equal(await page.locator('#engineFeed .feed-line').count(),initialFeed);
    await page.locator('#pauseFeed').click();
    assert.equal(await page.locator('#engineFeed .feed-line').count(),initialFeed+1);
    assert.equal(await page.locator('#engineFeed script').count(),0,'Feed text must not create elements');
    await page.locator('#tableArea tbody tr').filter({hasText:'#2  '}).click();
    await page.waitForFunction(()=>document.getElementById('detailsTitle').textContent.startsWith('Trade #2'));
    assert.equal(await page.locator('#lookingGlassBar').getAttribute('data-state'),'review');
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.scenarioView().paths.length),0,'Current forecast cannot become a historical trade forecast');
    assert.equal((await canvasLabels()).some(label=>label==='NOW'||label.startsWith('CLOSE ')),false);
    assert.match(await page.locator('#details').innerText(),/PAPER NET/);
    assert.match(await page.locator('#details').innerText(),/CLOSED POSITION/);
    assert.match(await page.locator('#details').innerText(),/NET %\s*\+52\.68%/);
    assert.match(await page.locator('#details').innerText(),/Net return basis\s*\$24\.83/);
    assert.match(await page.locator('#details').innerText(),/after fees, divided by original entry cost plus entry fee/);
    await page.locator('#liveEdge').click();
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.scenarioView().paths.length),0,'Return to Live does not invent an entry-time forecast in Review');
    await page.locator('#liveMode').click();
    await page.waitForFunction(()=>document.getElementById('lookingGlassBar').dataset.state==='ready');
    await page.locator('button[data-right="navigator"]').click();
    assert.match(await page.locator('#navigator').innerText(),/NAVIGATOR TERRAIN BRIEFING · EMBEDDED \/ READ ONLY/);
    await page.locator('button[data-right="positions"]').click();

    view.run.status='DRAINING';
    await page.waitForFunction(()=>document.getElementById('connection').textContent==='DRAINING');
    assert.match(await page.locator('#sourceStatus').innerText(),/ENTRY WINDOW CLOSED · HELD STRATEGY CONTINUES/);
    assert.match(await page.locator('#quoteSource').innerText(),/CURRENT/,'Draining keeps the current quote feed');
    assert.equal(await page.locator('#positions .position-card').count(),2,'Draining retains active and awaiting inventory');
    view.run.status='RUNNING';
    await page.waitForFunction(()=>document.getElementById('connection').textContent==='FEED CONNECTED');
    const recovering=view.positions.find(p=>p.ticker===view.market.ticker);
    const priorCustody=recovering.custody_state,priorCustodyMetadata=recovering.custody_metadata;
    recovering.custody_state='LAZARUS';
    recovering.custody_metadata={reason:'FIXTURE_SOURCE_BOUND_RECOVERY',reviewed_at:originalStamp};
    await page.waitForFunction(()=>document.getElementById('positions').textContent.includes('CUSTODY · LAZARUS'));
    assert.match(await page.locator('#positions').innerText(),/LAZARUS/,'Recovery custody stays visible with the exact position');
    assert.equal(await page.locator('#positions .position-card').count(),2,'Custody transition does not create another position');
    recovering.custody_state=priorCustody;recovering.custody_metadata=priorCustodyMetadata;

    // Read-only projection fixture: explicit independent strategy roles and
    // exact-contract aggregate exposure, without another trading process.
    const savedRoleView=view;
    const roleFixture=spawnSync(python,['-c',String.raw`
import json,time
from strategy_core.nautilus_projection import NautilusProjection
from tests.tool_rack.test_pid7516_nautilus_roles import role_fixture
t=time.time();source=role_fixture(t);source['run_id']='NAUTILUS_BROWSER_ROLES_FIXTURE'
print(json.dumps(NautilusProjection().project(source,now_ts=t)))
`],{cwd:root,encoding:'utf8'});
    assert.equal(roleFixture.status,0,roleFixture.stderr||roleFixture.stdout);
    view=JSON.parse(roleFixture.stdout.trim());
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_BROWSER_ROLES_FIXTURE');
    assert.equal(await page.locator('#positions .position-card').count(),2);
    assert.deepEqual(await page.locator('#positions .position-role').allTextContents(),['PRIMARY','TACTICAL']);
    assert.match(await page.locator('#positions .contract-exposure').innerText(),/18 YES · 30 NO/);
    assert.match(await page.locator('#positions .contract-exposure').innerText(),/Net 12 NO/);
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-primary-tactical-1884.png'),fullPage:true});
    view=savedRoleView;
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE');

    const savedTarget=view.market.target,savedTargets=view.targets;
    view.market.target=null;view.targets=[];
    await page.waitForFunction(()=>document.getElementById('targetValue').textContent==='—');
    assert.equal(await page.locator('#targetToggle').isDisabled(),true,'Missing official target remains unavailable');
    view.market.target=savedTarget;view.targets=savedTargets;
    await page.waitForFunction(()=>document.getElementById('targetValue').textContent==='$80,040.00');
    await page.locator('#spanSelect').selectOption('90');
    await page.reload();
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_SYNTHETIC_BROWSER_FIXTURE');
    assert.equal(await page.locator('#spanSelect').inputValue(),'90','Chart span persists across reload');
    assert.equal(await page.locator('#engineFeed .feed-line').count(),initialFeed+1,'Server feed survives browser reload');
    await page.locator('#spanSelect').selectOption('45');
    for(const size of [{width:1440,height:900},{width:1280,height:800},{width:390,height:844}]){
      await page.setViewportSize(size);
      await page.waitForTimeout(100);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Viewport overflows at '+size.width);
      assert.deepEqual(await page.evaluate(()=>['btcValue','targetValue','yesQuote','noQuote','timerValue','distanceValue'].filter(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();if(!r.width)return false;const range=document.createRange();range.selectNodeContents(e);const text=range.getBoundingClientRect(),cell=e.closest('.instrument').getBoundingClientRect();return text.right>cell.right-3||text.left<cell.left+3;})),[],'Instrument values clipped at '+size.width);
    }
    await page.locator('button[data-deck="feed"]').click();
    assert.equal(await page.locator('#engineFeed').isVisible(),true);
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-mobile-feed.png'),fullPage:true});
    await page.locator('button[data-deck="chart"]').click();
    assert.equal(await page.locator('#marketChart').isVisible(),true);
    assert.equal(await page.locator('#lookingGlassBar').isVisible(),true);
    assert.ok(await page.evaluate(()=>{const bar=document.getElementById('lookingGlassBar');return bar.scrollWidth<=bar.clientWidth+1;}),'Looking Glass legend and status wrap within the mobile chart');
    labels=await canvasLabels();
    assert.equal(labels.includes('Expand chart to inspect'),false,'Mobile Looking Glass controls must leave room for the actual chart');
    assert.ok(labels.includes('NOW')&&labels.some(label=>label.startsWith('CLOSE ')),'Mobile chart still displays the conditional future region');
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-mobile-chart.png'),fullPage:true});
    await page.setViewportSize({width:1920,height:1080});
    await page.locator('#liveMode').click();
    await observeGlassPaint();
    await page.waitForFunction(()=>window.__nautilusPaintedPaths===6);
    frozen=freshView();
    await page.waitForTimeout(6500);
    assert.equal(await page.locator('#connection').innerText(),'STALE','Repeated identical HTTP payload must age out');
    assert.match(await page.locator('#quoteSource').innerText(),/STALE/);
    assert.match(await page.locator('#positions').innerText(),/LAST VERIFIED MARK/);
    assert.equal(await page.locator('#timerValue').innerText(),'—:—','Frozen engine cannot retain a live timer');
    assert.equal(await page.locator('#lookingGlassBar').getAttribute('data-state'),'stale');
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.scenarioView().paths.length),0);
    assert.equal(await page.evaluate(()=>window.__nautilusPaintedPaths),0,'Frozen payload cannot leave a current-looking hurricane overlay');
    assert.deepEqual(external,[],'No external browser resources or requests');
    assert.deepEqual(errors,[],'No browser errors or CSP violations');
    console.log('Nautilus real-browser acceptance passed: startup, live/projection contract, actual Looking Glass prior-contract paths through exact close, retained history span, persistent overlay toggle, 40% ask-to-sale-bid screening with no exit authority, manual pan/review suppression, stale path removal without a new payload and recovery, explicit primary/tactical roles and exact-contract net exposure, full-lot/expired positions, partial-exit ledger, fee-inclusive net return for gain/loss/zero with open and missing-basis states, feed filters/pause/reload, safe text, trade review, source health, responsive layouts, persistent 45m controls, stale identical payload and timer.');
    await context.close();
  }finally{
    if(browser)await browser.close();
    if(server.exitCode===null){server.stdin.end('\n');await new Promise(resolve=>{server.once('exit',resolve);setTimeout(()=>{server.kill();resolve();},3000);});}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
