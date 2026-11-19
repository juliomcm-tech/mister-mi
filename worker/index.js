// Optional protected relay. GitHub credentials never reach the browser.
const REPO = 'juliomcm-tech/mister-mi';
const JSON_HEADERS = {'Content-Type':'application/json; charset=utf-8','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
let lastDispatch = 0;
let dispatching = false;
function reply(body,status=200,headers={}){return new Response(JSON.stringify(body),{status,headers:{...JSON_HEADERS,...headers}});}
function configured(env){return Boolean(env.GITHUB_TOKEN && /^[\w.-]+\/[\w.-]+$/.test(env.GITHUB_REPOSITORY??REPO) && env.REFRESH_TOKEN);}
function equal(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let difference=0;for(let i=0;i<a.length;i++)difference|=a.charCodeAt(i)^b.charCodeAt(i);return difference===0;}
function cors(request,env){const own=new URL(request.url).origin;const origin=request.headers.get('Origin');const allowed=new Set([own,'https://juliomcm-tech.github.io',...(env.ALLOWED_ORIGINS??'').split(',').map(s=>s.trim()).filter(Boolean)]);return origin&&allowed.has(origin)?{'Access-Control-Allow-Origin':origin,'Vary':'Origin','Access-Control-Allow-Headers':'Content-Type, Authorization','Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS'}:{};}
async function gh(env,path,options={}){
 const repo=env.GITHUB_REPOSITORY??REPO;
 if(!/^[\w.-]+\/[\w.-]+$/.test(repo))throw new Error('Repositório inválido no servidor.');
 const response=await fetch(`https://api.github.com/repos/${repo}${path}`,{...options,headers:{'Authorization':`Bearer ${env.GITHUB_TOKEN}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'MisterMi/1.0',...(options.headers??{})},redirect:'error',signal:AbortSignal.timeout(15000)});
 if(!response.ok){const error=new Error(response.status===404?'O ficheiro ou workflow ainda não existe no GitHub.':response.status===403||response.status===401?'O GitHub recusou o acesso. Verifica as permissões da chave do servidor.':`O GitHub não concluiu o pedido (${response.status}).`);error.status=response.status;throw error;}
 return response.status===204?null:response.json();
}
function decodeFile(file){return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\s/g,'')),c=>c.charCodeAt(0))));}
function encodeFile(value){const bytes=new TextEncoder().encode(JSON.stringify(value,null,2)+'\n');let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);return btoa(binary);}
async function dataFile(env,path){return decodeFile(await gh(env,`/contents/${path}?ref=data`));}
async function publicData(path){
 const response=await fetch(`https://raw.githubusercontent.com/${REPO}/data/${path}`,{headers:{'User-Agent':'MisterMi/1.0','Cache-Control':'no-cache'},redirect:'error',signal:AbortSignal.timeout(12000)});
 if(!response.ok)throw new Error('Publicação do GitHub ainda indisponível.');
 return response.json();
}
function seeded(path){const item=globalThis.STATIC_ASSETS?.[path];return item?JSON.parse(item.body):null;}
async function bodyJSON(request){const length=Number(request.headers.get('Content-Length')??0);if(length>30000)throw new Error('Pedido demasiado grande.');const body=await request.text();if(body.length>30000)throw new Error('Pedido demasiado grande.');try{return JSON.parse(body);}catch{throw new Error('JSON inválido.');}}
async function saveJSON(env,path,update,message){const file=await gh(env,`/contents/${path}?ref=main`);const original=decodeFile(file);const revised=update(original);return gh(env,`/contents/${path}`,{method:'PUT',body:JSON.stringify({message,content:encodeFile(revised),sha:file.sha,branch:'main'})});}
function checkedSettings(value){
 const output={};
 for(const key of ['excluded_sports','excluded_countries']){
  if(!Array.isArray(value[key])||value[key].length>100||value[key].some(x=>typeof x!=='string'||x.length>80))throw new Error('Lista de exclusões inválida.');output[key]=value[key];
 }
 if(value.excluded_sports.some(x=>!['football','tennis','basketball','hockey','american_football'].includes(x)))throw new Error('Desporto inválido.');
 if(!Array.isArray(value.excluded_combinations)||value.excluded_combinations.length>100||value.excluded_combinations.some(r=>!r||typeof r.sport!=='string'||typeof r.country!=='string'||r.sport.length>40||r.country.length>80))throw new Error('Combinações inválidas.');
 output.excluded_combinations=value.excluded_combinations.map(r=>({sport:r.sport,country:r.country}));
 for(const key of ['min_odds','max_odds']){if(value[key]!==null&&(typeof value[key]!=='number'||!Number.isFinite(value[key])||value[key]<=1||value[key]>1000))throw new Error('Limite de odds inválido.');output[key]=value[key];}
 if(output.min_odds!==null&&output.max_odds!==null&&output.min_odds>output.max_odds)throw new Error('Intervalo de odds inválido.');
 return output;
}
export default {
 async fetch(request,env={}){
  const url=new URL(request.url),headers=cors(request,env);
  if(request.method==='OPTIONS')return new Response(null,{status:204,headers});
  if(!url.pathname.startsWith('/api/')){
   if(!['GET','HEAD'].includes(request.method))return new Response('Método não permitido',{status:405});
   const key=url.pathname==='/'?'/index.html':url.pathname;
   const asset=globalThis.STATIC_ASSETS?.[key];
   if(!asset)return new Response('Não encontrado',{status:404});
   const bytes=asset.base64?Uint8Array.from(atob(asset.body),c=>c.charCodeAt(0)):asset.body;
   return new Response(request.method==='HEAD'?null:bytes,{headers:{'Content-Type':asset.type,'X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin','Cache-Control':key.startsWith('/assets/')?'public, max-age=86400':'no-cache'}});
  }
  try{
   if(url.pathname==='/api/health'&&request.method==='GET')return reply({configured:configured(env),repository:env.GITHUB_REPOSITORY??REPO,workflow:'collect.yml'},200,headers);
   if(request.method==='GET'&&['/api/today','/api/history'].includes(url.pathname)){
    const name=url.pathname.endsWith('today')?'consenso_hoje.json':'history.json';
    if(configured(env))return reply(await dataFile(env,name),200,headers);
    try{return reply(await publicData(name),200,headers);}catch{
     const snapshot=seeded(`/data/${name}`);if(snapshot)return reply({...snapshot,snapshot_fallback:true},200,headers);
     return reply(name==='history.json'?{records:[]}:{message:'A primeira recolha ainda não está disponível.'},name==='history.json'?200:503,headers);
    }
   }
   if(!configured(env))return reply({message:'A execução imediata ainda não está configurada. A recolha agendada continua no GitHub; configura as variáveis do serviço para pedir novas execuções.'},503,headers);
   if(!headers['Access-Control-Allow-Origin'])return reply({message:'Origem não autorizada.'},403,headers);
   if(!equal(request.headers.get('Authorization'),`Bearer ${env.REFRESH_TOKEN}`))return reply({message:'Chave de atualização inválida. Verifica a ligação nas definições.'},401,headers);
   if(url.pathname==='/api/refresh'&&request.method==='POST'){
    if(dispatching||Date.now()-lastDispatch<300000)return reply({state:'cooldown'},202,headers);
    dispatching=true;
    try{const request_id=crypto.randomUUID();await gh(env,'/actions/workflows/collect.yml/dispatches',{method:'POST',body:JSON.stringify({ref:'main',inputs:{request_id}})});lastDispatch=Date.now();return reply({state:'queued',request_id},202,headers);}finally{dispatching=false;}
   }
   if(url.pathname==='/api/settings'&&request.method==='PUT'){
    const value=checkedSettings(await bodyJSON(request));await saveJSON(env,'config/settings.json',old=>({...old,...value}),'Mister Mi: atualizar critérios partilhados');return reply({success:true},200,headers);
   }
   if(url.pathname==='/api/settlements'&&request.method==='POST'){
    const value=await bodyJSON(request);
    if(typeof value.id!=='string'||!/^[a-f0-9]{16}$/.test(value.id)||value.status!=='final'||![value.home_score,value.away_score].every(n=>Number.isInteger(n)&&n>=0&&n<=300))throw new Error('Resultado inválido.');
    const history=await dataFile(env,'history.json');const pick=history.records?.find(r=>r.id===value.id);
    if(!pick||pick.result!=='pending'||!Number.isFinite(+new Date(pick.kickoff))||new Date(pick.kickoff)>new Date())throw new Error('O registo não está disponível para confirmação.');
    if(pick.market==='MATCH_WINNER'&&value.home_score===value.away_score)throw new Error('Um vencedor do jogo requer um resultado sem empate.');
    await saveJSON(env,'config/results.json',old=>{if(old.results.some(r=>r.id===value.id))throw new Error('Este resultado já foi confirmado.');return {...old,results:[...old.results,{id:value.id,status:'final',home_score:value.home_score,away_score:value.away_score,source:'manual',verified_at:new Date().toISOString()}]};},'Mister Mi: registar resultado confirmado manualmente');
    return reply({success:true},200,headers);
   }
   return reply({message:'Operação não disponível.'},404,headers);
  }catch(error){return reply({message:error.message??'Serviço temporariamente indisponível.'},error.status===401||error.status===403?502:400,headers);}
 }
};
