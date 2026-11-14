const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const source=fs.readFileSync('docs/app.js','utf8').split('init().catch(')[0];
function run(expression){const c={RideEvidence:require('../docs/evidence.js')};vm.createContext(c);vm.runInContext(source+'\nDATA={routes:[],summary:{ride_spend_sgd:120,ride_transactions:6},food:{top_restaurants:[]}}; result='+expression,c);return c.result;}
test('classic Ride spend chip recognises spent',()=>assert.match(run('answer("How much have I spent on rides?")'),/S\$120\.00/));
test('classic cheaper answer does not imply current advantage',()=>assert.match(run('answer("Which is cheaper from home to office?")'),/cannot establish/));
test('classic missing money is not zero',()=>assert.equal(run('money(null)'),'—'));
