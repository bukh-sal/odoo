import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

test('palette close control resolves against the actual required callback contract without an optional alias',async()=>{
    const root=new URL('../framework_addons/web/static/src/core/commands/',import.meta.url);
    const source=await readFile(new URL('command_palette.js',root),'utf8');
    const definition=source.slice(source.indexOf('export class CommandPalette')).match(/static props = (\{[^]*?\n    });/)[1];
    const contract=new Function('EventBus','return '+definition)(class {});
    const calls=[],props=Object.fromEntries(Object.entries(contract)
        .filter(([,rule])=>rule===Function||(rule.type===Function&&!rule.optional))
        .map(([name])=>[name,()=>calls.push(name)]));
    const template=await readFile(new URL('command_palette.xml',root),'utf8');
    const button=template.match(/<button\b[^>]*aria-label="Close command palette"[^>]*>/)[0];
    const expression=button.match(/t-on-click="([^"]+)"/)[1];
    const handler=new Function('props','return '+expression)(props);
    assert.equal(typeof handler,'function');handler();assert.deepEqual(calls,['close']);
});
