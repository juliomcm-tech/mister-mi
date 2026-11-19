import {readFile,writeFile,mkdir,rm,readdir,copyFile} from 'node:fs/promises';
import {resolve,extname,relative,join} from 'node:path';
const root=process.cwd(),out=resolve(root,'dist');
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.webp':'image/webp','.webmanifest':'application/manifest+json','.woff2':'font/woff2','.txt':'text/plain; charset=utf-8'};
async function files(directory){const result=[];for(const e of await readdir(directory,{withFileTypes:true})){const p=join(directory,e.name);if(e.isDirectory())result.push(...await files(p));else result.push(p);}return result;}
await rm(out,{recursive:true,force:true});await mkdir(out,{recursive:true});
const pages=process.argv.includes('--pages');
const assets={};
for(const file of await files(resolve(root,'web'))){
 const name=relative(resolve(root,'web'),file).split('\\').join('/');
 if(name==='assets/mister-mi.png')continue;
 let bytes=await readFile(file);if(name==='config.js')bytes=Buffer.from(`window.APP_CONFIG=${JSON.stringify({apiBase:pages?(process.env.REFRESH_API_URL??''):'/api',repository:'juliomcm-tech/mister-mi'})};\n`);
 if(pages){const target=join(out,name);await mkdir(resolve(target,'..'),{recursive:true});await writeFile(target,bytes);}
 else{const binary=['.png','.webp','.woff2'].includes(extname(file));assets['/'+name]={body:binary?bytes.toString('base64'):bytes.toString('utf8'),base64:binary,type:mime[extname(file)]??'application/octet-stream'};}
}
if(pages)await writeFile(join(out,'.nojekyll'),'');
else{await mkdir(join(out,'server'),{recursive:true});await mkdir(join(out,'.openai'),{recursive:true});await writeFile(join(out,'server/index.js'),`globalThis.STATIC_ASSETS=${JSON.stringify(assets)};\n`+await readFile(join(root,'worker/index.js'),'utf8'));await copyFile(join(root,'.openai/hosting.json'),join(out,'.openai/hosting.json'));}
console.log(`Mister Mi: build ${pages?'GitHub Pages':'Worker'} concluído.`);
