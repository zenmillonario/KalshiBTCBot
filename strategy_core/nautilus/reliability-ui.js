/* Pure presentation rules, tested independently of the browser. No trading authority. */
'use strict';
(() => {
  const finite = n => typeof n === 'number' && Number.isFinite(n);
  function timer(state, now, connected) {
    const r=state?.run||{}, c=state?.clock||{};
    if(r.review)return {running:false,text:'ARCHIVE',close:c.close_ts};
    if(r.stopped)return {running:false,text:'ENDED',close:c.close_ts};
    const valid=connected&&r.fresh&&!r.pointer_changed&&c.verified&&c.clock?.continuous&&
      finite(c.close_ts)&&finite(c.valid_until)&&now<=c.valid_until&&finite(r.updated)&&
      now>=r.updated&&now-r.updated<=5;
    if(!valid)return {running:false,text:'—:—',close:c.close_ts,reason:c.status||'UNVERIFIED'};
    const seconds=Math.max(0,c.close_ts-now);
    if(seconds>905)return {running:false,text:'—:—',close:c.close_ts,reason:'INVALID_CLOSE'};
    return {running:true,text:String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(Math.floor(seconds%60)).padStart(2,'0'),
            seconds,close:c.close_ts,reason:seconds===0?'AWAITING_NEXT_CONTRACT':'VERIFIED_CONTRACT_CLOCK'};
  }
  function health(detail,name,now,connected,stopped) {
    let status=detail?.status||'UNAVAILABLE';
    const age=finite(detail?.updated)?now-detail.updated:null;
    if(!connected&&status==='CURRENT')status='CONNECTION_LOST';
    if(!stopped&&status==='CURRENT'&&finite(age)){
      const ttl=name==='price'||name==='quotes'?3:5;
      if(age<0||age>ttl)status='STALE';
    }
    const bad=['FAILED','READ_ERROR','UNVERIFIED','CLOCK_UNTRUSTED'];
    return {status,age,color:bad.includes(status)?'red':['CURRENT','READY'].includes(status)?'green':['STOPPED','LAST_RECORDED','ARCHIVE'].includes(status)?'muted':'amber'};
  }
  const api={timer,health};
  if(typeof window!=='undefined')window.NautilusReliability=api;
  if(typeof module!=='undefined')module.exports=api;
})();
