import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';import {fileURLToPath} from 'node:url';import {createHash} from 'node:crypto';
const here=dirname(fileURLToPath(import.meta.url)),root=resolve(here,'../..'),inputs=JSON.parse(readFileSync(resolve(here,'overlay-inputs.json'),'utf8'));
const read=p=>{const full=resolve(root,p);if(!full.startsWith(root+'/'))throw Error('Outside repository');return readFileSync(full);};
const files=Object.fromEntries(inputs.files.map(p=>[p,read(p).toString('utf8')])),assets=Object.fromEntries(inputs.assets.map(p=>[p,read(p).toString('base64')]));
const hash=s=>createHash('sha256').update(s).digest('hex'),raw=JSON.stringify(assets),chunks=[];mkdirSync(resolve(here,'overlay-assets'),{recursive:true});
for(let i=0;i<raw.length;i+=512000){const p='overlay-assets/'+String(chunks.length).padStart(3,'0')+'.json';writeFileSync(resolve(here,p),raw.slice(i,i+512000));chunks.push(p);}
writeFileSync(resolve(here,'overlay.json'),JSON.stringify({files,assetChunks:chunks,assetRevision:hash(raw),revision:hash(JSON.stringify({files,assets}))}));console.log(`Prepared ${Object.keys(files).length} sources and ${Object.keys(assets).length} assets.`);
