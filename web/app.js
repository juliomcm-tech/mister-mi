import {planPortfolio, DEFAULT_POLICY} from './portfolio.js';
import {initPWA} from './pwa.js';
import {getAnalystMood} from './mood.js';
import {coverageView,visibleWatchlist} from './coverage.js';
import {futureDate,outlookState,outlookCandidates} from './outlook.js';
import {gameCard} from './game-card.js';
import {operationState,canStartCollection} from './operation.js';
import {initOddspediaWidget} from './oddspedia.js';

const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const sports = {football:'Futebol',tennis:'Ténis',basketball:'Basquetebol',hockey:'Hóquei',american_football:'F. americano'};
const sourceNames = {olbg:'OLBG',forebet:'Forebet',protipster:'ProTipster',predictz:'PredictZ',api_football:'API-Football',betclan:'BetClan'};
const stateLabels = {ok:'Recolhida',partial:'Parcial',error:'Indisponível',not_configured:'Opcional',cached:'Em cache'};
const marketNames = {FT_1X2:'Resultado · tempo regulamentar',MATCH_WINNER:'Vencedor do jogo','FT_TOTAL_1.5':'Total de golos · 1.5','FT_TOTAL_2.5':'Total de golos · 2.5','FT_TOTAL_3.5':'Total de golos · 3.5',FT_BTTS:'Ambas marcam'};
const countryNames = {England:'Inglaterra',Scotland:'Escócia',Brazil:'Brasil',Germany:'Alemanha',France:'França',Spain:'Espanha',Italy:'Itália',Japan:'Japão',Netherlands:'Países Baixos',Denmark:'Dinamarca','United States':'Estados Unidos',Uruguay:'Uruguai',Argentina:'Argentina',Portugal:'Portugal'};
const safeURL = value => {try {const u=new URL(value);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
const read = (key, fallback, store=localStorage) => {try{return JSON.parse(store.getItem(key))??fallback;}catch{return fallback;}};
const write = (key,value,store=localStorage) => {try{store.setItem(key,JSON.stringify(value));}catch{}};
const emptyPreferences = {excluded_sports:[],excluded_countries:[],excluded_combinations:[],min_odds:null,max_odds:null};
let preferences = {...emptyPreferences,...read('mister-mi.preferences',{})};
let connection = {apiBase:window.APP_CONFIG?.apiBase??'',auto:false,...read('mister-mi.connection',{})};
let refreshToken = read('mister-mi.refresh-token','',sessionStorage);
let favorites = new Set(read('mister-mi.favorites',[]));
let payload=null, history={records:[]}, health=null, activeSport='all', onlyFavorites=false, busy=false, loadFailed=false, latestMessage='', lastReadError='';
let policy={...DEFAULT_POLICY,...read('mister-mi.policy',{})};
let view='hoje';
let oddspediaWidget;
let experiment=null,experimentRequested=false;
let motionEnabled=read('mister-mi.motion',true)===true;
const requestedDay=new URLSearchParams(location.search).get('day');
let previewOffset=requestedDay==='tomorrow'?1:requestedDay==='after'?2:0;

function lisbonDay(date=new Date()) {
 const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Lisbon',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
 const part=n=>p.find(x=>x.type===n).value;
 return `${part('year')}-${part('month')}-${part('day')}`;
}
const time = value => new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
const dateTime = value => {const d=new Date(value);return Number.isFinite(+d)?new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(d):'Data indisponível';};
const num = (value,digits=1) => typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('pt-PT',{maximumFractionDigits:digits,minimumFractionDigits:digits}):'—';
const money = value => new Intl.NumberFormat('pt-PT',{style:'currency',currency:'EUR'}).format(value);
const pct = value => value===null||value===undefined?'—':`${num(value)}%`;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,7000);}
function notice(message){latestMessage=message;$('notice').textContent=message;$('notice').hidden=!message;}
function changeView(name){
 if(!['hoje','estatisticas','carteira','fontes','definicoes'].includes(name))name='hoje';
 view=name;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${name}`);
 document.querySelectorAll('.rail-button').forEach(el=>{el.classList.toggle('active',el.dataset.view===name);el.setAttribute('aria-current',el.dataset.view===name?'page':'false');});
 if(location.hash!==`#${name}`)historyReplaceHash(name);
 render();oddspediaWidget?.show(name);window.scrollTo({top:0,behavior:'instant'});
}
function historyReplaceHash(name){window.history.replaceState(null,'',`#${name}`);}
document.addEventListener('click',e=>{const nav=e.target.closest('[data-view]');if(nav)changeView(nav.dataset.view);});
window.addEventListener('hashchange',()=>changeView(location.hash.slice(1)));

function freshness(){
 if(!payload)return {valid:false,reason:loadFailed?'Não foi possível obter os dados. Tenta atualizar a análise.':'O Mister Mi está a carregar os dados publicados.'};
 if(payload.date!==lisbonDay())return {valid:false,reason:'Os últimos dados publicados são de outro dia. O Mister Mi só apresenta jogos do dia corrente; é necessária uma nova recolha.'};
 const age=(Date.now()-new Date(payload.updated_at).getTime())/60000;
 if(!Number.isFinite(age)||age < -1)return {valid:false,reason:'A data da recolha não é válida. As opções foram ocultadas.'};
 if(age>(payload.settings?.max_age_minutes??45))return {valid:false,reason:'A última recolha ultrapassou o limite de frescura. As opções ficam ocultas até existir uma análise recente.'};
 if(loadFailed)return {valid:false,reason:lastReadError||'Não foi possível ler a análise publicada. Verifica a ligação e tenta atualizar.'};
 if(payload.status==='error')return {valid:false,reason:'As fontes estão indisponíveis. Ainda não existe uma análise validada para apresentar.'};
 return {valid:true,age};
}
function todaysPicks(){return freshness().valid?(payload?.data??[]).filter(p=>Number.isFinite(+new Date(p.kickoff))&&new Date(p.kickoff).getTime()>Date.now()+(payload.settings?.lead_minutes??5)*60000&&lisbonDay(new Date(p.kickoff))===lisbonDay()):[];}
function visiblePicks(){
 let picks=todaysPicks().filter(p=>!preferences.excluded_sports.includes(p.sport)&&!preferences.excluded_countries.includes(p.country)&&!preferences.excluded_combinations.some(r=>r.sport===p.sport&&r.country===p.country));
 if(preferences.min_odds!==null)picks=picks.filter(p=>typeof p.odds==='number'&&p.odds>=preferences.min_odds);
 if(preferences.max_odds!==null)picks=picks.filter(p=>typeof p.odds==='number'&&p.odds<=preferences.max_odds);
 picks=picks.filter(p=>p.score>=Number($('min-score').value)&&p.source_count>=($('three-sources').checked?3:2));
 if(activeSport!=='all')picks=picks.filter(p=>p.sport===activeSport);
 if(onlyFavorites)picks=picks.filter(p=>favorites.has(p.id));
 const q=$('search').value.toLocaleLowerCase('pt-PT').trim();
 if(q)picks=picks.filter(p=>`${p.match} ${p.competition} ${p.country} ${countryNames[p.country]??''}`.toLocaleLowerCase('pt-PT').includes(q));
 return picks.toSorted ? picks.toSorted(sorter) : [...picks].sort(sorter);
}
function sorter(a,b){const sort=$('sort').value;return sort==='time'?new Date(a.kickoff)-new Date(b.kickoff):sort==='score'?b.score-a.score:b.source_count-a.source_count||b.score-a.score;}
function emptyState(title,copy,action=''){return `<div class="empty-state"><span class="empty-icon">${icon('shield')}</span><h3>${esc(title)}</h3><p>${esc(copy)}</p>${action}</div>`;}
function initials(s){return s.split(/\s+/).filter(Boolean).slice(0,2).map(w=>w[0]).join('').toUpperCase();}
function previewCard(p,confirmed=false){return gameCard(p,{sports,countries:countryNames,markets:marketNames,sources:sourceNames,phase:confirmed?'future':'watchlist',featured:true});}
function sportCoverage(snapshot){
 const rows=snapshot?.diagnostics?.by_sport??[];if(!rows.length)return '';
 return `<div class="sport-coverage"><h3>Os 5 desportos integrados</h3><div class="table-wrap"><table><thead><tr><th>DESPORTO</th><th>EVENTOS IDENTIFICADOS</th><th>SINAIS APTOS</th><th>COM CONSENSO</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(sports[r.id]??r.id)}</td><td>${r.events}</td><td>${r.eligible}</td><td>${r.confirmed}</td></tr>`).join('')}</tbody></table></div><p class="muted">Contagens das previsões acessíveis nesta data. Não representam todos os jogos existentes.</p></div>`;
}
function renderOperation(){
 const state=operationState(payload,{connection,token:refreshToken,health});
 $('operation-banner').hidden=!payload;$('operation-banner').dataset.state=state.level;
 $('operation-title').textContent=state.title;$('operation-message').textContent=state.message;$('operation-schedule').textContent=state.scheduleNote;
 $('refresh').innerHTML=icon('refresh')+state.refreshLabel;$('hero-analyse').innerHTML=icon('refresh')+state.heroLabel;
 return state;
}
function renderOutlook(fresh){
 const shortDate=day=>new Intl.DateTimeFormat('pt-PT',{day:'numeric',month:'short',timeZone:'Europe/Lisbon'}).format(new Date(day+'T12:00:00Z'));
 for(const offset of [0,1,2]){$(`day-label-${offset}`).textContent=shortDate(offset?futureDate(offset):lisbonDay());}
 document.querySelectorAll('[data-preview-day]').forEach(button=>{const active=Number(button.dataset.previewDay)===previewOffset;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
 document.body.classList.toggle('view-future',previewOffset!==0);
 $('future-panel').hidden=previewOffset===0;$('today-workspace').hidden=previewOffset!==0;
 if(!previewOffset)return;
 const state=outlookState(payload,previewOffset);
 $('future-heading').textContent=`${previewOffset===1?'Amanhã':'Depois de amanhã'} · ${shortDate(state.date)}`;
 if(!state.valid||!fresh.valid){$('future-content').innerHTML=emptyState('É necessária uma nova recolha.',!fresh.valid?fresh.reason:state.reason);return;}
 const snap=state.snapshot,d=snap.diagnostics,c=outlookCandidates(snap,{preferences});
 const total=c.confirmed.length+c.watchlist.length;
 const callout=`<div class="candidate-callout"><img src="./assets/logo-mmi.webp" width="58" height="58" alt="M.Mi."><div><strong>${total} ${total===1?'jogo em foco':'jogos em foco'}</strong><span>${c.confirmed.length} com consenso preliminar · ${c.watchlist.length} a aguardar outra fonte</span></div></div>`;
 const confirmed=c.confirmed.length?`<h3 class="game-section-title">Com consenso preliminar</h3><div class="game-grid">${c.confirmed.map(p=>previewCard(p,true)).join('')}</div>`:'';
 const watch=c.watchlist.length?`<h3 class="game-section-title">O olhar do Mister Mi</h3><div class="game-grid">${c.watchlist.map(p=>previewCard(p)).join('')}</div>`:'';
 const empty=total?'':emptyState('Ainda sem candidatos para apresentar.',d.today_forecasts?'As previsões disponíveis não cumprem os critérios e os teus filtros.':'As fontes consultadas ainda não publicaram previsões suportadas para esta data.');
 $('future-content').innerHTML=callout+confirmed+watch+empty+`<p class="muted">Observado em ${dateTime(snap.updated_at)}. Os jogos futuros são reavaliados em cada recolha e ficam fora da carteira simulada.</p>`;
}
function renderCoverage(fresh){
 const c=coverageView(payload);
 $('coverage-panel').hidden=!c;
 if(c){
  $('coverage-funnel').innerHTML=c.metrics.map(([label,value])=>`<div><strong>${value}</strong><span>${esc(label)}</span></div>`).join('');
  $('coverage-note').textContent=`${c.usable} ${c.usable===1?'fonte com previsões aptas':'fontes com previsões aptas'} nesta recolha. ${c.unavailable} ${c.unavailable===1?'fonte indisponível':'fontes indisponíveis'}. A recolha cobre as previsões acessíveis; ainda não abrange todos os jogos do dia.`;
  const d=payload.discarded??{};
  const rows=[['Previsões de outros dias',d.other_day??0],['Início passado ou demasiado próximo',d.started_or_soon??0],['Dados fora do limite de frescura',d.stale??0],...c.reasons,...c.comparisons].filter(([,n])=>n>0);
  $('coverage-reasons').innerHTML=rows.map(([label,value])=>`<div class="coverage-reason"><span>${esc(label)}</span><strong>${value}</strong></div>`).join('')||'<p>Sem exclusões registadas.</p>';
 }
 const candidates=fresh.valid&&!onlyFavorites?visibleWatchlist(payload,{today:lisbonDay(),now:Date.now(),preferences,sport:activeSport,query:$('search').value.toLocaleLowerCase('pt-PT').trim()}):[];
 $('watchlist-panel').hidden=!candidates.length;
 $('watchlist').innerHTML=candidates.map(p=>gameCard(p,{sports,countries:countryNames,markets:marketNames,sources:sourceNames,phase:'watchlist',featured:candidates.length===1})).join('');
 $('coverage-sports').innerHTML=sportCoverage(payload);
}
function renderPicks(){
 const fresh=freshness(),all=todaysPicks(),picks=visiblePicks();
 const op=renderOperation();$('picks').classList.toggle('has-no-picks',!picks.length);
 $('pick-count').textContent=picks.length;
 $('hero-collected').textContent=payload?.total_collected??'—';
 $('hero-sources').textContent=payload?.sources?.filter(s=>s.status!=='not_configured').length??'—';
 $('hero-selected').textContent=all.length;
 $('freshness-status').textContent=busy?(op.canStart?'Mister Mi a recolher…':'A recarregar a publicação…'):fresh.valid?(previewOffset?'Recolha recente · pré-visualização':'Recolha recente · só hoje'):'A recolha precisa de atualização';
 $('last-update').textContent=payload?`Última recolha: ${dateTime(payload.updated_at)} · Lisboa`:'A aguardar a primeira recolha.';
 const d=payload?.diagnostics;
 $('mi-summary').textContent=!fresh.valid?fresh.reason:d?`Recolhi ${payload.total_collected} previsões; ${d.today_forecasts} são de hoje, para ${d.today_events} jogos identificados. ${d.eligible_forecasts} ${d.eligible_forecasts===1?'previsão passou':'previsões passaram'} a regra da sua fonte e ${all.length} opções têm confirmação suficiente. A cobertura ainda é parcial.`:all.length?`De ${payload.total_collected} previsões recolhidas, ${all.length} passaram os critérios. Consulta a evidência de cada opção antes de a incluir na tua simulação.`:'A recolha ainda não fornece confirmação suficiente entre fontes. Consulta o estado e as falhas em Fontes.';
 renderCoverage(fresh);
 renderOutlook(fresh);
 if(!fresh.valid){$('picks').innerHTML=emptyState('Primeiro, dados atuais.',fresh.reason);return;}
 if(!picks.length){$('picks').innerHTML=emptyState(all.length?'Os teus filtros são exigentes.':'Ainda sem confirmação suficiente.',all.length?'Não há opções que correspondam a estes filtros. Podes ajustá-los nas definições.':'Ainda não há opções com confirmação suficiente. Podes consultar o estado das fontes no separador Fontes.',`<button class="text-button blue" data-view="${all.length?'definicoes':'fontes'}">${all.length?'Ajustar filtros':'Ver a recolha do Mister Mi'}</button>`);return;}
 $('picks').innerHTML=picks.map(p=>gameCard(p,{sports,countries:countryNames,markets:marketNames,sources:sourceNames,phase:'today',featured:picks.length===1,favorite:favorites.has(p.id)})).join('');
}
function sourceSummary(){
 const sources=payload?.sources??[];const okay=sources.filter(s=>s.status==='ok').length;
 $('sources-ok').textContent=payload?`${coverageView(payload)?.usable??0} aptas hoje`:'—';
 $('source-summary').innerHTML=sources.length?sources.map(s=>`<div class="source-row"><span><span class="source-dot ${esc(s.status)}"></span>${esc(s.name)}</span><span class="source-state">${esc(stateLabels[s.status]??s.status)}${s.collected?` · ${s.collected}`:''}</span></div>`).join(''):'<p class="muted">A carregar a recolha…</p>';
}
const descriptors={
 betclan:{kind:'MODELO DA FONTE · NOVA INTEGRAÇÃO',url:'https://www.betclan.com/faq/',description:'Probabilidade publicada de pelo menos 65% para a seleção exata, lida no bloco do modelo. O índice de eventos serve para encontrar jogos; só os detalhes consultados contam como previsões. A métrica não foi calibrada pelo Mister Mi.'},
 olbg:{kind:'CONSENSO DA COMUNIDADE',url:'https://www.olbg.com/betting-tips',description:'Pelo menos 15 votos e 75% de apoio. Votos medem popularidade da seleção; não são uma probabilidade de acerto.'},
 forebet:{kind:'PREVISÃO ESTATÍSTICA',url:'https://www.forebet.com/',description:'Pelo menos 65% na probabilidade publicada para a seleção exata. O Mister Mi não calcula nem valida o modelo proprietário.'},
 protipster:{kind:'AVALIAÇÃO DE TIPSTERS',url:'https://www.protipster.com/betting-tips/today',description:'Tip Score público de pelo menos 8/10. Sem essa métrica explícita, a tip não contribui para o consenso.'},
 predictz:{kind:'CONFIRMAÇÃO CATEGÓRICA',url:'https://www.predictz.com/predictions/',description:'Confirma o resultado previsto para a data explícita. Sem probabilidade ou horário publicados, só corrobora uma fonte com início verificado.'},
 api_football:{kind:'API OPCIONAL · REQUER CHAVE',url:'https://www.api-football.com/',description:'Previsões e resultados de futebol. A disponibilidade da época e das competições depende do plano. Quota limitada por execução.'}
};
function renderSources(){
 $('source-details').innerHTML=(payload?.sources??Object.keys(descriptors).map(id=>({id,name:sourceNames[id],status:'not_configured',message:'A aguardar dados'}))).map(s=>{const d=descriptors[s.id]??{};return `<article class="panel source-card"><span class="source-kind">${esc(d.kind??'RESULTADOS')}</span><h2>${esc(s.name)}<span class="tiny-badge">${esc(stateLabels[s.status]??s.status)}</span></h2><p>${esc(d.description??'Verificação de resultados finais, separada dos prognósticos.')}</p><p><strong>${s.collected??0}</strong> previsões extraídas${s.today!==undefined?` · ${s.today} de hoje · ${s.eligible??0} aptas`:""}</p><div class="source-error">${esc(s.message??'')}${s.pages?`<details><summary>Ver páginas consultadas</summary>${s.pages.map(p=>`<p><a href="${safeURL(p.url)}" target="_blank" rel="noopener noreferrer">Página da fonte</a> · ${esc(stateLabels[p.status])}<br>${esc(p.message)}</p>`).join('')}</details>`:''}</div><p><a href="${safeURL(d.url??'https://github.com/juliomcm-tech/mister-mi')}" target="_blank" rel="noopener noreferrer">Consultar a fonte</a></p></article>`;}).join('');
 const resources=[
 ['Oddspedia','API e widgets anunciados como gratuitos para calendários, resultados e comparação de odds. Exigem conta, configuração do domínio e atribuição visível. O widget pode ser adicionado em Ajustes → Oddspedia; a análise automática requer acesso separado aos dados.','https://widgets.oddspedia.com/','Disponível após registo · não conta como previsão de consenso'],
 ['OpenLigaDB','Integrado para resultados finais da Bundesliga 1/2, quando há correspondência inequívoca. Dados comunitários ODbL 1.0; não conta como previsão.','https://www.openligadb.de/en/license','Dados de OpenLigaDB · ODbL 1.0'],
 ['openfootball','JSON CC0 para investigação histórica e validação. Atualização diária; sem garantia de resultados completos no próprio dia.','https://github.com/openfootball/football.json','Referência · não conta para o consenso'],
 ['scikit-learn','Referência para calibração e avaliação futura com períodos cronológicos separados. Não há modelo calibrado ativo nesta versão.','https://scikit-learn.org/stable/modules/calibration.html','Investigação futura · BSD'],
 ['QuantStats','Referência para relatórios de carteira. ROI e drawdown desta versão são calculados diretamente no livro de simulação.','https://github.com/ranaroussi/quantstats','Referência · Apache 2.0'],
 ['Wilson / statsmodels','Intervalo de 95% para a taxa de acerto. A fórmula é implementada no Mister Mi e mostra a incerteza da amostra.','https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html','Fórmula integrada · sem dependência pesada']
 ];
 $('open-resources').innerHTML=resources.map(([name,copy,url,note])=>`<div class="resource-row"><div><strong>${name}</strong><p class="muted">${esc(note)}</p></div><p>${esc(copy)}</p><a href="${url}" target="_blank" rel="noopener noreferrer">Ver projeto</a></div>`).join('');
}
function renderPerformance(){
 const performance=payload?.performance;const overall=performance?.overall??{};
 const cards=[['Taxa de acerto',pct(overall.hit_rate),`${overall.wins??0} acertos / ${overall.settled??0} resultados confirmados`],['Retorno simulado',pct(overall.paper_roi_pct),`${overall.priced_settled??0} entradas com odd registada`],['Perda máxima',`${num(overall.paper_max_drawdown_units??0)} u.`,'Drawdown com posições fixas de 1 unidade'],['Amostra confirmada',String(overall.settled??0),`${overall.pending??0} pendentes · ${overall.void??0} devolvidas`]];
 $('performance-cards').innerHTML=cards.map(([label,value,note])=>`<article class="stat-card"><span>${label}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`).join('');
 const dimension=$('stats-dimension').value;const rows=performance?.[dimension]??[];
 $('performance-table').innerHTML=`<table><thead><tr><th>SEGMENTO</th><th>AMOSTRA</th><th>ACERTO</th><th>INTERVALO 95%</th><th>ROI SIMULADO</th><th>COM ODDS</th></tr></thead><tbody>${rows.length?rows.map(r=>`<tr><td><strong>${esc(dimension==='by_combination'?`${sports[r.sport]??r.sport} × ${countryNames[r.country]??r.country}`:sports[r.key]??countryNames[r.key]??marketNames[r.key]??r.key)}</strong></td><td>${r.settled}${r.sufficient_sample?'':' · inicial'}</td><td>${pct(r.hit_rate)}</td><td>${r.settled?`${num(r.hit_rate_interval_95[0])}%–${num(r.hit_rate_interval_95[1])}%`:'—'}</td><td class="${(r.paper_roi_pct??0)<0?'negative':'positive'}">${pct(r.paper_roi_pct)}</td><td>${r.priced_settled??0}</td></tr>`).join(''):'<tr><td class="no-data-cell" colspan="6">O Mister Mi ainda não tem resultados confirmados. As estatísticas começam com as primeiras opções registadas e liquidadas.</td></tr>'}</tbody></table>`;
 const suggestions=performance?.by_combination?.filter(r=>r.review_suggested)??[];
 $('review-suggestions').innerHTML=`<h2>Segmentos a rever</h2><p>O Mister Mi sinaliza combinações com pelo menos ${performance?.min_sample??30} entradas liquidadas com odds e cobertura de preços suficiente. Um alerta pede revisão; não demonstra uma desvantagem futura.</p>${suggestions.length?suggestions.map(r=>`<div class="review-item"><p><strong>${esc(sports[r.sport]??r.sport)} × ${esc(countryNames[r.country]??r.country)}</strong><br>${r.priced_settled} com odds · ROI ${pct(r.paper_roi_pct)}</p><button class="button outline" data-exclude-combo="${esc(r.sport)}|${esc(r.country)}">Excluir na minha seleção</button></div>`).join(''):'<p class="muted">Ainda não há amostra suficiente para identificar os segmentos mais fortes ou mais fracos com este critério.</p>'}<p class="muted">ROI antes de comissões. Apenas preços observados, sem garantia de execução. Pendentes e devolvidas não entram na taxa de acerto; preços em falta não são inventados.</p>`;
 renderExperiment();
}
async function loadExperiment(){
 experimentRequested=true;
 try{const value=await request('./data/backtest.json');if(value.kind!=='experimental_poisson_baseline'||value.is_live_consensus_backtest!==false)throw new Error('Relatório experimental inválido.');experiment=value;}
 catch{experiment={error:true};}
 if(view==='estatisticas')renderExperiment();
}
function renderExperiment(){
 if(!experimentRequested){loadExperiment();return;}
 if(!experiment)return;
 if(experiment.error){$('backtest-results').innerHTML='<p class="muted">O relatório histórico está temporariamente indisponível. Este estado não altera as estatísticas reais.</p>';return;}
 const s=experiment.overall,interval=s.selected_hit_rate_wilson95_pct;
 $('backtest-results').innerHTML=`<div class="backtest-kpis"><div><strong>${pct(s.selected_hit_rate_pct)}</strong><span>${s.selected_correct} acertos / ${s.selected} seleções</span></div><div><strong>${s.selected_incorrect}</strong><span>seleções erradas</span></div><div><strong>${s.evaluated}</strong><span>jogos avaliados</span></div><div><strong>${pct(s.coverage_pct)}</strong><span>dos jogos selecionados</span></div></div><p>Treino: ${esc(experiment.config.training_season)} · Teste: ${esc(experiment.config.test_season)} · Apenas informação de dias anteriores. Intervalo de 95%: <strong>${pct(interval[0])} a ${pct(interval[1])}</strong>.</p><div class="table-wrap"><table><thead><tr><th>LIGA</th><th>ACERTOS / SELEÇÕES</th><th>TAXA</th><th>INTERVALO 95%</th></tr></thead><tbody>${Object.entries(experiment.by_league).map(([key,r])=>`<tr><td>${esc(experiment.leagues[key].name)}</td><td>${r.selected_correct} / ${r.selected}</td><td>${pct(r.selected_hit_rate_pct)}</td><td>${pct(r.selected_hit_rate_wilson95_pct[0])}–${pct(r.selected_hit_rate_wilson95_pct[1])}</td></tr>`).join('')}</tbody></table></div><p>O modelo selecionou apenas jogos com probabilidade estimada de pelo menos 65%. Nos ${s.evaluated} jogos, sem esse filtro, acertou ${pct(s.top1_accuracy_pct)}. A referência «sempre casa» acertou ${pct(s.always_home_on_selected_accuracy_pct)} nas mesmas seleções.</p><p class="muted">Probabilidades experimentais sem calibração. Não existem odds históricas verificadas para medir lucro ou ROI. A simulação retrospetiva não demonstra segurança nem o desempenho do consenso atual.</p><div class="report-links"><a class="text-link" href="https://github.com/juliomcm-tech/mister-mi/blob/main/docs/BACKTEST.md" target="_blank" rel="noopener noreferrer">Método e resultados</a><a class="text-link" href="https://github.com/juliomcm-tech/mister-mi/blob/main/docs/AUDIT.md" target="_blank" rel="noopener noreferrer">Auditoria independente</a></div>`;
}
function renderPortfolio(){
 const picks=visiblePicks();const planned=planPortfolio(picks,policy);const byId=new Map(picks.map(p=>[p.id,p]));
 $('portfolio-results').innerHTML=`<div class="portfolio-total"><div><span>Exposição simulada</span><br><strong>${money(planned.totalStake)}</strong></div><div><span>Limite diário</span><br><strong>${money(planned.cap)}</strong></div></div>${planned.allocations.length?`<table><thead><tr><th>OPÇÃO</th><th>ODD OBSERVADA</th><th>SIMULAÇÃO</th></tr></thead><tbody>${planned.allocations.map(a=>`<tr><td>${esc(byId.get(a.id)?.selection??a.id)}<br><small>${esc(byId.get(a.id)?.match??'')}</small></td><td>${num(byId.get(a.id)?.odds,2)}</td><td>${money(a.stake)}<br><small>${num(a.pct)}% da banca</small></td></tr>`).join('')}</tbody></table>`:emptyState('Sem posições para simular.','Só entram opções atuais, aprovadas pelos teus filtros e com uma odd observada. Não é necessário distribuir a banca todos os dias.')}${planned.skipped.length?`<details><summary class="muted">${planned.skipped.length} opções não incluídas</summary>${planned.skipped.map(s=>`<p>${esc(byId.get(s.id)?.match??s.id)} · ${esc(s.reason)}</p>`).join('')}</details>`:''}${planned.warnings.map(s=>`<p class="muted">${esc(s)}</p>`).join('')}<p class="muted">A simulação não reserva posições nem conhece apostas fora do Mister Mi. Os limites são uma política ilustrativa de exposição, não uma garantia de proteção.</p>`;
 const records=[...(history.records??[])].reverse().slice(0,100);
 const resultLabel={pending:'Pendente',win:'Acertou',loss:'Falhou',void:'Devolvida'};
 $('ledger').innerHTML=`<table><thead><tr><th>PUBLICAÇÃO</th><th>JOGO / SELEÇÃO</th><th>ODD INICIAL</th><th>RESULTADO</th><th>CONFIRMAÇÃO</th></tr></thead><tbody>${records.length?records.map(r=>`<tr><td>${dateTime(r.first_seen)}</td><td>${esc(r.match)}<br><small>${esc(r.selection)}</small></td><td>${r.odds?num(r.odds,2):'Sem preço'}</td><td class="${r.result==='loss'?'negative':r.result==='win'?'positive':''}">${resultLabel[r.result]??esc(r.result)}</td><td>${esc(r.settlement_source??'A aguardar')}</td></tr>`).join(''):'<tr><td colspan="5" class="no-data-cell">O livro de registo começa com a primeira opção que passar nos critérios do Mister Mi. Não há resultados de demonstração.</td></tr>'}</tbody></table>`;
 $('settlement-note').textContent=payload?.settlement_note??'Sem resultado verificável, a opção mantém-se pendente.';
 $('settlement-pick').innerHTML='<option value="">Selecionar registo pendente</option>'+(history.records??[]).filter(r=>r.result==='pending'&&new Date(r.kickoff)<new Date()).map(r=>`<option value="${esc(r.id)}">${esc(r.match)} · ${esc(r.selection)}</option>`).join('');
}
function metricLabel(s){return s.metric_kind==='vote_pct'?`${num(s.metric)}% de apoio · ${s.votes_for}/${s.votes_total} votos`:s.metric_kind==='model_pct'?`${num(s.metric)}% · modelo da fonte`:s.metric_kind==='tip_score'?`${num(s.metric)}/10 · Tip Score`:'Previsão categórica';}
function showAnalysis(id){
 const pick=todaysPicks().find(p=>p.id===id);if(!pick){toast('Esta opção já não está válida para hoje.');return;}
 $('analysis-detail').innerHTML=`<h2>${esc(pick.match)}</h2><p>${esc(sports[pick.sport]??pick.sport)} · ${esc(countryNames[pick.country]??pick.country)} · ${dateTime(pick.kickoff)}</p><div class="portfolio-total"><div><span>${esc(marketNames[pick.market]??pick.market)}</span><h3>${esc(pick.selection)}</h3></div><div><strong>${num(pick.score)}</strong><span> / 98 · consenso</span></div></div><p>${esc(pick.reason)}</p><h3>O que cada fonte diz</h3>${pick.sources.map(s=>`<div class="evidence-row"><strong>${esc(sourceNames[s.source]??s.source)}<span>${esc(metricLabel(s))}</span></strong><small>Recolhido ${dateTime(s.fetched_at)}${s.odds?` · Odd observada ${num(s.odds,2)}`:''}</small><a href="${safeURL(s.url)}" target="_blank" rel="noopener noreferrer">Ver evidência na fonte</a></div>`).join('')}<p>O Mister Mi verifica a concordância, a identidade do evento, os limiares e a frescura. Sem validação histórica suficiente, não estima uma probabilidade de acerto nem retorno esperado.</p>`;
 $('analysis-dialog').showModal();
}
function updateClock(){const now=new Date();$('date-label').textContent=new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',weekday:'long',day:'numeric',month:'long'}).format(now);$('calendar-day').textContent=new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',day:'2-digit'}).format(now);$('calendar-month').textContent=new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',month:'long',year:'numeric'}).format(now);}
function renderMood(){const mood=getAnalystMood(payload?.performance,payload?.settings);$('mi-avatar').dataset.miMood=mood.state;document.querySelectorAll('.mini-mi img,.rail-bottom img').forEach(img=>{const path=mood.state==='review'?'./assets/mister-mi-upset.webp':'./assets/mister-mi.webp';if(img.getAttribute('src')!==path)img.src=path;});}
function render(){updateClock();renderPicks();sourceSummary();renderMood();if(view==='fontes')renderSources();if(view==='estatisticas')renderPerformance();if(view==='carteira'||view==='definicoes')renderPortfolio();}
function fillPreferences(){
 $('sport-exclusions').innerHTML=Object.entries(sports).map(([key,label])=>`<label><input type="checkbox" name="excluded-sport" value="${key}" ${preferences.excluded_sports.includes(key)?'checked':''}>${label}</label>`).join('');
 $('country-exclusions').value=preferences.excluded_countries.join(', ');
 $('combination-exclusions').value=preferences.excluded_combinations.map(r=>`${r.sport} | ${r.country}`).join('\n');
 $('min-odd').value=preferences.min_odds??'';$('max-odd').value=preferences.max_odds??'';
 $('api-url').value=connection.apiBase.startsWith('/')?new URL(connection.apiBase,location.origin).href:connection.apiBase;
 $('refresh-token').value=refreshToken;$('auto-refresh').checked=connection.auto;
 $('bankroll').value=policy.bankroll;$('per-pick').value=policy.perPickPct;$('per-day').value=policy.maxDayPct;$('per-group').value=policy.maxSportPct;
}
function readPreferences(){
 const combinations=$('combination-exclusions').value.split('\n').map(x=>x.trim()).filter(Boolean).map(x=>{const [sport,country,...extra]=x.split('|').map(s=>s.trim());if(!sports[sport]||!country||extra.length)throw new Error('Usa o formato tennis | Japan, uma combinação por linha.');return {sport,country};});
 const min=$('min-odd').value?Number($('min-odd').value):null,max=$('max-odd').value?Number($('max-odd').value):null;
 if((min!==null&&min<=1)||(max!==null&&max<=1)||(min!==null&&max!==null&&min>max))throw new Error('Verifica os limites das odds.');
 return {excluded_sports:[...document.querySelectorAll('[name="excluded-sport"]:checked')].map(el=>el.value),excluded_countries:$('country-exclusions').value.split(',').map(x=>x.trim()).filter(Boolean),excluded_combinations:combinations,min_odds:min,max_odds:max};
}
async function request(url,options={}){
 const controller=typeof AbortController!=='undefined'?new AbortController():null;
 const timer=controller?setTimeout(()=>controller.abort(),options.method?25000:15000):null;
 try{
  const response=await fetch(url,{cache:'no-store',...options,...(controller?{signal:controller.signal}:{})});
  let result;try{result=await response.json();}catch{throw new Error(`A resposta não contém dados de análise válidos (HTTP ${response.status}).`);}
  if(!response.ok)throw new Error(result.message??`Pedido falhou (HTTP ${response.status}).`);
  return result;
 }catch(error){
  if(controller?.signal.aborted)throw new Error('A ligação demorou demasiado. Tenta atualizar novamente.');
  if(navigator.onLine===false)throw new Error('Sem ligação à Internet. As previsões atuais precisam de uma ligação ativa.');
  if(error instanceof TypeError)throw new Error('Não foi possível ligar à publicação dos dados. Verifica a rede e tenta novamente.');
  throw error;
 }finally{if(timer!==null)clearTimeout(timer);}
}
const apiURL=path=>connection.apiBase.replace(/\/$/,'')+path;
const publishedFile=name=>`https://raw.githubusercontent.com/${window.APP_CONFIG?.repository??'juliomcm-tech/mister-mi'}/data/${name}?t=${Date.now()}`;
async function authorised(path,method,body){
 if(!connection.apiBase||!refreshToken)throw new Error('Configura o serviço e a chave de atualização nas definições.');
 return request(apiURL(path),{method,headers:{'Content-Type':'application/json','Authorization':`Bearer ${refreshToken}`},body:JSON.stringify(body)});
}
function validatePayload(value){
 if(!value||!/^\d{4}-\d{2}-\d{2}$/.test(value.date)||!Array.isArray(value.data)||!Array.isArray(value.sources)||!Number.isFinite(+new Date(value.updated_at)))throw new Error('O ficheiro de análise não tem o formato esperado.');
 return value;
}
async function loadSnapshot({quiet=false}={}){
 try{
  let data,apiReadIssue='';
  if(connection.apiBase){
   try{data=await request(apiURL('/today'));}
   catch(error){apiReadIssue=error.message;data=await request(publishedFile('consenso_hoje.json'));}
  }else data=await request(publishedFile('consenso_hoje.json'));
  payload=validatePayload(data);loadFailed=Boolean(data.snapshot_fallback);lastReadError='';
  if(apiReadIssue&&!quiet)notice('O serviço personalizado não respondeu. Foi carregada a última publicação do GitHub; as escritas e novas execuções continuam a exigir a ligação configurada.');
  if(data.snapshot_fallback&&!quiet)notice('A publicação atual do GitHub está indisponível. A cópia inicial não é apresentada como uma análise atual.');
  try{const h=await request(connection.apiBase&&!apiReadIssue?apiURL('/history'):publishedFile('history.json'));if(Array.isArray(h.records))history=h;}catch{history={records:[]};}
  render();return true;
 }catch(error){loadFailed=true;lastReadError=error.message;render();if(!quiet)notice(error.message);return false;}
}
async function loadHealth(){
 if(!connection.apiBase){$('connection-status').textContent='Modo GitHub Pages: o refresh recarrega a última publicação. A recolha corre no GitHub Actions.';return;}
 try{health=await request(apiURL('/health'));$('connection-status').textContent=health.configured?'Serviço ligado ao repositório. Execução imediata disponível com a chave.':'Serviço acessível. A ligação permanente ao GitHub ainda precisa de configuração no servidor.';}
 catch{$('connection-status').textContent='Não foi possível contactar o serviço de atualização.';}
}
async function refreshAnalysis(run=true){
 if(busy)return;busy=true;$('refresh').disabled=true;$('hero-analyse').disabled=true;notice('');renderPicks();
 try{
  if(run&&canStartCollection(connection,refreshToken,health)){
   const result=await authorised('/refresh','POST',{});
   if(result.state==='cooldown'){await loadSnapshot();notice('Já houve um pedido recente. O Mister Mi está a usar a última análise disponível.');return;}
   notice('O Mister Mi pediu uma nova execução no GitHub. A recolha pode demorar alguns minutos.');
   const started=Date.now();let completed=false;
   while(Date.now()-started<240000){
    await new Promise(resolve=>setTimeout(resolve,5000));
    await loadSnapshot({quiet:true});
    if(payload?.request_id===result.request_id){completed=true;notice(payload.status==='error'?'A execução terminou com falhas nas fontes. Consulta o diagnóstico em Fontes.':'A nova recolha terminou. O Mister Mi voltou a aplicar os critérios de hoje.');break;}
   }
   if(!completed)notice('A execução ainda não publicou um novo resultado. Podes acompanhar o progresso no GitHub Actions e voltar a atualizar.');
  }else{
   const ok=await loadSnapshot();if(ok)notice(freshness().valid?'Última análise publicada recarregada. Para executar uma nova recolha ao fazer refresh, configura a ligação nas definições.':freshness().reason);
  }
 }catch(error){const message=error.message;const readOkay=await loadSnapshot({quiet:true});notice(readOkay?`Não foi possível iniciar uma nova execução: ${message} A última publicação do GitHub foi recarregada.`:message);}finally{busy=false;$('refresh').disabled=false;$('hero-analyse').disabled=false;render();}
}
document.addEventListener('click',e=>{
 const widgetSettings=e.target.closest('[data-oddspedia-settings]');if(widgetSettings)$('oddspedia-form').scrollIntoView({block:'start',behavior:'smooth'});
 const day=e.target.closest('[data-preview-day]');if(day){previewOffset=Number(day.dataset.previewDay);const url=new URL(location.href);if(previewOffset)url.searchParams.set('day',previewOffset===1?'tomorrow':'after');else url.searchParams.delete('day');window.history.replaceState(null,'',url);renderPicks();document.querySelector('.analysis-days')?.scrollIntoView({block:'start',behavior:'smooth'});}
 const analysis=e.target.closest('[data-analysis]');if(analysis)showAnalysis(analysis.dataset.analysis);
 const fav=e.target.closest('[data-favorite]');if(fav){favorites.has(fav.dataset.favorite)?favorites.delete(fav.dataset.favorite):favorites.add(fav.dataset.favorite);write('mister-mi.favorites',[...favorites]);renderPicks();}
 const exclude=e.target.closest('[data-exclude-combo]');if(exclude){const [sport,country]=exclude.dataset.excludeCombo.split('|');if(!preferences.excluded_combinations.some(r=>r.sport===sport&&r.country===country))preferences.excluded_combinations.push({sport,country});write('mister-mi.preferences',preferences);fillPreferences();render();toast('Combinação excluída na tua seleção. O histórico foi preservado.');}
 const tab=e.target.closest('[data-sport]');if(tab){activeSport=tab.dataset.sport;document.querySelectorAll('[data-sport]').forEach(el=>el.classList.toggle('active',el.dataset.sport===activeSport));renderPicks();}
});
$('close-dialog').onclick=()=>$('analysis-dialog').close();
$('analysis-dialog').addEventListener('click',e=>{if(e.target===$('analysis-dialog')){const r=$('analysis-dialog').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('analysis-dialog').close();}});
$('refresh').onclick=()=>refreshAnalysis();$('hero-analyse').onclick=()=>refreshAnalysis();
for(const id of ['search','sort','three-sources'])$(id).addEventListener('input',renderPicks);
$('min-score').addEventListener('input',()=>{$('score-label').textContent=$('min-score').value;renderPicks();});
$('favorites-toggle').onclick=()=>{onlyFavorites=!onlyFavorites;$('favorites-toggle').setAttribute('aria-pressed',String(onlyFavorites));$('favorites-toggle').style.color=onlyFavorites?'#a38a21':'';renderPicks();};
$('stats-dimension').onchange=renderPerformance;
$('preferences-form').onsubmit=e=>{e.preventDefault();try{preferences=readPreferences();write('mister-mi.preferences',preferences);render();toast('Filtros guardados neste dispositivo.');}catch(error){toast(error.message);}};
$('reset-preferences').onclick=()=>{preferences={...emptyPreferences};write('mister-mi.preferences',preferences);fillPreferences();render();toast('Filtros repostos.');};
$('save-shared-settings').onclick=async()=>{try{const settings=readPreferences();const result=await authorised('/settings','PUT',settings);if(result.success)toast('Regras guardadas no GitHub. A próxima recolha aplica as exclusões partilhadas.');}catch(error){toast(error.message);}};
$('connection-form').onsubmit=async e=>{e.preventDefault();const value=$('api-url').value.trim().replace(/\/$/,'');if(value){try{const u=new URL(value);if(u.protocol!=='https:')throw 0;}catch{toast('Usa um endereço HTTPS válido.');return;}}connection={apiBase:value,auto:$('auto-refresh').checked};refreshToken=$('refresh-token').value.trim();write('mister-mi.connection',connection);write('mister-mi.refresh-token',refreshToken,sessionStorage);await loadHealth();toast('Ligação guardada.');};
$('portfolio-form').onsubmit=e=>{e.preventDefault();policy={...DEFAULT_POLICY,bankroll:Number($('bankroll').value),perPickPct:Number($('per-pick').value),maxDayPct:Number($('per-day').value),maxSportPct:Number($('per-group').value),maxCountryPct:Number($('per-group').value),maxCompetitionPct:Number($('per-group').value)};write('mister-mi.policy',policy);renderPortfolio();};
$('settlement-form').onsubmit=async e=>{e.preventDefault();const id=$('settlement-pick').value;if(!id){toast('Seleciona um registo pendente.');return;}try{const result=await authorised('/settlements','POST',{id,status:'final',home_score:Number($('home-score').value),away_score:Number($('away-score').value)});if(result.success)toast('Confirmação guardada no GitHub. O livro será atualizado na próxima execução.');}catch(error){toast(error.message);}};
$('export-history').onclick=()=>{const columns=['id','first_seen','date','sport','country','match','market','selection','odds','odds_source','result','settlement_source'];const cell=v=>`"${String(v??'').replace(/"/g,'""').replace(/^[=+@-]/,"'$&")}"`;const csv='\uFEFF'+[columns,...(history.records??[]).map(r=>columns.map(k=>r[k]))].map(row=>row.map(cell).join(';')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`mister-mi-historico-${lisbonDay()}.csv`;a.click();URL.revokeObjectURL(url);};

function applyMotion(){document.body.classList.toggle('mi-paused',!motionEnabled||document.hidden);}
$('mi-motion').checked=motionEnabled;$('mi-motion').onchange=()=>{motionEnabled=$('mi-motion').checked;write('mister-mi.motion',motionEnabled);applyMotion();};
document.addEventListener('visibilitychange',()=>{applyMotion();if(!document.hidden&&!busy)loadSnapshot({quiet:true});});
if('IntersectionObserver' in window)new IntersectionObserver(entries=>{for(const entry of entries)$('mi-avatar').classList.toggle('mi-resting',!entry.isIntersecting);},{threshold:0.05}).observe($('mi-avatar'));
applyMotion();
function closeInstall(){const d=$('install-dialog');if(typeof d.close==='function')d.close();else{d.removeAttribute('open');d.hidden=true;}}
$('close-install').onclick=closeInstall;$('install-done').onclick=closeInstall;
initPWA({onOffline:offline=>{if(offline){loadFailed=true;lastReadError='Sem ligação à Internet. As previsões atuais precisam de uma ligação ativa.';notice(lastReadError);render();}else if(loadFailed)loadSnapshot({quiet:true});}});
oddspediaWidget=initOddspediaWidget({onOpen:()=>changeView('fontes'),onToast:toast});
fillPreferences();changeView(location.hash.slice(1)||'hoje');
await loadSnapshot();await loadHealth();renderPicks();

if(connection.auto&&refreshToken&&connection.apiBase)refreshAnalysis();
setInterval(()=>{render();},60000);
