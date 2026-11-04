"""Bind actual installed audit/zoom observations and preservation; UI09 stays failed."""
import base64,hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core24-ui-audit-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261104-core24-maintenance-01')]
import maintain as m
from secret_scan import Scanner
native=m.context();assert native.config['generation']==5;m.PRIVATE=PRIVATE
def load(p):return json.loads(p.read_bytes())
baseline=load(PRIVATE/'baseline/observations.json');zoom=load(PRIVATE/'zoom200/observations.json')
def item(value,name):return next(x['data'] for x in value['observations'] if x['name']==name)
a=item(baseline,'actual_window_zoom_metrics');b=item(zoom,'actual_window_zoom_metrics')
assert a['outer_width']==b['outer_width']==1280 and a['dpr']==1 and b['dpr']==2
assert a['inner_width']==2*b['inner_width'] and a['inner_height']==2*b['inner_height']
for value in [baseline,zoom]:
    assert value['image']==native.config['image_id'] and not value['findings'] and not value['foreign_requests'] and not value['runtime_exceptions']
    assert len(value['observations'])==18
    for theme in ['light','dark']:
        modal=item(value,theme+'-native-modal-keyboard');assert all(x['inside_modal'] for x in modal['cycle'])
        assert modal['restored']['name']==modal['initiator']['name']=='Delete note'
        labels=item(value,theme+'-Labels-keyboard');assert labels['restored']['name']=='Edit labels'
        assert labels['fieldAX'][0]['role']=='textbox'
    for name in ['actual_window_zoom_metrics','Arabic-window-metrics']:
        metric=item(value,name);assert metric['scroll_width']==metric['root_width']
    arabic=item(value,'complete-Arabic-admin');assert arabic['lang']=='ar' and arabic['dir']=='rtl'
    assert all(any('\u0600'<=char<='\u06ff' for char in text) for text in arabic['headings'])
    assert item(value,'reduced-motion')==dict(reduce=True,active_animations=0)
for name in ['baseline','zoom200']:
    process=load(PRIVATE/name/'process.json');assert process['state']=='stopped' and process['exit']==dict(code=0,signal=None)
profile=Path(load(ROOT/'.local/g7-ui-core24-01/browser-input.json')['profile'])
command="$mpOwned='"+str(profile).replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert subprocess.check_output(['powershell','-NoProfile','-Command',command],stderr=subprocess.PIPE,timeout=30).strip() in (b'',b'[]',b'null')
backup=load(PRIVATE/'zoom-before.json');prefs=load(profile/'Default/Preferences');part=prefs.get('partition',{})
for key,row in backup['keys'].items():assert (key in part)==row['existed'] and part.get(key)==row['value']
data=m.snapshot('data-after',native);assert data==load(PRIVATE/'tables-before.json')
worker=m.worker(native);assert worker==load(PRIVATE/'worker-before.json')
old=load(PRIVATE/'runtimes-before.json')
rows=json.loads(subprocess.check_output(['docker','inspect',*[r['id'] for r in old]],stderr=subprocess.PIPE,timeout=30))
actual=[dict(id=r['Id'],image=r['Image'],started=r['State']['StartedAt'],pid=r['State']['Pid'],mounts=r['Mounts'],networks=r['NetworkSettings']['Networks']) for r in rows]
assert old==actual
values={k:base64.b64decode(v) for k,v in load(m.REFERENCE/'qualification-known-values-worker.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
public=list(OUT.glob('*.py'))+list(OUT.glob('*.mjs'))+[OUT/'preparation.json']
for folder in ['baseline','zoom200']:
    public+=[PRIVATE/folder/'observations.json',PRIVATE/folder/'network.json',PRIVATE/folder/'process.json',PRIVATE/folder/'edge.log']
assert not [f for path in public for f in scanner.inspect_file(path,str(path.relative_to(ROOT)))]
# Only selected already visually reviewed synthetic screenshots are public.
screens=[('baseline','dark-confirm.png'),('zoom200','dark-confirm.png'),('zoom200','Arabic-settings.png')]
for folder,name in screens:
    target=OUT/(folder+'-'+name);shutil.copyfile(PRIVATE/folder/name,target);public.append(target)
report=dict(result='qualified_core24_real_zoom_and_bounded_UI_observations_UI09_still_failed',utc=datetime.now(timezone.utc).isoformat(),
    image=native.config['image_id'],generation=5,actual_browser_runs=2,observed_cases=36,text_contrast_findings=0,
    actual_zoom=dict(baseline=a,zoom200=b,engine_zoom_without_device_metrics_override=True),
    verified=['Both themes sampled headings/controls/native fields/Labels text contrast; disabled controls excluded.',
              'Native confirmation keyboard cycling/Escape/initiator restoration; Labels names/Escape/initiator restoration.',
              'Fully loaded Arabic administration labels/document language/direction and English restoration.',
              'Real100/200percent English/Arabic no horizontal document overflow; reduced motion no active settled animations.',
              'Foreign record error alert semantics; native main/title textbox and command combobox semantics.',
              'Two browsers exit0/no owned-profile processes; selected zoom preferences restored; all17tables/four runtimes/independent worker exact.'],
    defects=['Dark native close glyph remains blank/indistinct at100percent: white-close filter also affects generic filled button background.',
             'Native Odoo confirmation has role=dialog but no accessible name. Actual AX name empty in both themes/zooms; upstream Dialog template supplies no aria-label/labelledby. Add title association through an owned template extension while retaining native behavior.'],
    remaining=['Apply minimal owned native-close styling/title-label extension through normal versioned candidate gates and installed proof.',
               'Narrow viewport/mixed text/locale formatting/pluralization and actual assistive-technology announcement scope still require final reconciliation; this is not a blanket WCAG2.2AA claim.',
               'Independent final-image reproduction/current final kit/privacy/fresh-developer installed path/fullG7 audit.'],
    primary_zoom_source='https://chromium.googlesource.com/chromium/src/+/lkgr/chrome/browser/ui/zoom/chrome_zoom_level_prefs.cc',
    zoom_source_scope='Default partition key x and default zoom-level dictionary; browser behavior independently verifies applied200percent. Only owned profile preferences changed.',
    privacy=dict(known_values=len(values),findings=0,private_table_streams_excluded=True,private_zoom_backup_excluded=True),
    evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in public},
    limits=['CSS contrast excludes filtered raster glyphs; visual review catches close icon independently.',
            'No physical screen-reader speech test; AX live-region/role inspection alone is not a spoken-announcement certification.',
            'Complete SQL snapshots/streams and profile preferences remain protected intentional private inputs, not clean public logs.',
            'No Save/Delete/Labels submission, new profile, Docker asset, lifecycle operation or app source overlay.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
for folder in ['baseline','zoom200']:
    for name in ['observations.json','network.json']:shutil.copyfile(PRIVATE/folder/name,OUT/(folder+'-'+name))
print(json.dumps(dict(result=report['result'],actual_zoom200=True,browser_runs=2,all17tables_exact=True,owned_preferences_restored=True,privacy_findings=0)))
