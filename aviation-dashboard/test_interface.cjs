// Logic/render-template checks; these do not replace visual browser QA.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
if(!fs.existsSync('dist/results.json')){console.log('SKIP: requires locally generated, ignored result data.');process.exit(0);}
const data=JSON.parse(fs.readFileSync('dist/results.json','utf8'));
const context=vm.createContext({window:{DATA:data},document:{getElementById:()=>({})},console});
let source=fs.readFileSync('dist/app.js','utf8');
source=source.slice(0,source.lastIndexOf("document.querySelectorAll('nav button').forEach(b=>b.onclick"));
vm.runInContext(source,context);
for(const page of ['overview','actuator','delay','belt','methods']){
 const html=vm.runInContext(`view='${page}'; ${page}()`,context);
 assert(html.includes('<h1>'));assert(!html.includes('undefined'));assert(!html.includes('NaN'));
}
for(const c of ['case1','case2']) for(const row of data[c].rows){
 context.testRow=row;context.testTree=data[c].model.tree;
 const p=vm.runInContext('predict(testTree,testRow)',context);
 assert(Math.abs(p.value-row.probability)<1e-12);
}
assert.equal(vm.runInContext('riskBand(.2)',context),'Medium');
assert.equal(vm.runInContext('riskBand(.5)',context),'High');
assert.equal(vm.runInContext("view='actuator';query='__no_match__';month='All';risk='All';filtered().length",context),0);
assert.equal(vm.runInContext("query='another_no_match';filtered().length",context),0);
console.log('Five page templates, cross-language model parity, risk boundaries, and filters passed.');
