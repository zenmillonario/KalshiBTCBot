/* Read-only browser workspace. Untrusted engine text is rendered with textContent. */
'use strict';
(() => {
  const $=id=>document.getElementById(id), token=document.querySelector('meta[name="nautilus-read"]').content;
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
  const grid=(parent,items)=>{const g=el('div',null,'metric-grid'+(items.length===2?' two':''));items.forEach(([label,value])=>{const n=el('div');n.append(el('label',label),el('strong',value));g.append(n);});parent.append(g);};
  let state=null, selectedKey=null, tab='trades', receivedAt=0, online=false, mode='monitor';
  let feedPaused=false, feedShownId=null, feedSignature='', pendingFeed=0, programmaticScroll=false, userFeedScrollUntil=0;
  const chart=new NautilusChart($('marketChart'),$('chartTooltip'),trade=>selectTrade(trade));
  const backendNow=()=>state?.server_now+(performance.now()-receivedAt)/1000;
  const connected=()=>online&&receivedAt>0&&performance.now()-receivedAt<5500;
  const monitorFresh=()=>connected()&&state?.run?.fresh&&!state.run.stopped&&finite(state.run.updated)&&backendNow()-state.run.updated<=5;
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
    const fresh=monitorFresh()&&m.fresh&&backendNow()-m.time<=5;
    $('targetValue').textContent=finite(m.target)?'$'+price(m.target):'—';
    $('btcValue').textContent=finite(m.btc)?'$'+price(m.btc):'—';
    document.querySelector('.instrument.now').classList.toggle('paused-price',!fresh);
    $('priceAge').textContent=fresh?'· FEED '+Math.max(0,backendNow()-m.time).toFixed(1)+'s':'· LAST RECORDED';
    const delta=finite(m.btc)&&finite(m.target)?m.btc-m.target:null;
    $('distanceValue').textContent=finite(delta)?money(delta)+'  ('+pct(delta/m.target*100)+')  '+(delta>=0?'above':'below')+' target':'Target distance unavailable';
    positive($('distanceValue'),fresh?delta:null);
    $('contractLabel').textContent=m.ticker||'Target for current contract not recorded';
    const qfresh=monitorFresh()&&q.fresh&&finite(q.valid_until)&&backendNow()<=q.valid_until;
    $('yesQuote').textContent=qfresh?quote(q.yes_bid)+' / '+quote(q.yes_ask):'— / —';
    $('noQuote').textContent=qfresh?quote(q.no_bid)+' / '+quote(q.no_ask):'— / —';
    $('quoteSource').textContent=qfresh?'NATIVE BID / ASK · '+(q.source||'recorded source'):'NO CURRENT QUOTE · '+(q.reason||'awaiting fresh data');
    $('realizedValue').textContent=money(a.realized);positive($('realizedValue'),a.realized);
    $('recordSummary').textContent=(a.closed??0)+' closed · '+(a.wins??0)+' wins · before fees';
    $('runIdentity').textContent=[r.build,r.name,'PID '+(r.pid??'—')].filter(Boolean).join('  ·  ');
    $('runIdentity').title=r.path||'';
    $('sourceStatus').textContent=(r.review?'ARCHIVE':r.stopped?'ENGINE STOPPED':r.fresh?'RUNTIME CURRENT':'RUNTIME STALE')+' · PINNED SOURCE';
    $('ema9Value').textContent=price(m.e9);$('ema30Value').textContent=price(m.e30);
    $('chartQuality').textContent=state.diagnostics.sampled_candles?'Dashed = sampled OHLC · solid = engine candles':'Engine-exported candles';
    $('chartQuality').title=state.diagnostics.candle_note;
    $('chartEmpty').classList.toggle('hidden',!!state.candles?.length);
    $('footerStatus').textContent='NAUTILUS '+state.version+' · '+(state.run.review?'RECORDED REVIEW':'READ-ONLY MONITOR')+' · '+state.trades.length+' trades · '+(state.diagnostics.issues.length?'SOURCE NOTES AVAILABLE':'CANONICAL LEDGER VERIFIED');
    renderConnection();tick();
  }
  function renderConnection(){
    const b=$('connection');
    b.className='badge '+(!connected()?'red':state?.run.stopped?'amber':state?.run.fresh?'green':'amber');
    b.textContent=!connected()?'DISCONNECTED':state?.run.review?'ARCHIVE':state?.run.stopped?'STOPPED':state?.run.fresh?'FEED CONNECTED':'STALE';
  }
  function tick(){
    if(!state)return;
    const m=state.market||{},r=state.run||{};
    const running=monitorFresh()&&m.fresh&&backendNow()-m.time<=5&&finite(m.close_ts);
    let left=finite(m.close_ts)?Math.max(0,m.close_ts-backendNow()):null;
    $('timerValue').textContent=running?String(Math.floor(left/60)).padStart(2,'0')+':'+String(Math.floor(left%60)).padStart(2,'0'):r.review?'ARCHIVE':r.stopped?'ENDED':'—:—';
    if(!running)left=finite(m.close_ts)&&finite(m.time)?Math.max(0,m.close_ts-m.time):null;
    $('timerProgress').style.width=finite(left)?Math.max(0,Math.min(100,(900-left)/9))+'%':'0%';
    document.querySelector('.clock').classList.toggle('urgent',running&&left<=120);
    $('closeLabel').textContent=finite(m.close_ts)?'CLOSE '+clock(m.close_ts,false)+' ET'+(!running?' · timer paused':''):'Contract close not recorded';
    if(!connected()&&online){online=false;renderConnection();$('priceAge').textContent='· CONNECTION LOST';document.querySelector('.instrument.now').classList.add('paused-price');}
  }
  function renderPositions(){
    const parent=$('positions');clear(parent);
    $('positionCount').textContent=state?.positions?.length??'—';
    if(!state)return;
    if(state.accounting.issues.length){note(parent,'Accounting cannot be confirmed. Check Health before interpreting positions.','warning-note');}
    if(!state.positions.length){note(parent,state.accounting.issues.length?'Position inventory unavailable':'No open positions','empty');if(!state.accounting.issues.length)note(parent,'Flat is a valid state. Waiting reason: '+readable(state.interpretation.pilot.reason));return;}
    state.positions.forEach(p=>{
      const n=el('article',null,'position-card'),h=el('div',null,'position-header');
      const side=el('span',p.side,'side-label '+(p.side==='YES'?'yes-text':'no-text'));side.append(el('span','#'+p.trade_id,'trade-number'));
      const inspect=el('button','Inspect');inspect.title='Review this position without placing an order';inspect.onclick=()=>selectTrade(p);h.append(side,inspect);n.append(h);
      const valid=monitorFresh()&&p.mark_valid&&finite(p.valid_until)&&backendNow()<=p.valid_until;
      const pnl=el('div',valid?money(p.open_pnl):'Mark unavailable','position-value');positive(pnl,valid?p.open_pnl:null);n.append(pnl);
      grid(n,[['ENTRY',quote(p.entry_ask)],['NATIVE BID',valid?quote(p.current_bid):'—'],['CONTRACTS',price(p.qty,0)]]);
      note(n,readable(p.role)+' · '+p.state);
      note(n,p.ticker);
      if(!valid&&p.last_verified_mark){const last=p.last_verified_mark;note(n,'Historical mark: '+quote(last.bid)+' · '+money(last.pnl)+' · not current','snapshot-label');}
      parent.append(n);
    });
  }
  function renderProtection(){
    const parent=$('protection');clear(parent);if(!state)return;
    const p=state.positions.find(x=>x.key===selectedKey)||(!selectedKey?state.positions[0]:null);
    const selected=state.trades.find(t=>t.key===selectedKey);
    const record=p?.protection||(selected?.evidence||[]).filter(e=>e.event==='POSITION').at(-1);
    if(!record){note(parent,'No engine-reported floor in the available command window.','empty');note(parent,'A missing floor is not proof that protection is disabled. Nautilus never sets or changes it.');return;}
    const live=!!p&&monitorFresh()&&record.fresh;
    note(parent,(p||selected).side+' #'+(p||selected).trade_id+' · '+(live?'CURRENT RECORD':'HISTORICAL RECORD'),'snapshot-label');
    grid(parent,[['PEAK BID',quote(record.peak_bid)],['FLOOR BID',quote(record.stop_bid)],['CURRENT BID',p?.mark_valid&&monitorFresh()?quote(p.current_bid):'—']]);
    if(finite(record.peak_bid)&&finite(record.stop_bid)&&record.peak_bid>0){const scale=el('div',null,'protection-scale'),fill=el('span',null,'fill'),pin=el('span',null,'floor-pin');fill.style.width=(Math.max(0,Math.min(1,p?.current_bid??record.bid??record.peak_bid))*100)+'%';pin.style.left=(Math.max(0,Math.min(1,record.stop_bid))*100)+'%';scale.append(fill,pin);parent.append(scale);}
    row(parent,'Recorded',clock(record.time)+' ET');
    row(parent,'Reason',record.reason);
    if(p?.mark_valid&&finite(record.peak_bid)&&record.peak_bid>0)row(parent,'Bid giveback',pct((record.peak_bid-p.current_bid)/record.peak_bid*100));
    note(parent,live?'Engine report only. This viewer cannot arm or enforce protection.':'Not an active guarantee. Current protection status is unavailable.','warning-note');
  }
  function renderDetails(){
    const parent=$('details');clear(parent);if(!state)return;
    const t=state.trades.find(x=>x.key===selectedKey);
    document.querySelector('.intelligence-rail').classList.toggle('reviewing',!!t);
    $('detailsTitle').textContent=t?'Trade #'+t.trade_id+' · '+t.side:'Market interpretation';
    $('detailsBadge').textContent=t?'REVIEW':'RECORDED';
    if(t){
      note(parent,t.exit_ts?'CLOSED POSITION':'OPEN / UNRESOLVED','state-title');
      grid(parent,[['ENTRY',quote(t.entry_ask)],['EXIT',quote(t.exit_bid)],['PAPER GROSS',money(t.pnl)]]);
      grid(parent,[['RETURN',pct(t.roi)],['MFE · RECORDED',pct(t.mfe)],['MAE · RECORDED',pct(t.mae)]]);
      row(parent,'Entry',clock(t.entry_ts)+' ET');row(parent,'Exit',t.exit_ts?clock(t.exit_ts)+' ET':'Not closed in this ledger');
      row(parent,'Size',price(t.qty,0)+' contracts · cost $'+price(t.cost));
      note(parent,'ENTRY EVIDENCE','evidence-title');note(parent,t.entry_reason);
      note(parent,'EXIT EVIDENCE','evidence-title');note(parent,t.exit_reason);
      row(parent,'Mission',t.intent||t.role);row(parent,'Contract',t.ticker);
      if(t.evidence.length){const last=t.evidence.at(-1);note(parent,'LAST MATCHED COMMAND · '+clock(last.time)+' ET','evidence-title');note(parent,(last.event||'')+' · '+(last.reason||'Not recorded'));}
      else note(parent,'No matching command explanation in the loaded window. No retrospective explanation is substituted.','snapshot-label');
    }else{
      const m=state.market,p=state.interpretation.pilot||{};
      note(parent,readable(m.phase||m.terrain),'state-title');
      row(parent,'Terrain',m.terrain);row(parent,'EMA9 arc',m.arc_direction);
      for(const [label,keys] of [['Current play',['kind','mission','action']],['Side',['side','main_side']],['Preparing',['prepare_side','next_side']],['Reason',['reason','summary']]]){
        const k=keys.find(k=>p[k]!=null&&p[k]!=='');row(parent,label,k?p[k]:'Not recorded');
      }
      note(parent,'Source '+clock(m.time)+' ET · '+(monitorFresh()&&m.fresh&&backendNow()-m.time<=5?'updating':'last recorded state')+'. Interpretation is evidence, not a new trading authority.','snapshot-label');
    }
    const nav=$('navigator');clear(nav);const n=state.interpretation.navigator||{};
    if(!Object.keys(n).length){note(nav,'No session-matched Navigator snapshot.','empty');note(nav,'Unmatched or stale sidecars do not borrow the current engine identity.');}
    else {['naevyr_residence','return_clock','uranus_radar','dragon_backbone_warning'].forEach(k=>{if(n[k]!=null)row(nav,k.replaceAll('_',' '),n[k]);});note(nav,'Shadow-only · '+readable(n.timestamp_utc||n.updated_utc),'snapshot-label');}
  }
  function renderTable(){
    const parent=$('tableArea'),savedScroll={top:parent.scrollTop,left:parent.scrollLeft};clear(parent);if(!state)return;
    if(tab==='health'){renderHealth(parent);return;}
    const table=el('table'),head=el('thead'),hr=el('tr');
    const headers=tab==='trades'?['# / ET','SIDE','ENTRY','EXIT','GROSS P&L','RETURN']:['TIME · ET','EVENT','SIDE','REASON'];headers.forEach(h=>hr.append(el('th',h)));head.append(hr);table.append(head);const body=el('tbody');
    const rows=tab==='trades'?[...state.trades].reverse():[...state.commands].reverse().slice(0,250);
    rows.forEach(t=>{const tr=el('tr');if(t.key===selectedKey)tr.className='selected';
      const values=tab==='trades'?['#'+t.trade_id+'  '+clock(t.entry_ts,false),t.side,quote(t.entry_ask),t.exit_ts?quote(t.exit_bid):'OPEN',money(t.pnl),pct(t.roi)]:[clock(t.time),t.event,t.side,t.reason];
      values.forEach((v,i)=>{const td=el('td',v);if((tab==='trades'&&i===1)||(tab==='decisions'&&i===2))td.className=t.side==='YES'?'yes-text':'no-text';if(tab==='trades'&&i===4)positive(td,t.pnl);if(tab==='decisions'&&i===3){td.className='reason';td.title=readable(v);}tr.append(td);});
      const target=tab==='trades'?t:state.trades.find(x=>x.key===t.key);
      if(target){tr.tabIndex=0;tr.setAttribute('aria-label','Inspect '+target.side+' trade '+target.trade_id);tr.onclick=()=>selectTrade(target);tr.onkeydown=e=>{if(e.key==='Enter')selectTrade(target);};}
      body.append(tr);
    });table.append(body);parent.append(table);parent.scrollTop=savedScroll.top;parent.scrollLeft=savedScroll.left;if(!rows.length)note(parent,'No recorded '+(tab==='trades'?'trades':'commands in the loaded window')+'.','empty');
  }
  function renderHealth(parent){
    clear(parent);if(!state){note(parent,'No response from local adapter.','empty');return;}
    const wrap=el('div',null,'health-list');
    row(wrap,'App','Nautilus '+state.version+' · read only');row(wrap,'Run',state.run.name);row(wrap,'Path',state.run.path);row(wrap,'Build',state.run.version);row(wrap,'Session',state.run.session_id);row(wrap,'Pinned commit',state.run.source_commit);row(wrap,'Updated',clock(state.run.updated)+' ET');
    note(wrap,state.accounting.basis,'snapshot-label');note(wrap,state.diagnostics.candle_note);note(wrap,state.diagnostics.ema_note);note(wrap,state.diagnostics.command_window);
    for(const [name,r] of Object.entries(state.diagnostics.readers))row(wrap,name,r.file+' · '+(r.present===false?'NOT PRESENT':r.tail_limited?'bounded tail':'full initial window')+' · '+r.lag_bytes+' bytes behind · '+(r.malformed_rows_skipped||0)+' malformed rows skipped');
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
    const frag=document.createDocumentFragment();shown.forEach(l=>frag.append(el('div',l.text,'feed-line '+l.category)));parent.replaceChildren(frag);
    if(!shown.length)note(parent,lines.length?'No lines match this filter.':'No complete console.log lines available.','empty');
    parent.scrollTop=feedPaused?oldScroll:parent.scrollHeight;feedShownId=last;
    requestAnimationFrame(()=>{programmaticScroll=false;});
  }
  function disconnected(message){online=false;renderConnection();$('errorBanner').textContent=message;$('errorBanner').classList.remove('hidden');if(state){renderTop();renderPositions();renderProtection();}}
  async function poll(){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);
    try{
      const response=await fetch('/api/state',{headers:{'X-Nautilus-Read':token},signal:controller.signal,cache:'no-store'});
      if(!response.ok)throw new Error('Local reader returned HTTP '+response.status);
      const next=await response.json();if(next.error)throw new Error(next.error);
      if(next.mode!=='PAPER_ONLY'||next.readonly!==true||!Array.isArray(next.candles))throw new Error('Unsupported telemetry identity');
      state=next;receivedAt=performance.now();online=true;
      const major=next.run.pointer_changed?'Run pointer changed. This window remains pinned to '+next.run.name+'. Restart Nautilus to attach a new run.':next.accounting.issues.length?'Accounting verification is paused: '+next.accounting.issues.join('; '):'';
      $('errorBanner').textContent=major;$('errorBanner').classList.toggle('hidden',!major);
      chart.setData(state);if(selectedKey)chart.selected=state.trades.find(t=>t.key===selectedKey)||null;
      renderTop();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();if($('healthDialog').open)renderHealth($('healthContent'));
      window.__nautilus.state=state;
    }catch(error){disconnected('FEED DISCONNECTED — current quotes and marks are withheld. '+error.message);}
    finally{clearTimeout(timeout);setTimeout(poll,1000);}
  }
  window.__nautilus={chart,getState:()=>state,state:null};
  setInterval(tick,250);poll();
})();
