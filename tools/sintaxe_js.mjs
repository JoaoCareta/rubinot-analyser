import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
const raiz=process.cwd();let n=0;
function verificar(pasta){
 for(const item of readdirSync(pasta,{withFileTypes:true})){
  const p=join(pasta,item.name);
  if(item.isDirectory()){verificar(p);continue;}
  if(item.name.endsWith('.js')){
   const r=spawnSync(process.execPath,['--check',p],{encoding:'utf8'});
   if(r.status!==0)throw Error(r.stderr);n++;
  }else if(item.name.endsWith('.html')){
   const s=readFileSync(p,'utf8');
   for(const m of s.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)){
    if(/\bsrc=/.test(m[1]))continue;
    new vm.Script(m[2],{filename:p});n++;
   }
  }
 }
}
verificar(join(raiz,'ui'));
verificar(join(raiz,'../loe-hunt-tracker-solo/public'));
console.log(`Sintaxe JavaScript/HTML: ${n} scripts aprovados.`);
