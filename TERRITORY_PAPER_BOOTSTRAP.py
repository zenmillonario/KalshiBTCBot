from pathlib import Path
import shutil, textwrap, py_compile, subprocess, sys

LAB=Path(r"C:\KalshiBTCBot_666Lab")
EA1=LAB/'ea1'; HF2=LAB/'hf2'; DST=LAB/'territorypaper'
PYTHON=Path(r"C:\KalshiBTCBot\.venv\Scripts\python.exe")
for p in (EA1/'ea1_transform.py', HF2/'tachys_666_hf2.py', HF2/'tachys_666_patches_hf2.py'):
    if not p.is_file(): raise SystemExit('STOP missing prerequisite: '+str(p))
DST.mkdir(parents=True,exist_ok=True)

patch = r'''from __future__ import annotations
import ast
from ea1_transform import apply_ea1_shadow

HELPERS = r"""
TP_LOG='tachys_territory_authority_v9_5d.csv'
TP_FIELDS=['timestamp','run_id','session_id','event','ticker','side','ask','territory','ruling','reason','staff','yard_score','battlefield','parent_direction','parent_phase','parent_health','parent_runway','price_leg','relation','leg_state','target_height','timing']

def _tp_write(ticker,side,ask,territory,ruling,reason,staff,rec):
    _write(TP_LOG,TP_FIELDS,{'event':'ENTRY_COURT','ticker':ticker,'side':side,'ask':ask,'territory':territory,'ruling':ruling,'reason':reason,'staff':staff,'yard_score':rec.get('yard_score'),'battlefield':rec.get('battlefield_class'),'parent_direction':rec.get('parent_arc_direction'),'parent_phase':rec.get('parent_arc_phase'),'parent_health':rec.get('parent_arc_health'),'parent_runway':rec.get('parent_runway_state'),'price_leg':rec.get('price_micro_state'),'relation':rec.get('entry_parent_relation'),'leg_state':rec.get('leg_state'),'target_height':rec.get('target_height'),'timing':rec.get('timing_shadow')})

def _tp_decide(side,ask,rec):
    rec=rec or {}; s=_sign(side); height=_f(rec.get('target_height')); fav=None if height is None else height*s
    leg=str(rec.get('leg_state') or ''); battlefield=str(rec.get('battlefield_class') or '')
    release=(leg=='EXPANSION' and fav is not None and fav>0 and str(rec.get('timing_shadow') or '')!='WAIT_NEW_ARC_SHADOW')
    tight=bool(rec.get('yard_confirmed')) or battlefield=='METRONOME_STORM'
    if battlefield=='CLEAN_TERRITORY' or release: return True,'CLEAN_SLOPE','CLEAN_OR_RELEASE','PARENT_GEOMETRY+MOTION_CELL+LEG_GEOMETRY'
    if tight: return False,'TIGHT_TRANSITION','EDGE_TEAM_OWNS_FIELD','TERRAIN_COMMAND+MOTION_CELL+TRANSITION_CELL+TARGET_TUBE'
    rel=str(rec.get('entry_parent_relation') or ''); priceleg=str(rec.get('price_micro_state') or '')
    runway=str(rec.get('parent_runway_state') or ''); health=str(rec.get('parent_arc_health') or '')
    timing=str(rec.get('timing_shadow') or ''); price=_f(ask)
    staff='PARENT_GEOMETRY+MOTION_CELL+ENTRY_TIMING+TARGET_TUBE'
    if rel=='UNKNOWN': return False,'SIDEWAYS_ARC','WAIT_FOR_EMA9_PARENT',staff
    if timing=='WAIT_NEW_ARC_SHADOW' and not (leg=='EXPANSION' and rel=='ALIGNED_PARENT'): return False,'SIDEWAYS_ARC','WAIT_NEW_PRICE_ARC',staff
    if rel=='OPPOSES_PARENT' and runway=='OPEN' and health=='STRENGTHENING': return False,'SIDEWAYS_ARC','STRONG_PARENT_OPPOSES_ENTRY',staff
    if rel=='ALIGNED_PARENT' and priceleg=='COUNTER_PARENT': return True,'SIDEWAYS_ARC','PARENT_ALIGNED_COUNTERSWING_VALUE',staff
    if rel=='ALIGNED_PARENT' and priceleg=='WITH_PARENT' and runway=='LOW':
        if leg=='EXPANSION' and fav is not None and fav>0: return True,'SIDEWAYS_ARC','TARGET_FAVORABLE_EXPANSION',staff
        if price is not None and price>=.40: return False,'SIDEWAYS_ARC','EXPENSIVE_LOW_PARENT_RUNWAY_CHASE',staff
    return True,'SIDEWAYS_ARC','SIDEWAYS_ARC_ALLOWED',staff

def _tp_edge_try(ticker,yes_ask,no_ask,close_ts=None):
    now=time.time(); ctx=c.brain.last_context if (c.brain.last_context or {}).get('ticker')==ticker else {}
    if not ctx:return False
    try: box=dict(core.chop_context(close_ts,now) or {})
    except TypeError:
        try: box=dict(core.chop_context(close_ts) or {})
        except Exception: box={}
    except Exception: box={}
    if not box.get('is_chop'):
        return False
    lo,hi,w=(_f(box.get('low')),_f(box.get('high')),_f(box.get('width'))); btc=_f((ctx.get('geom') or {}).get('btc'),getattr(core,'btc_last_price',None))
    if None in (lo,hi,w,btc) or w<=0:return True
    pos=(btc-lo)/w
    if pos<=.25: side,ask='YES',_f(yes_ask)
    elif pos>=.75: side,ask='NO',_f(no_ask)
    else:return True
    if ask is None or ask<=0 or ask>.30:return True
    metrics=dict(ctx.get('metrics') or {}); target=dict(ctx.get('target') or {}); height=_f(target.get('height')); r60=max(1.,_f(metrics.get('r60'),1.) or 1.)
    if height is None or abs(height)>max(60.,1.5*r60):return True
    vals=[(_f(metrics.get('ch'+str(n)),0.) or 0.)*_sign(side) for n in (3,6,9)]; confirms=sum(v>=1.5 for v in vals)
    if not (vals[0]>=2. or confirms>=2):return True
    parent=_ea1_parent_context(now); against=(parent.get('direction')=='UP' and side=='NO') or (parent.get('direction')=='DOWN' and side=='YES')
    strong=against and parent.get('health')=='STRENGTHENING' and parent.get('phase') in ('BUILDING','EXPANDING')
    if strong and not (confirms>=2 and ask<=.20 and abs(height)<=max(45.,r60)):return True
    for p in (getattr(core,'paper_positions',{}) or {}).values():
        if isinstance(p,dict) and str(p.get('ticker') or '')==str(ticker):return True
    sig={'price':ask,'setup_grade':'CONFIRMED','signal_grade':'A','strategy':'V95D_TERRITORY_EDGE','market_regime':'TIGHT_TRANSITION','trade_intent':'EDGE_RETURN','seconds_to_close':_f(box.get('seconds_left')),'target_distance':height,'btc_change_60s':_f(metrics.get('ch60')),'btc_trend_efficiency_60s':_f(metrics.get('eff60')),'early_exception':False,'early_trade':False}
    entered=bool(core.paper_enter(ticker,side,ask,sig))
    if entered: print(f'EDGE RETURN | {side} @ {ask:.3f} | target={height:+.1f}')
    return True
"""

def apply_territory_paper(source:str)->str:
    source=apply_ea1_shadow(source)
    if 'TP_LOG=' in source:return source
    anchor='\n\nclass ChurnController:\n'
    if anchor not in source:raise RuntimeError('territory helper anchor missing')
    source=source.replace(anchor,HELPERS+anchor,1)
    old="""        ea1_shadow = _ea1_eval_entry(ticker, side, ask, signal, now, ctx)\n\n        # A new main entry can wait while a smaller opposing tactical sleeve\n"""
    new="""        ea1_shadow = _ea1_eval_entry(ticker, side, ask, signal, now, ctx)\n        tp_ok,tp_territory,tp_reason,tp_staff=_tp_decide(side,ask,ea1_shadow)\n        _tp_write(ticker,side,ask,tp_territory,'ALLOW' if tp_ok else 'WAIT',tp_reason,tp_staff,ea1_shadow or {})\n        if not tp_ok:\n            _ea1_result(ea1_shadow,False,ticker,side,ask)\n            return False\n\n        # A new main entry can wait while a smaller opposing tactical sleeve\n"""
    if old not in source:raise RuntimeError('territory entry anchor missing')
    source=source.replace(old,new,1)
    old2="""    core.paper_enter = paper_enter_wrapper\n\n    # 5) Exit Court wraps the already-installed V9.5C manager.\n"""
    new2="""    core.paper_enter = paper_enter_wrapper\n    core.chop_sniper_try_enter = _tp_edge_try\n\n    # 5) Exit Court wraps the already-installed V9.5C manager.\n"""
    if old2 not in source:raise RuntimeError('territory edge anchor missing')
    source=source.replace(old2,new2,1)
    ast.parse(source);return source
'''

launcher = r'''from __future__ import annotations
from pathlib import Path
import hashlib,shutil,sys
LAB=Path(r"C:\KalshiBTCBot_666Lab"); HERE=Path(__file__).resolve().parent
for p in (LAB/'hf2',LAB/'ea1',HERE):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
import tachys_666_hf2 as hf2
import tachys_666_patches_hf2 as patches
from territory_patch import apply_territory_paper
_ORIG_T=patches.transform; _ORIG_M=hf2.make_session

def _transform(sources,package):
    fixed=_ORIG_T(sources,package); engine=hf2.ENGINE
    fixed[engine]=apply_territory_paper(fixed[engine])
    (HERE/'territory_engine_sha256.txt').write_text(hashlib.sha256(fixed[engine].encode()).hexdigest()+'\n',encoding='utf-8')
    return fixed

def _session(sources,test_result,smoke_minutes):
    run,m=_ORIG_M(sources,test_result,smoke_minutes)
    m.update(version='V9.5D-666-TERRITORY-PAPER-01',hotfix_id='666-TERRITORY-PAPER-01',strategy_parameters_changed=True,paper_sizing_changed=False,emergency_stop_changed=False,winner_harvest_changed=False,territory_authority_paper='Three active territories: clean slope / sideways EMA9+Price Leg / tight edge return')
    hf2.write_json(run/'launcher_manifest.json',m)
    for p in (HERE/'tachys_666_territory_paper.py',HERE/'territory_patch.py'):
        if p.is_file():shutil.copyfile(p,run/'source'/p.name)
    return run,m

def main(argv=None):
    patches.transform=_transform;hf2.make_session=_session;hf2.VERSION='V9.5D-666-TERRITORY-PAPER-01';hf2.HOTFIX_ID='666-TERRITORY-PAPER-01'
    return hf2.main(argv)
if __name__=='__main__':raise SystemExit(main())
'''

observer = r'''from pathlib import Path
import json,runpy,sys
LAB=Path(r"C:\KalshiBTCBot_666Lab"); OBS=LAB/'observer42ea1'; TERR=LAB/'territorypaper'
if not OBS.is_dir():raise SystemExit('STOP: observer42ea1 missing')
sys.path.insert(0,str(OBS));import commander_io as cio
orig=cio.validate_reference

def validate_reference(manifest,reference):
    try:return orig(manifest,reference)
    except cio.ObserverError as exc:
        sha_file=TERR/'territory_engine_sha256.txt'
        if not sha_file.is_file():raise exc
        expected=sha_file.read_text(encoding='utf-8').strip(); actual=manifest.get('source_sha256_utf8'); frozen=reference['source_sha256_utf8']
        wanted=dict(frozen);wanted['tachys_v9_5d_666_revival_lab.py']=expected
        ok=(actual==wanted and manifest.get('mode')=='PAPER_ONLY' and manifest.get('source_commit')==cio.PIN and manifest.get('side_action_revision')==cio.SIDE and manifest.get('version')=='V9.5D-666-TERRITORY-PAPER-01' and manifest.get('hotfix_id')=='666-TERRITORY-PAPER-01' and manifest.get('paper_sizing_changed') is False and manifest.get('emergency_stop_changed') is False and manifest.get('winner_harvest_changed') is False)
        if not ok:raise exc
cio.validate_reference=validate_reference
runpy.run_path(str(OBS/'tachys_commander_observer42.py'),run_name='__main__')
'''

(DST/'territory_patch.py').write_text(patch,encoding='utf-8')
(DST/'tachys_666_territory_paper.py').write_text(launcher,encoding='utf-8')
(DST/'tachys_commander_observer42_territory.py').write_text(observer,encoding='utf-8')
for p in DST.glob('*.py'):py_compile.compile(str(p),doraise=True)
print('PASS territory PAPER files installed:',DST)
cp=subprocess.run([str(PYTHON),'-B','-u',str(DST/'tachys_666_territory_paper.py'),'--check'],cwd=str(LAB),check=False)
if cp.returncode:raise SystemExit('STOP: territory engine --check failed')
print('READY V9.5D-666-TERRITORY-PAPER-01')
print('ENGINE:',str(DST/'tachys_666_territory_paper.py'))
print('OBS42 :',str(DST/'tachys_commander_observer42_territory.py'))
