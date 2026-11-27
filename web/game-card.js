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
/* Emblema gerado a partir do nome: cores e desenho estáveis para cada equipa (sem imagens externas).
   Ténis: medalhão redondo; desportos de equipa: escudo com faixa. */
function hashName(v){let h=2166136261;for(const c of String(v??''))h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0;}
export function crest(name,sport){
 const h=hashName(name),hue=h%360,hue2=(hue+40+(h>>9)%90)%360,style=(h>>5)%4,ini=esc(initials(name)||'?');
 const c1=`hsl(${hue} 62% 42%)`,c2=`hsl(${hue2} 70% 56%)`,id=`g${h.toString(36)}`;
 if(sport==='tennis')return `<svg class="crest" viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs><circle cx="20" cy="20" r="18.5" fill="url(#${id})" stroke="#ffffffb0" stroke-width="1.5"/><text x="20" y="25" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">${ini}</text></svg>`;
 const shield='M20 2 L36 7 V19 C36 29 29 35.5 20 38 C11 35.5 4 29 4 19 V7 Z';
 const deco=style===0?`<path d="M4 15 H36 V22 H4 Z" fill="${c2}" opacity=".9"/>`:style===1?`<path d="M20 2 L36 7 V19 C36 29 29 35.5 20 38 Z" fill="${c2}" opacity=".85"/>`:style===2?`<path d="M4 7 L36 27 V31 L4 11 Z" fill="${c2}" opacity=".9"/>`:`<path d="M14 4.2 V36 M26 4.2 V36" stroke="${c2}" stroke-width="5" opacity=".75"/>`;
 return `<svg class="crest" viewBox="0 0 40 40" aria-hidden="true"><defs><clipPath id="${id}"><path d="${shield}"/></clipPath></defs><g clip-path="url(#${id})"><rect width="40" height="40" fill="${c1}"/>${deco}</g><path d="${shield}" fill="none" stroke="#ffffffc0" stroke-width="1.6"/><text x="20" y="25" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" stroke="#0006" stroke-width=".6" paint-order="stroke">${ini}</text></svg>`;
}
function dayShort(k){if(!k.iso)return k.date;const f=d=>new Intl.DateTimeFormat('pt-PT',{timeZone:'Europe/Lisbon',day:'2-digit',month:'2-digit'}).format(d);const t=new Date(),m=new Date(Date.now()+864e5),d=new Date(k.iso);return f(d)===f(t)?'hoje':f(d)===f(m)?'amanhã':f(d);}
const sportIcon={football:'⚽',tennis:'🎾',basketball:'🏀',hockey:'🏒',american_football:'🏈'};
export function gameCard(p,{sports={},countries={},markets={},sources={},phase='watchlist',featured=false,favorite=false}={}){
 const confirmed=phase==='today'||phase==='future';
 const status=phase==='today'?'Validado':phase==='future'?'Preliminar':'Em observação';
 const evidence=Array.isArray(p.sources)?p.sources:[];
 const kickoff=kickoffLabel(p.kickoff);
 const chips=evidence.map(s=>`<a href="${url(s.url)}" target="_blank" rel="noopener noreferrer">${esc(sources[s.source]??s.source)}${s.metric_kind==='vote_pct'?` ${num(s.metric)}%`:s.metric_kind==='model_pct'?` ${num(s.metric)}%`:s.metric_kind==='tip_score'?` ${num(s.metric)}/10`:''}</a>`).join('');
 const team=n=>`<div class="gc-team">${crest(n,p.sport)}<span>${esc(n)}</span></div>`;
 return `<article class="game-card gc ${confirmed?'game-card-confirmed':''} ${p.zebra?'gc-zebra':''}" aria-label="${esc(p.match)}">
<div class="gc-top"><time class="game-schedule" datetime="${esc(kickoff.iso)}"><strong>${esc(kickoff.time)}</strong><span>${esc(dayShort(kickoff))}</span><small>Hora de Lisboa · ${esc(kickoff.date)}</small></time><span class="gc-league">${sportIcon[p.sport]??''} ${esc(p.competition||sports[p.sport]||p.sport||'')}</span><span class="game-state">${p.zebra?'🦓 Zebra':esc(status)}</span>${phase==='today'?`<button class="game-favorite ${favorite?'on':''}" data-favorite="${esc(p.id)}" aria-label="${favorite?'Remover dos favoritos':'Adicionar aos favoritos'}" aria-pressed="${favorite}">★</button>`:''}</div>
<div class="gc-teams">${team(p.home)}${team(p.away)}</div>
<div class="gc-pick"><div><small>${esc(markets[p.market]??p.market)}</small><strong>${esc(p.selection)}</strong></div><div class="gc-nums"><div><b>${num(p.odds)}</b><small>odd</small></div><div><b>${esc(p.source_count??evidence.length)}</b><small>fontes</small></div>${typeof p.score==='number'?`<div><b>${num(p.score)}</b><small>pontos</small></div>`:''}</div></div>
<div class="gc-foot"><div class="game-evidence">${chips}</div>${phase==='today'?`<button class="gc-more" data-analysis="${esc(p.id)}">Análise ›</button>`:evidence.length?`<a class="gc-more" href="${url(evidence[0].url)}" target="_blank" rel="noopener noreferrer">Fonte ›</a>`:''}</div>
</article>`;
}
