"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const finite = value => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
  const num = value => finite(value) ? Number(value) : null;
  const cash = value => finite(value) ? Number(value).toLocaleString("en-US", {style:"currency",currency:"USD",minimumFractionDigits:2,maximumFractionDigits:2}) : "—";
  const price = value => finite(value) ? `${(Number(value)*100).toFixed(1).replace(/\.0$/, "")}¢` : "—";
  const percent = value => finite(value) ? `${Number(value)>=0?"+":""}${Number(value).toFixed(1)}%` : "—";
  const text = (id, value) => { $(id).textContent = value; };
  const esc = value => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const human = value => String(value || "Unavailable").replace(/_/g," ");
  const clock = value => finite(value) ? new Date(Number(value)*1000).toLocaleTimeString("en-GB",{timeZone:"UTC",hour12:false}) : "—";
  const age = value => finite(value) ? `${Math.max(0,Number(value)).toFixed(1)}s` : "Unknown";
  const chip = (id, content, state) => { text(id,content); $(id).className = `status-chip ${state}`; };
  let payload = null, range = 45, lastVersion = -1, connected = false, decisionLog = [], lastDecisionKey = "", chartModel = null;
  try { const stored=Number(localStorage.getItem("tachyos.paper.chart.minutes")); if ([15,45,90].includes(stored)) range=stored; } catch {}
  document.querySelectorAll("[data-range]").forEach(button => {
    button.classList.toggle("selected",Number(button.dataset.range)===range);
    button.addEventListener("click",()=>{range=Number(button.dataset.range);try{localStorage.setItem("tachyos.paper.chart.minutes",String(range));}catch{}document.querySelectorAll("[data-range]").forEach(b=>b.classList.toggle("selected",b===button));drawChart();});
  });

  function bid(book, side) { const levels=book?.[side==="YES"?"yes_bids":"no_bids"];return levels?.length ? num(levels[0].price) : null; }
  function quoteUsable(book, side, now) {
    if (!book || book.current!==true || book[side==="YES"?"yes_sell_allowed":"no_sell_allowed"]!==true) return false;
    const observed=num(book.observed_ts), source=num(book.exchange_ts), close=num(book.close_ts);
    return observed!==null && close!==null && now>=observed && now-observed<=3 && now<close && (source===null || now-source<=15 && now-source>=-2);
  }
  function metric(label,value,note="",cls="") { return `<div><label>${esc(label)}</label><strong class="${cls}">${esc(value)}</strong>${note?`<small>${esc(note)}</small>`:""}</div>`; }

  function renderPositions(status, now) {
    const positions=Object.values(status.positions || {}), book=status.book;
    if (!positions.length) {
      $("positions").innerHTML='<div class="flat-state"><span class="flat-icon">◇</span><div><strong>Flat · no open paper positions</strong><p>Commander remains free to wait for a qualified tool opportunity.</p></div></div>';
      return;
    }
    $("positions").innerHTML=positions.map(position=>{
      const exact=book?.ticker===position.ticker ? book : null;
      const usable=quoteUsable(exact,position.side,now), held=usable?bid(exact,position.side):null;
      const entry=num(position.entry_price), qty=num(position.qty), floor=num(position.floor_bid), peak=num(position.peak_bid);
      const roi=held!==null&&entry>0?(held/entry-1)*100:null;
      const maxGross=entry!==null&&qty!==null?(1-entry)*qty:null, maxPct=entry>0?(1/entry-1)*100:null;
      const expired=finite(position.close_ts)&&now>=Number(position.close_ts);
      const state=expired?"AWAITING OFFICIAL RESULT":position.exit_required?"EXIT PENDING":floor!==null?"FLOOR ARMED":"TOOL CUSTODY";
      return `<article class="position-card"><div class="position-head"><span class="tool">${esc(position.tool)}</span><span class="side">${esc(position.side)}</span><span class="contract">${esc(position.ticker)} · Position ${esc(position.position_id)}</span><span class="position-state">${state}</span></div><div class="position-metrics">${metric("Quantity",qty??"—","contracts")}${metric("Entry",price(entry),"Average fill")}${metric("Held-side bid",price(held),usable?"Current native top bid":expired?"Contract closed":"Bid unavailable / stale")}${metric("Bid ROI",percent(roi),"Before fees",roi===null?"":roi>=0?"positive":"negative")}${metric("Armed floor",floor===null?"Not armed":price(floor),peak===null?"No full-lot peak":`Peak ${price(peak)}`)}${metric("Max gross @ $1",cash(maxGross),"Theoretical remaining outcome")}${metric("Max return @ $1",percent(maxPct),"Entry-to-$1 · before fees")}</div></article>`;
    }).join("");
  }

  function updateAges() {
    if (!payload?.status) return;
    const status=payload.status, now=Date.now()/1000, source=status.source_status||{}, book=status.book||{}, latest=status.latest_geometry||{};
    const updated=num(status.updated_at), lag=updated===null?Infinity:now-updated;
    const stopped=status.state==="STOPPED", stale=!connected||lag>10;
    chip("run-state",!connected?"VIEW DISCONNECTED":stopped?"STOPPED":stale?"ENGINE OBSERVATION OLD":status.state||"RUNNING",!connected?"bad":stopped?"neutral":stale?"warn":"good");
    $("engine-dot").className=`source-dot ${!connected?"bad":stale||stopped?"warn":"good"}`;
    const close=num(status.market?.close_ts);
    if (close!==null) { const remaining=Math.max(0,Math.floor(close-now));text("contract-countdown",remaining?`${String(Math.floor(remaining/60)).padStart(2,"0")}:${String(remaining%60).padStart(2,"0")}`:"CLOSED"); }
    const receive=num(book.observed_ts), exchange=num(book.exchange_ts), geometry=num(latest.epoch_ms);
    const bookAge=receive===null?null:now-receive, geometryAge=geometry===null?null:now-geometry/1000;
    const bookCurrent=book.current===true&&bookAge!==null&&bookAge>=0&&bookAge<=3&&close!==null&&now<close&&(exchange===null||now-exchange<=15&&now-exchange>=-2);
    const btcCurrent=source.btc_current===true&&geometryAge!==null&&geometryAge>=-2&&geometryAge<=3;
    chip("book-state",bookCurrent?(book.entry_allowed?"CURRENT":"EXIT ONLY"):"UNAVAILABLE",bookCurrent?"good":"warn");
    chip("geometry-state",btcCurrent?"CURRENT":geometry===null?"WARMING":"STALE",btcCurrent?"good":"warn");
    text("book-age",age(bookAge));text("exchange-age",exchange===null?"Unknown · native sequence proof":`${age(now-exchange)} ago`);
    text("geometry-note",geometry===null?"Awaiting actual trade geometry":`Source ${age(geometryAge)} ago · epoch ${source.btc_connection_epoch??"—"}`);
    text("btc-source",geometry===null?"Awaiting actual Coinbase trades":`Coinbase · observed ${age(geometryAge)} ago`);
    renderPositions(status,now);
  }

  function render(data) {
    payload=data;
    const status=data.status;
    if (!status) { chip("run-state","AWAITING ENGINE","neutral");return; }
    const source=status.source_status||{}, rack=status.rack||{}, book=status.book||{}, physical=status.physical||{}, latest=status.latest_geometry||{};
    text("cash",cash(status.cash));text("net",cash(status.realized_net));$("net").className=num(status.realized_net)>0?"positive":num(status.realized_net)<0?"negative":"";
    text("gross",`Gross ${cash(status.realized_gross)}`);text("fees",cash(status.fees_paid));const held=Object.keys(status.positions||{}).length;
    text("position-count",String(held));text("inventory-note",held?"Exact-contract custody":"Flat · no carried inventory");text("btc-price",cash(latest.btc_price));
    text("ticker",status.market?.ticker||"Discovering KXBTC15M");text("run-id",status.run_id||"No run attached");text("last-observed",clock(status.updated_at));
    text("owned",human(rack.owned_territory));text("raw",`Raw · ${human(rack.raw_decision?.territory)}`);text("primary",rack.active_tool||"NONE");text("territory-id",rack.territory_id||"No physical ownership yet");
    text("overlay",rack.active_overlays?.length?rack.active_overlays.join(" + "):"NONE");text("handoff",rack.handoff_confirmed?"Handoff confirmed":rack.release_transition_pending?"Transition under observation":"No confirmed handoff");
    const entry=(status.decisions||[]).find(row=>row.scope==="ENTRY")?.decision;
    text("command-action",entry?.action||"—");text("command-reason",human(entry?.reason));text("owner-reason",human(rack.ownership_reason||"Waiting for physical qualification"));
    text("ema9",finite(latest.ema9)?Number(latest.ema9).toLocaleString("en-US",{maximumFractionDigits:2}):"—");text("ema30",finite(latest.ema30)?Number(latest.ema30).toLocaleString("en-US",{maximumFractionDigits:2}):"—");
    text("book-note",book.quote_id?`${book.quote_id} · ${book.entry_allowed?"entries permitted":"entries unavailable"}`:"Awaiting sequence snapshot");
    text("ledger-note",finite(status.ledger_seq)?`Committed boundary ${status.ledger_seq}`:"No committed record");chip("ledger-state",finite(status.ledger_seq)?"PAPER":"WAITING",finite(status.ledger_seq)?"good":"neutral");
    const yb=bid(book,"YES"), nb=bid(book,"NO");text("yes-quote",`${price(yb)} / ${price(nb===null?null:1-nb)}`);text("no-quote",`${price(nb)} / ${price(yb===null?null:1-yb)}`);
    const span=num(physical.observed_history_seconds);text("history-span",span===null?"—":`${(span/60).toFixed(1)} min · ${physical.geometry_rows_used??0} samples`);text("engine-sequence",`observation ${status.sequence??"—"}`);
    const key=JSON.stringify((status.decisions||[]).map(row=>[row.scope,row.position_id,row.decision?.action,row.decision?.reason]));
    if (key!==lastDecisionKey) { lastDecisionKey=key;for (const row of status.decisions||[]) decisionLog.unshift({...row,time:status.updated_at});decisionLog=decisionLog.slice(0,14); }
    $("decision-feed").innerHTML=decisionLog.length?decisionLog.map(row=>`<div class="decision-row"><span class="decision-kind">${esc(row.decision?.action)}</span><div><p>${esc(human(row.decision?.reason))}</p><small>${clock(row.time)} · ${esc(row.scope)}${row.position_id?` ${esc(row.position_id)}`:""}</small></div></div>`).join(""):'<p class="empty-small">No Commander decisions published.</p>';
    const error=source.source_error||source.discovery_error||source.rest_diagnostic_error||source.native?.last_error||null;$("source-error").hidden=!error;text("source-error",error?human(error):"");
    const events=(status.events||[]).slice(-12).reverse();text("event-count",`${(status.events||[]).length} recent events`);
    $("events").innerHTML=events.length?events.map(event=>`<tr><td>${clock(event.timestamp??event.now_ts??event.time)}</td><td>${esc(event.event)}</td><td>${esc(event.tool)} / ${esc(event.side)}</td><td>${esc(event.ticker)}</td><td>${esc(event.qty)}</td><td>${price(event.price)}</td><td class="${num(event.net_pnl)>0?"positive":num(event.net_pnl)<0?"negative":""}">${cash(event.net_pnl)}</td><td title="${esc(event.reason)}">${esc(human(event.reason))}</td></tr>`).join(""):'<tr><td colspan="8" class="empty-row">No committed trade events.</td></tr>';
    updateAges();drawChart();
  }

  function drawChart() {
    const canvas=$("chart"), bounds=canvas.getBoundingClientRect(), ratio=window.devicePixelRatio||1;
    const width=Math.max(100,bounds.width), height=Math.max(100,bounds.height);canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    const ctx=canvas.getContext("2d");ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);
    const rows=(payload?.geometry_rows||[]).filter(row=>finite(row.epoch_ms)&&finite(row.btc_price)).sort((a,b)=>a.epoch_ms-b.epoch_ms);
    const last=rows.at(-1), end=Math.ceil((num(payload?.status?.updated_at)??(last?last.epoch_ms/1000:Date.now()/1000))/60)*60000, start=end-range*60000;
    const visible=rows.filter(row=>row.epoch_ms>=start&&row.epoch_ms<=end), map=new Map();
    for (const row of visible) { const t=Math.floor(row.epoch_ms/60000)*60000,p=Number(row.btc_price);let bar=map.get(t);if(!bar){bar={t,open:p,high:p,low:p,close:p,e9:num(row.ema9),e30:num(row.ema30),count:0};map.set(t,bar);}bar.high=Math.max(bar.high,p);bar.low=Math.min(bar.low,p);bar.close=p;bar.e9=num(row.ema9);bar.e30=num(row.ema30);bar.count++; }
    const bars=[...map.values()], left=15,right=76,top=18,bottom=32,pw=width-left-right,ph=height-top-bottom;
    const x=t=>left+(t-start)/(end-start)*pw;
    $("chart-empty").hidden=bars.length>0;text("chart-mode",`${range} minutes · ${range/15} contract windows · UTC`);
    text("chart-coverage",`${visible.length.toLocaleString()} received samples · ${bars.length} observed minute bars · no gap filling`);
    if(!bars.length){chartModel=null;ctx.strokeStyle="#183340";ctx.lineWidth=1;for(let n=0;n<5;n++){const y=top+n*ph/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(width-right,y);ctx.stroke();}return;}
    const values=visible.flatMap(row=>[num(row.btc_price),num(row.ema9),num(row.ema30)]).filter(v=>v!==null), low=Math.min(...values), high=Math.max(...values), pad=Math.max((high-low)*.12,5), min=low-pad,max=high+pad;
    const y=p=>top+(max-p)/(max-min)*ph;ctx.font="10px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif";ctx.textAlign="left";
    for(let i=0;i<=5;i++){const p=min+(max-min)*i/5,yy=y(p);ctx.strokeStyle="#193541";ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(width-right,yy);ctx.stroke();ctx.fillStyle="#6c8d9b";ctx.fillText(p.toLocaleString("en-US",{maximumFractionDigits:0}),width-right+10,yy+3);}
    for(let t=Math.ceil(start/900000)*900000;t<=end;t+=900000){ctx.setLineDash([3,5]);ctx.strokeStyle="#32505a";ctx.beginPath();ctx.moveTo(x(t),top);ctx.lineTo(x(t),height-bottom);ctx.stroke();ctx.setLineDash([]);}
    const labelStep=range<=15?300000:range<=45?900000:1800000;ctx.textAlign="center";ctx.fillStyle="#6c8d9b";
    for(let t=Math.ceil(start/labelStep)*labelStep;t<end;t+=labelStep)ctx.fillText(new Date(t).toISOString().slice(11,16),x(t),height-10);
    const bw=Math.max(2,Math.min(13,pw/range*.55));
    for(const bar of bars){const xx=x(bar.t+30000),up=bar.close>=bar.open;ctx.strokeStyle=up?"#55bfae":"#de8190";ctx.fillStyle=up?"#3a9e91":"#b76676";ctx.beginPath();ctx.moveTo(xx,y(bar.high));ctx.lineTo(xx,y(bar.low));ctx.stroke();const yy=Math.min(y(bar.open),y(bar.close));ctx.fillRect(xx-bw/2,yy,bw,Math.max(1.4,Math.abs(y(bar.open)-y(bar.close))));}
    function line(field,color){ctx.strokeStyle=color;ctx.lineWidth=1.6;ctx.beginPath();let prior=null;for(const row of visible){const p=num(row[field]);if(p===null){prior=null;continue;}if(prior===null||row.epoch_ms-prior>15000)ctx.moveTo(x(row.epoch_ms),y(p));else ctx.lineTo(x(row.epoch_ms),y(p));prior=row.epoch_ms;}ctx.stroke();ctx.lineWidth=1;}
    line("ema9","#edc276");line("ema30","#b8a1ed");
    const lastPrice=Number(visible.at(-1).btc_price),yy=y(lastPrice);ctx.setLineDash([3,4]);ctx.strokeStyle="#4f8e92";ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(width-right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle="#1e5056";ctx.fillRect(width-right+3,yy-10,right-8,20);ctx.fillStyle="#a9efdf";ctx.textAlign="left";ctx.fillText(lastPrice.toLocaleString("en-US",{maximumFractionDigits:0}),width-right+9,yy+3);
    chartModel={bars,start,end,left,right,pw,width,height};
  }

  $("chart").addEventListener("mousemove",event=>{if(!chartModel)return;const rect=$("chart").getBoundingClientRect(),px=event.clientX-rect.left, model=chartModel;if(px<model.left||px>model.width-model.right)return;const t=model.start+(px-model.left)/model.pw*(model.end-model.start),bar=model.bars.reduce((a,b)=>Math.abs(b.t+30000-t)<Math.abs(a.t+30000-t)?b:a);if(Math.abs(bar.t+30000-t)>60000){$("chart-tooltip").hidden=true;return;}const tip=$("chart-tooltip");tip.innerHTML=`<b>${new Date(bar.t).toISOString().slice(11,16)} UTC · ${bar.count} received samples</b><br>O ${cash(bar.open)} &nbsp; H ${cash(bar.high)}<br>L ${cash(bar.low)} &nbsp; C ${cash(bar.close)}<br>EMA9 ${cash(bar.e9)} · EMA30 ${cash(bar.e30)}`;tip.hidden=false;tip.style.left=`${Math.min(Math.max(10,px+18),model.width-290)}px`;tip.style.top=`${Math.max(8,Math.min(event.clientY-rect.top-90,model.height-100))}px`;});
  $("chart").addEventListener("mouseleave",()=>{$("chart-tooltip").hidden=true;});
  new ResizeObserver(drawChart).observe($("chart-wrap"));
  async function poll(){try{const response=await fetch("/api/state",{cache:"no-store"});if(!response.ok)throw new Error("LOCAL_VIEW_UNAVAILABLE");const data=await response.json();connected=true;if(data.version!==lastVersion){lastVersion=data.version;render(data);}else updateAges();}catch{connected=false;chip("run-state","VIEW DISCONNECTED","bad");$("engine-dot").className="source-dot bad";}finally{setTimeout(poll,1000);}}
  setInterval(updateAges,1000);poll();drawChart();
})();
