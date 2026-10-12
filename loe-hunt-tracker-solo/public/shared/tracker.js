// Fonte canônica; cópias dos trackers são geradas por tools/sincronizar_trackers.py.
(function(root){
function parseNum(s){
  s = String(s).trim();
  const neg = /^-/.test(s);
  const digits = s.replace(/[^\d]/g,"");
  if(!digits) return 0;
  const n = parseInt(digits,10);
  return neg ? -n : n;
}

function kk(n){
  if(n===0) return "0";
  const sign = n<0 ? "-" : "";
  let a = Math.abs(n);
  const strip = x => x.toFixed(2).replace(/\.?0+$/,"");
  if(a>=1e9) return sign+strip(a/1e9)+"kkk";
  if(a>=1e6) return sign+strip(a/1e6)+"kk";
  if(a>=1e3) return (a/1e3).toFixed(a>=1e5?0:1).replace(/\.?0+$/,"")*(n<0?-1:1)+"k";
  return sign+a;
}

function kkC(n, dec){ // comma-decimal kk (e.g. 8991163 -> "9,0 kk")
  dec = dec==null ? 1 : dec;
  const s = n<0?"-":""; const a=Math.abs(n);
  if(a>=1e9) return s+(a/1e9).toFixed(dec).replace(".",",")+" kkk";
  if(a>=1e6) return s+(a/1e6).toFixed(dec).replace(".",",")+" kk";
  if(a>=1e3) return s+(a/1e3).toFixed(dec).replace(".",",")+" k";
  return s+Math.round(a);
}

function toDate(s){ // "2026-07-24, 06:59:05"
  if(!s) return null;
  const d = new Date(s.replace(", ","T"));
  return isNaN(d) ? null : d;
}

function parseParty(text){
  if(!text || !text.trim()) return null;
  const lines = text.split("\n").map(l => l.replace(/\r$/,""));
  const p = { players:[] };
  let cur = null;
  for(const raw of lines){
    if(!raw.trim()) continue;
    const indented = /^\s/.test(raw);
    const line = raw.trim();
    if(!indented){
      let m;
      if((m = line.match(/^Session data:\s*From\s+(.+?)\s+to\s+(.+)$/))){ p.start=m[1]; p.end=m[2]; }
      else if(/^Session:/.test(line)){ p.durationH = durFromHeader(line); }
      else if(/^Loot Type:/.test(line)){ p.lootType = line.split(":")[1].trim(); }
      else if((m = line.match(/^Loot:\s*(.+)$/))){ p.loot = parseNum(m[1]); }
      else if((m = line.match(/^Supplies:\s*(.+)$/))){ p.supplies = parseNum(m[1]); }
      else if((m = line.match(/^Balance:\s*(.+)$/))){ p.balance = parseNum(m[1]); }
      else { // player name
        cur = { name: line.replace(/\s*\(Leader\)\s*$/,""), leader:/\(Leader\)/.test(line),
                loot:0, supplies:0, balance:0, damage:0, healing:0 };
        p.players.push(cur);
      }
    } else if(cur){
      const m = line.match(/^(Loot|Supplies|Balance|Damage|Healing):\s*(.+)$/);
      if(m) cur[m[1].toLowerCase()] = parseNum(m[2]);
    }
  }
  if(p.balance==null || !p.players.length) return null;
  if(!p.durationH && p.start && p.end){
    const a=toDate(p.start), b=toDate(p.end);
    if(a&&b) p.durationH = Math.max((b-a)/3.6e6, 1/60);
  }
  if(!p.durationH) p.durationH = 1;
  return p;
}
function durFromHeader(line){
  const m = line.match(/Session:\s*(\d+):(\d+)/);
  return m ? (+m[1]) + (+m[2])/60 : null;
}


const api={durFromHeader,parseNum,kk,kkC,toDate,parseParty};
if(typeof module!=='undefined')module.exports=api;else root.RubinotTracker=api;
})(globalThis);
