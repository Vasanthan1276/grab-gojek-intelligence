/* On-device place matching. No network, logging, geocoding or trip storage. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RideLocation=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const KEY='ride-place-anchors-v1', RADIUS=250, MAX_ACCURACY=100, MAX_AGE=120000;
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  function validPoint(p){return !!p&&finite(p.latitude)&&Math.abs(p.latitude)<=90&&finite(p.longitude)&&Math.abs(p.longitude)<=180&&finite(p.accuracy)&&p.accuracy>=0&&p.accuracy<=MAX_ACCURACY;}
  function position(p,now=Date.now()){
    if(!p||!finite(p.timestamp)||p.timestamp>now+10000||now-p.timestamp>MAX_AGE)return {status:'stale'};
    if(!validPoint(p.coords))return {status:'inaccurate'};
    return {status:'ready',point:{latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy},timestamp:p.timestamp};
  }
  function metres(a,b){
    if(!validPoint(a)||!validPoint(b))return null;
    const rad=x=>x*Math.PI/180, dlat=rad(b.latitude-a.latitude),dlon=rad(b.longitude-a.longitude);
    const h=Math.sin(dlat/2)**2+Math.cos(rad(a.latitude))*Math.cos(rad(b.latitude))*Math.sin(dlon/2)**2;
    return 6371000*2*Math.atan2(Math.sqrt(Math.min(1,h)),Math.sqrt(Math.max(0,1-h)));
  }
  function match(point,anchors){
    if(!validPoint(point))return {status:'inaccurate'};
    const candidates=anchors.filter(a=>validPoint(a)).map(a=>({alias:a.alias,distance:metres(point,a),uncertainty:point.accuracy+a.accuracy}));
    const possible=candidates.filter(a=>a.distance-a.uncertainty<=RADIUS);
    if(possible.length>1)return {status:'ambiguous'};
    if(possible.length===1&&possible[0].distance+possible[0].uncertainty<=RADIUS)return {status:'matched',alias:possible[0].alias};
    return {status:'unmatched'};
  }
  function cleanAnchors(anchors,aliases){
    if(!Array.isArray(anchors))return [];
    const allowed=new Set(aliases),seen=new Set();
    return anchors.filter(a=>a&&allowed.has(a.alias)&&!seen.has(a.alias)&&validPoint(a)&&(seen.add(a.alias),true)).map(a=>({alias:a.alias,latitude:a.latitude,longitude:a.longitude,accuracy:a.accuracy}));
  }
  function load(storage,aliases){
    try{const raw=storage.getItem(KEY);if(!raw)return {anchors:[],remember:false};const value=JSON.parse(raw);if(value.version!==1)throw Error();return {anchors:cleanAnchors(value.anchors,aliases),remember:true};}
    catch(_){return {anchors:[],remember:false,error:true};}
  }
  function save(storage,anchors,aliases,remember){
    try{if(remember)storage.setItem(KEY,JSON.stringify({version:1,anchors:cleanAnchors(anchors,aliases)}));else storage.removeItem(KEY);return true;}catch(_){return false;}
  }
  function routesFor(routes,origin,destination){return routes.filter(r=>r.origin===origin&&r.destination===destination);}
  function singaporeTime(date=new Date()){
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Singapore',hourCycle:'h23',hour:'2-digit',minute:'2-digit',weekday:'long'}).formatToParts(date);
    const get=type=>parts.find(p=>p.type===type).value;
    return {hour:get('hour'),weekday:get('weekday'),label:`${get('weekday')} ${get('hour')}:${get('minute')} Singapore time`};
  }
  function request(geolocation,secure=true){
    if(!secure)return Promise.resolve({status:'insecure'});
    if(!geolocation||typeof geolocation.getCurrentPosition!=='function')return Promise.resolve({status:'unsupported'});
    return new Promise(resolve=>{
      try{geolocation.getCurrentPosition(p=>resolve(position(p)),e=>resolve({status:({1:'denied',2:'unavailable',3:'timeout'})[e?.code]||'unavailable'}),{enableHighAccuracy:true,timeout:15000,maximumAge:0});}
      catch(_){resolve({status:'unavailable'});}
    });
  }
  return {KEY,RADIUS,MAX_ACCURACY,MAX_AGE,validPoint,position,metres,match,cleanAnchors,load,save,routesFor,singaporeTime,request};
});
