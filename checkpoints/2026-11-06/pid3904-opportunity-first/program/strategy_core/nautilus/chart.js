/* Nautilus native canvas chart. No third-party feed, remote script, or strategy.
   Epoch-based viewport persists independently of updates and contract rollovers. */
'use strict';
class NautilusChart {
  constructor(canvas, tooltip, onSelect) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.tooltip=tooltip;
    this.onSelect=onSelect; this.data=null; this.follow=true; this.end=null;
    this.fontScale=1; this.touches=new Map(); this.pinch=null; this.span=2700; this.fitTarget=false; this.manualY=null; this.selected=null;
    this.showLookingGlass=true; this.reviewMode=false; this.viewportSpan=null;
    this.pointer=null; this.drag=null; this.markers=[]; this.ratio=.83; this.raf=0;
    try { const n=Number(localStorage.getItem('nautilus.span')); if(n>=300&&n<=64800)this.span=n; } catch(e){}
    try { this.showLookingGlass=localStorage.getItem('nautilus.lookingGlass')!=='off'; } catch(e){}
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
      if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();this.freezeViewport();this.end+=(e.key==='ArrowLeft'?-1:1)*this.viewSpan()/8;this.requestDraw();}
      if(e.key==='Home'){e.preventDefault();this.toLive();}
      if(e.key==='+'||e.key==='='){this.setSpan(this.span/1.2);}
      if(e.key==='-'){this.setSpan(this.span*1.2);}
    });
  }
  saveSpan(){try{localStorage.setItem('nautilus.span',String(this.span));}catch(e){}}
  viewSpan(){return this.viewportSpan??this.span;}
  freezeViewport(){this.viewportSpan=this.viewSpan();this.follow=false;}
  setSpan(seconds){this.span=Math.max(300,Math.min(64800,seconds));this.viewportSpan=this.span;this.saveSpan();if(this.follow)this.syncLiveViewport();this.requestDraw();}
  historyEnd(){const candles=this.data?.candles||[];return candles.length?candles[candles.length-1].time+Math.min(120,this.span*.07):Date.now()/1000;}
  liveEnd(){const end=this.historyEnd(),view=this.scenarioView();return view.paths.length?Math.max(end,view.glass.close_ts+Math.min(30,this.span*.02)):end;}
  syncLiveViewport(){const end=this.historyEnd();this.end=this.liveEnd();this.viewportSpan=this.span+Math.max(0,this.end-end);}
  toLive(){this.follow=true;this.syncLiveViewport();this.manualY=null;this.requestDraw();}
  inspect(trade){this.selected=trade;this.follow=false;this.viewportSpan=this.span;this.manualY=null;const end=trade.exit_ts??trade.entry_ts+240;this.end=(trade.entry_ts+end)/2+this.span/2;this.requestDraw();}
  setData(data){this.data=data;if(this.end===null||this.follow)this.syncLiveViewport();this.requestDraw();}
  setLookingGlass(enabled){this.showLookingGlass=Boolean(enabled);try{localStorage.setItem('nautilus.lookingGlass',enabled?'on':'off');}catch(e){}if(this.follow)this.syncLiveViewport();this.requestDraw();}
  scenarioView({ignorePreference=false,ignoreViewport=false}={}){
    const glass=this.data?.looking_glass,market=this.data?.market;
    const result=(status,reason,paths=[])=>({status,reason,paths,glass:glass||null,active:null,issued:null});
    if(!ignorePreference&&!this.showLookingGlass)return result('OFF','Looking Glass is hidden');
    if(this.data?.run?.review)return result('REVIEW','Recorded run · current scenario paths are unavailable');
    if(this.reviewMode||this.selected)return result('REVIEW','Trade review · select Monitor for current scenario paths');
    if(!ignoreViewport&&!this.follow)return result('PAUSED','Inspecting chart history · Return to Live for current paths');
    if(!glass)return result('UNAVAILABLE','Waiting for Looking Glass observations');
    if(!['READY','PARTIAL'].includes(glass.status))return result(glass.status==='STALE'?'STALE':'UNAVAILABLE',glass.reason||glass.thesis?.reason||glass.notes?.[0]||'Not enough continuous history for scenario paths');
    const now=typeof this.sourceClock==='function'?this.sourceClock():this.data.server_now;
    if(this.data?.run?.stopped||this.data?.run?.fresh!==true||market?.fresh!==true||
       (typeof this.sourceConnected==='function'&&!this.sourceConnected())||
       !Number.isFinite(now)||!Number.isFinite(glass.source_ts)||!Number.isFinite(glass.valid_until)||
       now<glass.source_ts||now>glass.valid_until||now>=glass.close_ts)
      return result('STALE','Scenario source is stale; waiting for a current observation');
    if(glass.execution_authority!==false||glass.probabilities_calibrated!==false||
       glass.ticker!==market.ticker||glass.close_ts!==market.close_ts||
       !Number.isFinite(glass.close_ts)||glass.close_ts<=glass.source_ts||
       !Number.isFinite(market.time)||Math.abs(market.time-glass.source_ts)>3)
      return result('UNAVAILABLE','Scenario identity or observation time does not match this contract');
    const paths=(Array.isArray(glass.paths)?glass.paths:[]).filter(path=>{
      if(path.conditional!==true||!['CONTINUATION','ROTATION_STALL','REVERSAL','PATTERN'].includes(path.family)||!Array.isArray(path.points)||path.points.length<2)return false;
      const first=path.points[0],last=path.points.at(-1);
      const finitePattern=path.family==='PATTERN';
      if(finitePattern&&(!Number.isFinite(path.horizon_ts)||Math.abs(last.time-path.horizon_ts)>1e-6||
         path.time_stretched!==false||path.repeated!==false||!Number.isFinite(path.reference_end_ts)||
         path.reference_end_ts>glass.close_ts-900||path.reference_known_by_ts!==glass.source_ts))return false;
      if(Math.abs(first.time-glass.source_ts)>1e-6||(!finitePattern&&Math.abs(last.time-glass.close_ts)>1e-6)||
         !Number.isFinite(market.btc)||Math.abs(first.btc-market.btc)>1e-6||
         !Number.isFinite(market.e9)||Math.abs(first.e9-market.e9)>1e-6)return false;
      return path.points.every((point,index)=>Number.isFinite(point.time)&&Number.isFinite(point.btc)&&point.btc>0&&
        Number.isFinite(point.e9)&&point.e9>0&&point.time>=glass.source_ts&&point.time<=glass.close_ts&&
        (index===0||point.time>path.points[index-1].time));
    }).slice(0,12);
    if(!paths.length)return result('UNAVAILABLE','No valid current-contract scenario paths');
    const view=result(glass.status,'Conditional paths, bounded by this contract close',paths),active=glass.active_pattern;
    if(active?.status==='READY'&&active.conditional===true&&active.execution_authority===false&&
       active.source_ts===glass.source_ts&&typeof active.key==='string'&&
       paths.some(path=>path.id===active.path_id))view.active=active;
    if(view.active){
      const samples=Array.isArray(glass.research?.as_issued)?glass.research.as_issued:[];
      view.issued=samples.slice(-16).find(sample=>{
        if(sample.frozen!==true||sample.conditional!==true||sample.execution_authority!==false||
           sample.run_id!==(this.data.run.run_id??this.data.run.name)||sample.ticker!==glass.ticker||
           sample.close_ts!==glass.close_ts||sample.pattern_key!==active.key||
           sample.continuity_generation!==active.continuity_generation||
           !Number.isFinite(sample.source_ts)||sample.source_ts>=glass.source_ts||
           !Number.isFinite(sample.issued_at_ts)||sample.issued_at_ts>now||sample.issued_at_ts<sample.source_ts||
           !Array.isArray(sample.path?.points)||sample.path.points.length<2)return false;
        const points=sample.path.points,anchor=sample.anchor,first=points[0];
        return sample.path.conditional===true&&anchor&&first.time===sample.source_ts&&
          first.time===anchor.time&&first.btc===anchor.btc&&first.e9===anchor.e9&&
          points.every((point,index)=>Number.isFinite(point.time)&&point.time>=sample.source_ts&&point.time<=glass.close_ts&&
            Number.isFinite(point.btc)&&point.btc>0&&Number.isFinite(point.e9)&&point.e9>0&&
            (index===0||point.time>points[index-1].time));
      })||null;
    }
    return view;
  }
  requestDraw(){if(!this.raf)this.raf=requestAnimationFrame(()=>{this.raf=0;this.draw();});}
  localPoint(e){const r=this.canvas.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
  down(e){
    if(e.pointerType==='touch'){
      this.touches.set(e.pointerId,this.localPoint(e));
      this.canvas.setPointerCapture(e.pointerId);
      if(this.touches.size===2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        const span=this.viewSpan();this.pinch={distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),span,anchor:this.end-span+(mid-this.left)/this.plotW*span};
        this.drag=null;this.freezeViewport();this.tooltip.classList.add('hidden');return;
      }
      if(this.touches.size>2)return;
    }
    if(e.button!==0)return;const p=this.localPoint(e);this.canvas.focus();this.canvas.setPointerCapture(e.pointerId);let mode='pan';if(p.x>this.w-73)mode='scale';else if(Math.abs(p.y-this.divider)<7)mode='divider';this.drag={...p,end:this.end,span:this.viewSpan(),mode,moved:false,range:this.range?{...this.range}:null};}
  move(e){const p=this.localPoint(e);this.pointer=p;
    if(e.pointerType==='touch'&&this.touches.has(e.pointerId)){
      this.touches.set(e.pointerId,p);
      if(this.pinch&&this.touches.size>=2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        this.span=Math.max(300,Math.min(64800,this.pinch.span*this.pinch.distance/Math.max(1,Math.hypot(a.x-b.x,a.y-b.y))));
        this.viewportSpan=this.span;
        this.end=this.pinch.anchor+(1-(mid-this.left)/this.plotW)*this.span;
        this.manualY=null;this.saveSpan();this.requestDraw();return;
      }
    }
    if(this.drag){const d=this.drag;d.moved=d.moved||Math.abs(p.x-d.x)+Math.abs(p.y-d.y)>4;
      if(d.mode==='scale'&&d.range){const mid=(d.range.high+d.range.low)/2,half=(d.range.high-d.range.low)/2*Math.exp((p.y-d.y)/110);this.manualY={low:Math.max(1,mid-half),high:mid+half};}
      else if(d.mode==='divider'){this.ratio=Math.max(.5,Math.min(.87,p.y/Math.max(200,this.h)));}
      else{this.follow=false;this.viewportSpan=d.span;this.end=d.end-(p.x-d.x)*d.span/this.plotW;this.manualY=null;}
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
    else{const old=this.follow?this.span:this.viewSpan(),f=(Math.max(0,Math.min(this.plotW,p.x-this.left)))/this.plotW;const anchor=this.end-this.viewSpan()+f*this.viewSpan();this.span=Math.max(300,Math.min(64800,old*Math.exp(e.deltaY*.0015)));this.viewportSpan=this.span;if(this.follow)this.syncLiveViewport();else this.end=anchor+(1-f)*this.span;this.saveSpan();this.manualY=null;}this.requestDraw();}
  x(t){return this.left+(t-(this.end-this.viewSpan()))/this.viewSpan()*this.plotW;}
  y(v){return this.top+(this.range.high-v)/(this.range.high-this.range.low)*(this.mainBottom-this.top);}
  qy(v){return this.quoteBottom-v*(this.quoteBottom-this.quoteTop);}
  clock(t,seconds=false){return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{}),hour12:false}).format(new Date(t*1000));}
  price(v,d=2){return Number.isFinite(v)?v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';}
  text(s,x,y,color='#7897a9',size=10,align='left'){const c=this.ctx;c.fillStyle=color;c.font=`${size*this.fontScale}px "Segoe UI",sans-serif`;c.textAlign=align;c.fillText(s,x,y);c.textAlign='left';}
  line(x1,y1,x2,y2,color,width=1,dash=[]){const c=this.ctx;c.beginPath();c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();c.setLineDash([]);}
  badge(s,y,color){const c=this.ctx;const yy=Math.max(this.top+8,Math.min(this.mainBottom-8,y));c.fillStyle=color;c.fillRect(this.w-73,yy-10,73,20);this.text(s,this.w-5,yy+3,'#07141c',10,'right');}
  drawLookingGlass(view){
    if(!view.paths.length)return;
    const c=this.ctx,start=this.x(view.glass.source_ts),end=this.x(view.glass.close_ts);
    if(end<this.left||start>this.w-74)return;
    if(view.issued){
      c.save();c.beginPath();c.rect(this.left,this.top,this.plotW,this.mainBottom-this.top);c.clip();
      c.beginPath();c.strokeStyle='#d1e2ef82';c.lineWidth=1.4;c.setLineDash([2,6]);
      view.issued.path.points.forEach((point,index)=>{const x=this.x(point.time),y=this.y(point.btc);if(index===0)c.moveTo(x,y);else c.lineTo(x,y);});c.stroke();c.setLineDash([]);c.restore();
      this.text('ISSUED '+this.clock(view.issued.issued_at_ts)+' · FIXED',Math.max(this.left+5,this.x(view.issued.source_ts)+5),this.mainBottom-10,'#a5b7c5',9);
    }
    c.save();c.beginPath();c.rect(Math.max(this.left,start),this.top,Math.max(0,Math.min(end,this.w-74)-Math.max(this.left,start)),this.mainBottom-this.top);c.clip();
    c.fillStyle='#6595ba0a';c.fillRect(start,this.top,end-start,this.mainBottom-this.top);
    const colors={CONTINUATION:'#65c9fa',ROTATION_STALL:'#b7a0ec',REVERSAL:'#edaa65',PATTERN:'#bcffb0'};
    const ordered=[...view.paths].sort((a,b)=>Number(a.id===view.active?.path_id)-Number(b.id===view.active?.path_id));
    for(const path of ordered){
      const featured=path.id===view.active?.path_id;
      for(const field of ['btc','e9']){
        c.beginPath();c.strokeStyle=(featured?'#bcffb0':colors[path.family])+(featured?(field==='btc'?'ff':'b8'):(view.active?(field==='btc'?'45':'28'):(field==='btc'?'a0':'55')));
        c.lineWidth=featured?(field==='btc'?3:1.8):(field==='btc'?1.15:.8);
        c.setLineDash(field==='btc'?(featured?[10,5]:[7,5]):[2,5]);
        path.points.forEach((point,index)=>{const x=this.x(point.time),y=this.y(point[field]);if(index===0)c.moveTo(x,y);else c.lineTo(x,y);});
        c.stroke();
      }
      if(featured){const point=path.points.at(-1);c.setLineDash([]);c.beginPath();c.strokeStyle='#bcffb0';c.lineWidth=2;c.arc(this.x(point.time),this.y(point.btc),3.5,0,Math.PI*2);c.stroke();}
    }
    c.setLineDash([]);c.restore();
    if(start>=this.left&&start<=this.w-74){this.line(start,this.top,start,this.mainBottom,'#a9cbd4a0',1,[3,5]);this.text('NOW',start+5,this.top+13,'#b3d4dc',9);}
    if(end>=this.left&&end<=this.w-74){this.line(end,this.top,end,this.mainBottom,'#8bb5c18c',1,[3,5]);this.text('CLOSE '+this.clock(view.glass.close_ts),end-5,this.top+(end-start<125*this.fontScale?28:13),'#8baab8',9,'right');}
    if(end-start>130)this.text('CONDITIONAL PATHS',Math.max(this.left+5,start+6),this.top+29,'#668ba1',8);
    if(view.active&&end-start>180*this.fontScale){
      this.text('ACTIVE · '+view.active.label.toUpperCase(),Math.max(this.left+5,start+6),this.top+47,'#bcffb0',9);
      if(view.active.horizon_ts<view.glass.close_ts)this.text('SHAPE ENDS '+this.clock(view.active.horizon_ts),Math.max(this.left+5,start+6),this.top+63,'#b5d8b4',8);
    }
  }
  draw(){
    const r=this.canvas.parentElement.getBoundingClientRect();this.w=Math.max(1,Math.floor(r.width));this.h=Math.max(1,Math.floor(r.height));const dpr=window.devicePixelRatio||1;
    if(this.canvas.width!==Math.round(this.w*dpr)||this.canvas.height!==Math.round(this.h*dpr)){this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);}
    const c=this.ctx;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,this.w,this.h);
    if(this.w<160||this.h<180){this.text('Expand chart to inspect',this.w/2,this.h/2,'#829daa',10,'center');return;}
    this.left=10;this.top=13;this.plotW=this.w-85;this.divider=Math.floor(Math.min(this.h*this.ratio,this.h-90));this.mainBottom=this.divider-15;this.quoteTop=this.divider+29;this.quoteBottom=this.h-28;
    if(!this.data||!this.data.candles?.length)return;
    const span=this.viewSpan(),from=this.end-span,scenarios=this.scenarioView();const bars=this.data.candles.filter(b=>b.time>=from-60&&b.time<=this.end+60);const emas=this.data.emas.filter(b=>b.time>=from-60&&b.time<=this.end+60);
    const vals=bars.flatMap(b=>[b.low,b.high]);emas.forEach(e=>{if(Number.isFinite(e.e9))vals.push(e.e9);if(Number.isFinite(e.e30))vals.push(e.e30);});
    for(const path of scenarios.paths)for(const point of path.points)if(point.time>=from&&point.time<=this.end)vals.push(point.btc,point.e9);
    if(scenarios.issued)for(const point of scenarios.issued.path.points)if(point.time>=from&&point.time<=this.end)vals.push(point.btc);
    if(this.fitTarget)this.data.targets.filter(t=>t.start_ts<this.end&&(t.close_ts??this.end)>from).forEach(t=>vals.push(t.target));
    if(!vals.length){this.text('No recorded candles in this window · Return to Live →',this.w/2,this.h/2,'#829daa',12,'center');return;}
    let low=Math.min(...vals),high=Math.max(...vals),padding=Math.max(3,(high-low)*.16);this.range=this.manualY||{low:Math.max(1,low-padding),high:high+padding};
    // Grid and quarter-hour fenceposts preserve a continuous time axis.
    const rawStep=(this.range.high-this.range.low)/6,mag=10**Math.floor(Math.log10(rawStep));let step=[1,2,2.5,5,10].find(x=>x*mag>=rawStep)*mag;
    for(let v=Math.ceil(this.range.low/step)*step;v<=this.range.high;v+=step){const y=this.y(v);this.line(this.left,y,this.w-74,y,'#16314299');this.text(this.price(v,step<1?2:0),this.w-8,y+3,'#7294a7',10,'right');}
    const tick=span>10800?3600:span>5400?900:300;
    for(let t=Math.floor(from/tick)*tick;t<=this.end;t+=tick){const x=this.x(t);if(x<this.left)continue;const major=t%900===0;this.line(x,this.top,x,this.quoteBottom,major?'#3b687d99':'#17314188',1,major?[4,4]:[]);this.text(this.clock(t),x,this.h-9,major?'#a0bac9':'#658399',9,'center');}
    this.line(this.w-74,0,this.w-74,this.h,'#2d495b');this.line(0,this.divider,this.w,this.divider,'#2c4d61');
    this.text('NATIVE CONTRACT QUOTES',14,this.divider+18,'#85a3b5',9);this.text('0–1 · bid / ask · gaps remain gaps',this.w-86,this.divider+18,'#5d8196',8,'right');
    for(const v of [0,.5,1]){const y=this.qy(v);this.line(this.left,y,this.w-74,y,'#152e3c');this.text(v.toFixed(2),this.w-8,y+3,'#7294a7',9,'right');}
    c.save();c.beginPath();c.rect(this.left,0,this.plotW,this.mainBottom+10);c.clip();
    if(this.selected){const a=this.x(this.selected.entry_ts),b=this.x(this.selected.exit_ts??this.data.market.time);c.fillStyle='#1d7a8d1c';c.fillRect(a,this.top,Math.max(2,b-a),this.mainBottom-this.top);this.line(a,this.top,a,this.mainBottom,'#35c2d77a',1,[2,3]);}
    for(const target of this.data.targets){if(!target.target||target.start_ts>this.end||(target.close_ts??this.end)<from)continue;const y=this.y(target.target);const active=target.ticker===this.data.market.ticker;this.line(Math.max(this.left,this.x(target.start_ts)),y,Math.min(this.w-74,this.x(target.close_ts??this.end)),y,active?'#efbd5baa':'#99784c66',1,[5,4]);if(active&&y>20&&y<this.mainBottom-10)this.text('TO BEAT  $'+this.price(target.target),Math.min(this.w-87,this.x(target.close_ts??this.end)-6),y-7,'#e6b559',10,'right');}
    const bodyWidth=Math.max(1,Math.min(20,this.plotW*60/span*.62));
    for(const b of bars){const x=this.x(b.time),up=b.close>=b.open,color=up?'#35cdb4':'#ec8575';const yOpen=this.y(b.open),yClose=this.y(b.close);this.line(x,this.y(b.high),x,this.y(b.low),color,1);const top=Math.min(yOpen,yClose),height=Math.max(1,Math.abs(yOpen-yClose));c.fillStyle=up?'#34c7b49e':'#e47b6bac';c.fillRect(x-bodyWidth/2,top,bodyWidth,height);if(b.quality==='sampled'){c.strokeStyle=color;c.lineWidth=1;c.setLineDash([2,2]);c.strokeRect(x-bodyWidth/2,top,bodyWidth,height);c.setLineDash([]);}else if((b.complete===false&&b.quality!=='sampled')){c.strokeStyle='#37cede';c.lineWidth=1.3;c.strokeRect(x-bodyWidth/2,top,bodyWidth,height);}else{c.fillStyle=color;c.fillRect(x-bodyWidth/2,top,bodyWidth,height);}}
    for(const [field,color]of[['e30','#e8ad51'],['e9','#37cede']]){c.beginPath();c.strokeStyle=color;c.lineWidth=field==='e9'?1.8:1.5;let previous=null;for(const e of emas){if(!Number.isFinite(e[field])){previous=null;continue;}const x=this.x(e.time),y=this.y(e[field]);if(!Number.isFinite(y)){previous=null;continue;}if(previous===null||e.time-previous>90)c.moveTo(x,y);else c.lineTo(x,y);previous=e.time;}c.stroke();}
    this.drawLookingGlass(scenarios);
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
    this.crosshair(bars,scenarios);
    if(typeof this.onViewport==='function')this.onViewport({follow:this.follow,span:this.span,visibleSpan:span,end:this.end});
  }
  crosshair(bars,scenarios=this.scenarioView()){if(!this.pointer||this.drag||this.pointer.x<this.left||this.pointer.x>this.w-75){this.tooltip.classList.add('hidden');return;}
    const p=this.pointer,span=this.viewSpan(),t=this.end-span+(p.x-this.left)/this.plotW*span;this.line(p.x,this.top,p.x,this.quoteBottom,'#719aa175',1,[3,3]);if(p.y<this.mainBottom)this.line(this.left,p.y,this.w-75,p.y,'#719aa14d',1,[3,3]);
    if(scenarios.paths.length&&t>scenarios.glass.source_ts&&t<=scenarios.glass.close_ts&&p.y<this.mainBottom){
      const lines=[this.clock(t)+' ET · CONDITIONAL','Possible paths, not observed prices'];
      if(scenarios.active){const active=scenarios.paths.find(path=>path.id===scenarios.active.path_id);if(t<=active.points.at(-1).time)lines.push('ACTIVE · '+scenarios.active.label+': '+this.price(active.points.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b).btc));else lines.push('Active historical shape has ended');}
      for(const [family,label]of [['CONTINUATION','Continuation'],['ROTATION_STALL','Rotation / stall'],['REVERSAL','Return / reversal']]){
        const values=scenarios.paths.filter(path=>path.family===family).map(path=>path.points.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b).btc);
        if(values.length)lines.push(label+': '+this.price(Math.min(...values))+(Math.max(...values)>Math.min(...values)?' – '+this.price(Math.max(...values)):''));
      }
      lines.push('Near the nearest scenario sample · no win probabilities');this.showTooltip(lines,p);return;
    }
    const b=bars.reduce((a,b)=>!a||Math.abs(b.time-t)<Math.abs(a.time-t)?b:a,null);if(!b||Math.abs(b.time-t)>45){this.tooltip.classList.add('hidden');return;}
    const ema=this.data.emas.find(e=>e.time===b.time);const lines=[this.clock(b.time)+' ET · 1 minute',`O ${this.price(b.open)}   H ${this.price(b.high)}`,`L ${this.price(b.low)}   C ${this.price(b.close)}`,b.quality==='sampled'?'SAMPLED OHLC · extremes may be missing':b.complete===false?'DEVELOPING TRADE BAR · not complete':'COMPLETED SOURCE BAR · '+(b.source||b.quality)];
    if(Number.isFinite(b.first_observed_in_scan))lines.push('Earliest scanned observation '+this.clock(b.first_observed_in_scan,true)+' ET');
    else if(Number.isFinite(b.known_at))lines.push('Snapshot observation '+this.clock(b.known_at,true)+' ET');
    if(ema)lines.push(`NAEVYR ${this.price(ema.e9)}  THAERYON ${this.price(ema.e30)}`);
    this.showTooltip(lines,p);
  }
  showTooltip(lines,p){this.tooltip.textContent=lines.join('\n');this.tooltip.classList.remove('hidden');this.tooltip.style.left=Math.max(6,Math.min(this.w-290,p.x+15))+'px';this.tooltip.style.top=Math.max(5,Math.min(this.h-170,p.y+15))+'px';}
}
window.NautilusChart=NautilusChart;
