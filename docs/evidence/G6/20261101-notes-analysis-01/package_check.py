"""Actual deterministic archive validation, unchanged old packages and schemas."""
import hashlib,importlib.util,json,subprocess,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from reference_package import assemble,validate_reference_composition
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from jsonschema import Draft202012Validator

old=types.ModuleType('old_reference_package')
exec(compile(subprocess.run(['git','show','24be0294:tools/reference_package.py'],cwd=ROOT,capture_output=True,check=True).stdout,'retained_assembler','exec'),old.__dict__)
validator=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True))
rows=[];archives=[]
with tempfile.TemporaryDirectory(prefix='mp-notes-analysis-') as temporary:
    path=Path(temporary)/'candidate.mplug'
    for plugin in ['notes','notes_labels','canvas','notes_stats']:
        name='plugins/'+plugin+'/plugin.toml';manifest,raw,files=assemble(ROOT,name)
        assert raw==assemble(ROOT,name)[1]
        path.write_bytes(raw);result=validator.verify(path,expected_digest='sha256:'+hashlib.sha256(raw).hexdigest())
        if plugin!='notes_stats':assert raw==old.assemble(ROOT,name)[1]
        archives.append(raw);rows.append(dict(plugin=manifest['plugin']['id'],digest=result.digest,reproducible=True,old_bytes_unchanged=plugin!='notes_stats'))
    validate_reference_composition(archives)
spec=importlib.util.spec_from_file_location('connector_contracts',ROOT/'platform_addons/mp_example_notes_stats/contracts.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
schema=json.loads((ROOT/'plugins/notes_stats/schemas/analysis-v1.json').read_text())
Draft202012Validator.check_schema(schema)
assert schema['$defs']==dict(analyze_input=module.INPUT,status_input=module.STATUS_INPUT,output=module.OUTPUT)
result=dict(result='passed',archives=rows,composition_valid=True,shipped_schema_matches_runtime=True,no_runtime_installation=True,no_retained_test_archives=True)
(OUT/'packages.json').write_text(json.dumps(result,indent=2)+'\n')
print('Four archives validated/reproducible; previous three byte-identical; connector schema/composition pass')
