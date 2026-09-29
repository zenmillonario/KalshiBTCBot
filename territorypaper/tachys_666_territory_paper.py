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

    # PAPER-03 IO3: leave frozen HF2 runtime source untouched.
    # Install a narrow in-memory wrapper from the transformed engine before
    # hf2.install(). This avoids the launcher package-copy overwrite and keeps
    # run/source integrity identical to the manifest.
    eng=fixed[engine]
    old_hook="""    install_v95d_hooks()
    import tachys_666_runtime_hf2 as hf2
    hf2.install(core, execution_shadow, supervisor, side_policy={k: globals()[k] for k in hf2.SIDE_POLICY_KEYS})
"""
    new_hook="""    install_v95d_hooks()
    import tachys_666_runtime_hf2 as hf2
    import tachys_666_io_hf2 as hf2io

    _tp_atomic_json_original = hf2.atomic_json
    def _tp_runtime_checkpoint_json(path, payload):
        is_runtime_state = hf2.Path(path).name == hf2.STATE_FILE
        now_mono = time.monotonic()
        retry_after = float(getattr(_tp_runtime_checkpoint_json, '_retry_after', 0.0) or 0.0)
        if is_runtime_state and now_mono < retry_after:
            return None
        try:
            result = _tp_atomic_json_original(path, payload)
            if is_runtime_state and getattr(_tp_runtime_checkpoint_json, '_degraded', False):
                print('CHECKPOINT IO | RECOVERED | runtime telemetry publication resumed')
            if is_runtime_state:
                _tp_runtime_checkpoint_json._degraded = False
                _tp_runtime_checkpoint_json._retry_after = 0.0
            return result
        except hf2io.CheckpointIOError as exc:
            locked_runtime_state = (
                is_runtime_state
                and getattr(exc, 'safe_file', None) == hf2.STATE_FILE
                and getattr(exc, 'operation', None) == 'replace_checkpoint'
                and getattr(exc, 'os_winerror', None) in (5, 32, 33)
            )
            if not locked_runtime_state:
                raise
            _tp_runtime_checkpoint_json._degraded = True
            _tp_runtime_checkpoint_json._retry_after = time.monotonic() + 1.5
            last_warn = float(getattr(_tp_runtime_checkpoint_json, '_last_warn', 0.0) or 0.0)
            if now_mono - last_warn >= 5.0:
                _tp_runtime_checkpoint_json._last_warn = now_mono
                print('CHECKPOINT IO | TELEMETRY_STALE_CONTINUE | ' + hf2io.error_detail(exc))
            return None

    hf2.atomic_json = _tp_runtime_checkpoint_json
    hf2.install(core, execution_shadow, supervisor, side_policy={k: globals()[k] for k in hf2.SIDE_POLICY_KEYS})
"""
    if old_hook not in eng:raise RuntimeError('IO3 engine hook anchor missing')
    eng=eng.replace(old_hook,new_hook,1)
    import ast
    ast.parse(eng)
    fixed[engine]=eng

    (HERE/'territory_engine_sha256.txt').write_text(hashlib.sha256(fixed[engine].encode()).hexdigest()+'\n',encoding='utf-8')
    return fixed
def _session(sources,test_result,smoke_minutes):
    run,m=_ORIG_M(sources,test_result,smoke_minutes)
    m.update(version='V9.5D-666-TERRITORY-PAPER-03-IO3',hotfix_id='666-TERRITORY-PAPER-03-IO3',
      strategy_parameters_changed=False,entry_authority_changed=True,paper_sizing_changed=False,
      emergency_stop_changed=False,winner_harvest_changed=True,profit_vault_changed=True,
      territory_authority_paper='Master-of-Borders tight authority + EMA9/Price-Leg sideways court + qualified local Prodigal edge bypass',
      profit_vault='One-time 90% ROI vault: sell 60% ordinary high winner / 25% OBS4.2-style LEVIATHAN candidate',
      runtime_io_hotfix='IO3: frozen runtime source unchanged; exact checkpoint-lock handler installed in memory before HF2 runtime install')
    hf2.write_json(run/'launcher_manifest.json',m)
    for p in (HERE/'tachys_666_territory_paper.py',HERE/'territory_patch.py'):
        if p.is_file():shutil.copyfile(p,run/'source'/p.name)
    return run,m
def main(argv=None):
    patches.transform=_transform;hf2.make_session=_session;hf2.VERSION='V9.5D-666-TERRITORY-PAPER-03-IO3';hf2.HOTFIX_ID='666-TERRITORY-PAPER-03-IO3'
    return hf2.main(argv)
if __name__=='__main__':raise SystemExit(main())
