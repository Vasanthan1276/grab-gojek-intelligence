const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const L=require('../docs/location.js');
class Element{
  constructor(){this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.listeners={};this.options=[];}
  add(option){this.options.push(option);}
  replaceChildren(...options){this.options=options;this.value=options[0]?.value||'';}
  addEventListener(name,callback){this.listeners[name]=callback;}
  async fire(name){await this.listeners[name]?.({preventDefault(){}});}
  focus(){this.focused=true;}
  scrollIntoView(){this.scrolled=true;}
}
function app({routes=[{key:'out',origin:'HOME',destination:'OFFICE',journey_type:'direct'},{key:'back',origin:'OFFICE',destination:'HOME',journey_type:'direct'}],geo,stored,clock=Date}={}){
  const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const values=new Map(stored?[[L.KEY,JSON.stringify({version:1,anchors:stored})]]:[]),writes=[],selected=[];
  const storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>{writes.push(k);values.set(k,v);},removeItem:k=>{writes.push(k);values.delete(k);}};
  const context=vm.createContext({RideLocation:L,window:{localStorage:storage,isSecureContext:true},navigator:{geolocation:geo},document:{getElementById:get},Option:function(text,value){return {text,value};},Date:clock});
  vm.runInContext(fs.readFileSync('docs/booking.js','utf8'),context);
  context.initBooking(routes,(key,time)=>selected.push({key,time}));
  return {get,values,writes,selected};
}
const coords={latitude:0,longitude:0,accuracy:10};
test('page load does not ask for location or write storage; manual journey works',async()=>{
  const a=app({geo:{getCurrentPosition(){assert.fail('no prompt on load');}}});
  assert.equal(a.writes.length,0);assert.equal(a.get('remember-places').checked,false);
  a.get('booking-origin').value='HOME';await a.get('booking-origin').fire('change');
  a.get('booking-destination').value='OFFICE';await a.get('booking-destination').fire('change');
  await a.get('booking-form').fire('submit');
  assert.equal(a.selected[0].key,'out');assert.equal(a.get('compare-title').focused,true);
  assert.match(a.get('booking-result').textContent,/Historical paid fares only/);
});
test('unsupported direction blocks estimates and multi-stop variants require explicit choice',async()=>{
  const a=app({routes:[{key:'direct',origin:'HOME',destination:'OFFICE'},{key:'via',origin:'HOME',destination:'OFFICE',stops:['HOME','V_PLACE','OFFICE'],journey_type:'multi_stop'}]});
  a.get('booking-origin').value='OFFICE';a.get('booking-destination').value='HOME';await a.get('booking-origin').fire('change');
  assert.equal(a.get('show-estimate').disabled,true);assert.match(a.get('booking-result').textContent,/No comparable/);
  a.get('booking-origin').value='HOME';a.get('booking-destination').value='OFFICE';await a.get('booking-origin').fire('change');
  assert.equal(a.get('journey-picker').hidden,false);await a.get('booking-form').fire('submit');assert.equal(a.selected.length,0);
  a.get('booking-journey').value='via';await a.get('booking-form').fire('submit');assert.equal(a.selected[0].key,'via');
  const only=app({routes:[{key:'via',origin:'HOME',destination:'OFFICE',stops:['HOME','V_PLACE','OFFICE'],journey_type:'multi_stop'}]});
  only.get('booking-origin').value='HOME';only.get('booking-destination').value='OFFICE';await only.get('booking-origin').fire('change');
  assert.equal(only.get('journey-picker').hidden,false);assert.equal(only.get('booking-journey').value,'via');
});
test('matched GPS selects a configured alias without exposing coordinates in status or persisting the reading',async()=>{
  const a=app({stored:[{alias:'HOME',...coords}],geo:{getCurrentPosition(s){s({coords,timestamp:Date.now()});}}});
  await a.get('use-location').fire('click');
  assert.equal(a.get('booking-origin').value,'HOME');assert.match(a.get('location-status').textContent,/Near Home/);
  assert.equal(a.writes.length,0);assert.equal(a.get('location-status').textContent.includes('latitude'),false);
});
test('denial clears a previous origin instead of silently using a stale location',async()=>{
  const a=app({geo:{getCurrentPosition(s,e){e({code:1});}}});a.get('booking-origin').value='HOME';
  await a.get('use-location').fire('click');assert.equal(a.get('booking-origin').value,'');
  assert.match(a.get('location-status').textContent,/denied/);assert.equal(a.get('show-estimate').disabled,true);
});
test('place setup is session-only until explicit remember opt-in; forgetting removes only anchor storage',async()=>{
  const a=app({geo:{getCurrentPosition(s){s({coords,timestamp:Date.now()});}}});
  await a.get('use-location').fire('click');assert.equal(a.get('place-setup').open,true);
  a.get('place-alias').value='HOME';await a.get('save-place').fire('click');assert.equal(a.values.has(L.KEY),false);
  a.get('remember-places').checked=true;await a.get('remember-places').fire('change');
  assert.equal(JSON.parse(a.values.get(L.KEY)).anchors[0].alias,'HOME');
  await a.get('forget-places').fire('click');assert.equal(a.values.has(L.KEY),false);assert.equal(a.get('booking-origin').value,'');
});
test('forgetting while a location request is pending ignores the delayed result',async()=>{
  let done;const a=app({geo:{getCurrentPosition(s){done=s;}}});
  const pending=a.get('use-location').fire('click');await a.get('forget-places').fire('click');
  done({coords,timestamp:Date.now()});await pending;
  assert.equal(a.get('booking-origin').value,'');assert.equal(a.get('save-place').disabled,true);assert.equal(a.get('use-location').disabled,false);
});

test('an old automatic origin cannot be used for a new estimate',async()=>{
  let now=Date.now();const a=app({clock:{now:()=>now},stored:[{alias:'HOME',...coords}],geo:{getCurrentPosition(s){s({coords,timestamp:now});}}});
  await a.get('use-location').fire('click');a.get('booking-destination').value='OFFICE';await a.get('booking-destination').fire('change');
  now+=L.MAX_AGE+1;await a.get('booking-form').fire('submit');
  assert.equal(a.selected.length,0);assert.equal(a.get('booking-origin').value,'');assert.match(a.get('location-status').textContent,/expired/);
});
test('ambiguous nearby aliases require a manual origin before estimates',async()=>{
  const a=app({stored:[{alias:'HOME',...coords},{alias:'OFFICE',...coords}],geo:{getCurrentPosition(s){s({coords,timestamp:Date.now()});}}});
  await a.get('use-location').fire('click');assert.equal(a.get('booking-origin').value,'');assert.match(a.get('location-status').textContent,/Several configured/);
  assert.equal(a.get('show-estimate').disabled,true);
});
