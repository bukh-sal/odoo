import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../framework_addons/web/static/src/views/fields/identity/identity_field.js', import.meta.url), 'utf8');
const registered = new Map();
class Component {}
class CharField {}
const {IdentityField, identityField} = new Function('Component', 'CharField', 'standardFieldProps', 'registry', '_t',
    source.replace(/^import .*;\r?\n/gm, '').replace(/^export /gm, '') + ';return {IdentityField,identityField};')(
        Component, CharField, {}, {category: () => ({add: (key, field) => registered.set(key, field)})}, text => text);

function cell(name, secondary = '', readonly = true) {
    const field = new IdentityField();
    field.props = {name: 'name', record: {data: {name, email: secondary}}, readonly, secondaryField: 'email', id: 'native-field'};
    return field;
}

test('registered identity field loads its secondary field through native dependencies', () => {
    assert.equal(registered.get('mp_identity'), identityField);
    assert.deepEqual(identityField.supportedTypes, ['char']);
    assert.deepEqual(identityField.extractProps({options: {secondary_field: 'email'}}), {secondaryField: 'email'});
    assert.deepEqual(identityField.fieldDependencies({options: {secondary_field: 'email'}}),
        [{name: 'email', type: 'char', readonly: true}]);
    assert.deepEqual(identityField.fieldDependencies({options: {}}), []);
});

test('identity uses loaded data and handles empty, long and non-Latin names without requests', () => {
    for (const [name, expected] of [['Northline Studio', 'NS'], [' Leah  Ortiz ', 'LO'], ['L', 'L'],
        ['', ''], [false, ''], ['ليلى حسن', 'لح'], ['😀 Team', '😀T']]) {
        assert.equal(cell(name).initials, expected);
    }
    const field = cell('A'.repeat(200), '<img src=x onerror=alert(1)>');
    assert.equal(field.value.length, 200);
    assert.equal(field.secondary, '<img src=x onerror=alert(1)>');
    field.props.record.data.email = false;
    assert.equal(field.secondary, '');
});

test('editing delegates original record and field props without read-only decoration options', () => {
    const field = cell('Northline', 'hello@example.invalid', false);
    assert.equal(IdentityField.components.CharField, CharField);
    assert.equal(field.charProps.record, field.props.record);
    assert.deepEqual(Object.keys(field.charProps).sort(), ['id', 'name', 'readonly', 'record']);
    assert.equal(field.charProps.readonly, false);
});
