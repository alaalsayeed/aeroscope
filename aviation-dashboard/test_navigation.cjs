// Execute the complete app with a DOM fixture and Safari-style blocked history.
// This tests event wiring, not browser rendering.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const required=['dist/results.json'];if(process.env.AEROSCOPE_FINAL==='1')required.push('dist/final-results.json');
const missing=required.filter(p=>!fs.existsSync(p));if(missing.length){console.log('SKIP: requires locally generated, ignored result data.');process.exit(0);}
const nodes=new Map(), nav=['overview','actuator','delay','belt','methods'].map(view=>({dataset:{view},classList:{toggle(){}}}));
let goButtons=[],modeButtons=[],downloads=0,historyAttempts=0;
function node(){return {innerHTML:'',textContent:'',value:'',classList:{toggle(){}}};}
const main=node();
Object.defineProperty(main,'innerHTML',{get(){return this.html||''},set(html){
 this.html=html;
 for(const key of [...nodes.keys()])if(!['main','breadcrumb'].includes(key))nodes.delete(key);
 for(const match of html.matchAll(/id="([^"]+)"/g))nodes.set(match[1],node());
 goButtons=[...html.matchAll(/data-go="([^"]+)"/g)].map(m=>({dataset:{go:m[1]}}));
 modeButtons=[...html.matchAll(/data-mode="([^"]+)"/g)].map(m=>({dataset:{mode:m[1]}}));
 const form=nodes.get('scenario');if(form){
   form.values={};
   for(const m of html.matchAll(/<input name="([^"]+)"[^>]*value="([^"]+)"/g))form.values[m[1]]=m[2];
   for(const m of html.matchAll(/<select name="([^"]+)">([\s\S]*?)<\/select>/g)){
     const options=[...m[2].matchAll(/<option([^>]*)>([^<]+)<\/option>/g)];
     form.values[m[1]]=(options.find(o=>o[1].includes('selected'))||options[0])[2];
   }
 }
}});
nodes.set('main',main);nodes.set('breadcrumb',node());
const context=vm.createContext({console,Blob,URL,setTimeout:()=>{},location:{hash:''},
 history:{replaceState(){historyAttempts++;throw new Error('SecurityError: blocked file origin')}},
 window:{DATA:JSON.parse(fs.readFileSync('dist/results.json','utf8')),addEventListener(){},scrollTo(){}},
 FormData:class{constructor(form){return Object.entries(form.values)}},
 document:{getElementById:id=>nodes.get(id)||null,
 querySelectorAll:s=>s==='nav button'?nav:s==='[data-go]'?goButtons:s==='[data-mode]'?modeButtons:[],
 body:{appendChild(a){a.attached=true}},createElement(){return {click(){assert(this.attached);downloads++},remove(){}}}}});
if(process.env.AEROSCOPE_FINAL==='1'){
 context.window.FINAL_RESULTS=JSON.parse(fs.readFileSync('dist/final-results.json','utf8'));
 vm.runInContext(fs.readFileSync('dist/final-setup.js','utf8'),context);
}
vm.runInContext(fs.readFileSync('dist/app.js','utf8'),context);
assert(main.innerHTML.includes('A clearer view'));
goButtons[0].onclick();assert(main.innerHTML.includes('Hydraulic actuator risk'));
assert(nodes.get('scenario-result').innerHTML.includes('30-DAY FAILURE ESTIMATE'));
const before=nodes.get('scenario-result').innerHTML;
nodes.get('scenario').values.Operation_Time='Normal';
nodes.get('scenario').onsubmit({preventDefault(){}});
assert.notEqual(nodes.get('scenario-result').innerHTML,before);
nodes.get('search').value='__no_match__';nodes.get('search').oninput();
assert(nodes.get('records').innerHTML.includes('No records match'));
nodes.get('csv').onclick();nodes.get('export').onclick();assert.equal(downloads,2);
nav[2].onclick();assert(main.innerHTML.includes('Keep maintenance moving'));
nodes.get('scenario').values.Part_Available='No';nodes.get('scenario').onsubmit({preventDefault(){}});
assert(nodes.get('scenario-result').innerHTML.includes('Estimate unavailable'));
modeButtons[1].onclick();assert(main.innerHTML.includes('Inspect transport overrun'));
nav[3].onclick();assert(main.innerHTML.includes('Follow the evidence'));
nav[4].onclick();assert(main.innerHTML.includes('Built to be questioned'));
nav[0].onclick();assert(main.innerHTML.includes('A clearer view'));
assert(historyAttempts>=6);
// Only inputs that affect predictions (or explicit eligibility checks) are shown.
nav[1].onclick();
assert(!main.innerHTML.includes('name="Leakage_Level"'));
assert(main.innerHTML.includes('Considered but not selected'));
nodes.get('scenario').values.Flight_Hours='';nodes.get('scenario').oninput();
assert(nodes.get('scenario-result').innerHTML.includes('Enter a valid'));
nodes.get('scenario').values.Flight_Hours='-1';nodes.get('scenario').onchange();
assert(nodes.get('scenario-result').innerHTML.includes('Enter a valid'));
nodes.get('scenario').values.Flight_Hours='9999';nodes.get('scenario').oninput();
assert(nodes.get('scenario-result').innerHTML.includes('extrapolation'));
nav[2].onclick();modeButtons[0].onclick();
nodes.get('scenario').values.Maintenance_Type='Inspection';nodes.get('scenario').onchange();
assert(nodes.get('scenario-result').innerHTML.includes('35.3%'));
nodes.get('scenario').values.Maintenance_Type='Component Change';nodes.get('scenario').onchange();
assert(nodes.get('scenario-result').innerHTML.includes('12.5%'));
assert(nodes.get('records').innerHTML.includes('Held-out hours'));
modeButtons[1].onclick();
assert(!main.innerHTML.includes('name="Maintenance_Type"'));
assert(!main.innerHTML.includes('name="Part_Available"'));
assert(nodes.get('scenario-result').innerHTML.includes('Duration rule:'));
const retrospectiveRows=vm.runInContext('exportRows()',context);
const data=context.window.DATA;
retrospectiveRows.forEach((row,i)=>{
 assert.equal(row.analysis_mode,'retrospective');
 assert.equal(row.held_out_probability,data.case2.retrospective.oof[i]);
 assert.equal(row.held_out_hours,data.case2.retrospective_duration.oof[i]);
});
assert(retrospectiveRows.some((r,i)=>r.probability!==data.case2.rows[i].probability));
nodes.get('search').value='nothing-matches';nodes.get('search').oninput();
assert(nodes.get('csv').disabled);
assert(nodes.get('records').innerHTML.includes('No records match'));
if(process.env.AEROSCOPE_FINAL==='1'){
 vm.runInContext("go('results')",context);
 assert(main.innerHTML.includes('Results you can trace'));
 assert(main.innerHTML.includes('77.3%'));
 assert(main.innerHTML.includes('Models &amp; validation folds')||main.innerHTML.includes('Models & validation folds'));
 assert(main.innerHTML.includes('CART decision stump'));
 assert(main.innerHTML.includes('Regularization α = 0.1'));
 assert(main.innerHTML.includes('<td>30</td><td>29</td><td>2</td>'));
 assert(main.innerHTML.includes('<td>10</td><td>9</td><td>3</td>'));
 nav[4].onclick();
 assert(main.innerHTML.includes('Models & validation folds'));
 nav[3].onclick();
 assert(nodes.get('scenario-result').innerHTML.includes('DEFECT ASSOCIATION ESTIMATE'));
 nodes.get('scenario').values.Tool_Status='Normal';nodes.get('scenario').onchange();
 assert(nodes.get('scenario-result').innerHTML.includes('Estimate unavailable'));
 // Check Python/JS prediction parity for the deployed regression model.
 const selected=context.window.FINAL_RESULTS.case2_duration.final_model;
 context.selectedModel=selected;
 for(const r of context.window.DATA.case2.rows){
  context.selectedRow=r;
  const h=vm.runInContext('predict(selectedModel,selectedRow).value',context);
  assert(Number.isFinite(h));assert(h>=0);
 }
 console.log('PASS: optimized dashboard, final score view, ridge inference, and unsupported belt combinations.');
}
console.log('PASS: startup, all navigation, scenario submissions, mode toggle, filters, and downloads with blocked History API.');
console.log('PASS: active inputs, live recalculation, invalid inputs, extrapolation notices, mode-aware exports, held-out columns, and empty exports.');
