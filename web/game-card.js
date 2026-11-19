const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=v=>{try{const u=new URL(v);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
const initials=v=>String(v??'').split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join('').toUpperCase();
const num=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('pt-PT',{maximumFractionDigits:2}):'—';
export function kickoffLabel(value){
 const valid=typeof value==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(+new Date(value));
 if(!valid)return {date:'Data por confirmar',time:'Hora por confirmar',iso:''};
 const date=new Date(value);
 return {date:new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',day:'2-digit',month:'2-digit',year:'numeric'}).format(date),time:new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',hour:'2-digit',minute:'2-digit'}).format(date),iso:date.toISOString()};
}
export function gameCard(p,{sports={},countries={},markets={},sources={},phase='watchlist',featured=false,favorite=false}={}){
 const confirmed=phase==='today'||phase==='future';
 const status=phase==='today'?'Validado entre fontes':phase==='future'?'Consenso preliminar':'Em observação';
 const evidence=Array.isArray(p.sources)?p.sources:[];
 const community=evidence.find(s=>s.source==='olbg');
 const model=evidence.find(s=>s.metric_kind==='model_pct');
 const kickoff=kickoffLabel(p.kickoff);
 const metric=community?`${community.votes_for}/${community.votes_total}`:model?`${num(model.metric)}%`:'—';
 const metricTitle=community?'Votos OLBG':model?`Modelo ${sources[model.source]??model.source}`:'Métrica publicada';
 const foot=phase==='today'?`${p.source_count} fontes concordam no mesmo mercado.`:phase==='future'?'Consenso observado agora. Reavaliar no dia do jogo.':'Falta confirmação independente para entrar na seleção validada.';
 return `<article class="game-card ${featured?'game-card-featured':''} ${confirmed?'game-card-confirmed':''}" aria-label="${esc(p.match)}"><div class="mi-card-signature"><img src="./assets/logo-mmi.webp" alt="M.Mi." width="48" height="48"><div><strong>MISTER MI<span>.</span></strong><small>O OLHAR DO TEU ANALISTA</small></div><span class="mi-analysis-seal" lang="ja" aria-label="Análise">分析</span></div><div class="game-card-top"><span class="game-state">${esc(status)}</span>${phase==='today'?`<button class="game-favorite ${favorite?'on':''}" data-favorite="${esc(p.id)}" aria-label="${favorite?'Remover dos favoritos':'Adicionar aos favoritos'}" aria-pressed="${favorite}">★</button>`:''}<span>${esc(sports[p.sport]??p.sport)} · ${esc(countries[p.country]??p.country)}</span><time class="game-schedule" datetime="${esc(kickoff.iso)}"><span>${esc(kickoff.date)}</span><strong>${esc(kickoff.time)}</strong><small>Hora de Lisboa</small></time></div><div class="game-teams"><div><span class="game-avatar">${esc(initials(p.home))}</span><h3>${esc(p.home)}</h3></div><span class="game-vs">VS</span><div><span class="game-avatar">${esc(initials(p.away))}</span><h3>${esc(p.away)}</h3></div></div><div class="game-selection"><span>${esc(markets[p.market]??p.market)}</span><strong>${esc(p.selection)}</strong></div><div class="game-stats"><div><strong>${num(p.odds)}</strong><span>Odd observada</span></div><div><strong>${esc(p.source_count??evidence.length)}</strong><span>Fontes com sinal apto</span></div><div><strong>${esc(metric)}</strong><span>${esc(metricTitle)}</span></div></div><p class="game-competition">${esc(p.competition)}</p><div class="game-evidence">${evidence.map(s=>`<a href="${url(s.url)}" target="_blank" rel="noopener noreferrer">${esc(sources[s.source]??s.source)}${s.metric_kind==='vote_pct'?` · ${num(s.metric)}% de apoio`:s.metric_kind==='model_pct'?` · ${num(s.metric)}% no modelo`:''}</a>`).join('')}</div><div class="game-card-bottom"><span>${esc(foot)}${p.fixture_verification?.status==='verified'?' Calendário verificado.':''}</span>${phase==='today'?`<button class="button lime" data-analysis="${esc(p.id)}">Ver análise completa</button>`:evidence.length?`<a class="game-action" href="${url(evidence[0].url)}" target="_blank" rel="noopener noreferrer">Ver evidência na fonte</a>`:''}</div></article>`;
}
