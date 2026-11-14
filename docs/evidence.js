/* Shared, testable historical evidence rules. No model, live fetch or storage. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RideEvidence = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const MIN = 5;
  const numeric = x => typeof x === 'number' && Number.isFinite(x);
  function validStats(s) {
    return !!s && Number.isInteger(s.count) && s.count >= MIN &&
      ['average','median','p25','p75'].every(k => numeric(s[k]) && s[k] >= 0) &&
      s.p25 <= s.median && s.median <= s.p75;
  }
  function groups(route, provider, pricing = 'Any') {
    if (!route) return {};
    if (provider === 'Grab' && pricing !== 'Any') return {
      overall: route.grab_pricing_types?.[pricing], hour: route.grab_pricing_hourly?.[pricing],
      weekday: route.grab_pricing_weekdays?.[pricing], label: `Grab ${pricing}`
    };
    if (provider === 'Overall') return {
      overall: route.overall, hour: route.hourly, weekday: route.weekdays, label: 'All providers / mixed services'
    };
    if (!['Grab','Gojek'].includes(provider)) return {};
    return { overall: route.providers?.[provider], hour: route.provider_hourly?.[provider],
      weekday: route.provider_weekdays?.[provider], label: provider === 'Grab' ? 'Grab / mixed services' : 'Gojek' };
  }
  function candidate(g, scope, key) { return scope === 'overall' ? g.overall : g[scope]?.[key]; }
  function pack(g, s, scope, key, requested) {
    return { stats: s, sampleCount: s.count, providerLabel: g.label, scope,
      source: `${g.label} · ${scope === 'overall' ? 'all observed times' : scope === 'hour' ? `${key}:00–${key}:59` : key}`,
      dateRange: s.date_range || null, widened: scope === 'overall' && !!(requested.hour || requested.weekday),
      weekdayAdjustment: null, status: s.count < 10 ? 'low_sample' : 'historical_sample' };
  }
  function select(route, provider, pricing, hour, weekday) {
    const g = groups(route, provider, pricing);
    for (const [scope,key] of [['hour',hour],['weekday',weekday],['overall',null]]) {
      if (scope !== 'overall' && !key) continue;
      const s = candidate(g,scope,key);
      if (validStats(s)) return pack(g,s,scope,key,{hour,weekday});
    }
    return { stats: null, status: 'insufficient_data', source: g.label || 'Unavailable', sampleCount: null,
      reason: 'Fewer than 5 usable comparable trips, withheld small groups, or missing data. No other provider/service substituted.' };
  }
  function compare(route, options, hour, weekday) {
    const gs = options.map(o => groups(route,o.provider,o.pricing));
    if (gs.length < 2) return null;
    for (const [scope,key] of [['hour',hour],['weekday',weekday],['overall',null]]) {
      if (scope !== 'overall' && !key) continue;
      const ss = gs.map(g => candidate(g,scope,key));
      if (ss.every(validStats)) return gs.map((g,i)=>pack(g,ss[i],scope,key,{hour,weekday}));
    }
    return null;
  }
  function distance(route) {
    const d = route?.distance;
    return numeric(d?.distance_km) && d.distance_km > 0 ? d.distance_km : null;
  }
  function perKm(amount, km) { return numeric(amount) && amount >= 0 && numeric(km) && km > 0 ? amount / km : null; }
  function position(amount, stats) {
    if (!numeric(amount) || amount <= 0 || !validStats(stats)) return null;
    return amount < stats.p25 ? 'Below the historical middle 50%' : amount > stats.p75 ?
      'Above the historical middle 50%' : 'Within the historical middle 50%';
  }
  function stale(date, today = new Date()) {
    if (!date) return null;
    const value = Date.parse(date);
    return Number.isFinite(value) ? Math.floor((today - value) / 86400000) > 30 : null;
  }
  function historyNote(data) {
    const source = data?.history_basis === 'private_source_records' ?
      'Rebuilt from available source statements and the preserved private baseline. Comparable-group dates are shown where supported. Fare components and ordered stops remain unverified; disputed endpoints are excluded from route benchmarks.' :
      'Legacy aggregate only. Comparable-trip dates and receipt-level provenance are unavailable; a private-source rebuild is needed.';
    const review = data?.history_reconciliation?.status;
    if (review === 'reviewed_legacy_difference') return source +
      ' Historical reconciliation limitation: the earlier published summary differs from the recovered source records. The earlier snapshot and review are preserved privately. No balancing transactions were invented; completeness is not guaranteed.';
    if (review && review !== 'matched') return source + ' Historical reconciliation is unresolved.';
    return source;
  }
  return { MIN, validStats, groups, select, compare, distance, perKm, position, stale, historyNote };
});
