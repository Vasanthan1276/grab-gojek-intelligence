'use strict';
const E = RideEvidence;
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = n => typeof n === 'number' && Number.isFinite(n) ? `S$${n.toLocaleString('en-SG',{minimumFractionDigits:2,maximumFractionDigits:2})}` : 'Unavailable';
const typical = n => `~S$${Math.round(n)}`;
const range = s => `S$${Math.floor(s.p25)}–${Math.ceil(s.p75)}`;
const name = route => (route.stops || [route.origin,route.destination]).map(x=>x.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase())).join(' → ');
const options = [{provider:'Grab',pricing:'Fixed',label:'Grab Fixed'},{provider:'Grab',pricing:'Metered',label:'Grab Metered'},{provider:'Gojek',pricing:'Any',label:'Gojek'}];
let data, route;
function period(b) { return b.dateRange ? `${esc(b.dateRange.start)} to ${esc(b.dateRange.end)}` : 'Comparable-trip dates unavailable'; }
function renderRoute() {
  route = data.routes.find(r=>r.key === $('route').value);
  $('quote-result').textContent = 'Compare a quote for this selection. Quotes are not saved.';
  document.querySelectorAll('[data-route]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.route === route?.key)));
  if (!route) {
    $('options').textContent = 'No publishable route data. Refresh and review the private history first.';
    ['route-context','distance','timing','comparison'].forEach(id=>$(id).textContent='');
    return;
  }
  const hour = $('hour').value, day = $('weekday').value;
  const kind = route.journey_type === 'multi_stop' ? 'Reviewed ordered multi-stop route' : route.journey_type === 'direct' ? 'Reviewed direct route' : 'Legacy endpoint grouping · stops unverified';
  $('route-context').innerHTML = `<strong>${esc(name(route))}</strong> · ${esc(kind)}<br>Route sample: ${route.overall.count} paid trips. ${route.date_range ? esc(route.date_range.start + ' to ' + route.date_range.end) : 'Route date range unavailable in the existing aggregate.'}`;
  const cards = [...options];
  if (route.grab_pricing_types?.Premium) cards.push({provider:'Grab',pricing:'Premium',label:'Grab Premium / Plus'});
  $('options').innerHTML = cards.map(o=>{
    const b = E.select(route,o.provider,o.pricing,hour,day);
    if (!b.stats) return `<article class="option empty"><h3>${esc(o.label)}<span class="service-dot"></span></h3><div class="value">Insufficient data</div><p class="muted">Missing or withheld sample. No provider or service substitution.</p><span class="badge low">No benchmark</span></article>`;
    return `<article class="option"><h3>${esc(o.label)}<span class="service-dot"></span></h3><div class="value">${typical(b.stats.median)}</div><small>Typical historical paid fare</small><div class="range">${range(b.stats)}<br><small>Middle 50% of observations</small></div><div class="meta muted">${esc(b.source)}<br>${b.sampleCount} trips · ${period(b)}${b.widened ? '<br>Time/day match unavailable; using all observed times.' : ''}</div><span class="badge ${b.sampleCount<10?'low':''}">${b.sampleCount<10?'Low sample · descriptive only':'Historical sample · not a forecast'}</span></article>`;
  }).join('');
  const paired = E.compare(route,[options[0],options[2]],hour,day);
  $('comparison').innerHTML = paired ? `<strong>Grab Fixed / Gojek: ${paired[0].scope === 'overall' ? 'all observed times' : paired[0].scope === 'hour' ? esc(hour)+':00 hour' : esc(day)}.</strong> Historical medians ${typical(paired[0].stats.median)} (${paired[0].sampleCount} trips) and ${typical(paired[1].stats.median)} (${paired[1].sampleCount} trips).<br>These are separate completed-ride samples, not simultaneous quotes. ${paired.every(b=>b.dateRange)?'Date periods may differ.':'Comparable date overlap is unknown.'} Check both apps; the lower current price cannot be inferred from this history.` : '<strong>No supported Grab Fixed / Gojek comparison for this route.</strong> At least five observations in each matching group are needed. Check both apps for current prices.';
  const km = E.distance(route), d = route.distance;
  $('distance').innerHTML = km ? `<p><strong>~${km.toFixed(1)} km</strong> · ${esc(d.source || 'Source unavailable')} modelled driving route · rounded to ${esc(d.distance_precision_km || 'unknown')} km.</p><p>Calculated: ${esc(d.calculated_on || 'not recorded')}. ${d.status === 'carried_forward' ? 'Carried forward after a failed refresh; not newly measured.' : 'Not the distance actually travelled.'}</p><ul>${cards.map(o=>{ const b=E.select(route,o.provider,o.pricing,hour,day);return `<li>${esc(o.label)}: ${b.stats ? `~${money(E.perKm(b.stats.median,km))}/km · same ${b.sampleCount}-trip sample` : 'insufficient data'}</li>`; }).join('')}</ul><p>Statement totals may include tolls, waiting, fees and discounts. Components are unavailable. S$/km inherits uncertainty from fares, rounded distance and unknown legacy stops.</p>` : '<p>Distance unavailable for this journey. No straight-line, reverse-route or endpoint-only multi-stop substitute is used; S$/km is withheld.</p>';
  const hours = Array.from({length:24},(_,i)=>String(i).padStart(2,'0')).map(h=>({h,p:E.compare(route,[options[0],options[2]],h,null)})).filter(x=>x.p && x.p[0].scope==='hour');
  $('timing').innerHTML = hours.length ? '<p>Grab Fixed / Gojek at the same hour. Weekdays are mixed; these are not paired quotes.</p>'+hours.map(x=>`<div class="timing-row"><span>${x.h}:00–${x.h}:59</span><span>${typical(x.p[0].stats.median)} (n=${x.p[0].sampleCount}) / ${typical(x.p[1].stats.median)} (n=${x.p[1].sampleCount})</span></div>`).join('')+'<p>No causal “best time” recommendation is supported.</p>' : '<p>No same-hour Grab Fixed / Gojek groups meet the sample threshold. There is no supported “best time to book” conclusion.</p>';
}
function checkQuote(event) {
  event.preventDefault();
  const value=$('quote-amount').value.trim(), amount=value ? Number(value) : NaN;
  if (!route || !Number.isFinite(amount) || amount <= 0) { $('quote-result').textContent='Choose a route and enter a positive finite amount.'; return; }
  const [provider,pricing]=$('quote-service').value.split('|');
  const b=E.select(route,provider,pricing,$('hour').value,$('weekday').value);
  if (!b.stats) { $('quote-result').textContent='Insufficient comparable history. Your quote cannot be rated; no other service is substituted. Check current prices and inclusions in both apps.'; return; }
  $('quote-result').innerHTML=`<strong>${esc(E.position(amount,b.stats))}</strong><p>Your entered quote: ${money(amount)}. Historical middle 50%: ${range(b.stats)}. ${esc(b.source)} · ${b.sampleCount} trips · ${period(b)}.</p><p>${pricing==='Metered'?'A metered quote may be an estimate or range; the final fare can differ. ':''}This is a historical comparison, not a prediction, live quote or booking recommendation. Check fees and promotions. Nothing has been saved.</p>`;
}
function renderHistory() {
  const s=data.summary || {};
  $('totals').innerHTML=[['Recorded ride spend',money(s.ride_spend_sgd),'SGD paid-fare totals'],['Ride records',s.ride_transactions ?? 'Unavailable','Includes other currencies'],['Food spend',money(s.food_spend_sgd),`${s.food_orders ?? 0} recorded orders`],['Published routes',data.routes.length,'Small route samples withheld']].map(([l,v,n])=>`<div class="total"><span>${esc(l)}</span><strong>${esc(v)}</strong><span>${esc(n)}</span></div>`).join('');
  const months=data.monthly || [], max=Math.max(1,...months.map(m=>m.total));
  $('monthly').innerHTML=months.map(m=>`<div class="month-row"><span>${esc(m.month)}</span><div class="month-bar" aria-hidden="true"><i style="width:${Math.min(100,100*m.total/max)}%"></i></div><span class="amount">${money(m.total)}</span></div>`).join('') || '<p>Monthly detail is withheld because the old aggregates do not record sample counts. A reviewed private-history rebuild can restore supported months.</p>';
  $('sources').innerHTML=Object.entries(data.source_summary || {}).map(([p,s])=>`<p><strong>${esc(p)}</strong><br>${esc(s.period || 'Date range unavailable')}<br>${esc(s.transactions)} transactions; dates include food where present.</p>`).join('')+`<p>${esc(E.historyNote(data))}</p>`;
  const food=data.food || {};
  $('food').innerHTML=`<p>${food.order_count || 0} recorded orders · ${money(food.total_spend_sgd)}.</p>`+(food.top_restaurants?.length ? food.top_restaurants.map(r=>`<p>${esc(r.restaurant)} · ${r.count} orders · ${money(r.average_order)} average</p>`).join(''):'<p>Restaurant detail withheld where the sample or public-label checks are not met.</p>');
}
async function init() {
  try {
    const response=await fetch('data/analytics.json',{cache:'no-store'});
    if (!response.ok) throw new Error('Unavailable');
    data=await response.json();
    if (!Array.isArray(data.routes)) throw new Error('Invalid data');
    const refreshed=data.history_refreshed_at || data.generated_on;
    const freshness=E.stale(refreshed);
    const refreshLabel = freshness === null ? 'unknown' : new Date(refreshed).toLocaleString('en-SG',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Singapore'}) + ' SGT';
    $('freshness').innerHTML=`<strong>${freshness === true ? 'Historical data needs refreshing' : freshness === null ? 'History refresh date unavailable' : 'Historical data loaded'}</strong>History refresh: ${esc(refreshLabel)}. ${data.history_refreshed_at ? '' : 'Exact refresh time was not recorded.'} Distance enrichment: ${esc(data.distance_analysis?.generated_on || 'unknown')}. Neither is a live-price update. Current app quotes may differ materially.`;
    $('coverage').textContent=`${data.routes.length} published routes · groups below ${E.MIN} withheld`;
    if (data.history_reconciliation?.status !== 'matched' && data.history_reconciliation) {
      $('freshness').appendChild(document.createElement('p')).textContent = 'Rebuilt from available statements. An older summary differs; completeness is not guaranteed. See Spending & coverage for details.';
    }
    $('route').innerHTML=data.routes.length ? data.routes.map(r=>`<option value="${esc(r.key)}">${esc(name(r))}${r.journey_type==='direct'?' (reviewed direct)':r.journey_type==='multi_stop'?' (multi-stop)':' (stops unverified)'}</option>`).join('') : '<option value="">No routes available</option>';
    $('frequent').innerHTML=data.routes.slice(0,4).map(r=>`<button class="route-card" data-route="${esc(r.key)}" aria-pressed="false"><strong>${esc(name(r))} →</strong><span>${r.overall.count} trips · historical endpoint group</span></button>`).join('');
    document.querySelectorAll('[data-route]').forEach(b=>b.addEventListener('click',()=>{ $('route').value=b.dataset.route;renderRoute(); }));
    $('hour').insertAdjacentHTML('beforeend',Array.from({length:24},(_,i)=>`<option value="${String(i).padStart(2,'0')}">${String(i).padStart(2,'0')}:00–${String(i).padStart(2,'0')}:59</option>`).join(''));
    $('weekday').insertAdjacentHTML('beforeend',['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map(d=>`<option>${d}</option>`).join(''));
    ['route','hour','weekday'].forEach(id=>$(id).addEventListener('change',renderRoute));
    $('quote-service').addEventListener('change',()=>{ $('quote-result').textContent='Service changed. Compare again to update the result.'; });
    $('quote-amount').addEventListener('input',()=>{ $('quote-result').textContent='Quote changed. Compare again to update the result.'; });
    $('quote-form').addEventListener('submit',checkQuote);
    renderRoute();renderHistory();
    initBooking(data.routes,(key,time)=>{ $('route').value=key;$('hour').value=time.hour;$('weekday').value=time.weekday;renderRoute(); });
  } catch (_) { $('freshness').textContent='Unable to load historical data. No fare estimates are available. Reload or check the data build.'; }
}
init();
