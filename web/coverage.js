const count = value => Number.isInteger(value) && value >= 0 ? value : 0;
export const rejectionLabels = {
  insufficient_votes:'Poucos votos na fonte', below_source_threshold:'Apoio abaixo do limiar da fonte',
  missing_metric:'Métrica pública em falta', invalid_votes:'Contagem de votos inválida',
  ambiguous_identity:'Identidade ambígua', invalid_record:'Registo inválido',
  not_scheduled:'Jogo fora do estado agendado', unsupported_market:'Mercado sem suporte',
  unsupported_source:'Fonte sem regra de validação'
};
export function coverageView(payload) {
  const d=payload?.diagnostics;
  if(!d)return null;
  const sources=payload.sources??[];
  const available=new Set(sources.filter(s=>['ok','partial'].includes(s.status)).map(s=>s.id));
  const usable=(d.by_source??[]).filter(s=>available.has(s.id)&&s.eligible>0).length;
  const unavailable=sources.filter(s=>s.status==='error').length;
  return {
    metrics:[['Previsões extraídas',count(payload.total_collected)],['Do dia corrente',count(d.today_forecasts)],
      ['Jogos identificados',count(d.today_events)],['Passam a regra da fonte',count(d.eligible_forecasts)],
      ['Opções validadas',count(payload.total_selected)]],
    usable,unavailable,
    reasons:Object.entries(d.threshold_reasons??{}).filter(([,n])=>n>0).map(([key,n])=>[rejectionLabels[key]??'Outros registos sem validação',count(n)]),
    comparisons:[['Falta confirmação de outra fonte',count(d.comparison_rejections?.insufficient_sources)],
      ['Sem horário que confirme o início',count(d.comparison_rejections?.missing_kickoff)],
      ['Conflitos de seleção',count(payload.discarded?.conflict)],
      ['Exclusões definidas',count(payload.discarded?.excluded)],
      ['Fora dos limites de odds',count(d.comparison_rejections?.odds_filter)],
      ['Consenso abaixo do limiar',count(d.comparison_rejections?.below_consensus_score)]].filter(([,n])=>n>0)
  };
}

export function visibleWatchlist(payload,{now=Date.now(),today,preferences={},sport='all',query=''}={}) {
  const lead=(payload?.settings?.lead_minutes??5)*60000;
  if(!today||payload?.date!==today)return [];
  const dayOf=value=>{
    if(typeof value!=='string'||!/(?:Z|[+-]\d{2}:\d{2})$/.test(value))return '';
    const date=new Date(value);if(!Number.isFinite(+date))return '';
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Lisbon',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
    return ['year','month','day'].map(key=>parts.find(p=>p.type===key).value).join('-');
  };
  return (payload.watchlist??[]).filter(p=>p.is_recommendation===false
    &&p.status==='awaiting_independent_source'&&dayOf(p.kickoff)===today&&new Date(p.kickoff).getTime()>now+lead
    &&!preferences.excluded_sports?.includes(p.sport)&&!preferences.excluded_countries?.includes(p.country)
    &&!preferences.excluded_combinations?.some(r=>r.sport===p.sport&&r.country===p.country)
    &&(preferences.min_odds==null||(typeof p.odds==='number'&&p.odds>=preferences.min_odds))
    &&(preferences.max_odds==null||(typeof p.odds==='number'&&p.odds<=preferences.max_odds))
    &&(sport==='all'||sport===p.sport)
    &&(!query||`${p.match} ${p.competition} ${p.country}`.toLocaleLowerCase('pt-PT').includes(query)));
}
