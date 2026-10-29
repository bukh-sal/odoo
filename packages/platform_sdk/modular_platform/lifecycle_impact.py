"""Read-only uninstall effects; no Odoo registry, addon import or execution.

Callers supply independently verified source bytes/descriptors for the exact
current image, including relevant core model definitions. This is a bounded
static preview, never a promise about arbitrary fully trusted native hooks.
"""
from __future__ import annotations

import ast
from collections import defaultdict
import hashlib
import re
import zipfile
from pathlib import Path

from .contracts import native_version, validate, validate_binding
from .plans import data_digest
from .resolution import PlanningError


WARNING = ('Static declarations and database metadata identify known effects only; '
           'arbitrary trusted native code or hooks may have additional effects.')
_UNKNOWN = object()
_ADDON = re.compile(r'[a-z_][a-z0-9_]{0,62}\Z')


def verified_archive_sources(path, descriptor):
    """Read source as data after verifying the exact archive and file hashes.

    The descriptor must already pass current trust/layout validation. Recheck
    bytes here, rather than trusting a catalog filename or cached descriptor.
    """
    with open(path, 'rb') as stream:
        if 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() != descriptor['digest']:
            raise PlanningError('Impact archive differs from the verified identity')
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            result = {}
            addon = descriptor['manifest']['runtime']['addon_name']
            prefix = 'backend/odoo_addons/' + addon + '/'
            for name, digest in descriptor['inventory'].items():
                if name.startswith(prefix) and name.endswith('.py'):
                    raw = archive.read(descriptor['manifest']['plugin']['id'] + '/' + name)
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise PlanningError('Impact source differs from verified inventory')
                    result[addon + '/' + name[len(prefix):]] = raw
            return result


def inspect_current_image(connection, *, root, inventory_digest, descriptors, site_id, requested):
    """Application-side preview from actual inventoried bytes, not cache paths.

    Image archive identities are checked locally as data. This confers no
    current operator trust/approval; the independent catalog is still required.
    """
    from .artifacts import ArtifactValidator, TrustPolicy
    from .contracts import checked_path, load_json
    root = Path(root)
    raw = (root / 'distribution-inventory.json').read_bytes()
    if 'sha256:' + hashlib.sha256(raw).hexdigest() != inventory_digest:
        raise PlanningError('Native preview differs from the running image inventory')
    inventory = load_json(raw)
    artifacts = inventory['artifacts']
    if {d['plugin_id'] for d in descriptors} != set(artifacts):
        raise PlanningError('Native preview must cover every actual image package')
    validator = ArtifactValidator(TrustPolicy(approved_digests=frozenset(a['digest'] for a in artifacts.values())))
    addons, sources = {'mp_identity'}, {}
    for descriptor in descriptors:
        artifact = artifacts[descriptor['plugin_id']]
        if (artifact['digest'], artifact['version'], artifact['addon']) != (
                descriptor['digest'], descriptor['version'], descriptor['manifest']['runtime'].get('addon_name')):
            raise PlanningError('Native preview package differs from the actual image')
        path = root / checked_path('artifacts/' + artifact['file'])
        verified = validator.verify(path, expected_digest=descriptor['digest'])
        if (verified.manifest != descriptor['manifest'] or verified.inventory != descriptor['inventory']
                or verified.native_manifest != descriptor['native_manifest'] or verified.manifest['runtime']['kind'] != 'native'):
            raise PlanningError('Native preview declarations differ from actual archive bytes')
        sources.update(verified_archive_sources(path, descriptor))
        addons.add(verified.manifest['runtime']['addon_name'])
    for name, digest in inventory['files'].items():
        if name.startswith('addons/') and name.endswith('.py') and name.split('/')[1] in addons:
            raw = (root / checked_path(name)).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise PlanningError('Native preview actual source differs from its inventory')
            relative = name[len('addons/'):]
            if relative in sources and sources[relative] != raw:
                raise PlanningError('Native preview source differs from actual package bytes')
            sources[relative] = raw
    return inspect_native_impact(connection, site_id=site_id, requested=requested, descriptors=descriptors, sources=sources)


def static_relations(sources):
    """Map literal model declarations conservatively, without executing Python.

    Unknown/dynamic model metadata poisons the mapping instead of guessing.
    Missing inherited definitions, SQL views, custom Python bases, conflicting
    tables and dynamic attributes remain unknown. All table-specific source
    declarations must agree, including extensions of an existing model.
    """
    definitions = defaultdict(list)
    dynamic = False
    for raw in sources.values():
        try:
            tree = ast.parse(raw)
        except (SyntaxError, ValueError, RecursionError) as error:
            raise PlanningError('Native source cannot be inspected statically') from error
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            attrs = {}
            conditional_metadata = False
            for statement in node.body:
                targets = statement.targets if isinstance(statement, ast.Assign) else (
                    [statement.target] if isinstance(statement, ast.AnnAssign) else [])
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in {
                            '_name', '_inherit', '_table', '_auto', '_abstract', '_inherits', '_table_query'}:
                        try:
                            attrs[target.id] = ast.literal_eval(statement.value)
                        except (ValueError, TypeError):
                            attrs[target.id] = _UNKNOWN
                if isinstance(statement, (ast.If, ast.Try, ast.For, ast.While, ast.With, ast.Match)):
                    for nested in ast.walk(statement):
                        if isinstance(nested, ast.Name) and isinstance(nested.ctx, ast.Store) and nested.id in {
                                '_name', '_inherit', '_table', '_auto', '_abstract', '_inherits', '_table_query'}:
                            conditional_metadata = True
            if not attrs:
                continue
            model = attrs.get('_name', attrs.get('_inherit'))
            if not isinstance(model, str) or not model:
                dynamic = True
                continue
            parents = attrs.get('_inherit', [])
            if isinstance(parents, str):
                parents = [parents]
            safe_base = all(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                            and base.value.id == 'models' and base.attr in {
                                'Model', 'AbstractModel', 'TransientModel'} for base in node.bases)
            abstract = any(isinstance(base, ast.Attribute) and base.attr == 'AbstractModel' for base in node.bases)
            safe = (safe_base and not conditional_metadata and bool(node.bases) and isinstance(parents, list)
                    and all(isinstance(parent, str) for parent in parents)
                    and not any(value is _UNKNOWN for value in attrs.values())
                    and attrs.get('_auto', True) is not False
                    and not attrs.get('_table_query') and not attrs.get('_inherits'))
            definitions[model].append((attrs, parents if isinstance(parents, list) else [], safe, abstract))

    def resolve(model, visiting):
        entries = definitions.get(model)
        if dynamic or not entries or model in visiting:
            return None
        tables = set()
        roots = 0
        for attrs, parents, safe, abstract in entries:
            if not safe:
                return None
            if model not in parents:
                roots += 1
                if not abstract and attrs.get('_abstract') is not True:
                    tables.add(model.replace('.', '_'))
            if '_table' in attrs:
                table = attrs['_table']
                if not isinstance(table, str) or not table or '\x00' in table or len(table.encode('utf8')) > 63:
                    return None
                # An explicit table replaces the default for this root.
                if model not in parents:
                    tables.discard(model.replace('.', '_'))
                tables.add(table)
            for parent in parents:
                if parent == model:
                    continue
                # Abstract mixins have no table unless they explicitly supply one.
                inherited = definitions.get(parent)
                if not inherited or any(not entry[2] for entry in inherited):
                    return None
                if any(entry[0].get('_table') for entry in inherited):
                    table = resolve(parent, visiting | {model})
                    if table is None:
                        return None
                    tables.add(table)
                elif any((not entry[3] and entry[0].get('_abstract') is not True)
                         or entry[1] for entry in inherited):
                    # This bounded parser does not reconstruct an abstract
                    # inheritance MRO. A deeper mixin may override _table.
                    return None
        if roots != 1 or len(tables) != 1:
            return None
        table = next(iter(tables))
        return table if len(table.encode('utf8')) <= 63 else None

    return {model: resolve(model, set()) for model in sorted(definitions)}


def native_closure(requested, modules, descriptors, required_consumers=()):
    """Compare the database dependency graph with verified native manifests."""
    if not requested or len(requested) > 100 or len(set(requested)) != len(requested):
        raise PlanningError('A nonempty unique bounded native nomination is required')
    if any(not isinstance(name, str) or not _ADDON.fullmatch(name) for name in requested):
        raise PlanningError('Invalid native addon nomination')
    installed = {row['addon']: row for row in modules}
    if len(installed) != len(modules) or any(row['state'] != 'installed' for row in modules):
        raise PlanningError('Pending or ambiguous native registry state')
    packaged = {}
    for descriptor in descriptors:
        if descriptor['manifest']['runtime']['kind'] != 'native':
            continue
        addon = descriptor['manifest']['runtime']['addon_name']
        if addon in packaged:
            raise PlanningError('Ambiguous installed native source')
        packaged[addon] = descriptor
        if addon in installed:
            if set(installed[addon]['depends']) != set(descriptor['native_manifest']['depends']):
                raise PlanningError('Native dependency metadata differs from verified source')
            if installed[addon].get('version') != native_version(descriptor['version']):
                raise PlanningError('Native installed version differs from verified source')
    if not set(requested) <= installed.keys():
        raise PlanningError('Native uninstall requires currently installed addons')
    result = set(requested)
    while True:
        downstream = {name for name, row in installed.items() if result.intersection(row['depends'])}
        downstream.update(consumer for consumer, provider in required_consumers if provider in result)
        expanded = result | downstream
        if expanded == result:
            break
        result = expanded
    if len(result) > 100 or not result <= packaged.keys() or not result <= installed.keys():
        raise PlanningError('Native closure includes unsupported core or non-package dependents')
    return sorted(result)


def _rows(cursor, query, params=(), maximum=1000):
    cursor.execute(query, params)
    rows = cursor.fetchmany(maximum + 1)
    if len(rows) > maximum:
        raise PlanningError('Native impact exceeds the bounded inspection profile')
    return rows


def inspect_native_impact(connection, *, site_id, requested, descriptors, sources):
    """Observe one consistent READ ONLY snapshot; caller owns the transaction.

    PostgreSQL timeout and repeatable-read/read-only mode are checked rather
    than silently changing the application's transaction or importing Odoo.
    Identifiers from static declarations are quoted with psycopg2.sql.
    """
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('transaction_read_only'),current_setting('transaction_isolation'),"
                       "(SELECT setting::bigint FROM pg_settings WHERE name='statement_timeout')")
        readonly, isolation, timeout = cursor.fetchone()
        if readonly != 'on' or isolation not in ('repeatable read', 'serializable') or not 0 < timeout <= 5000:
            raise PlanningError('Impact requires a timed repeatable-read READ ONLY transaction')
        cursor.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'")
        if cursor.fetchone() != (site_id,):
            raise PlanningError('Impact site differs from the independently observed target')
        modules = [dict(addon=name, state=state, version=version, depends=depends) for name, state, version, depends in _rows(cursor, '''
            SELECT m.name,m.state,m.latest_version,COALESCE(array_agg(d.name ORDER BY d.name) FILTER (WHERE d.name IS NOT NULL),'{}')
            FROM ir_module_module m LEFT JOIN ir_module_module_dependency d ON d.module_id=m.id
            WHERE m.state IN ('installed','to install','to upgrade','to remove') GROUP BY m.name,m.state,m.latest_version ORDER BY m.name''')]
        by_addon = {d['manifest']['runtime']['addon_name']: d for d in descriptors if d['manifest']['runtime']['kind'] == 'native'}
        by_plugin = {d['plugin_id']: d for d in descriptors}
        installations = {public_id: (plugin, runtime) for public_id, plugin, runtime in _rows(cursor,
            'SELECT public_id,plugin_id,runtime FROM mp_plugin_installation ORDER BY public_id')}
        required_consumers = []
        for (binding,) in _rows(cursor, 'SELECT descriptor FROM mp_service_binding ORDER BY public_id'):
            validate('binding', binding)
            consumer = installations.get(binding['consumer_installation_id'])
            provider = installations.get(binding['provider_installation_id'])
            if (binding['site_id'] != site_id or not consumer or not provider
                    or provider[0] != binding['provider_plugin_id'] or consumer[0] not in by_plugin or provider[0] not in by_plugin):
                raise PlanningError('Native impact has an unavailable service binding identity')
            requirement = next((r for r in by_plugin[consumer[0]]['manifest']['services']['requires'] if r['alias'] == binding['alias']), None)
            if requirement is None or requirement.get('optional', False) != binding['optional']:
                raise PlanningError('Native impact binding differs from its verified requirement')
            provided = next((p for p in by_plugin[provider[0]]['manifest']['services']['provides']
                             if p['id'] == binding['service_id'] and p['api_version'] == binding['api_version']), None)
            if provided is None:
                raise PlanningError('Native impact has an unavailable service provider contract')
            validate_binding(binding, requirement, {**provided, 'plugin_id': provider[0],
                                                     'installation_id': binding['provider_installation_id']})
            if not requirement.get('optional', False):
                if consumer[1] != 'native' or provider[1] != 'native':
                    raise PlanningError('External required consumers need the G6 lifecycle adapter')
                required_consumers.append((by_plugin[consumer[0]]['manifest']['runtime']['addon_name'],
                                           by_plugin[provider[0]]['manifest']['runtime']['addon_name']))
        closure = native_closure(requested, modules, descriptors, required_consumers)
        plugins = []
        for addon in closure:
            descriptor = by_addon[addon]
            rows = _rows(cursor, '''SELECT i.public_id,i.version,i.artifact_digest,i.state,w.public_id
                FROM mp_plugin_installation i LEFT JOIN mp_workspace_plugin f ON f.installation_id=i.id
                LEFT JOIN mp_workspace w ON w.id=f.workspace_id WHERE i.plugin_id=%s ORDER BY i.public_id,w.public_id''',
                [descriptor['plugin_id']])
            if (not rows or len({row[0] for row in rows}) != 1 or any(
                    row[1:4] != (descriptor['version'], descriptor['digest'], 'installed') or row[4] is None for row in rows)):
                raise PlanningError('Native installation identity or complete workspace coverage unavailable')
            plugins.append(dict(plugin_id=descriptor['plugin_id'], installation_id=rows[0][0], native_addon=addon,
                                artifact_digest=descriptor['digest'], version=descriptor['version'],
                                workspace_ids=sorted({row[4] for row in rows})))
        metadata = [dict(native_addon=module, model=model, records=count) for module, model, count in _rows(cursor,
            'SELECT module,model,count(*) FROM ir_model_data WHERE module=ANY(%s) GROUP BY module,model ORDER BY module,model', [closure])]
        # Native uninstall preserves records with another module's XML ID.
        ownership = '''d.module=ANY(%s) AND NOT EXISTS (SELECT 1 FROM ir_model_data other
            WHERE other.model=d.model AND other.res_id=d.res_id AND other.module<>ALL(%s)
              AND other.module<>'__cloc_exclude__')'''
        model_names = _rows(cursor, '''SELECT DISTINCT m.model FROM ir_model_data d JOIN ir_model m
            ON d.model='ir.model' AND d.res_id=m.id WHERE ''' + ownership + ' ORDER BY m.model', [closure, closure])
        field_names = _rows(cursor, '''SELECT DISTINCT f.model,f.name,f.ttype,f.store FROM ir_model_data d
            JOIN ir_model_fields f ON d.model='ir.model.fields' AND d.res_id=f.id WHERE ''' + ownership +
            ' ORDER BY f.model,f.name', [closure, closure])
        relations = static_relations(sources)

        def table_for(model):
            table = relations.get(model)
            if table:
                cursor.execute('SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
                               "WHERE n.nspname='public' AND c.relname=%s AND c.relkind IN ('r','p')", [table])
                if cursor.fetchone():
                    return table
            return None

        models, fields, affected = [], [], set()
        for (model,) in model_names:
            table = table_for(model)
            count = None
            if table:
                cursor.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier('public'), sql.Identifier(table)))
                count = cursor.fetchone()[0]
                affected.add(table)
            models.append(dict(model=model, relation=table, mapping='static_declaration' if table else 'unknown',
                               records=count, unknown_reason=None if table else 'No unambiguous static ordinary-table mapping.'))
        for model, field, ttype, stored in field_names:
            table, column, count = table_for(model), None, None
            if table and stored and ttype not in ('one2many', 'many2many'):
                cursor.execute('SELECT 1 FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s',
                               ['public', table, field])
                if cursor.fetchone():
                    column = field
                    cursor.execute(sql.SQL('SELECT count(*) FROM {}.{} WHERE {} IS NOT NULL').format(
                        sql.Identifier('public'), sql.Identifier(table), sql.Identifier(field)))
                    count = cursor.fetchone()[0]
                    affected.add(table)
            fields.append(dict(model=model, field=field, relation=table if column else None, column=column,
                               mapping='static_declaration' if column else 'unknown', non_null_records=count,
                               unknown_reason=None if column else 'No unambiguous stored scalar-column mapping.'))
        # These are known constraints/references on affected relations, not a
        # claim that every displayed constraint will be dropped by uninstall.
        constraints = [dict(relation=table, name=name, definition=definition) for table, name, definition in _rows(cursor, '''
            SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY c.relname,k.conname''', [sorted(affected)])]
        references = [dict(relation=table, name=name, referenced_relation=target, definition=definition)
                      for table, name, target, definition in _rows(cursor, '''
            SELECT c.relname,k.conname,t.relname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_class t ON t.oid=k.confrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace WHERE k.contype='f' AND n.nspname='public'
            AND t.relname=ANY(%s) ORDER BY c.relname,k.conname''', [sorted(affected)])]
        dispatch = [name for (name,) in _rows(cursor,
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('mp_job','mp_outbox') ORDER BY table_name")]
        assets = sorted({(addon, path) for addon in closure
                         for paths in by_addon[addon]['native_manifest'].get('assets', {}).values() for path in paths})
        impact = dict(site_id=site_id, requested_addons=sorted(requested), native_closure=closure, plugins=plugins,
                      models=models, fields=fields, constraints=constraints, foreign_references=references,
                      metadata_records=metadata, assets=[dict(native_addon=addon, path=path, source='declared_source') for addon, path in assets],
                      dispatch=dict(state='unsupported' if dispatch else 'not_present', tables=dispatch),
                      warnings=[WARNING, 'Shared metadata with surviving XML IDs is retained by native uninstall. Constraints and foreign references describe affected relations; not every listed constraint is deleted.'])
        return impact


def impact_view(impact, *, operation_id, plan_hash, observed_at):
    value = dict(schema_version=1, kind='native_uninstall_impact', operation_id=operation_id, plan_hash=plan_hash,
                 impact_digest=data_digest(impact), impact=impact, database_action='native_uninstall',
                 artifact_action='retain_in_runtime', destructive=True, requires_backup=True,
                 native_code_fully_trusted=True, completeness='known_effects_only',
                 control_authority='independent_local_os', observed_at=observed_at)
    return validate('lifecycle-impact', value)


def check_impact_view(value, *, operation_id, plan_hash, expected_impact_digest):
    validate('lifecycle-impact', value)
    if (value['operation_id'] != operation_id or value['plan_hash'] != plan_hash
            or value['impact_digest'] != expected_impact_digest or data_digest(value['impact']) != expected_impact_digest):
        raise PlanningError('Uninstall impact no longer matches the exact operation preimage')
    return value
