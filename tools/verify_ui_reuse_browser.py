"""Bind recorded browser observations to the current release and preserved data."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.plans import data_digest
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import notes_snapshot,files


def contrast(a,b):
    def luminance(value):
        numbers=[int(part.strip())/255 for part in value.removeprefix('rgb(').removesuffix(')').split(',')]
        values=[number/12.92 if number<=0.04045 else ((number+0.055)/1.055)**2.4 for number in numbers]
        return sum(number*weight for number,weight in zip(values,[0.2126,0.7152,0.0722]))
    first,second=sorted([luminance(a),luminance(b)]);return (second+0.05)/(first+0.05)


def main():
    output=ROOT/'docs/evidence/G5/20261028T151500Z-native-interactions-browser'
    if (output/'browser-qualification.json').exists():raise ValueError('Browser proof already recorded; do not overwrite')
    operator=ROOT/'.local/operator';config=json.loads((operator/'targets/g5.json').read_text())
    assert config['generation']==15 and config['image_id']=='sha256:7dbb65483943315f5f48ef0c40001a2c8e33061a4d3ff8141def6745a1defaf4'
    observer=DockerObserver(config);catalog=Catalog(operator/'catalog',configuration(operator/'trust.json'),readonly=True).snapshot()
    current=observer.state(observer.read(),catalog)['state']
    notes=notes_snapshot(observer);migration=json.loads(sql(observer,"SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.post';"))
    assert len(notes)==4 and hashlib.sha256(json.dumps(notes,sort_keys=True,separators=(',',':')).encode()).hexdigest()==migration['rows_sha256']
    probe=json.loads((output/'disposable-note.json').read_text());assert probe['state']=='created_updated_deleted_by_browser_probe'
    assert sql(observer,"SELECT count(*) FROM mp_example_note WHERE public_id='"+probe['id']+"';").strip()==b'0'
    completed=OperatorStore(operator/'control').status('91ceba46-a1ef-43ab-8fa2-4435d7e26df5')
    assert completed['state']=='completed' and completed['traffic_resumed']
    checkpoint=operator/'control/checkpoints'/completed['backup_id'];saved={};prefix='filestore/'+config['sites'][0]['database']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz') as archive:
        for member in archive:
            if member.isfile():
                assert member.name.startswith(prefix)
                saved[member.name.removeprefix(prefix)]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    current_files=files(observer);assert all(current_files.get(name)==digest for name,digest in saved.items())
    colors=json.loads((output/'native-palette-colors.json').read_text());assert colors['direction']=='rtl' and colors['dialogs']==1
    ratios={'body':contrast(colors['text'],colors['background']),
        'selected':contrast(colors['selectedText'],colors['selectedBackground']),
        'category':contrast(colors['categoryText'],colors['background'])}
    assert min(ratios.values())>=4.5
    paths=[path for path in (ROOT/'platform_addons/mp_shell').rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    paths+=[Path(__file__),ROOT/'tests/test_native_interactions.mjs']
    report={'result':'passed_service_adapter_subset','utc':datetime.now(timezone.utc).isoformat(),'generation':config['generation'],
        'image_id':config['image_id'],'worker_id':config['worker_id'],'database':config['sites'][0]['database'],
        'observations':{'native_list_form_create_update_revision2_and_delete':True,'focused_widget_committed_before_save':True,
            'native_saved_and_deleted_notifications_visible':True,'native_destructive_confirmation_and_cancel_focus':True,
            'native_unsaved_escape_preserves_draft':True,'control_k_from_editable_one_palette':True,
            'workspace_retirement_hides_previous_commands':True,'authorized_palette_contains_exactly_settings_export':True,
            'suspended_workspace_page_denied':True,'native_rtl_overlay_direction':True,'english_light_preferences_restored':True},
        'palette_contrast_ratios':ratios,'original_business_rows_preserved':4,'probe_record_removed':probe['id'],
        'prior_checkpoint_assets_preserved':len(saved),'deployment_state_digest':data_digest(current),
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'artifacts_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir() if path.is_file()},
        'limits':['Browser CRUD/draft/dialog/command tests executed on gen13/14; unchanged JS/native backend plus palette-only CSS delta qualified on gen15.',
            'Native list/form remains the default; no full WebClient/action-stack replacement or client release-fence/UI07 claim.',
            'Canvas/expired-session/two-tab authority regression, action/view pilot and full UI09 zoom/keyboard/contrast sweep remain separate G5/G7 work.',
            'Only the newly created disposable probe was deleted; original rows and prior asset bytes preserved. Expected audit/idempotency metadata remains.']}
    (output/'browser-qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'generation':config['generation'],'original_notes':len(notes),'contrast':ratios}))


if __name__=='__main__':main()
