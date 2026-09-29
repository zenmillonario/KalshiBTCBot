from __future__ import annotations
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
    m.update(version='V9.5D-666-TERRITORY-PAPER-04-CAMPAIGN-CONTEXT',hotfix_id='666-TERRITORY-PAPER-04-CAMPAIGN-CONTEXT',
      strategy_parameters_changed=False,entry_authority_changed=True,paper_sizing_changed=False,
      emergency_stop_changed=False,winner_harvest_changed=True,profit_vault_changed=True,
      territory_authority_paper='Campaign context-only + Master-of-Borders tight authority + EMA9/Price-Leg sideways court + qualified local Prodigal edge bypass',
      profit_vault='One-time 90% ROI vault: sell 60% ordinary high winner / 25% OBS4.2-style LEVIATHAN candidate',
      runtime_io_hotfix='DATAHOLD: frozen HF2 runtime source unchanged; 30s unresolved watchdog becomes paused hold until quote recovery')
    hf2.write_json(run/'launcher_manifest.json',m)
    for p in (HERE/'tachys_666_territory_paper.py',HERE/'territory_patch.py'):
        if p.is_file():shutil.copyfile(p,run/'source'/p.name)
    return run,m
def main(argv=None):
    patches.transform=_transform;hf2.make_session=_session;hf2.VERSION='V9.5D-666-TERRITORY-PAPER-04-CAMPAIGN-CONTEXT';hf2.HOTFIX_ID='666-TERRITORY-PAPER-04-CAMPAIGN-CONTEXT'
    return hf2.main(argv)
if __name__=='__main__':raise SystemExit(main())
