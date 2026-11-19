import {visibleWatchlist} from './coverage.js';

export function lisbonDate(value=Date.now()) {
  const date=new Date(value);if(!Number.isFinite(+date))return '';
  const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Lisbon',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
  return ['year','month','day'].map(key=>p.find(part=>part.type===key).value).join('-');
}
export function futureDate(offset,now=Date.now()) {
  const current=lisbonDate(now);
  if(![1,2].includes(offset)||!current)return '';
  return new Date(Date.parse(current+'T12:00:00Z')+offset*86400000).toISOString().slice(0,10);
}
export function outlookState(payload,offset,{now=Date.now()}={}) {
  const date=futureDate(offset,now);
  if(!date)return {valid:false,date,reason:'Data de pré-visualização inválida.'};
  if(!payload||payload.date!==lisbonDate(now))return {valid:false,date,reason:'É necessária uma recolha do dia corrente para consultar os próximos dias.'};
  const age=(now-new Date(payload.updated_at).getTime())/60000;
  if(!Number.isFinite(age)||age < -1||age>(payload.settings?.max_age_minutes??45))
    return {valid:false,date,reason:'A recolha perdeu frescura. Atualiza os dados antes de consultar os próximos dias.'};
  if(payload.status==='error')return {valid:false,date,reason:'As fontes estão indisponíveis nesta recolha.'};
  const snapshot=(Array.isArray(payload.previews)?payload.previews:[]).find(p=>p?.date===date&&p.day_offset===offset);
  if(!snapshot)return {valid:false,date,reason:'Esta recolha ainda não publicou a pré-visualização desta data. É necessária uma nova execução no GitHub.'};
  if(snapshot.is_preview!==true||snapshot.analysis_mode!=='future_preview'||snapshot.updated_at!==payload.updated_at
      ||!Array.isArray(snapshot.candidates)||!Array.isArray(snapshot.watchlist)||!snapshot.diagnostics
      ||![snapshot.total_eligible,snapshot.total_consensus_candidates,snapshot.diagnostics.today_forecasts,snapshot.diagnostics.today_events].every(n=>Number.isSafeInteger(n)&&n>=0))
    return {valid:false,date,reason:'A pré-visualização desta data não tem dados válidos.'};
  return {valid:true,date,snapshot};
}
export function outlookCandidates(snapshot,{now=Date.now(),preferences={}}={}) {
  const watchlist=visibleWatchlist(snapshot,{today:snapshot.date,now,preferences});
  const lead=(snapshot.settings?.lead_minutes??5)*60000;
  const confirmed=(snapshot.candidates??[]).filter(p=>p.status==='preliminary_consensus'&&p.is_recommendation===false
    &&typeof p.kickoff==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(p.kickoff)
    &&lisbonDate(p.kickoff)===snapshot.date&&new Date(p.kickoff).getTime()>now+lead
    &&!preferences.excluded_sports?.includes(p.sport)&&!preferences.excluded_countries?.includes(p.country)
    &&!preferences.excluded_combinations?.some(r=>r.sport===p.sport&&r.country===p.country)
    &&(preferences.min_odds==null||(typeof p.odds==='number'&&p.odds>=preferences.min_odds))
    &&(preferences.max_odds==null||(typeof p.odds==='number'&&p.odds<=preferences.max_odds)));
  return {confirmed,watchlist};
}
