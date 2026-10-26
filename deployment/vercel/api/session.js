import {randomBytes} from 'node:crypto';
import {openPreview} from '../runtime.js';
export default async function handler(req,res){
  res.setHeader('Cache-Control','no-store');res.setHeader('Referrer-Policy','no-referrer');
  if((req.headers.host||'').split(':')[0]!=='montara-tau.vercel.app')return res.status(400).json({error:'Abre siempre https://montara-tau.vercel.app/ para iniciar la prueba.'});
  if(req.method!=='GET')return res.status(405).json({error:'Open the preview from the Montara page.'});
  const cookie=(req.headers.cookie||'').split(';').map(v=>v.trim()).find(v=>v.startsWith('montara_demo='))?.split('=')[1];
  const id=/^[a-f0-9]{32}$/.test(cookie||'')?cookie:randomBytes(16).toString('hex');
  res.setHeader('Set-Cookie',`montara_demo=${id}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800`);
  try{const preview=await openPreview(id);return res.status(200).json({url:preview.url});}
  catch(error){console.error('Preview startup failed:',error.message);return res.status(503).json({error:error.message.startsWith('PREVIEW_BUSY:')?error.message.slice(14).trim():'No se ha podido iniciar el motor de prueba. Puede haberse agotado la cuota gratuita. Tus datos se conservan; vuelve a intentarlo desde esta dirección.'});}
}
