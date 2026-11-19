import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
const root=resolve('web'),port=Number(process.env.PORT??3000);
const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.png':'image/png'};
createServer(async(req,res)=>{
 try{let path=new URL(req.url,'http://localhost').pathname;
  if(path==='/api/health'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({configured:false}));return;}
  if(path==='/api/today')path='/data/consenso_hoje.json';if(path==='/api/history')path='/data/history.json';
  if(path.startsWith('/api/')){res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({message:'Execução imediata não configurada nesta pré-visualização.'}));return;}
  if(path==='/config.js'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end('window.APP_CONFIG={apiBase:"/api",repository:"juliomcm-tech/mister-mi"};');return;}
  const file=resolve(root,'.'+(path==='/'?'/index.html':path));if(!file.startsWith(root+'/')||path.includes('/.'))throw 0;
  const data=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]??'application/octet-stream','Cache-Control':'no-store'});res.end(data);
 }catch{res.writeHead(404);res.end('Não encontrado');}
}).listen(port,'0.0.0.0',()=>console.log(`Mister Mi ready at http://0.0.0.0:${port}`));
