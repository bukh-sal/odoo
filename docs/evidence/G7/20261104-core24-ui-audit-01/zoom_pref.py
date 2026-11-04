"""Change only selected zoom keys in the closed project-owned browser profile."""
import json,math,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();PRIVATE=ROOT/'.local/g7-core24-ui-audit-01'
record=json.loads((ROOT/'.local/g7-ui-core24-01/browser-input.json').read_bytes());profile=Path(record['profile'])
assert profile.resolve()==(ROOT/'.local/g7-ui-qualification-01/profile').resolve()
command="$mpOwned='"+str(profile).replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert subprocess.check_output(['powershell','-NoProfile','-Command',command],stderr=subprocess.PIPE,timeout=30).strip() in (b'',b'[]',b'null'), 'Owned browser must be closed'
backup=json.loads((PRIVATE/'zoom-before.json').read_bytes());path=profile/'Default/Preferences';value=json.loads(path.read_bytes())
mode=sys.argv[1];assert mode in ['100','200','restore'];part=value.setdefault('partition',{})
if mode=='restore':
    for key,row in backup['keys'].items():
        if row['existed']:part[key]=row['value']
        else:part.pop(key,None)
    if not backup['partition_existed'] and not part:value.pop('partition',None)
else:
    part['default_zoom_level']={'x':math.log(int(mode)/100)/math.log(1.2)}
    part['per_host_zoom_levels']={}
temporary=path.with_name('Preferences.mp-ui09.tmp');assert not temporary.exists()
with temporary.open('x',encoding='utf8') as f:json.dump(value,f,separators=(',',':'))
temporary.replace(path)
with (PRIVATE/('zoom-pref-'+mode+'.json')).open('x',encoding='utf8') as f:json.dump(dict(mode=mode,owned_profile_only=True,closed_profile_checked=True,selected_zoom_keys_only=True),f)
print(json.dumps(dict(result='owned_zoom_preferences_'+mode)))
