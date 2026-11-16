import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../framework_addons/web/static/src/views/list/column_width_hook.js', import.meta.url), 'utf8');
const computeWidths = new Function('getComputedStyle',
    source.replace(/^import[\s\S]*?;\r?\n/gm, '').replace(/^export /gm, '') + ';return computeWidths;')(
        node => node.computed);

function fixture({minimum = '56px', padding = 8, selectors = true, actions = true} = {}) {
    const headers = [
        ...(selectors ? [{computed: {minWidth: '0px', paddingLeft: '16px', paddingRight: '4px'}}] : []),
        {computed: {minWidth: '0px', paddingLeft: '8px', paddingRight: '8px'}},
        ...(actions ? [{computed: {minWidth: minimum, paddingLeft: padding + 'px', paddingRight: padding + 'px'}}] : []),
    ];
    return {
        table: {querySelectorAll: selector => {
            assert.equal(selector, 'thead th');
            return headers;
        }},
        state: {
            columns: [{id: 'name', type: 'field', fieldType: 'char', field: {}, attrs: {width: '80px'}}],
            isEmpty: true, hasSelectors: selectors, hasActionsColumn: actions, hasOpenFormViewColumn: false,
        },
    };
}

test('actual width producer fits the installed 36px chooser inside its declared 56px cell', () => {
    const f = fixture();
    const widths = computeWidths(f.table, f.state, 800);
    assert.equal(widths[0], 20, 'selector still keeps its native content width');
    assert.equal(widths.at(-1) + 16, 56, 'header padding must be counted exactly once');
    assert.ok(widths.at(-1) >= 36, 'chooser fits without overflowing the cell');
    assert.equal(widths.reduce((a, b) => a + b), 800);
});

test('coarse/narrow target minimum is honored when recomputing previously frozen widths', () => {
    const f = fixture({minimum: '64px'});
    const widths = computeWidths(f.table, f.state, 800, [20, 768, 12]);
    assert.equal(widths.at(-1) + 16, 64);
    assert.ok(widths.at(-1) >= 44);
    assert.equal(widths.reduce((a, b) => a + b), 800);
});

test('no selection and ordinary deletion-only headers retain usable native widths', () => {
    for (const minimum of ['auto', '0px', '8px']) {
        const f = fixture({minimum, selectors: false});
        const widths = computeWidths(f.table, f.state, 800);
        assert.equal(widths.length, 2);
        assert.equal(widths.at(-1), 12, 'legacy deletion floor remains when no larger minimum is declared');
    }
    const f = fixture({actions: false});
    const widths = computeWidths(f.table, f.state, 800);
    assert.equal(widths.length, 2);
    assert.equal(widths[0], 20);
    assert.equal(widths[1], 780);
});
