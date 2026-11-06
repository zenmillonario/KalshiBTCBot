/* Read-only browser workspace. Untrusted engine text is rendered with textContent. */
'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const price=(v,d=2)=>finite(v)?v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const money=v=>finite(v)?(v<0?'−':v>0?'+':'')+'$'+price(Math.abs(v)):'—';
  const pct=v=>finite(v)?(v>0?'+':'')+v.toFixed(2)+'%':'—';
  const netPct=t=>finite(t.exit_ts)?pct(t.net_roi):t.inventory_verified===false?'UNKNOWN':'OPEN';
  const netReturnNote='NET % is realized net P&L after fees, divided by original entry cost plus entry fee. Available after the whole position closes or settles.';
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
  let lookingGlassState='',missionState='';
  let feedPaused=false, feedShownId=null, feedSignature='', pendingFeed=0, programmaticScroll=false, userFeedScrollUntil=0;
  const chart=new NautilusChart($('marketChart'),$('chartTooltip'),trade=>selectTrade(trade));
  // A responsive HTTP server does not make an unchanged engine snapshot fresh.
  const backendNow=()=>finite(clockAnchorWall)?clockAnchorWall+(performance.now()-clockAnchorMono)/1000:NaN;
  const connected=()=>online&&receivedAt>0&&performance.now()-receivedAt<5500;
  const monitorFresh=()=>connected()&&state?.run?.fresh&&!state.run.stopped&&finite(state.run.updated)&&backendNow()>=state.run.updated&&backendNow()-state.run.updated<=5;
  const missionCurrent=()=>monitorFresh()&&state?.mission_context?.current===true&&finite(state.mission_context.valid_until)&&backendNow()<=state.mission_context.valid_until;
  const quoteFresh=()=>monitorFresh()&&state.quote?.fresh&&state.quote.ticker===state.market?.ticker&&finite(state.quote.valid_until)&&backendNow()<=state.quote.valid_until;
  const lastQuote=()=>state.quote?.last_verified?.ticker===state.market?.ticker?state.quote.last_verified:{};
  const currentMark=p=>monitorFresh()&&p?.mark_valid&&p.ticker===state.market?.ticker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts&&finite(p.valid_until)&&backendNow()<=p.valid_until;
  chart.sourceClock=backendNow;chart.sourceConnected=connected;
  function syncModes(){ $('liveMode').classList.toggle('active',mode==='monitor');$('reviewMode').classList.toggle('active',mode==='review');chart.reviewMode=mode==='review';renderLookingGlassStatus();chart.requestDraw(); }
  function selectTrade(trade){selectedKey=trade.key;mode='review';chart.inspect(trade);syncModes();renderDetails();renderTable();document.dispatchEvent(new CustomEvent('nautilus:trade-selected',{detail:{key:trade.key}}));}
  function monitor(){mode='monitor';selectedKey=null;chart.selected=null;chart.toLive();syncModes();renderDetails();renderTable();document.dispatchEvent(new Event('nautilus:monitor'));}
  $('liveMode').onclick=monitor;
  $('reviewMode').onclick=()=>{mode='review';chart.freezeViewport();syncModes();const t=state?.trades?.find(t=>t.key===selectedKey)||state?.trades?.at(-1);if(t)selectTrade(t);else renderDetails();};
  $('liveEdge').onclick=()=>{chart.toLive();};
  $('spanSelect').value=String(chart.span/60);
  $('spanSelect').onchange=e=>chart.setSpan(Number(e.target.value)*60);
  $('targetToggle').onclick=()=>{chart.fitTarget=!chart.fitTarget;$('targetToggle').setAttribute('aria-pressed',String(chart.fitTarget));chart.requestDraw();};
  $('lookingGlassToggle').setAttribute('aria-pressed',String(chart.showLookingGlass));
  $('lookingGlassToggle').onclick=()=>{chart.setLookingGlass(!chart.showLookingGlass);renderLookingGlassStatus();renderDetails();};
  $('fullChart').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else $('chartPanel').requestFullscreen().catch(()=>{});};
  chart.onViewport=({follow,span})=>{
    $('liveEdge').textContent=mode==='review'?(follow?'Latest chart · Review':'Latest chart →'):follow?(state?.run?.stopped?'Latest recorded ✓':'Following live ✓'):'Return to Live →';
    $('liveEdge').classList.toggle('active',follow);
    const match=[...$('spanSelect').options].some(o=>Number(o.value)*60===span);
    if(match)$('spanSelect').value=String(span/60);
    else {let o=$('spanSelect').querySelector('[data-custom]');if(!o){o=el('option');o.dataset.custom='true';$('spanSelect').append(o);}o.value=String(span/60);o.textContent=(span/60).toFixed(0)+'m · custom zoom';$('spanSelect').value=o.value;}
  };
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));renderTable();});
  $('healthButton').onclick=()=>{renderHealth($('healthContent'));$('healthDialog').showModal();};
  $('closeHealth').onclick=()=>$('healthDialog').close();
  $('healthDialog').onclick=e=>{if(e.target===$('healthDialog'))$('healthDialog').close();};
  function renderQuotes(){
    if(!state)return;
    const q=state.quote||{},fresh=quoteFresh(),last=lastQuote(),shown=fresh?q:last;
    const age=finite(last.verified_at)?Math.max(0,backendNow()-last.verified_at):q.last_verified_age_seconds;
    const ageLabel=finite(age)?Math.max(0,age).toFixed(0)+'s':null;
    const exchangeNote=finite(q.exchange_age_sec)?' · exchange age at capture '+Math.max(0,q.exchange_age_sec).toFixed(0)+'s':'';
    const provenance='Native bid / ask · '+(q.source||'source unavailable')+' · '+(q.ticker||state.market?.ticker||'contract unavailable')+exchangeNote;
    for(const [side,statusId]of [['yes','quoteSource'],['no','quoteSourceNo']]){
      const bid=shown[side+'_bid'],ask=shown[side+'_ask'],available=finite(bid)||finite(ask);
      const status=fresh&&available?'CURRENT':available?'STALE'+(ageLabel?' · '+ageLabel:''):'NO QUOTE';
      $(side+'Bid').textContent=quote(bid);$(side+'Ask').textContent=quote(ask);
      const card=$(side+'Quote').closest('.quote-card');
      card.dataset.quoteState=fresh&&available?'current':available?'stale':'unavailable';
      card.title=provenance+' · '+status+(fresh?'':' · last verified values · '+(q.reason||'awaiting fresh data'));
      $(statusId).textContent=status;$(statusId).title=card.title;
    }
  }
  function renderTop(){
    if(!state)return;
    const m=state.market||{},r=state.run||{},a=state.accounting||{};
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
    renderQuotes();
    $('realizedValue').textContent=money(a.realized_net);positive($('realizedValue'),a.realized_net);
    $('recordSummary').textContent=(a.realized_stale?'LAST VERIFIED · STALE · ':'')+'Gross '+money(a.realized)+' · total fees paid $'+price(a.fees_paid)+' · '+(a.closed??0)+' closed';
    $('recordSummary').title=(a.realized_stale?'Recorded ledger snapshot. ':'')+'Realized net includes allocated entry and exit model fees for realized contracts. Total fees paid also includes entry fees on open positions.';
    $('runIdentity').textContent=[r.build,r.name,'PID '+(r.pid??'—')].filter(Boolean).join('  ·  ');
    $('runIdentity').title='Pinned run '+(r.name||'unavailable');
    $('sourceStatus').textContent=(r.review?'ARCHIVE':r.stopped?'ENGINE STOPPED':monitorFresh()?(r.status==='DRAINING'?'ENTRY WINDOW CLOSED · HELD STRATEGY CONTINUES':r.status==='STOPPING'?'MANUAL STOP · FLATTENING':'RUNTIME CURRENT'):'RUNTIME STALE')+' · PINNED SOURCE';
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
    b.textContent=!connected()?'DISCONNECTED':state?.run.review?'ARCHIVE':state?.run.stopped?'STOPPED':monitorFresh()?(state?.run.status==='DRAINING'?'DRAINING':state?.run.status==='STOPPING'?'STOPPING':'FEED CONNECTED'):'STALE';
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
    const now=backendNow();
    const timer=NautilusReliability.timer(state,now,connected());
    $('timerValue').textContent=timer.text;
    $('timerProgress').style.width=timer.running?Math.max(0,Math.min(100,(900-timer.seconds)/9))+'%':'0%';
    document.querySelector('.clock').classList.toggle('urgent',timer.running&&timer.seconds<=120);
    $('closeLabel').textContent=finite(timer.close)?'CLOSE '+clock(timer.close,false)+' ET'+(timer.running?(timer.seconds===0?' · awaiting new contract':' · verified contract clock'):' · timer paused'):'Contract close not verified';
    $('closeLabel').title='Local system clock checked for monotonic continuity; absolute exchange clock offset is not measured.';
    const priceFresh=monitorFresh()&&state.market.fresh&&finite(state.market.time)&&now-state.market.time>=-2&&now-state.market.time<=3;
    document.querySelector('.instrument.now').classList.toggle('paused-price',!priceFresh);
    if(!priceFresh)$('priceAge').textContent='· LAST RECORDED'+(finite(state.market.time)?' · '+Math.max(0,now-state.market.time).toFixed(0)+'s':'');
    if(!quoteFresh())renderQuotes();
    if(!connected()&&online){online=false;renderConnection();$('priceAge').textContent='· CONNECTION LOST';renderPositions();}
    const freshness=String(monitorFresh())+'|'+String(missionCurrent())+'|'+state.positions.map(p=>[p.key,currentMark(p)].join(':')).join('|');
    if(freshness!==positionFreshness){positionFreshness=freshness;renderPositions();}
    const missionFreshness=String(missionCurrent());
    if(missionFreshness!==missionState){missionState=missionFreshness;renderDetails();}
    if(renderLookingGlassStatus())renderDetails();
    renderConnection();renderComponentHealth();
  }
  function renderLookingGlassStatus(){
    const view=chart.scenarioView(),glass=state?.looking_glass,ready=view.paths.length>0;
    const summary=$('lookingGlassStatus'),bar=$('lookingGlassBar');
    $('lookingGlassToggle').setAttribute('aria-pressed',String(chart.showLookingGlass));
    const side=glass?.thesis?.side;
    const active=view.active;
    summary.textContent=ready?(active?active.label+' · conditional to '+clock(active.horizon_ts,false):
      glass?.active_pattern?.kind?'Active shape unavailable · '+glass.active_pattern.label:
      (side==='YES'||side==='NO'?side+' scenario bias':side==='MIXED'?'Mixed paths':'Scenario direction uncertain'))+
      ' · '+clock(glass.close_ts,false)+' close':view.reason;
    summary.title=ready?(active?active.reason:glass?.active_pattern?.reason||'Conditional scenario comparisons')+' Brightness identifies the active pattern, not confidence or an instruction to trade.':view.reason;
    bar.dataset.state=ready?'ready':view.status.toLowerCase();
    bar.dataset.featured=String(Boolean(active));
    $('lookingGlassLegend').classList.toggle('hidden',!ready);
    $('lookingGlassActive').classList.toggle('hidden',!active);
    $('lookingGlassIssued').classList.toggle('hidden',!view.issued);
    if(view.issued)$('lookingGlassIssued').textContent='Issued '+clock(view.issued.issued_at_ts,false)+' · fixed';
    for(const [family,selector] of [['CONTINUATION','.glass-continuation'],['ROTATION_STALL','.glass-rotation'],['REVERSAL','.glass-reversal']])
      $('lookingGlassLegend').querySelector(selector).classList.toggle('hidden',!view.paths.some(path=>path.family===family));
    const signature=[view.status,chart.showLookingGlass,mode,ready,active?.key,view.issued?.id].join('|'),changed=signature!==lookingGlassState;
    if(changed){lookingGlassState=signature;if(chart.follow)chart.syncLiveViewport();chart.requestDraw();}
    return changed;
  }
  function renderLookingGlass(parent){
    const glass=state?.looking_glass,view=chart.scenarioView({ignorePreference:true,ignoreViewport:true});
    const block=el('section',null,'looking-glass-briefing');block.id='lookingGlassBriefing';
    const heading=el('div',null,'glass-heading');heading.append(el('h3','Looking Glass'),el('span','OBSERVATION ONLY','badge'));block.append(heading);
    if(mode==='review'){
      note(block,'Live scenarios are hidden in review. No forecast recorded at this trade’s entry is supplied.','context-note');parent.append(block);return;
    }
    if(!glass){note(block,'Waiting for enough continuous price and EMA history.','context-note');parent.append(block);return;}
    const usable=['READY','PARTIAL'].includes(view.status)&&view.paths.length>0;
    if(usable){
      const active=view.active;
      note(block,'ACTIVE PATTERN','evidence-title');
      note(block,active?active.label:glass.active_pattern?.label||'Active pattern unavailable','glass-pattern-title');
      note(block,active?active.reason:glass.active_pattern?.reason||'No comparable current pattern path is available.','context-note');
      if(active){
        row(block,'Path through',clock(active.horizon_ts,false)+' ET'+(active.horizon_ts<glass.close_ts?' · historical shape ends':' · current contract close'));
        row(block,'Local territory',readable(active.local_context));
        if(active.mirrored)note(block,'The historical shape is mirrored into the current leg’s direction; its timing and size are unchanged.','context-note');
        note(block,'Bright green marks the current pattern’s conditional continuation. Dimmer paths are alternative outcomes, not lower probability forecasts.','context-note');
      }
      if(view.issued)row(block,'Fixed comparison','Issued '+clock(view.issued.issued_at_ts,true)+' ET · its points have not been redrawn');
      note(block,'The first pattern path issued for this contract is kept while this process runs. The pale dotted trace lets you compare it with later candles. Restarting the engine clears these display samples.','context-note');
    }
    note(block,usable?'SCENARIO DIRECTION':'SCENARIO DIRECTION · '+(view.status==='STALE'?'STALE':'UNAVAILABLE'),'evidence-title');
    const side=usable?glass.thesis?.side:'UNKNOWN';
    note(block,side==='YES'?'YES · scenario bias':side==='NO'?'NO · scenario bias':side==='MIXED'?'Mixed · no single side established':'No scenario direction established','glass-thesis'+(side==='YES'?' yes-text':side==='NO'?' no-text':''));
    note(block,usable?readable(glass.thesis?.reason).replaceAll('_',' '):view.reason,'context-note');
    if(usable){
      const observed=glass.observations||{},reference=glass.reference_window||{},timing=glass.timing||{};
      const count=Array.isArray(reference.completed_prior_contracts)?reference.completed_prior_contracts.length:reference.completed_prior_contracts;
      const history=(finite(reference.observed_seconds)?(reference.observed_seconds/60).toFixed(1)+' minutes observed':'Coverage unavailable')+
        (finite(count)?' · '+count+' prior contract'+(count===1?'':'s'):'');
      row(block,'History',history);
      if(observed.ema9_direction)row(block,'EMA9',String(observed.ema9_direction).replaceAll('_',' ')+(finite(observed.ema9_slope_per_min)?' · $'+price(observed.ema9_slope_per_min)+'/min':''));
      const continuation=glass.thesis?.continuation_side;
      row(block,'If continued',continuation==='YES'?'YES · conditional endpoints above the current target':
        continuation==='NO'?'NO · conditional endpoints below the current target':
        continuation==='MIXED'?'Mixed · continuation endpoints do not agree on one side':
        continuation==='AT_TARGET'?'At the current target · no side implied':
        'No supported continuation result');
      if(observed.regime)row(block,'Recent motion',String(observed.regime).replaceAll('_',' '));
      if(timing.reason)row(block,'Entry timing',String(timing.reason).replaceAll('_',' '));
      note(block,'The paths are conditional comparisons through '+clock(glass.close_ts,false)+' ET. They are not win probabilities or official settlement values.','context-note');
      if(glass.status==='PARTIAL'&&reference.coverage==='PARTIAL')note(block,'Partial history · missing intervals are not filled.','warning-note');
    }
    const swing=glass.swing_review||{},threshold=swing.minimum_gross_roi;
    note(block,'SEPARATE SWING REVIEW','evidence-title');
    note(block,finite(threshold)?'Minimum review level · '+price(threshold*100,0)+'% gross return on entry':'Swing review level unavailable','glass-swing-title');
    note(block,'A screening reference before fees; it is not a take-profit or an instruction to sell.','context-note');
    const cards=el('div',null,'glass-swing-grid');
    for(const key of ['YES','NO']){
      const evidence=swing.sides?.[key]||{},card=el('div',null,'glass-swing-card');
      note(card,key,key==='YES'?'yes-text':'no-text');
      const quoteCurrent=quoteFresh()&&glass.ticker===state.market?.ticker&&finite(evidence.entry_ask)&&
        evidence.entry_ask===state.quote?.[key.toLowerCase()+'_ask'];
      row(card,'Ask now',quoteCurrent?quote(evidence.entry_ask):'Unavailable');
      row(card,'Review bid',quoteCurrent&&evidence.status!=='TARGET_ABOVE_ONE'?quote(evidence.required_exit_bid):'Unavailable');
      note(card,!quoteCurrent?'Current quote required':evidence.status==='TARGET_ABOVE_ONE'?'Required bid exceeds $1':
        'Future swing unassessed · depth, fees and the physical return still need review','snapshot-label');
      const prior=evidence.historical_excursion;
      if(prior&&finite(prior.gross_roi))note(card,'Observed earlier: '+price(prior.gross_roi*100,1)+'% gross · historical quotes, not future capacity','context-note');
      cards.append(card);
    }
    block.append(cards);note(block,'Source '+clock(glass.source_ts)+' ET · no entry, exit or veto authority.','snapshot-label');parent.append(block);
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
  const missionPurpose=value=>value==='MAIN_CONTRACT'?'Main contract':value==='ARC_RETURN'?'Mountain return leg':value==='TACTICAL_RETURN'?'Tactical return':'Purpose unavailable';
  const missionText=value=>typeof value==='string'&&value?value.replaceAll('_',' '):'Unavailable';
  function destinationText(mission){
    const destination=mission?.destination||{},kind=destination.kind||mission?.target_kind;
    const parts=[];
    if(kind)parts.push(mission?.purpose==='ARC_RETURN'&&kind==='PARENT_TERMINAL'?'Next mountain peak or valley':missionText(kind));
    if(finite(destination.btc))parts.push('BTC $'+price(destination.btc)+(finite(destination.tolerance)?' ± $'+price(destination.tolerance):''));
    return parts.length?parts.join(' · '):'Unavailable';
  }
  function renderPositionMission(parent,position,details=false){
    const mission=position?.mission||{},block=el('div',null,'position-mission');
    note(block,missionPurpose(mission.purpose),'mission-purpose');
    row(block,'Holding destination',destinationText(mission));
    const collection=position?.collection_review;
    if(mission.collection_policy==='THIRD_DISTINCT_WEAKNESS_V1'&&collection?.available){
      const current=position.management_current&&missionCurrent();
      const contractInterruption=collection.collection_authority==='ARC_PROFITABLE_CONTRACT_INTERRUPTION';
      let progress='Awaiting observed leg';
      if(collection.collection_authority==='CONFIRMED_PARENT_END')progress='Confirmed leg end';
      else if(collection.collection_authority==='MATURE_FULL_ARC_HANDOFF')progress='Full arc complete · return leg';
      else if(collection.weakness_proof_valid&&finite(collection.weakness_count)&&finite(collection.weakness_required_count)){
        progress=String(collection.weakness_count)+' / '+String(collection.weakness_required_count)
          +(contractInterruption?' · leg still active':collection.collection_qualified?' · spent leg':' · holding the leg');
      }
      row(block,'Leg weakness',(current?'':'Last observed · ')+progress);
      if(contractInterruption)row(block,'Collection',(current?'':'Last observed · ')+'Profitable return · contract closing');
    }
    if(details){
      row(block,'Parent leg',mission.parent_leg_id||'Unavailable');
      row(block,'Local swing',mission.swing_id||'Unavailable');
      row(block,'Entry mission source',finite(mission.source_ms)?clock(mission.source_ms/1000)+' ET':'Unavailable');
      const economics=position?.tactical_economics;
      if(economics?.available){note(block,'RECORDED ENTRY SWING REVIEW','evidence-title');renderMissionEconomics(block,economics);}
    }else{
      note(block,'Parent '+(mission.parent_leg_id||'unavailable')+' · local '+(mission.swing_id||'unavailable'),'mission-scope');
    }
    parent.append(block);
  }
  function renderMissionEconomics(parent,economics){
    const e=economics||{};
    row(parent,'Engine scenario review',missionText(e.status));
    row(parent,'Entry ask · full lot',finite(e.entry_ask)?quote(e.entry_ask):'Unavailable');
    row(parent,'Required exit bid',finite(e.required_exit_bid)?quote(e.required_exit_bid):'Unavailable');
    row(parent,'Estimated exit bid',finite(e.estimated_exit_bid)?quote(e.estimated_exit_bid):'Unavailable');
    row(parent,'Minimum gross return',finite(e.minimum_gross_roi)?pct(e.minimum_gross_roi*100):'Unavailable');
    row(parent,'Estimated gross return',finite(e.gross_roi)?pct(e.gross_roi*100):'Unavailable');
    row(parent,'Estimated net · proposed lot',finite(e.net_after_fees)?money(e.net_after_fees)+(finite(e.quantity)?' · '+price(e.quantity,0)+' contracts':''):'Unavailable');
    if(e.reason)note(parent,missionText(e.reason),'context-note');
    if(e.estimate_method)row(parent,'Estimate method',missionText(e.estimate_method));
    if(e.uncertainty)note(parent,'Uncertainty · '+readable(e.uncertainty),'context-note');
    note(parent,'Recorded scenario estimate; future exit depth and profit are not established by this display.','snapshot-label');
  }
  function renderEngineMission(parent,compact=false){
    const context=state?.mission_context||{},contract=context.contract||{},leg=context.parent||{};
    const current=missionCurrent(),side=contract.thesis_side,block=el('section',null,compact?'engine-mission-summary':'engine-mission-briefing');
    if(!compact)block.id='engineMissionBriefing';
    block.dataset.state=current?'current':context.available?'recorded':'unavailable';
    const heading=el('div',null,'engine-mission-heading');
    heading.append(el('strong','ENGINE THESIS'),el('span',current?'CURRENT':context.available?'LAST RECORDED':'UNAVAILABLE','badge'));
    block.append(heading);
    note(block,side==='YES'||side==='NO'?side+' · main contract thesis':contract.thesis_status==='MIXED'?'Mixed conditional endpoints':'Contract thesis unavailable','engine-thesis'+(side==='YES'?' yes-text':side==='NO'?' no-text':''));
    const direction=leg.side==='YES'||leg.side==='NO'?leg.side+(leg.direction?' / '+leg.direction:''):'Unavailable';
    const terminal=leg.terminal?.qualified===true?'terminal qualified':leg.terminal?.qualified===false?'terminal not qualified':'terminal unavailable';
    if(compact){
      note(block,'Parent '+direction+' · '+terminal,'mission-scope');
      block.title=missionText(contract.reason)+' · parent '+(leg.id||'unavailable')+' · source '+(finite(context.source_ms)?clock(context.source_ms/1000)+' ET':'unavailable');
    }else{
      row(block,'Engine reason',missionText(contract.reason));
      row(block,'Parent leg',direction+' · '+(leg.id||'ID unavailable'));
      row(block,'Parent terminal',terminal+(leg.terminal?.reason?' · '+missionText(leg.terminal.reason):''));
      const successor=leg.successor;
      row(block,'Successor',successor?.side==='YES'||successor?.side==='NO'?successor.side+' · '+missionText(successor.status)+(successor.id?' · '+successor.id:''):'Unavailable');
      row(block,'Prior contract summaries',finite(contract.prior_contract_count)?String(contract.prior_contract_count):'Unavailable');
      row(block,'History status',missionText(contract.history_status));
      row(block,'Time remaining at source',finite(contract.remaining_seconds)?price(contract.remaining_seconds,0)+'s':'Unavailable');
      row(block,'Engine source',finite(context.source_ms)?clock(context.source_ms/1000)+' ET':'Unavailable');
      note(block,'Engine decision context · the Looking Glass section below shows separate conditional scenarios.','context-note');
      note(block,current?'CANDIDATE ADMISSION REVIEW':'LAST RECORDED CANDIDATE REVIEW','evidence-title');
      const reviews=Array.isArray(state.candidate_review)?state.candidate_review:[];
      if(!reviews.length)note(block,'Candidate review unavailable.','context-note');
      for(const candidate of reviews){
        const card=el('article',null,'mission-candidate');
        note(card,(candidate.side||'Side unavailable')+' · '+missionPurpose(candidate.purpose),'mission-purpose');
        row(card,'Engine decision',missionText(candidate.decision));
        row(card,'Reason',missionText(candidate.reason));
        if(candidate.economics?.available)renderMissionEconomics(card,candidate.economics);
        else if(candidate.purpose==='ARC_RETURN')note(card,'Peak or valley entry · held for the return leg.','context-note');
        else note(card,'Candidate economics unavailable.','context-note');
        block.append(card);
      }
    }
    parent.append(block);
  }
  function renderPositions(){
    const parent=$('positions');clear(parent);
    const currentTicker=state?.market?.ticker;
    const inventoryVerified=state?.accounting?.inventory_verified!==false;
    const active=state?.positions?.filter(p=>p.ticker===currentTicker&&finite(state.market?.close_ts)&&backendNow()<state.market.close_ts).length??0;
    const awaiting=(state?.positions?.length??0)-active;
    $('positionCount').textContent=inventoryVerified?(awaiting?`${active} active · ${awaiting} awaiting`:String(active)):`${state?.positions?.length??0} last recorded`;
    $('positionTitle').textContent=inventoryVerified?'Current positions':'Last recorded positions';
    if(!state)return;
    renderEngineMission(parent,true);
    if(!inventoryVerified){note(parent,'Current inventory and settlement status are not confirmed by this trade projection.','warning-note');}
    if(!inventoryVerified&&state.accounting.runtime_reports_no_positions){note(parent,'The runtime reports no positions. Recorded trade history is waiting to catch up.','snapshot-label');}
    if(!state.positions.length){note(parent,inventoryVerified?'No open positions':'Current inventory unavailable in the trade projection','empty');if(inventoryVerified)note(parent,'Flat is a valid state. Waiting reason: '+readable(state.interpretation.pilot.reason));return;}
    const exposure=(state.contract_exposure||[]).find(row=>row.ticker===currentTicker);
    if(exposure&&exposure.inventory_verified){
      const box=el('div',null,'contract-exposure');
      note(box,inventoryVerified&&monitorFresh()?'CURRENT CONTRACT EXPOSURE':'LAST RECORDED CONTRACT EXPOSURE','evidence-title');
      const net=exposure.net_side==='BALANCED'?'Equal quantities':`Net ${price(exposure.net_qty,0)} ${exposure.net_side}`;
      note(box,`${price(exposure.yes_qty,0)} YES · ${price(exposure.no_qty,0)} NO · ${net}`,'exposure-quantities');
      const roles=state.positions.filter(p=>p.ticker===currentTicker&&['PRIMARY','TACTICAL'].includes(p.position_role)).map(p=>`${p.position_role} ${p.side} #${p.trade_id}`);
      if(roles.length)note(box,roles.join(' · '),'role-overview');
      box.title='Combined quantity in this exact contract. Opposite strategy lots offset directional exposure; cash, costs and fees remain in the ledger.';
      parent.append(box);
    }
    const displayedPositions=[...state.positions].sort((a,b)=>Number(b.ticker===currentTicker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts)-Number(a.ticker===currentTicker&&finite(state.market.close_ts)&&backendNow()<state.market.close_ts));
    displayedPositions.forEach(p=>{
      const n=el('article',null,'position-card'),h=el('div',null,'position-header');
      const side=el('span',p.side,'side-label '+(p.side==='YES'?'yes-text':'no-text'));side.append(el('span','#'+p.trade_id,'trade-number'));
      const inspect=el('button','Inspect');inspect.title='Review this position without placing an order';inspect.onclick=()=>selectTrade(p);h.append(side,inspect);n.append(h);
      if(['PRIMARY','TACTICAL'].includes(p.position_role))note(n,p.position_role,'position-role '+p.position_role.toLowerCase());
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
      renderPositionMission(n,p);
      renderFloorSummary(n,p.protection,inventoryVerified&&monitorFresh()&&p.protection?.fresh);
      if(!valid&&finite(shownBid))note(n,'STALE · '+(finite(p.mark_age_seconds)?Math.max(0,p.mark_age_seconds).toFixed(0)+'s':'age unknown')+' · LAST VERIFIED MARK','warning-note');
      if(p.partial_exits>0)note(n,`Partially sold · ${price(p.original_qty??p.qty,0)} originally · ${money(p.partial_realized)} realized gross`);
      if(!inventoryVerified){
        note(n,'LAST RECORDED ENTRY · CURRENT POSITION / SETTLEMENT STATUS UNKNOWN','warning-note');
      }else if(p.ticker!==currentTicker){
        note(n,'EXPIRED CONTRACT · AWAITING VERIFIED SETTLEMENT · NOT CURRENTLY TRADABLE','warning-note');
      }else if(finite(state?.market?.close_ts)&&state.market.close_ts<=backendNow()){
        note(n,'CONTRACT CLOCK ENDED · SETTLEMENT VERIFICATION PENDING','warning-note');
      }
      note(n,readable(p.manager||p.role)+' · '+p.state);
      const managementLabels={ENTRY_CANDLE_BREATHING:'Holding through entry candle',LIVING_LEG_BREATHING:'Healthy leg · allowing pullbacks',CURRENT_PHYSICAL_COLLECTION:'Terminal or structural break · protection review',AWAIT_CURRENT_PHYSICAL_COLLECTION:'Holding · no current collection signal',PRESERVE_COMMITTED_FLOOR:'Armed protection remains active',BOUNDED_HEIST_COLLECTION:'Box edge · collection review'};
      if(managementLabels[p.profit_protection_state])note(n,(p.management_current&&monitorFresh()?'':'Last management · ')+managementLabels[p.profit_protection_state],'context-note');
      else if(p.management_reason)note(n,(p.management_current&&monitorFresh()?'Management · ':'Last management · ')+missionText(p.management_reason),'context-note');
      if(p.custody_state&&p.custody_state!=='NORMAL')note(n,'CUSTODY · '+readable(p.custody_state).replaceAll('_',' ')+' · '+readable(p.custody_metadata?.reason),p.custody_state==='LAZARUS'?'warning-note':'snapshot-label');
      note(n,'Depth-swept full-lot mark before exit fees. MAX @ $1 is theoretical gross.','snapshot-label');
      note(n,p.ticker);
      parent.append(n);
    });
  }
  function renderFloorSummary(parent,record,current=false){
    if(!record){note(parent,'Engine floor not reported','snapshot-label');return;}
    const summary=el('div',null,'position-protection');
    summary.title='Read-only engine record · '+clock(record.time)+' ET · '+readable(record.reason);
    grid(summary,[['PEAK BID',quote(record.peak_bid)],['ENGINE FLOOR',finite(record.stop_bid)?quote(record.stop_bid):'Not armed']]);
    if(record.armed&&finite(record.protected_peak_bid)&&record.protected_peak_bid!==record.peak_bid)note(summary,'Protection peak '+quote(record.protected_peak_bid),'context-note');
    note(summary,current?'Floor record · current':'Floor record · last recorded',current?'context-note':'warning-note');
    parent.append(summary);
  }
  function renderDetails(){
    const parent=$('details');clear(parent);if(!state)return;
    const t=state.trades.find(x=>x.key===selectedKey);
    document.querySelector('.intelligence-rail').classList.toggle('reviewing',!!t);
    $('detailsTitle').textContent=t?'Trade #'+t.trade_id+' · '+t.side:'Tool Rack briefing';
    $('detailsBadge').textContent=t?'REVIEW':'RECORDED';
    if(t){
      note(parent,t.exit_ts?'CLOSED POSITION':t.inventory_verified===false?'LAST RECORDED / STATUS UNKNOWN':'OPEN / UNRESOLVED','state-title');
      if(['PRIMARY','TACTICAL'].includes(t.position_role))row(parent,'Position role',t.position_role);
      renderPositionMission(parent,t,true);
      grid(parent,[['ENTRY',quote(t.entry_ask)],['EXIT',quote(t.exit_bid)],['PAPER NET',money(t.net_pnl)],['PAPER GROSS',money(t.pnl)]]);
      row(parent,'Modeled fees',finite(t.fees_paid)?'$'+price(t.fees_paid):'See committed ledger');
      if(t.exit_type)row(parent,'Exit type',t.exit_type);
      grid(parent,[['NET %',netPct(t)],['GROSS RETURN',pct(t.roi)],['CONTRACTS',price(t.original_qty??t.qty,0)]]);
      row(parent,'Net return basis',finite(t.net_return_basis)?'$'+price(t.net_return_basis):'Not available');
      note(parent,netReturnNote,'snapshot-label');
      const protection=t.protection||(t.evidence||[]).filter(e=>e.event==='POSITION').at(-1);
      if(protection)renderFloorSummary(parent,protection,false);
      row(parent,'Entry',clock(t.entry_ts)+' ET');row(parent,'Exit',t.exit_ts?clock(t.exit_ts)+' ET':'Not closed in this ledger');
      row(parent,'Entry cost',finite(t.cost)?'$'+price(t.cost):'Not recorded');
      note(parent,'ENTRY EVIDENCE','evidence-title');note(parent,t.entry_reason);
      note(parent,'EXIT EVIDENCE','evidence-title');note(parent,t.exit_reason);
      row(parent,'Entry opportunity',t.intent||'Unavailable');row(parent,'Contract',t.ticker);
      if(t.evidence?.length){const last=t.evidence.at(-1);note(parent,'LAST MATCHED COMMAND · '+clock(last.time)+' ET','evidence-title');note(parent,(last.event||'')+' · '+(last.reason||'Not recorded'));}
      else note(parent,'No matching command explanation in the loaded window. No retrospective explanation is substituted.','snapshot-label');
    }else{
      const m=state.market,tr=state.tool_rack||{},p=state.interpretation.pilot||{},bp=state.interpretation.battle_plan||{};
      renderEngineMission(parent);
      renderLookingGlass(parent);
      const briefs=Array.isArray(tr.briefings)?tr.briefings:[];
      note(parent,'POSITIVE BRIEFINGS','state-title');
      if(briefs.length){
        briefs.slice(0,6).forEach(b=>{
          const line=[b.tool||'ADVISER',(b.state||'PREPARE').replaceAll('_',' '),b.side||''].filter(Boolean).join(' · ');
          note(parent,line,'evidence-title');
          if(finite(b.max_price))row(parent,'Entry value','<= '+quote(b.max_price));
          if(b.reason)note(parent,readable(b.reason),'context-note');
        });
      }else note(parent,'Commander idle · awaiting a positive briefing.','context-note');
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
    row(nav,'Quote source',state.quote?.source||'Unavailable');
    row(nav,'Quote contract',state.quote?.ticker||'Unavailable');
    if(finite(state.quote?.exchange_age_sec))row(nav,'Exchange age at capture',Math.max(0,state.quote.exchange_age_sec).toFixed(0)+'s');
    for(const [key,label]of [['price','BTC observations'],['quotes','Native order book'],['physical','Physical geometry'],['commander','Commander']]){
      const h=state.health?.[key]||{};row(nav,label,h.status||'UNAVAILABLE');if(h.reason)note(nav,h.reason,'snapshot-label');
    }
    note(nav,'NAVIGATOR TERRAIN BRIEFING · EMBEDDED / READ ONLY','evidence-title');
    note(nav,'Navigator now summarizes cross-contract EMA9 parent continuity in the Briefing panel. It cannot enter, exit or veto. No separate Navigator, Observer42 or AI critic process is started.');
    row(nav,'Looking Glass',state.looking_glass?.status||'UNAVAILABLE');
    note(nav,'Looking Glass compares prior observations as conditional paths inside Nautilus. It does not send orders or change Tool Rack decisions.');
  }
  function renderTable(){
    const parent=$('tableArea'),savedScroll={top:parent.scrollTop,left:parent.scrollLeft};clear(parent);if(!state)return;
    if(tab==='health'){renderHealth(parent);return;}
    const table=el('table'),head=el('thead'),hr=el('tr');
    const headers=tab==='trades'?['# / ET','SIDE','ENTRY','EXIT','NET %','NET P&L','GROSS P&L']:['TIME · ET','EVENT','SIDE','REASON'];headers.forEach(h=>{const th=el('th',h);if(h==='NET %')th.title=netReturnNote;hr.append(th);});head.append(hr);table.append(head);const body=el('tbody');
    const rows=tab==='trades'?[...state.trades].reverse():[...state.commands].reverse().slice(0,250);
    rows.forEach(t=>{const tr=el('tr');if(t.key===selectedKey)tr.className='selected';
      const values=tab==='trades'?['#'+t.trade_id+'  '+clock(t.entry_ts,false),t.side,quote(t.entry_ask),t.exit_ts?quote(t.exit_bid):t.inventory_verified===false?'UNKNOWN':'OPEN',netPct(t),money(t.net_pnl),money(t.pnl)]:[clock(t.time),t.event,t.side,t.reason];
      values.forEach((v,i)=>{const td=el('td',v);if((tab==='trades'&&i===1)||(tab==='decisions'&&i===2))td.className=t.side==='YES'?'yes-text':'no-text';if(tab==='trades'&&i===4){positive(td,finite(t.exit_ts)?t.net_roi:null);td.title=netReturnNote;}if(tab==='trades'&&i===5)positive(td,t.net_pnl);if(tab==='trades'&&i===6)positive(td,t.pnl);if(tab==='decisions'&&i===3){td.className='reason';td.title=readable(v);}tr.append(td);});
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
  function disconnected(message){online=false;renderConnection();$('errorBanner').textContent=message;$('errorBanner').classList.remove('hidden');if(state){renderTop();renderToolRack();renderPositions();}}
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
      renderTop();renderToolRack();renderPositions();renderDetails();renderTable();renderFeed();if($('healthDialog').open)renderHealth($('healthContent'));
      window.__nautilus.state=state;
    }catch(error){disconnected('FEED DISCONNECTED — current quotes and marks are withheld. '+error.message);}
    finally{clearTimeout(timeout);setTimeout(poll,1000);}
  }
  window.__nautilus={chart,getState:()=>state,state:null};
  setInterval(tick,250);poll();
})();
