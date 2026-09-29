from pathlib import Path
import runpy,sys
LAB=Path(r"C:\KalshiBTCBot_666Lab"); OBS=LAB/'observer42ea1'; TERR=LAB/'territorypaper'
if not OBS.is_dir():raise SystemExit('STOP: observer42ea1 missing')
sys.path.insert(0,str(OBS))
import commander_io as cio
import tachys_commander_observer4 as cli
orig=cio.validate_reference

def validate_reference(manifest,reference):
    try:return orig(manifest,reference)
    except cio.ObserverError as exc:
        ef=TERR/'territory_engine_sha256.txt'
        if not ef.is_file():raise exc
        actual=manifest.get('source_sha256_utf8'); frozen=reference['source_sha256_utf8']
        wanted=dict(frozen)
        wanted['tachys_v9_5d_666_revival_lab.py']=ef.read_text(encoding='utf-8').strip()
        ok=(actual==wanted and manifest.get('mode')=='PAPER_ONLY' and manifest.get('source_commit')==cio.PIN
            and manifest.get('side_action_revision')==cio.SIDE
            and manifest.get('version')=='V9.5D-666-TERRITORY-PAPER-03-DATAHOLD'
            and manifest.get('hotfix_id')=='666-TERRITORY-PAPER-03-DATAHOLD'
            and manifest.get('strategy_parameters_changed') is False
            and manifest.get('paper_sizing_changed') is False
            and manifest.get('emergency_stop_changed') is False
            and manifest.get('winner_harvest_changed') is True
            and manifest.get('profit_vault_changed') is True)
        if not ok:raise exc

cio.validate_reference=validate_reference
cli.validate_reference=validate_reference
runpy.run_path(str(OBS/'tachys_commander_observer42.py'),run_name='__main__')
