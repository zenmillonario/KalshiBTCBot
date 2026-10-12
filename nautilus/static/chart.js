/* Nautilus native canvas chart. No third-party feed, remote script, or strategy.
   Epoch-based viewport persists independently of updates and contract rollovers. */
'use strict';
class NautilusChart {
  constructor(canvas, tooltip, onSelect) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.tooltip=tooltip;
    this.onSelect=onSelect; this.data=null; this.follow=true; this.end=null;
    this.fontScale=1; this.touches=new Map(); this.pinch=null; this.span=2700; this.fitTarget=false; this.manualY=null; this.selected=null;
    this.pointer=null; this.drag=null; this.markers=[]; this.ratio=.75; this.raf=0;
    try { const n=Number(localStorage.getItem('nautilus.span')); if(n>=300&&n<=64800)this.span=n; } catch(e){}
    this.resizeObserver=new ResizeObserver(()=>this.requestDraw());
    this.resizeObserver.observe(canvas.parentElement);
    canvas.addEventListener('wheel',e=>this.wheel(e),{passive:false});
    canvas.addEventListener('pointerdown',e=>this.down(e));
    canvas.addEventListener('pointermove',e=>this.move(e));
    canvas.addEventListener('pointerup',e=>this.up(e));
    canvas.addEventListener('pointercancel',e=>this.cancelPointer(e));
    canvas.addEventListener('pointerleave',()=>{if(!this.drag){this.pointer=null;this.tooltip.classList.add('hidden');this.requestDraw();}});
    canvas.addEventListener('dblclick',e=>{if(e.offsetX>this.w-73)this.manualY=null;else this.toLive();this.requestDraw();});
    canvas.addEventListener('keydown',e=>{
      if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();this.follow=false;this.end+=(e.key==='ArrowLeft'?-1:1)*this.span/8;this.requestDraw();}
      if(e.key==='Home'){e.preventDefault();this.toLive();}
      if(e.key==='+'||e.key==='='){this.setSpan(this.span/1.2);}
      if(e.key==='-'){this.setSpan(this.span*1.2);}
    });
  }
  saveSpan(){try{localStorage.setItem('nautilus.span',String(this.span));}catch(e){}}
  setSpan(seconds){this.span=Math.max(300,Math.min(64800,seconds));this.saveSpan();if(this.follow)this.end=this.liveEnd();this.requestDraw();}
  liveEnd(){const candles=this.data?.candles||[];return candles.length?candles[candles.length-1].time+Math.min(120,this.span*.07):Date.now()/1000;}
  toLive(){this.follow=true;this.end=this.liveEnd();this.manualY=null;this.requestDraw();}
  inspect(trade){this.selected=trade;this.follow=false;this.manualY=null;const end=trade.exit_ts??trade.entry_ts+240;this.end=(trade.entry_ts+end)/2+this.span/2;this.requestDraw();}
  setData(data){this.data=data;if(this.end===null||this.follow)this.end=this.liveEnd();this.requestDraw();}
  requestDraw(){if(!this.raf)this.raf=requestAnimationFrame(()=>{this.raf=0;this.draw();});}
  localPoint(e){const r=this.canvas.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
  down(e){
    if(e.pointerType==='touch'){
      this.touches.set(e.pointerId,this.localPoint(e));
      this.canvas.setPointerCapture(e.pointerId);
      if(this.touches.size===2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        this.pinch={distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),span:this.span,anchor:this.end-this.span+(mid-this.left)/this.plotW*this.span};
        this.drag=null;this.follow=false;this.tooltip.classList.add('hidden');return;
      }
      if(this.touches.size>2)return;
    }
    if(e.button!==0)return;const p=this.localPoint(e);this.canvas.focus();this.canvas.setPointerCapture(e.pointerId);let mode='pan';if(p.x>this.w-73)mode='scale';else if(Math.abs(p.y-this.divider)<7)mode='divider';this.drag={...p,end:this.end,mode,moved:false,range:this.range?{...this.range}:null};}
  move(e){const p=this.localPoint(e);this.pointer=p;
    if(e.pointerType==='touch'&&this.touches.has(e.pointerId)){
      this.touches.set(e.pointerId,p);
      if(this.pinch&&this.touches.size>=2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        this.span=Math.max(300,Math.min(64800,this.pinch.span*this.pinch.distance/Math.max(1,Math.hypot(a.x-b.x,a.y-b.y))));
        this.end=this.pinch.anchor+(1-(mid-this.left)/this.plotW)*this.span;
        this.manualY=null;this.saveSpan();this.requestDraw();return;
      }
    }
    if(this.drag){const d=this.drag;d.moved=d.moved||Math.abs(p.x-d.x)+Math.abs(p.y-d.y)>4;
      if(d.mode==='scale'&&d.range){const mid=(d.range.high+d.range.low)/2,half=(d.range.high-d.range.low)/2*Math.exp((p.y-d.y)/110);this.manualY={low:Math.max(1,mid-half),high:mid+half};}
      else if(d.mode==='divider'){this.ratio=Math.max(.5,Math.min(.87,p.y/Math.max(200,this.h)));}
      else{this.follow=false;this.end=d.end-(p.x-d.x)*this.span/this.plotW;this.manualY=null;}
      this.tooltip.classList.add('hidden');
    }
    this.canvas.style.cursor=this.drag?'grabbing':p.x>this.w-73?'ns-resize':Math.abs(p.y-this.divider)<7?'row-resize':'crosshair';this.requestDraw();
  }
  up(e){
    if(e.pointerType==='touch'&&this.pinch){this.touches.delete(e.pointerId);if(!this.touches.size)this.pinch=null;this.drag=null;try{this.canvas.releasePointerCapture(e.pointerId);}catch(_){}this.requestDraw();return;}
    this.touches.delete(e.pointerId);
    if(this.drag&&!this.drag.moved){const p=this.localPoint(e);const near=this.markers.map(m=>({...m,d:Math.hypot(m.x-p.x,m.y-p.y)})).sort((a,b)=>a.d-b.d)[0];if(near&&near.d<20)this.onSelect(near.trade);}
    this.drag=null;try{this.canvas.releasePointerCapture(e.pointerId);}catch(e){}this.requestDraw();}
  cancelPointer(e){this.touches.delete(e.pointerId);if(!this.touches.size)this.pinch=null;this.drag=null;this.pointer=null;this.tooltip.classList.add('hidden');this.requestDraw();}
  wheel(e){e.preventDefault();const p=this.localPoint(e);if(p.x>this.w-73){const r=this.manualY||this.range;if(r){const mid=(r.low+r.high)/2,half=(r.high-r.low)/2*Math.exp(e.deltaY*.002);this.manualY={low:Math.max(1,mid-half),high:mid+half};}}
    else{const old=this.span,f=(Math.max(0,Math.min(this.plotW,p.x-this.left)))/this.plotW;const anchor=this.end-old+f*old;this.span=Math.max(300,Math.min(64800,old*Math.exp(e.deltaY*.0015)));this.end=this.follow?this.liveEnd():anchor+(1-f)*this.span;this.saveSpan();this.manualY=null;}this.requestDraw();}
  x(t){return this.left+(t-(this.end-this.span))/this.span*this.plotW;}
  y(v){return this.top+(this.range.high-v)/(this.range.high-this.range.low)*(this.mainBottom-this.top);}
  qy(v){return this.quoteBottom-v*(this.quoteBottom-this.quoteTop);}
  clock(t,seconds=false){return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{}),hour12:false}).format(new Date(t*1000));}
  price(v,d=2){return Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});}
  text(s,x,y,color='#7897a9',size=10,align='left'){const c=this.ctx;c.fillStyle=color;c.font=`${size*this.fontScale}px "Segoe UI",sans-serif`;c.textAlign=align;c.fillText(s,x,y);c.textAlign='left';}
  line(x1,y1,x2,y2,color,width=1,dash=[]){const c=this.ctx;c.beginPath();c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();c.setLineDash([]);}
  badge(s,y,color){const c=this.ctx;const yy=Math.max(this.top+8,Math.min(this.mainBottom-8,y));c.fillStyle=color;c.fillRect(this.w-73,yy-10,73,20);this.text(s,this.w-5,yy+3,'#07141c',10,'right');}
  draw(){
    const r=this.canvas.parentElement.getBoundingClientRect();this.w=Math.max(1,Math.floor(r.width));this.h=Math.max(1,Math.floor(r.height));const dpr=window.devicePixelRatio||1;
    if(this.canvas.width!==Math.round(this.w*dpr)||this.canvas.height!==Math.round(this.h*dpr)){this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);}
    const c=this.ctx;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,this.w,this.h);
    if(this.w<160||this.h<180){this.text('Expand chart to inspect',this.w/2,this.h/2,'#829daa',10,'center');return;}
    this.left=10;this.top=13;this.plotW=this.w-85;this.divider=Math.floor(Math.min(this.h*this.ratio,this.h-90));this.mainBottom=this.divider-15;this.quoteTop=this.divider+29;this.quoteBottom=this.h-28;
    if(!this.data||!this.data.candles?.length)return;
    const from=this.end-this.span;const bars=this.data.candles.filter(b=>b.time>=from-60&&b.time<=this.end+60);const emas=this.data.emas.filter(b=>b.time>=from-60&&b.time<=this.end+60);
    const vals=bars.flatMap(b=>[b.low,b.high]);emas.forEach(e=>{if(Number.isFinite(e.e9))vals.push(e.e9);if(Number.isFinite(e.e30))vals.push(e.e30);});
    if(this.fitTarget)this.data.targets.filter(t=>t.start_ts<this.end&&(t.close_ts??this.end)>from).forEach(t=>vals.push(t.target));
    if(!vals.length){this.text('No recorded candles in this window · Return to Live →',this.w/2,this.h/2,'#829daa',12,'center');return;}
    let low=Math.min(...vals),high=Math.max(...vals),padding=Math.max(3,(high-low)*.16);this.range=this.manualY||{low:Math.max(1,low-padding),high:high+padding};
    // Grid and quarter-hour fenceposts preserve a continuous time axis.
    const rawStep=(this.range.high-this.range.low)/6,mag=10**Math.floor(Math.log10(rawStep));let step=[1,2,2.5,5,10].find(x=>x*mag>=rawStep)*mag;
    for(let v=Math.ceil(this.range.low/step)*step;v<=this.range.high;v+=step){const y=this.y(v);this.line(this.left,y,this.w-74,y,'#16314299');this.text(this.price(v,step<1?2:0),this.w-8,y+3,'#7294a7',10,'right');}
    const tick=this.span>10800?3600:this.span>5400?900:300;
    for(let t=Math.floor(from/tick)*tick;t<=this.end;t+=tick){const x=this.x(t);if(x<this.left)continue;const major=t%900===0;this.line(x,this.top,x,this.quoteBottom,major?'#3b687d99':'#17314188',1,major?[4,4]:[]);this.text(this.clock(t),x,this.h-9,major?'#a0bac9':'#658399',9,'center');}
    this.line(this.w-74,0,this.w-74,this.h,'#2d495b');this.line(0,this.divider,this.w,this.divider,'#2c4d61');
    this.text('NATIVE CONTRACT QUOTES',14,this.divider+18,'#85a3b5',9);this.text('0–1 · bid / ask · gaps remain gaps',this.w-86,this.divider+18,'#5d8196',8,'right');
    for(const v of [0,.5,1]){const y=this.qy(v);this.line(this.left,y,this.w-74,y,'#152e3c');this.text(v.toFixed(2),this.w-8,y+3,'#7294a7',9,'right');}
    c.save();c.beginPath();c.rect(this.left,0,this.plotW,this.mainBottom+10);c.clip();
    if(this.selected){const a=this.x(this.selected.entry_ts),b=this.x(this.selected.exit_ts??this.data.market.time);c.fillStyle='#1d7a8d1c';c.fillRect(a,this.top,Math.max(2,b-a),this.mainBottom-this.top);this.line(a,this.top,a,this.mainBottom,'#35c2d77a',1,[2,3]);}
    for(const target of this.data.targets){if(!target.target||target.start_ts>this.end||(target.close_ts??this.end)<from)continue;const y=this.y(target.target);const active=target.ticker===this.data.market.ticker;this.line(Math.max(this.left,this.x(target.start_ts)),y,Math.min(this.w-74,this.x(target.close_ts??this.end)),y,active?'#efbd5baa':'#99784c66',1,[5,4]);if(active&&y>20&&y<this.mainBottom-10)this.text('TO BEAT  $'+this.price(target.target),Math.min(this.w-87,this.x(target.close_ts??this.end)-6),y-7,'#e6b559',10,'right');}
    const bodyWidth=Math.max(1,Math.min(20,this.plotW*60/this.span*.62));
    for(const b of bars){const x=this.x(b.time),up=b.close>=b.open,color=up?'#35cdb4':'#ec8575';const yOpen=this.y(b.open),yClose=this.y(b.close);this.line(x,this.y(b.high),x,this.y(b.low),color,1);const top=Math.min(yOpen,yClose),height=Math.max(1,Math.abs(yOpen-yClose));c.fillStyle=up?'#34c7b49e':'#e47b6bac';c.fillRect(x-bodyWidth/2,top,bodyWidth,height);if(b.quality==='sampled'){c.strokeStyle=color;c.lineWidth=1;c.setLineDash([2,2]);c.strokeRect(x-bodyWidth/2,top,bodyWidth,height);c.setLineDash([]);}else{c.fillStyle=color;c.fillRect(x-bodyWidth/2,top,bodyWidth,height);}}
    for(const [field,color]of[['e30','#e8ad51'],['e9','#37cede']]){c.beginPath();c.strokeStyle=color;c.lineWidth=field==='e9'?1.8:1.5;let previous=null;for(const e of emas){const x=this.x(e.time),y=this.y(e[field]);if(!Number.isFinite(y)){previous=null;continue;}if(previous===null||e.time-previous>90)c.moveTo(x,y);else c.lineTo(x,y);previous=e.time;}c.stroke();}
    const market=this.data.market;if(Number.isFinite(market.btc)&&market.time>=from&&market.time<=this.end){this.line(this.left,this.y(market.btc),this.w-74,this.y(market.btc),market.fresh?'#30ceac77':'#758b9844',1,[2,4]);}
    this.markers=[];
    for(const t of this.data.trades){for(const event of['entry','exit']){const time=t[event+'_ts'];if(time===null||time<from||time>this.end)continue;const b=bars.find(b=>b.time===Math.floor(time/60)*60);if(!b)continue;const x=this.x(time),below=t.side==='YES',y=this.y(below?b.low:b.high)+(below?14:-14),color=event==='exit'?'#a5bbc7':t.side==='YES'?'#51dfbc':'#f1c272';c.beginPath();c.fillStyle=color;c.strokeStyle=color;if(event==='exit'){c.arc(x,y,3,0,Math.PI*2);c.stroke();}else{c.moveTo(x,y+(below?-5:5));c.lineTo(x-4,y+(below?3:-3));c.lineTo(x+4,y+(below?3:-3));c.closePath();c.fill();}this.markers.push({x,y,trade:t,event});const selected=this.selected?.key===t.key;if(selected||event==='entry'){const label=this.compactLabels?`#${t.trade_id} ${event==='exit'?'OUT':t.side}`:`#${t.trade_id} ${event==='exit'?'EXIT':t.side} ${(Number.isFinite(t[event==='entry'?'entry_ask':'exit_bid'])?t[event==='entry'?'entry_ask':'exit_bid'].toFixed(3):'—')}`;this.text(label,x+(x>this.w-190?-7:7),y+(below?14:-8),color,selected?10:9,x>this.w-190?'right':'left');}}}
    c.restore();
    if(Number.isFinite(market.btc)&&market.time>=from&&market.time<=this.end)this.badge(this.price(market.btc),this.y(market.btc),market.fresh?'#36cdb2':'#8dabb6');
    if(Number.isFinite(market.target)&&(this.y(market.target)<this.top||this.y(market.target)>this.mainBottom))this.text((this.y(market.target)<this.top?'↑ ':'↓ ')+'TARGET OFF SCALE',this.w-85,this.y(market.target)<this.top?this.top+5:this.mainBottom-4,'#d4b369',8,'right');
    // Contract lines stop at boundaries. Invalid quotes explicitly break paths.
    c.save();c.beginPath();c.rect(this.left,this.quoteTop,this.plotW,this.quoteBottom-this.quoteTop);c.clip();
    const quotes=this.data.quotes.filter(q=>q.time>=from-6&&q.time<=this.end);
    for(const [field,color]of[['yes_bid','#3dc9af'],['yes_ask','#7cdac5'],['no_bid','#e0a64c'],['no_ask','#f3ce8a']]){c.beginPath();c.strokeStyle=color;c.lineWidth=field.endsWith('bid')?1.25:.8;c.setLineDash(field.endsWith('ask')?[3,2]:[]);let prev=null;for(const q of quotes){const v=q[field];if(v===null||!Number.isFinite(v)){prev=null;continue;}const x=this.x(q.time),y=this.qy(v);if(prev&&q.ticker===prev.ticker&&q.time-prev.time<=6&&q.time>=prev.time){c.lineTo(x,this.qy(prev[field]));c.lineTo(x,y);}else c.moveTo(x,y);prev=q;}c.stroke();c.setLineDash([]);}
    c.restore();
    this.crosshair(bars);
    if(typeof this.onViewport==='function')this.onViewport({follow:this.follow,span:this.span,end:this.end});
  }
  crosshair(bars){if(!this.pointer||this.drag||this.pointer.x<this.left||this.pointer.x>this.w-75){this.tooltip.classList.add('hidden');return;}
    const p=this.pointer,t=this.end-this.span+(p.x-this.left)/this.plotW*this.span;this.line(p.x,this.top,p.x,this.quoteBottom,'#719aa175',1,[3,3]);if(p.y<this.mainBottom)this.line(this.left,p.y,this.w-75,p.y,'#719aa14d',1,[3,3]);
    const b=bars.reduce((a,b)=>!a||Math.abs(b.time-t)<Math.abs(a.time-t)?b:a,null);if(!b||Math.abs(b.time-t)>45){this.tooltip.classList.add('hidden');return;}
    const ema=this.data.emas.find(e=>e.time===b.time);const lines=[this.clock(b.time)+' ET · 1 minute',`O ${this.price(b.open)}   H ${this.price(b.high)}`,`L ${this.price(b.low)}   C ${this.price(b.close)}`,b.quality==='sampled'?'SAMPLED OHLC · intraminute extremes may be missing':'ENGINE CANDLE · '+b.quality];
    if(ema)lines.push(`NAEVYR ${this.price(ema.e9)}  THAERYON ${this.price(ema.e30)}`);
    this.tooltip.textContent=lines.join('\n');this.tooltip.classList.remove('hidden');this.tooltip.style.left=Math.max(6,Math.min(this.w-290,p.x+15))+'px';this.tooltip.style.top=Math.max(5,Math.min(this.h-140,p.y+15))+'px';
  }
}
window.NautilusChart=NautilusChart;
