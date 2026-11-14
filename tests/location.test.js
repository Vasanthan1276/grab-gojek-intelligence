const test=require('node:test');
const assert=require('node:assert/strict');
const L=require('../docs/location.js');
const point=(latitude=0,longitude=0,accuracy=10)=>({latitude,longitude,accuracy});
const anchor=(alias='HOME',latitude=0,longitude=0)=>({alias,...point(latitude,longitude)});
function storage(){const values=new Map();return {values,getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};}
test('coordinate and accuracy bounds reject missing, nonfinite and imprecise data',()=>{
  assert.ok(L.validPoint(point()));
  for(const p of [null,{},point(91),point(0,181),point(NaN),point(0,0,101),point(0,0,-1),point('0')])assert.equal(L.validPoint(p),false);
});
test('position readings must be fresh and keep only needed coordinate fields',()=>{
  const now=1000000,p={coords:{...point(),altitude:50},timestamp:now};
  assert.deepEqual(L.position(p,now),{status:'ready',point:point(),timestamp:now});
  for(const timestamp of [now-120001,now+10001,null,NaN])assert.equal(L.position({...p,timestamp},now).status,'stale');
  assert.equal(L.position({...p,coords:point(0,0,500)},now).status,'inaccurate');
});
test('haversine measures metres, including dateline crossing, and never supplies road distance',()=>{
  assert.equal(L.metres(point(),point()),0);
  assert.ok(Math.abs(L.metres(point(),point(0,.001))-111.195)<.1);
  assert.ok(L.metres(point(0,179.999),point(0,-179.999))<223);
  assert.equal(L.metres(null,point()),null);
});
test('matching requires an unambiguous place and allows for both accuracy radii',()=>{
  assert.deepEqual(L.match(point(),[anchor()]),{status:'matched',alias:'HOME'});
  assert.equal(L.match(point(),[]).status,'unmatched');
  assert.equal(L.match(point(0,.003),[anchor()]).status,'unmatched');
  assert.equal(L.match(point(),[anchor(),anchor('OFFICE',0,.001)]).status,'ambiguous');
  assert.equal(L.match(point(0,.0022),[anchor()]).status,'unmatched');
  assert.equal(L.match(point(0,0,150),[anchor()]).status,'inaccurate');
});
test('storage allowlists aliases and fields without quotes, trips or raw receipts',()=>{
  const s=storage();
  const input=[{...anchor(),address:'synthetic private field',quote:22},anchor(),anchor('OTHER'),{alias:'OFFICE',...point(500)}];
  assert.equal(L.save(s,input,['HOME','OFFICE'],true),true);
  assert.deepEqual(L.load(s,['HOME']),{anchors:[anchor()],remember:true});
  assert.equal(s.values.get(L.KEY).includes('address'),false);
  assert.equal(s.values.get(L.KEY).includes('quote'),false);
});
test('opt-out deletes only this feature’s key and does not persist default session points',()=>{
  const s=storage();s.values.set('unrelated','keep');
  L.save(s,[anchor()],['HOME'],true);L.save(s,[anchor()],['HOME'],false);
  assert.deepEqual(L.load(s,['HOME']),{anchors:[],remember:false});
  assert.equal(s.values.get('unrelated'),'keep');
});
test('corrupt, old or unavailable storage is handled without leaking exception content',()=>{
  const s=storage();for(const raw of ['{','null','{"version":99}']){s.values.set(L.KEY,raw);assert.equal(L.load(s,['HOME']).error,true);}
  const blocked={getItem(){throw Error('secret');},setItem(){throw Error('secret');},removeItem(){throw Error('secret');}};
  assert.equal(L.load(blocked,['HOME']).error,true);
  assert.equal(L.save(blocked,[anchor()],['HOME'],true),false);
  assert.equal(L.save(blocked,[],['HOME'],false),false);
});
test('route selection preserves direction and separate stop sequences without inventing coverage',()=>{
  const routes=[{key:'direct',origin:'HOME',destination:'OFFICE',stops:['HOME','OFFICE']},{key:'via',origin:'HOME',destination:'OFFICE',stops:['HOME','V_PLACE','OFFICE']},{key:'reverse',origin:'OFFICE',destination:'HOME'}];
  assert.deepEqual(L.routesFor(routes,'HOME','OFFICE').map(r=>r.key),['direct','via']);
  assert.deepEqual(L.routesFor(routes,'OFFICE','HOME').map(r=>r.key),['reverse']);
  assert.deepEqual(L.routesFor(routes,'HOME','V_PLACE'),[]);
});
test('booking time is Singapore time at midnight across UTC date boundary',()=>{
  assert.deepEqual(L.singaporeTime(new Date('2026-11-13T16:01:00Z')),{hour:'00',weekday:'Saturday',label:'Saturday 00:01 Singapore time'});
});
test('geolocation is one shot, requests a new reading, and has a finite timeout',async()=>{
  let calls=0;
  const result=await L.request({getCurrentPosition(success,error,options){calls++;assert.deepEqual(options,{enableHighAccuracy:true,timeout:15000,maximumAge:0});success({coords:point(),timestamp:Date.now()});}});
  assert.equal(calls,1);assert.equal(result.status,'ready');
});
test('permission denial, unavailable, timeout and thrown errors produce safe fallback states',async()=>{
  for(const [code,status] of [[1,'denied'],[2,'unavailable'],[3,'timeout'],[99,'unavailable']])assert.deepEqual(await L.request({getCurrentPosition(s,e){e({code,message:'private details'});}}),{status});
  assert.deepEqual(await L.request({getCurrentPosition(){throw Error('private details');}}),{status:'unavailable'});
  assert.deepEqual(await L.request(null),{status:'unsupported'});
  assert.deepEqual(await L.request({getCurrentPosition(){assert.fail('must not request');}},false),{status:'insecure'});
});
