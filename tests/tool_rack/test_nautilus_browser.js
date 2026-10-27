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
p=NautilusProjection()
with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory)/'fixture') as e:
    b=native(t-900,ticker='KX_FIXTURE_OLD',close=t-100)
    e.execute(decision(t-900,opportunity='OLD',ticker=b.ticker),b,now_ts=t-900,command_id='OLD')
    p.observe(status(e,ts=t-900,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t-120,close=t+650)
    e.execute(decision(t-120,opportunity='EDGE1'),b,now_ts=t-120,command_id='ENTRY1')
    p.observe(status(e,ts=t-120,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t-90,bid=.27,quantity=50,close=t+650)
    e.execute(decision(t-90,action=Action.EXIT),b,now_ts=t-90,command_id='PARTIAL',position_id='2')
    p.observe(status(e,ts=t-90,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t-89,bid=.30,close=t+650)
    e.execute(decision(t-89,action=Action.EXIT),b,now_ts=t-89,command_id='EXIT',position_id='2')
    p.observe(status(e,ts=t-89,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t-70,close=t+650)
    e.execute(decision(t-70,opportunity='EDGE2'),b,now_ts=t-70,command_id='ENTRY2')
    p.observe(status(e,ts=t-70,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t-50,bid=.30,close=t+650)
    e.observe_floors(b,now_ts=t-50,policies={'3':FloorPolicy(.5,.05)})
    p.observe(status(e,ts=t-50,book=b,run='NAUTILUS_BROWSER_FIXTURE'))
    b=native(t,bid=.29,close=t+650)
    s=status(e,ts=t,book=b,run='NAUTILUS_BROWSER_FIXTURE')
    s['market'].update(target=80040,target_source='KALSHI_MARKET_FLOOR_STRIKE')
    s['latest_geometry'].update(btc_price=80012,ema9=80020,ema30=80040)
    minute=int(t//60)*60
    candles=[]
    for i in range(46):
        ts=minute-(45-i)*60
        close=80030+60*math.sin(i/8)
        candles.append({'time':ts,'open':close-8,'high':close+13,'low':close-17,
            'close':close,'quality':'coinbase-completed' if i<45 else 'coinbase-developing',
            'complete':i<45,'source':'SYNTHETIC_BROWSER_FIXTURE', 'e9':close-4 if i>=8 else None,'e30':close+8 if i>=29 else None})
    chart={'candles':candles,'history':{'status':'READY','requested_minutes':45,
        'completed_minutes':45,'developing_status':'OBSERVED_TRADES'}}
    view=p.project(s,[s['latest_geometry']],chart_data=chart,now_ts=t)
    assert len(view['positions'])==2 and len(view['trades'])==3,view
    assert view['trades'][1]['partial_exits']==1,view['trades']
    assert view['positions'][1]['mark_valid'],view['positions']
    print(json.dumps(view))
`;
const built = spawnSync(python, ['-c', fixtureCode], {cwd: root, encoding: 'utf8'});
assert.equal(built.status, 0, built.stderr || built.stdout);
let view = JSON.parse(built.stdout.trim().split('\n').at(-1));
const initialFeed = view.feed.length;
const expectedNet = view.accounting.realized_net;
const originalStamp = view.server_now;

function freshView() {
  const result = structuredClone(view), now = Date.now()/1000;
  result.server_now=now; result.run.updated=now; result.run.fresh=true;
  result.market.time=now; result.market.fresh=true;
  result.quote.observed_wall=now; result.quote.time=now; result.quote.valid_until=now+3;
  result.quote.last_verified.verified_at=now; result.quote.exchange_age_sec=0;
  result.clock.valid_until=now+5;
  for(const key of ['engine','price','quotes','physical','commander'])result.health[key].updated=now;
  for(const p of result.positions)if(p.ticker===result.market.ticker){
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
    const context=await browser.newContext({viewport:{width:1920,height:1080}});
    const page=await context.newPage();
    const errors=[],external=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    page.on('request',request=>{if(!request.url().startsWith(url))external.push(request.url());});
    await page.goto(url);
    await page.waitForFunction(()=>document.getElementById('sourceStatus').textContent.includes('first Tool Rack'));
    assert.equal(await page.locator('#errorBanner').isVisible(),false,'Cold start should show loading, not an error');
    let frozen=null;
    await page.route('**/api/nautilus',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(frozen||freshView())}));
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_BROWSER_FIXTURE');
    assert.equal(await page.locator('#spanSelect').inputValue(),'45');
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.ratio),.83);
    assert.equal(await page.evaluate(()=>window.__nautilus.chart.price(null)),'—','Unknown seed EMA cannot display zero');
    assert.ok(await page.evaluate(()=>{const c=window.__nautilus.chart,ctx=c.ctx,ys=[],move=ctx.moveTo,line=ctx.lineTo;ctx.moveTo=function(x,y){ys.push(y);return move.call(this,x,y);};ctx.lineTo=function(x,y){ys.push(y);return line.call(this,x,y);};try{c.draw();}finally{ctx.moveTo=move;ctx.lineTo=line;}return ys.every(y=>Number.isFinite(y)&&Math.abs(y)<c.h*2);}), 'Null seed EMAs cannot draw fake zero-price line segments');
    assert.equal(await page.locator('#toolRackPrimary').innerText(),'MOUNTAIN');
    assert.equal(await page.locator('#targetValue').innerText(),'$80,040.00');
    assert.match(await page.locator('#distanceValue').innerText(),/28\.00/);
    assert.match(await page.locator('#realizedValue').innerText(),new RegExp(Math.abs(expectedNet).toFixed(2).replace('.','\\.')));
    assert.match(await page.locator('#positionCount').innerText(),/1 active · 1 awaiting/);
    assert.match(await page.locator('#positions').innerText(),/AWAITING OFFICIAL RESULT/);
    assert.match(await page.locator('#positions').innerText(),/FULL-LOT BID/);
    assert.match(await page.locator('#positions').innerText(),/MAX @ \$1/);
    assert.match(await page.locator('#positions .position-card').first().innerText(),/#3/,'Active inventory is shown first');
    assert.match(await page.locator('#protection').innerText(),/YES #3/,'Default protection follows active contract');
    assert.equal(await page.locator('#engineFeed .feed-line').count(),initialFeed);
    assert.match(await page.locator('#engineFeed').innerText(),/ET ·/);
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-desktop.png'),fullPage:true});

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
    assert.match(await page.locator('#details').innerText(),/PAPER NET/);
    assert.match(await page.locator('#details').innerText(),/CLOSED POSITION/);
    await page.locator('#liveMode').click();
    await page.locator('button[data-right="navigator"]').click();
    assert.match(await page.locator('#navigator').innerText(),/ADVISORY AI \/ NAVIGATOR · NOT RUNNING/);
    await page.locator('button[data-right="positions"]').click();

    const savedTarget=view.market.target,savedTargets=view.targets;
    view.market.target=null;view.targets=[];
    await page.waitForFunction(()=>document.getElementById('targetValue').textContent==='—');
    assert.equal(await page.locator('#targetToggle').isDisabled(),true,'Missing official target remains unavailable');
    view.market.target=savedTarget;view.targets=savedTargets;
    await page.waitForFunction(()=>document.getElementById('targetValue').textContent==='$80,040.00');
    await page.locator('#spanSelect').selectOption('90');
    await page.reload();
    await page.waitForFunction(()=>window.__nautilus.getState()?.run.name==='NAUTILUS_BROWSER_FIXTURE');
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
    await page.screenshot({path:path.join(os.tmpdir(),'nautilus-mobile-chart.png'),fullPage:true});
    await page.setViewportSize({width:1920,height:1080});
    await page.locator('#liveMode').click();
    frozen=freshView();
    await page.waitForTimeout(6500);
    assert.equal(await page.locator('#connection').innerText(),'STALE','Repeated identical HTTP payload must age out');
    assert.match(await page.locator('#quoteSource').innerText(),/STALE/);
    assert.match(await page.locator('#positions').innerText(),/LAST VERIFIED MARK/);
    assert.equal(await page.locator('#timerValue').innerText(),'—:—','Frozen engine cannot retain a live timer');
    assert.deepEqual(external,[],'No external browser resources or requests');
    assert.deepEqual(errors,[],'No browser errors or CSP violations');
    console.log('Nautilus real-browser acceptance passed: startup, live/projection contract, full-lot/expired positions, partial-exit ledger, feed filters/pause/reload, safe text, trade review, source health, responsive layouts, persistent 45m controls, stale identical payload and timer.');
    await context.close();
  }finally{
    if(browser)await browser.close();
    if(server.exitCode===null){server.stdin.end('\n');await new Promise(resolve=>{server.once('exit',resolve);setTimeout(()=>{server.kill();resolve();},3000);});}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
