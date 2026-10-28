"""Development operator reconciliation, never reuses a version for changed bytes."""
import hashlib,json,tomllib,zipfile
from pathlib import Path
from modular_platform.contracts import normalize_manifest,package_version

assert env.cr.dbname.startswith('mp_disposable_r0_r1_')
inventory=json.loads(Path('/opt/modular/distribution-inventory.json').read_text())
for plugin,descriptor in inventory['artifacts'].items():
    artifact=Path('/opt/modular/artifacts')/descriptor['file'];assert 'sha256:'+hashlib.sha256(artifact.read_bytes()).hexdigest()==descriptor['digest']
    with zipfile.ZipFile(artifact) as archive:manifest=normalize_manifest(tomllib.loads(archive.read(plugin+'/plugin.toml').decode()))
    row=env['mp.plugin.installation'].search([('plugin_id','=',plugin)]);assert len(row)==1
    native=env['ir.module.module'].search([('name','=',descriptor['addon'])]);assert native.state=='installed' and native.latest_version=='19.0.'+descriptor['version']
    if row.artifact_digest!=descriptor['digest']:assert package_version(descriptor['version'])>package_version(row.version)
    row.write({'version':descriptor['version'],'artifact_digest':descriptor['digest'],'manifest':manifest})
env.cr.commit();env.registry.signal_changes()
print('MP_G4_PATCH='+json.dumps(inventory['artifacts']))
