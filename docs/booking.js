/* Coordinates stay in memory unless the user opts into this browser's storage. */
'use strict';
function initBooking(routes,onSelect){
  const L=RideLocation, el=id=>document.getElementById(id);
  const label=alias=>alias.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
  const origins=[...new Set(routes.map(r=>r.origin))].sort();
  const destinations=[...new Set(routes.map(r=>r.destination))].sort();
  const aliases=[...new Set([...origins,...destinations])];
  const add=(id,values)=>values.forEach(v=>el(id).add(new Option(label(v),v)));
  add('booking-origin',origins);add('booking-destination',destinations);add('place-alias',aliases);
  let storage;try{storage=window.localStorage;}catch(_){}
  const saved=L.load(storage,aliases);
  let anchors=saved.anchors, current=null, generation=0, matchedAt=null;
  el('remember-places').checked=saved.remember;
  const status=text=>{el('location-status').textContent=text;};
  function places(){
    el('saved-places').textContent=anchors.length?`Configured places: ${anchors.map(a=>label(a.alias)).join(', ')}. ${el('remember-places').checked?'Remembered on this browser.':'This page session only.'}`:'No places configured. Your private places need to be identified on this device first.';
  }
  function persist(){
    if(!L.save(storage,anchors,aliases,el('remember-places').checked)){
      status('Browser storage could not be updated. Places work for this page session. If removing saved places, clear this site’s storage in browser settings.');
      el('remember-places').checked=false;
    }
    places();
  }
  function update(){
    const choices=L.routesFor(routes,el('booking-origin').value,el('booking-destination').value);
    el('booking-journey').replaceChildren(new Option('Choose journey / stops',''));
    choices.forEach(r=>el('booking-journey').add(new Option(`${(r.stops||[r.origin,r.destination]).map(label).join(' → ')} (${r.journey_type==='direct'?'reviewed direct':r.journey_type==='multi_stop'?'multi-stop':'stops unverified'})`,r.key)));
    if(choices.length===1)el('booking-journey').value=choices[0].key;
    el('journey-picker').hidden=choices.length===0||(choices.length===1&&choices[0].journey_type!=='multi_stop');
    el('show-estimate').disabled=!choices.length;
    el('booking-result').textContent=!el('booking-origin').value||!el('booking-destination').value?'Choose a starting place and destination.':!choices.length?'No comparable route history for this direction. No fare is estimated; check both provider apps.':choices.length>1?'Choose the exact journey, including stops. Routes with the same endpoints are kept separate.':`Available history: ${choices[0].journey_type==='multi_stop'?'a multi-stop journey; check its ordered stops':choices[0].journey_type==='direct'?'a reviewed direct route':'an older endpoint group with unverified stops'}. Show the estimate to update the comparison below.`;
  }
  el('booking-origin').addEventListener('change',()=>{matchedAt=null;status('Starting place selected manually.');update();});
  el('booking-destination').addEventListener('change',update);
  el('booking-journey').addEventListener('change',()=>{el('booking-result').textContent='Journey changed. Show the estimate to update the comparison below.';});
  el('use-location').addEventListener('click',async()=>{
    const token=++generation;current=null;matchedAt=null;
    el('booking-origin').value='';el('save-place').disabled=true;update();
    el('use-location').disabled=true;el('booking-origin').disabled=true;
    status('Requesting one current location reading. Allow location access in your browser if you want to use it.');
    const result=await L.request(navigator.geolocation,window.isSecureContext);
    if(token!==generation)return;
    el('use-location').disabled=false;el('booking-origin').disabled=false;
    const errors={denied:'Location access was denied. Choose your starting place manually or change this site’s browser permission.',unavailable:'Location is unavailable. Choose your starting place manually.',timeout:'Location took too long. Try again outdoors or choose your starting place manually.',insecure:'Location needs an HTTPS page. Choose your starting place manually.',unsupported:'This browser does not provide location. Choose your starting place manually.',inaccurate:'Location is too imprecise to identify a place safely. Try again outdoors or choose manually.',stale:'The location reading is old. Try again or choose your starting place manually.'};
    if(result.status!=='ready'){status(errors[result.status]||errors.unavailable);return;}
    current=result;el('save-place').disabled=false;
    const match=L.match(current.point,anchors);
    if(match.status==='matched'&&origins.includes(match.alias)){
      el('booking-origin').value=match.alias;matchedAt=current.timestamp;
      status(`Near ${label(match.alias)}. Confirm the starting place, then choose your destination. Location matching is approximate.`);
    }else{
      status(match.status==='ambiguous'?'Several configured places may match. Choose your starting place manually.':'No supported starting place matches this location. Choose manually, or identify this spot in Place setup.');
      el('place-setup').open=true;
    }
    update();
  });
  el('save-place').addEventListener('click',()=>{
    const alias=el('place-alias').value;
    if(!alias){status('Choose the place alias to identify this spot.');return;}
    if(!current||Date.now()-current.timestamp>L.MAX_AGE){current=null;el('save-place').disabled=true;status('Get a fresh current location before identifying this place.');return;}
    anchors=anchors.filter(a=>a.alias!==alias).concat({alias,...current.point});
    status(`${label(alias)} is configured at this spot. This replaces any earlier point for that alias.`);persist();
    if(origins.includes(alias)){el('booking-origin').value=alias;matchedAt=current.timestamp;update();}
  });
  el('remember-places').addEventListener('change',persist);
  el('forget-places').addEventListener('click',()=>{
    generation++;anchors=[];current=null;matchedAt=null;
    el('remember-places').checked=false;el('use-location').disabled=false;el('booking-origin').disabled=false;
    el('booking-origin').value='';el('save-place').disabled=true;
    status('Configured places and the current reading cleared from this page.');persist();update();
  });
  el('booking-form').addEventListener('submit',event=>{
    event.preventDefault();
    if(matchedAt&&Date.now()-matchedAt>L.MAX_AGE){el('booking-origin').value='';matchedAt=null;update();status('Your location match has expired. Use current location again or choose your starting place manually.');return;}
    const r=L.routesFor(routes,el('booking-origin').value,el('booking-destination').value).find(r=>r.key===el('booking-journey').value);
    if(!r){el('booking-result').textContent='Choose a supported journey and its stops first.';return;}
    const time=L.singaporeTime();onSelect(r.key,time);
    el('booking-result').textContent=`Showing ${label(r.origin)} → ${label(r.destination)} for ${time.label}. Historical paid fares only; no live quote or validated price prediction. Check the sample and time-match limits below.`;
    el('compare-title').focus();el('compare-title').scrollIntoView({block:'start'});
  });
  places();update();
  if(saved.error)status('Saved-place storage is unavailable or unreadable. Manual selection and this page’s location setup still work.');
}
