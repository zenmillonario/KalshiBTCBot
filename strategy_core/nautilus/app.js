/* Read-only browser workspace. Untrusted engine text is rendered with textContent. */
'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const price=(v,d=2)=>finite(v)?v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const money=v=>finite(v)?(v<0?'−':v>0?'+':'')+'$'+price(Math.abs(v)):'—';
  const pct=v=>finite(v)?(v>0?'+':'')+v.toFixed(2)+'%':'—';
  const quote=v=>price(v,3);
  const clock=(v,seconds=true)=>finite(v)?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{}),hour12:false}).format(new Date(v*1000)):'Not recorded';
  const readable=v=>v==null||v===''?'Not recorded':typeof v==='object'?JSON.stringify(v):String(v);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const clear=n=>n.replaceChildren();
  const note=(parent,text,cls='context-note')=>parent.append(el('div',text,cls));
  const row=(parent,label,value)=>{const n=el('div',null,'detail-row');n.append(el('span',label),el('span',readable(value)));parent.append(n);};
  const positive=(node,v)=>{node.classList.toggle('positive',finite(v)&&v>0);node.classList.toggle('negative',finite(v)&&v<0);};
  const grid=(parent,items)=>{const g=el('div',null,'metric-grid'+(items.length===2?' two':items.length===4?' four':''));items.forEach(([label,value])=>{const n=el('div');n.append(el('label',label),el('strong',value));g.append(n);});parent.append(g);};
  let state=null, selectedKey=null, tab='trades', receivedAt=0, online=false, mode='monitor';
  let clockAnchorWall=null, clockAnchorMono=0, positionFreshness='';
  let feedPaused=false, feedShownId=null, feedSignature='', pendingFeed=0, programmaticScroll=false, userFeedScrollUntil=0;
  const chart=new NautilusChart($('marketChart'),$('chartTooltip'),trade=>selectTrade(trade));
  // A responsive HTTP server does not make an unchanged engine snapshot fresh.
  const backendNow=()=>finite(clockAnchorWall)?clockAnchorWall+(performance.now()-clockAnchorMono)/1000:NaN;
  const connected=()=>online&&receivedAt>0&&performance.now()-receivedAt<5500;
  const monitorFresh=()=>connected()&&state?.run?.fresh&&!state.run.stopped&&finite(state.run.updated)&&backendNow()>=state.run.updated&&backendNow()-state.run.updated<=5;
  const quoteFresh=()=>monitorFresh()&&state.quote?.fresh&&state.quote.ticker===state.market?.ticker&&finite(state.quote.valid_until)&&backendNow()<=state.quote.valid_until;
  const lastQuote=()=>state.quote?.last_verified?.ticker===state.market?.ticker?state.quote.last_verified:{};
  const currentMark=p=>monitorFresh()&&p?.mark_valid&&p.ticker===state.market?.ticker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts&&finite(p.valid_until)&&backendNow()<=p.valid_until;
  function syncModes(){ $('liveMode').classList.toggle('active',mode==='monitor');$('reviewMode').classList.toggle('active',mode==='review'); }
  function selectTrade(trade){selectedKey=trade.key;mode='review';chart.inspect(trade);syncModes();renderDetails();renderProtection();renderTable();document.dispatchEvent(new CustomEvent('nautilus:trade-selected',{detail:{key:trade.key}}));}
  function monitor(){mode='monitor';selectedKey=null;chart.selected=null;chart.toLive();syncModes();renderDetails();renderProtection();renderTable();document.dispatchEvent(new Event('nautilus:monitor'));}
  $('liveMode').onclick=monitor;
  $('reviewMode').onclick=()=>{mode='review';chart.follow=false;syncModes();const t=state?.trades?.find(t=>t.key===selectedKey)||state?.trades?.at(-1);if(t)selectTrade(t);};
  $('liveEdge').onclick=()=>{chart.toLive();};
  $('spanSelect').value=String(chart.span/60);
  $('spanSelect').onchange=e=>chart.setSpan(Number(e.target.value)*60);
  $('targetToggle').onclick=()=>{chart.fitTarget=!chart.fitTarget;$('targetToggle').setAttribute('aria-pressed',String(chart.fitTarget));chart.requestDraw();};
  $('fullChart').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else $('chartPanel').requestFullscreen().catch(()=>{});};
  chart.onViewport=({follow,span})=>{
    $('liveEdge').textContent=follow?(state?.run?.stopped?'Latest recorded ✓':'Following live ✓'):'Return to Live →';
    $('liveEdge').classList.toggle('active',follow);
    const match=[...$('spanSelect').options].some(o=>Number(o.value)*60===span);
    if(match)$('spanSelect').value=String(span/60);
    else {let o=$('spanSelect').querySelector('[data-custom]');if(!o){o=el('option');o.dataset.custom='true';$('spanSelect').append(o);}o.value=String(span/60);o.textContent=(span/60).toFixed(0)+'m · custom zoom';$('spanSelect').value=o.value;}
  };
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));renderTable();});
  $('healthButton').onclick=()=>{renderHealth($('healthContent'));$('healthDialog').showModal();};
  $('closeHealth').onclick=()=>$('healthDialog').close();
  $('healthDialog').onclick=e=>{if(e.target===$('healthDialog'))$('healthDialog').close();};
  function renderTop(){
    if(!state)return;
    const m=state.market||{},q=state.quote||{},r=state.run||{},a=state.accounting||{};
    const fresh=monitorFresh()&&m.fresh&&finite(m.time)&&backendNow()-m.time>=-2&&backendNow()-m.time<=3;
    $('targetValue').textContent=finite(m.target)?'$'+price(m.target):'—';
    $('btcValue').textContent=finite(m.btc)?'$'+price(m.btc):'—';
    document.querySelector('.instrument.now').classList.toggle('paused-price',!fresh);
    $('priceAge').textContent=fresh?'· FEED '+Math.max(0,backendNow()-m.time).toFixed(1)+'s':'· LAST RECORDED';
    const delta=finite(m.btc)&&finite(m.target)?m.btc-m.target:null;
    $('distanceValue').textContent=finite(delta)?money(delta):'—';
    $('distanceLabel').textContent=finite(delta)?pct(delta/m.target*100)+' · '+(delta>=0?'ABOVE':'BELOW')+' TARGET':'Target distance unavailable';
    positive($('distanceValue'),fresh?delta:null);
    $('contractLabel').textContent=(m.ticker||'Discovering current contract')+(finite(m.target)?'':' · target not supplied');
    $('targetToggle').disabled=!finite(m.target);
    $('targetToggle').title=finite(m.target)?'Include official contract target in vertical scale':'Official contract target unavailable in this feed';
    const qfresh=quoteFresh();
    const last=lastQuote();
    const yb=qfresh?q.yes_bid:last.yes_bid, ya=qfresh?q.yes_ask:last.yes_ask, nb=qfresh?q.no_bid:last.no_bid, na=qfresh?q.no_ask:last.no_ask;
    $('yesQuote').textContent=(finite(yb)||finite(ya))?quote(yb)+' / '+quote(ya):'— / —';
    $('noQuote').textContent=(finite(nb)||finite(na))?quote(nb)+' / '+quote(na):'— / —';
    const staleAge=finite(q.last_verified_age_seconds)?Math.max(0,q.last_verified_age_seconds).toFixed(0)+'s':'age unknown';
    const exchangeAge=finite(q.exchange_age_sec)?Math.max(0,q.exchange_age_sec).toFixed(0)+'s':null;
    const exchangeNote=exchangeAge?' · EXCHANGE AGE '+exchangeAge:'';
    $('quoteSource').textContent=qfresh?'NATIVE BID / ASK · '+(q.source||'recorded source')+exchangeNote:
      ((finite(yb)||finite(ya)||finite(nb)||finite(na))?'STALE · '+staleAge+' · LAST VERIFIED BID / ASK':'NO VERIFIED QUOTE YET')+exchangeNote+' · '+(q.reason||'awaiting fresh data');
    $('quoteSourceNo').textContent=$('quoteSource').textContent;
    $('realizedValue').textContent=money(a.realized_net);positive($('realizedValue'),a.realized_net);
    $('recordSummary').textContent=(a.realized_stale?'LAST VERIFIED · STALE · ':'')+'Gross '+money(a.realized)+' · total fees paid $'+price(a.fees_paid)+' · '+(a.closed??0)+' closed';
    $('recordSummary').title=(a.realized_stale?'Recorded ledger snapshot. ':'')+'Realized net includes allocated entry and exit model fees for realized contracts. Total fees paid also includes entry fees on open positions.';
    $('runIdentity').textContent=[r.build,r.name,'PID '+(r.pid??'—')].filter(Boolean).join('  ·  ');
    $('runIdentity').title='Pinned run '+(r.name||'unavailable');
    $('sourceStatus').textContent=(r.review?'ARCHIVE':r.stopped?'ENGINE STOPPED':monitorFresh()?'RUNTIME CURRENT':'RUNTIME STALE')+' · PINNED SOURCE';
    $('ema9Value').textContent=price(m.e9);$('ema30Value').textContent=price(m.e30);
    const sampled=state.diagnostics.sampled_candles??0;
    $('chartQuality').textContent=state.candles.length?(sampled?'Mixed sources · dashed = sampled OHLC':'Source-labeled BTC candles'):'Waiting for actual BTC trade observations';
    $('chartQuality').title=state.diagnostics.candle_note;
    $('chartEmpty').classList.toggle('hidden',!!state.candles?.length);
    $('footerStatus').textContent='NAUTILUS '+state.version+' · '+(state.run.review?'RECORDED REVIEW':'READ-ONLY MONITOR')+' · '+state.trades.length+' trades · '+(state.diagnostics.issues.length?'SOURCE NOTES AVAILABLE':'COMMITTED PAPER LEDGER');
    renderConnection();renderComponentHealth();renderHistory();tick();
  }
  function renderConnection(){
    const b=$('connection');
    b.className='badge '+(!connected()?'red':state?.run.stopped?'amber':monitorFresh()?'green':'amber');
    b.textContent=!connected()?'DISCONNECTED':state?.run.review?'ARCHIVE':state?.run.stopped?'STOPPED':monitorFresh()?'FEED CONNECTED':'STALE';
  }
  function renderComponentHealth(){
    if(!state)return;
    const parent=$('componentHealth');
    const labels={engine:'ENGINE',price:'BTC PRICE',quotes:'QUOTES',physical:'PHYSICAL',commander:'COMMANDER',candles:'CHART'};
    const alerts=[];
    for(const [name,label]of Object.entries(labels)){
      const d=state.health?.[name]||{};
      const h=NautilusReliability.health(d,name,backendNow(),connected(),state.run.stopped);
      if(name==='quotes'&&h.status==='CURRENT'&&(!finite(state.quote.valid_until)||backendNow()>state.quote.valid_until)){h.status='UNAVAILABLE';h.color='amber';}
      let chip=$('component-'+name);
      if(!chip){chip=el('button');chip.id='component-'+name;chip.onclick=()=>{renderHealth($('healthContent'));$('healthDialog').showModal();};parent.append(chip);}
      const timeLabel=h.status==='FAILED'&&finite(d.failed_at)?' · '+clock(d.failed_at)+' ET':h.status==='STALE'&&finite(h.age)?(h.age<0?' · FUTURE '+(-h.age).toFixed(2)+'s':' · '+h.age.toFixed(0)+'s'):'';
      chip.textContent=label+' · '+h.status.replaceAll('_',' ')+timeLabel;
      chip.className=h.color;chip.title=readable(d.reason)+(d.reader_errors?' · Reader errors this viewer: '+d.reader_errors:'');
      if(['FAILED','READ_ERROR','UNVERIFIED'].includes(h.status))alerts.push(label+' '+h.status.replaceAll('_',' ')+timeLabel+(d.reason?' — '+d.reason:''));
    }
    $('componentAlert').textContent=alerts.join('  |  ');
    $('componentAlert').classList.toggle('hidden',!alerts.length);
  }
  function renderHistory(){
    if(!state)return;
    const h=state.history||{};
    const text='HISTORY '+(h.completed_minutes??0)+' completed source bars · '+(h.status||'WARMING')+
      ' · FORMING '+(h.developing_status||'UNAVAILABLE').replaceAll('_',' ');
    $('historyStatus').textContent=text;
    $('historyStatus').title=h.developing_note||state.diagnostics.candle_note;
    $('historyStatus').classList.toggle('incomplete',h.status!=='READY');
  }
  function tick(){
    if(!state)return;
    const now=backendNow(),r=state.run||{},q=state.quote||{};
    const timer=NautilusReliability.timer(state,now,connected());
    $('timerValue').textContent=timer.text;
    $('timerProgress').style.width=timer.running?Math.max(0,Math.min(100,(900-timer.seconds)/9))+'%':'0%';
    document.querySelector('.clock').classList.toggle('urgent',timer.running&&timer.seconds<=120);
    $('closeLabel').textContent=finite(timer.close)?'CLOSE '+clock(timer.close,false)+' ET'+(timer.running?(timer.seconds===0?' · awaiting new contract':' · verified contract clock'):' · timer paused'):'Contract close not verified';
    $('closeLabel').title='Local system clock checked for monotonic continuity; absolute exchange clock offset is not measured.';
    const priceFresh=monitorFresh()&&state.market.fresh&&finite(state.market.time)&&now-state.market.time>=-2&&now-state.market.time<=3;
    document.querySelector('.instrument.now').classList.toggle('paused-price',!priceFresh);
    if(!priceFresh)$('priceAge').textContent='· LAST RECORDED'+(finite(state.market.time)?' · '+Math.max(0,now-state.market.time).toFixed(0)+'s':'');
    if(!quoteFresh()){
      const last=lastQuote();
      $('yesQuote').textContent=(finite(last.yes_bid)||finite(last.yes_ask))?quote(last.yes_bid)+' / '+quote(last.yes_ask):'— / —';
      $('noQuote').textContent=(finite(last.no_bid)||finite(last.no_ask))?quote(last.no_bid)+' / '+quote(last.no_ask):'— / —';
      if(Object.keys(last).length){const a=finite(last.verified_at)?Math.max(0,now-last.verified_at).toFixed(0)+'s':'age unknown';const ex=finite(q.exchange_age_sec)?' · EXCHANGE AGE '+Math.max(0,q.exchange_age_sec).toFixed(0)+'s':'';$('quoteSource').textContent='STALE · '+a+' · LAST VERIFIED BID / ASK'+ex+' · '+(q.reason||'awaiting fresh data');$('quoteSourceNo').textContent=$('quoteSource').textContent;}
    }
    if(!connected()&&online){online=false;renderConnection();$('priceAge').textContent='· CONNECTION LOST';renderPositions();renderProtection();}
    const freshness=String(monitorFresh())+'|'+state.positions.map(p=>[p.key,currentMark(p)].join(':')).join('|');
    if(freshness!==positionFreshness){positionFreshness=freshness;renderPositions();renderProtection();}
    renderConnection();renderComponentHealth();
  }
  function renderToolRack(){
    const strip=$('toolRackStrip');if(!strip)return;const tr=state?.tool_rack;
    if(!tr){strip.classList.add('hidden');return;}
    strip.classList.remove('hidden');
    $('toolRackTerritory').textContent=readable(tr.owned_territory||'QUALIFYING')+(tr.owned_side?' · '+tr.owned_side:'');
    $('toolRackPrimary').textContent=readable(tr.active_tool||'NONE');
    $('toolRackOverlay').textContent=(tr.active_overlays||[]).join(' + ')||'NONE';
    const action=tr.commander_action||'WAIT',side=tr.accepted_side?' '+tr.accepted_side:'';
    const ask=finite(tr.accepted_observed_ask)?' · '+quote(tr.accepted_observed_ask):'';
    const cap=finite(tr.accepted_max_price)?' ≤ '+quote(tr.accepted_max_price):'';
    $('toolRackIntent').textContent=action+side+ask+cap;
    $('toolRackReason').textContent=readable(tr.commander_reason||tr.lane_resolution_reason||tr.ownership_reason);
    $('toolRackReason').title=$('toolRackReason').textContent;
  }
  function renderPositions(){
    const parent=$('positions');clear(parent);
    const currentTicker=state?.market?.ticker;
    const inventoryVerified=state?.accounting?.inventory_verified!==false;
    const active=state?.positions?.filter(p=>p.ticker===currentTicker&&finite(state.market?.close_ts)&&backendNow()<state.market.close_ts).length??0;
    const awaiting=(state?.positions?.length??0)-active;
    $('positionCount').textContent=inventoryVerified?(awaiting?`${active} active · ${awaiting} awaiting`:String(active)):`${state?.positions?.length??0} last recorded`;
    $('positionTitle').textContent=inventoryVerified?'Open positions':'Last recorded positions';
    if(!state)return;
    if(!inventoryVerified){note(parent,'Current inventory and settlement status are not confirmed by this trade projection.','warning-note');}
    if(!inventoryVerified&&state.accounting.runtime_reports_no_positions){note(parent,'The runtime reports no positions. Recorded trade history is waiting to catch up.','snapshot-label');}
    if(!state.positions.length){note(parent,inventoryVerified?'No open positions':'Current inventory unavailable in the trade projection','empty');if(inventoryVerified)note(parent,'Flat is a valid state. Waiting reason: '+readable(state.interpretation.pilot.reason));return;}
    const displayedPositions=[...state.positions].sort((a,b)=>Number(b.ticker===currentTicker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts)-Number(a.ticker===currentTicker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts));
    displayedPositions.forEach(p=>{
      const n=el('article',null,'position-card'),h=el('div',null,'position-header');
      const side=el('span',p.side,'side-label '+(p.side==='YES'?'yes-text':'no-text'));side.append(el('span','#'+p.trade_id,'trade-number'));
      const inspect=el('button','Inspect');inspect.title='Review this position without placing an order';inspect.onclick=()=>selectTrade(p);h.append(side,inspect);n.append(h);
      const valid=inventoryVerified&&currentMark(p);
      const last=p.last_verified_mark||{};
      const shownPnl=valid?p.open_pnl:(finite(p.display_pnl)?p.display_pnl:last.pnl);
      const shownRoi=valid?p.open_roi:(finite(p.display_roi)?p.display_roi:last.roi);
      const shownBid=valid?p.current_bid:(finite(p.display_bid)?p.display_bid:last.bid);
      const pnlText=finite(shownPnl)?money(shownPnl)+' · '+pct(shownRoi):(valid?'$0.00 · —':'Mark unavailable');
      const pnl=el('div',pnlText,'position-value');positive(pnl,shownPnl);n.append(pnl);
      const remaining=p.remaining_qty??p.qty;
      const maximumRoi=finite(p.maximum_roi_pct)?p.maximum_roi_pct:finite(p.entry_ask)&&p.entry_ask>0?(1/p.entry_ask-1)*100:null;
      const maximumGross=finite(p.maximum_gross_profit)?p.maximum_gross_profit:finite(p.entry_ask)&&finite(remaining)?(1-p.entry_ask)*remaining:null;
      const maxWin=finite(maximumRoi)||finite(maximumGross)?pct(maximumRoi)+' · '+money(maximumGross):'—';
      grid(n,[['ENTRY',quote(p.entry_ask)],['FULL-LOT BID',finite(shownBid)?quote(shownBid):'—'],['CONTRACTS',price(p.remaining_qty??p.qty,0)],['MAX @ $1',maxWin]]);
      if(!valid&&finite(shownBid))note(n,'STALE · '+(finite(p.mark_age_seconds)?Math.max(0,p.mark_age_seconds).toFixed(0)+'s':'age unknown')+' · LAST VERIFIED MARK','warning-note');
      if(p.partial_exits>0)note(n,`Partially sold · ${price(p.original_qty??p.qty,0)} originally · ${money(p.partial_realized)} realized gross`);
      if(!inventoryVerified){
        note(n,'LAST RECORDED ENTRY · CURRENT POSITION / SETTLEMENT STATUS UNKNOWN','warning-note');
      }else if(p.ticker!==currentTicker){
        note(n,'EXPIRED CONTRACT · AWAITING VERIFIED SETTLEMENT · NOT CURRENTLY TRADABLE','warning-note');
      }else if(finite(state?.market?.close_ts)&&state.market.close_ts<=backendNow()){
        note(n,'CONTRACT CLOCK ENDED · SETTLEMENT VERIFICATION PENDING','warning-note');
      }
      note(n,readable(p.role)+' · '+p.state);
      note(n,'Depth-swept full-lot mark before exit fees. MAX @ $1 is theoretical gross.','snapshot-label');
      note(n,p.ticker);
      parent.append(n);
    });
  }
  function renderProtection(){
    const parent=$('protection');clear(parent);if(!state)return;
    const active=state.positions.find(x=>x.ticker===state.market.ticker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts);
    const p=state.positions.find(x=>x.key===selectedKey)||(!selectedKey?(active||state.positions[0]):null);
    const selected=state.trades.find(t=>t.key===selectedKey);
    const record=p?.protection||(selected?.evidence||[]).filter(e=>e.event==='POSITION').at(-1);
    if(!record){note(parent,'No engine-reported floor in the available command window.','empty');note(parent,'A missing floor is not proof that protection is disabled. Nautilus never sets or changes it.');return;}
    const live=!!p&&p.inventory_verified!==false&&monitorFresh()&&record.fresh;
    const validMark=currentMark(p);
    note(parent,(p||selected).side+' #'+(p||selected).trade_id+' · '+(live?'CURRENT RECORD':'HISTORICAL RECORD'),'snapshot-label');
    grid(parent,[['PEAK BID',quote(record.peak_bid)],['FLOOR BID',finite(record.stop_bid)?quote(record.stop_bid):'Not armed'],['FULL-LOT BID',validMark?quote(p.current_bid):'—']]);
    if(finite(record.peak_bid)&&finite(record.stop_bid)&&record.peak_bid>0){const scale=el('div',null,'protection-scale'),fill=el('span',null,'fill'),pin=el('span',null,'floor-pin');fill.style.width=(validMark?Math.max(0,Math.min(1,p.current_bid))*100:0)+'%';pin.style.left=(Math.max(0,Math.min(1,record.stop_bid))*100)+'%';scale.append(fill,pin);parent.append(scale);}
    row(parent,'Recorded',clock(record.time)+' ET');
    row(parent,'Reason',record.reason);
    if(validMark&&finite(record.peak_bid)&&record.peak_bid>0)row(parent,'Bid giveback',pct((record.peak_bid-p.current_bid)/record.peak_bid*100));
    note(parent,live?'Engine report only. This viewer cannot arm or enforce protection.':'Not an active guarantee. Current protection status is unavailable.','warning-note');
  }
  function renderDetails(){
    const parent=$('details');clear(parent);if(!state)return;
    const t=state.trades.find(x=>x.key===selectedKey);
    document.querySelector('.intelligence-rail').classList.toggle('reviewing',!!t);
    $('detailsTitle').textContent=t?'Trade #'+t.trade_id+' · '+t.side:'Tool Rack briefing';
    $('detailsBadge').textContent=t?'REVIEW':'RECORDED';
    if(t){
      note(parent,t.exit_ts?'CLOSED POSITION':t.inventory_verified===false?'LAST RECORDED / STATUS UNKNOWN':'OPEN / UNRESOLVED','state-title');
      grid(parent,[['ENTRY',quote(t.entry_ask)],['EXIT',quote(t.exit_bid)],['PAPER NET',money(t.net_pnl)],['PAPER GROSS',money(t.pnl)]]);
      row(parent,'Modeled fees',finite(t.fees_paid)?'$'+price(t.fees_paid):'See committed ledger');
      if(t.exit_type)row(parent,'Exit type',t.exit_type);
      grid(parent,[['GROSS RETURN',pct(t.roi)],['CONTRACTS',price(t.original_qty??t.qty,0)]]);
      row(parent,'Entry',clock(t.entry_ts)+' ET');row(parent,'Exit',t.exit_ts?clock(t.exit_ts)+' ET':'Not closed in this ledger');
      row(parent,'Entry cost',finite(t.cost)?'$'+price(t.cost):'Not recorded');
      note(parent,'ENTRY EVIDENCE','evidence-title');note(parent,t.entry_reason);
      note(parent,'EXIT EVIDENCE','evidence-title');note(parent,t.exit_reason);
      row(parent,'Mission',t.intent||t.role);row(parent,'Contract',t.ticker);
      if(t.evidence?.length){const last=t.evidence.at(-1);note(parent,'LAST MATCHED COMMAND · '+clock(last.time)+' ET','evidence-title');note(parent,(last.event||'')+' · '+(last.reason||'Not recorded'));}
      else note(parent,'No matching command explanation in the loaded window. No retrospective explanation is substituted.','snapshot-label');
    }else{
      const m=state.market,tr=state.tool_rack||{},p=state.interpretation.pilot||{},bp=state.interpretation.battle_plan||{};
      note(parent,'CURRENT TOOL RACK RECORD','state-title');
      row(parent,'Owned territory',readable(tr.owned_territory)+(tr.owned_side?' · '+tr.owned_side:''));
      row(parent,'Primary tool',tr.active_tool||'NONE');
      row(parent,'Overlays',(tr.active_overlays||[]).join(' + ')||'NONE');
      row(parent,'Commander',tr.commander_action||p.action||'WAIT');
      row(parent,'Reason',tr.commander_reason||p.reason||tr.ownership_reason);
      row(parent,'Ownership',tr.ownership_reason);
      for(const [key,label]of [['current_leg','Current leg'],['recent_comparison','Comparison'],['expected_next','Tool expectation'],['entry_plan','Entry plan'],['change_condition','Change condition']]){
        if(bp[key]!=null)row(parent,label,bp[key]);
      }
      note(parent,'Source '+clock(bp.source_ts||m.time)+' ET · recorded tool state. This viewer has no trading authority.','snapshot-label');
    }
    const nav=$('navigator');clear(nav);
    note(nav,'DIRECT MARKET DATA','state-title');
    note(nav,'Coinbase BTC trades provide physical observations and EMA values. The Kalshi native order book provides exact-contract quotes.');
    for(const [key,label]of [['price','BTC observations'],['quotes','Native order book'],['physical','Physical geometry'],['commander','Commander']]){
      const h=state.health?.[key]||{};row(nav,label,h.status||'UNAVAILABLE');if(h.reason)note(nav,h.reason,'snapshot-label');
    }
    note(nav,'ADVISORY AI / NAVIGATOR · NOT RUNNING','evidence-title');
    note(nav,'This package publishes the Tool Rack decision and trade feed directly. No AI critic, Observer42 or separate Navigator process is started.');
  }
  function renderTable(){
    const parent=$('tableArea'),savedScroll={top:parent.scrollTop,left:parent.scrollLeft};clear(parent);if(!state)return;
    if(tab==='health'){renderHealth(parent);return;}
    const table=el('table'),head=el('thead'),hr=el('tr');
    const headers=tab==='trades'?['# / ET','SIDE','ENTRY','EXIT','NET P&L','GROSS P&L']:['TIME · ET','EVENT','SIDE','REASON'];headers.forEach(h=>hr.append(el('th',h)));head.append(hr);table.append(head);const body=el('tbody');
    const rows=tab==='trades'?[...state.trades].reverse():[...state.commands].reverse().slice(0,250);
    rows.forEach(t=>{const tr=el('tr');if(t.key===selectedKey)tr.className='selected';
      const values=tab==='trades'?['#'+t.trade_id+'  '+clock(t.entry_ts,false),t.side,quote(t.entry_ask),t.exit_ts?quote(t.exit_bid):t.inventory_verified===false?'UNKNOWN':'OPEN',money(t.net_pnl),money(t.pnl)]:[clock(t.time),t.event,t.side,t.reason];
      values.forEach((v,i)=>{const td=el('td',v);if((tab==='trades'&&i===1)||(tab==='decisions'&&i===2))td.className=t.side==='YES'?'yes-text':'no-text';if(tab==='trades'&&i===4)positive(td,t.net_pnl);if(tab==='trades'&&i===5)positive(td,t.pnl);if(tab==='decisions'&&i===3){td.className='reason';td.title=readable(v);}tr.append(td);});
      const target=tab==='trades'?t:state.trades.find(x=>x.key===t.key);
      if(target){tr.tabIndex=0;tr.setAttribute('aria-label','Inspect '+target.side+' trade '+target.trade_id);tr.onclick=()=>selectTrade(target);tr.onkeydown=e=>{if(e.key==='Enter')selectTrade(target);};}
      body.append(tr);
    });table.append(body);parent.append(table);parent.scrollTop=savedScroll.top;parent.scrollLeft=savedScroll.left;if(!rows.length)note(parent,'No recorded '+(tab==='trades'?'trades':'commands in the loaded window')+'.','empty');
  }
  function renderHealth(parent){
    clear(parent);if(!state){note(parent,'No response from local adapter.','empty');return;}
    const wrap=el('div',null,'health-list');
    row(wrap,'App','Nautilus '+state.version+' · read only');row(wrap,'Run',state.run.name);row(wrap,'Build',state.run.version);row(wrap,'Session',state.run.session_id);row(wrap,'Pinned commit',state.run.source_commit);row(wrap,'Updated',clock(state.run.updated)+' ET');
    note(wrap,state.accounting.basis,'snapshot-label');
    row(wrap,'PAPER cash','$'+price(state.accounting.cash));row(wrap,'Gross P&L',money(state.accounting.realized));row(wrap,'Modeled fees','$'+price(state.accounting.fees_paid));row(wrap,'Net P&L',money(state.accounting.realized_net));
    for(const [name,detail]of Object.entries(state.health||{}))row(wrap,name.toUpperCase(),detail);
    row(wrap,'Contract clock',state.clock);row(wrap,'Freshness timing',state.diagnostics.freshness_check);row(wrap,'Candle history',{...state.history});
    row(wrap,'Health receipt',state.diagnostics.health_receipt||'Disabled');note(wrap,state.diagnostics.candle_note);note(wrap,state.diagnostics.ema_note);note(wrap,state.diagnostics.command_window);
    if(state.diagnostics.storage){row(wrap,'Long-run storage',state.diagnostics.storage.run_root+' · '+state.diagnostics.storage.free_gib+' GiB free · '+readable(state.diagnostics.storage.policy));}
    for(const [name,r] of Object.entries(state.diagnostics.readers||{}))row(wrap,name,r.file+' · '+(r.present===false?'NOT PRESENT':r.tail_limited?'bounded tail':'full initial window')+' · '+r.lag_bytes+' bytes behind · '+(r.malformed_rows_skipped||0)+' malformed rows skipped');
    for(const issue of state.diagnostics.issues)note(wrap,issue,'warning-note');
    if(!state.diagnostics.issues.length)note(wrap,'No adapter identity/accounting issues reported. This is not a strategy or execution-quality assessment.');
    parent.append(wrap);
  }
  function setFeedPause(value){feedPaused=value;$('pauseFeed').textContent=value?'Resume scroll':'Pause scroll';$('pauseFeed').setAttribute('aria-pressed',String(value));if(!value){feedSignature='';renderFeed();}}
  $('pauseFeed').onclick=()=>setFeedPause(!feedPaused);
  $('feedFilter').onchange=()=>{feedSignature='';renderFeed(true);};
  $('engineFeed').addEventListener('wheel',e=>{if(e.deltaY<0)setFeedPause(true);},{passive:true});
  $('engineFeed').addEventListener('pointerdown',()=>{userFeedScrollUntil=performance.now()+10000;});
  $('engineFeed').addEventListener('keydown',e=>{if(['ArrowUp','PageUp','Home'].includes(e.key))setFeedPause(true);});
  $('engineFeed').addEventListener('scroll',()=>{if(performance.now()<userFeedScrollUntil&&!programmaticScroll&&!feedPaused){const p=$('engineFeed');if(p.scrollHeight-p.clientHeight-p.scrollTop>45)setFeedPause(true);}},{passive:true});
  function renderFeed(force=false){
    if(!state)return;
    const lines=state.feed||[],last=lines.at(-1)?.id;
    const shownIndex=lines.findIndex(l=>l.id===feedShownId);
    pendingFeed=last===feedShownId?0:shownIndex<0?lines.length:lines.length-shownIndex-1;
    $('newLines').textContent=feedPaused?(pendingFeed+' new · scroll paused'):'';
    if(feedPaused&&!force)return;
    const filter=$('feedFilter').value;
    const shown=lines.filter(l=>filter==='all'||(filter==='important'?l.category!=='info':['trade','protection','warning'].includes(l.category)));
    const signature=[filter,shown.length,shown.at(-1)?.id].join('|');if(signature===feedSignature)return;feedSignature=signature;
    const parent=$('engineFeed'),oldScroll=parent.scrollTop;programmaticScroll=true;
    const frag=document.createDocumentFragment();shown.forEach(l=>frag.append(el('div',(finite(l.time)?clock(l.time)+' ET · ':'')+l.text,'feed-line '+l.category)));parent.replaceChildren(frag);
    if(!shown.length)note(parent,lines.length?'No lines match this filter.':'Waiting for recorded Tool Rack decisions and trade events.','empty');
    parent.scrollTop=feedPaused?oldScroll:parent.scrollHeight;feedShownId=last;
    requestAnimationFrame(()=>{programmaticScroll=false;});
  }
  function disconnected(message){online=false;renderConnection();$('errorBanner').textContent=message;$('errorBanner').classList.remove('hidden');if(state){renderTop();renderToolRack();renderPositions();renderProtection();}}
  async function poll(){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);
    try{
      const response=await fetch('/api/nautilus',{signal:controller.signal,cache:'no-store'});
      if(!response.ok)throw new Error('Local reader returned HTTP '+response.status);
      const next=await response.json();
      if(next==null){online=false;$('connection').textContent='CONNECTING';$('connection').className='badge muted';$('sourceStatus').textContent='Waiting for the first Tool Rack observation';$('errorBanner').classList.add('hidden');return;}
      if(next.error)throw new Error(next.error);
      if(next.mode!=='PAPER_ONLY'||next.readonly!==true||!Array.isArray(next.candles)||!finite(next.server_now))throw new Error('Unsupported telemetry identity');
      const changedRun=state?.run?.name!==next.run?.name;
      if(changedRun||!finite(clockAnchorWall)||next.server_now!==clockAnchorWall){clockAnchorWall=next.server_now;clockAnchorMono=performance.now();}
      state=next;receivedAt=performance.now();online=true;
      const major=next.run.pointer_changed?'Run pointer changed. This window remains pinned to '+next.run.name+'. Restart Nautilus to attach a new run.':next.accounting.issues.length?'Accounting verification is paused: '+next.accounting.issues.join('; '):'';
      $('errorBanner').textContent=major;$('errorBanner').classList.toggle('hidden',!major);
      chart.setData(state);if(selectedKey)chart.selected=state.trades.find(t=>t.key===selectedKey)||null;
      renderTop();renderToolRack();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();if($('healthDialog').open)renderHealth($('healthContent'));
      window.__nautilus.state=state;
    }catch(error){disconnected('FEED DISCONNECTED — current quotes and marks are withheld. '+error.message);}
    finally{clearTimeout(timeout);setTimeout(poll,1000);}
  }
  window.__nautilus={chart,getState:()=>state,state:null};
  setInterval(tick,250);poll();
})();
