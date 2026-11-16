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

const useWidths = new Function('getComputedStyle', 'useComponent',
    source.replace(/^import[\s\S]*?;\r?\n/gm, '').replace(/^export /gm, '') + ';return useMagicColumnWidths;')(
        node => node.computed, () => ({constructor: {useMagicColumnWidths: false}}));

function paintedFixture({parentWidth = 863, border = 1, collapsed = true} = {}) {
    // Installed Partners45 geometry. The renderer's integer clientWidth excludes
    // the scrollbar; collapsed table edges occupy half of each outer border.
    const parent = {clientWidth: parentWidth, style: {}, computed: {paddingLeft: '0px', paddingRight: '0px'}};
    const widths = [40, 329, 169, 269, 56];
    const headers = widths.map((width, i) => ({
        style: {},
        computed: {paddingLeft: i === 0 ? '16px' : i === 4 ? '8px' : '4.8px',
            paddingRight: i === 0 ? '4px' : i === 4 ? '8px' : '4.8px',
            minWidth: i === 4 ? '56px' : '0px'},
        getBoundingClientRect: () => ({width}),
    }));
    const table = {style: {}, parentNode: parent, parentElement: parent,
        computed: {borderLeftWidth: border + 'px', borderRightWidth: border + 'px',
            borderCollapse: collapsed ? 'collapse' : 'separate'},
        classList: {add() {}, remove() {}},
        querySelectorAll: selector => selector === 'thead th' ? headers : [],
    };
    const state = {columns: ['char','selection','many2one'].map((fieldType, i) => ({
        id: String(i), type: 'field', fieldType, field: {}, attrs: {},
    })), isEmpty: false, hasSelectors: true, hasActionsColumn: true, hasOpenFormViewColumn: false};
    return {headers, parent, table, state, paintedWidth: () =>
        Math.max(parentWidth, headers.reduce((sum, h) => sum + parseFloat(h.style.width), 0)
            + border * (collapsed ? 1 : 2))};
}

test('production hook fits the full table box, including collapsed borders at desktop widths', () => {
    for (const parentWidth of [863, 864, 1057]) {
        for (const border of [1, 10/11]) {
            const f = paintedFixture({parentWidth, border});
            useWidths({el:f.table}, () => f.state).resetWidths();
            assert.ok(f.paintedWidth() <= parentWidth, `full table must fit ${parentWidth}px at border ${border}`);
            assert.equal(parseFloat(f.headers.at(-1).style.width), 56);
        }
    }
});

test('borderless and separate-border tables retain their complete box budget', () => {
    for (const options of [{border:0}, {border:1, collapsed:false}]) {
        const f = paintedFixture(options);
        useWidths({el:f.table}, () => f.state).resetWidths();
        assert.ok(f.paintedWidth() <= f.parent.clientWidth);
    }
});

test('genuinely narrow tables keep local overflow and column/control minimums', () => {
    const f = paintedFixture({parentWidth:284});
    useWidths({el:f.table}, () => f.state).resetWidths();
    assert.ok(f.paintedWidth() > 284, 'columns that cannot fit remain horizontally scrollable');
    assert.equal(parseFloat(f.headers.at(-1).style.width), 56);
    for (const h of f.headers.slice(1,4)) assert.ok(parseFloat(h.style.width) >= 89);
});
