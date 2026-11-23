import React,{useState} from 'react';

const CDN=new Set(['cdn.discordapp.com','media.discordapp.net','images-ext-1.discordapp.net','images-ext-2.discordapp.net']);
export function mediaSource(value,consent=false){
 try{
  const url=new URL(value,location.origin);
  if(url.origin===location.origin&&url.pathname.startsWith('/api/image/'))return {src:url.href};
  if(url.protocol!=='https:'||url.username||url.password||url.port)return {blocked:true};
  const host=url.hostname.toLowerCase();
  if(host==='localhost'||host.endsWith('.local')||host.endsWith('.internal')||
     /^\d+\.\d+\.\d+\.\d+$/.test(host)||host.includes(':'))return {blocked:true};
  return CDN.has(host)||consent?{src:'/api/media?url='+encodeURIComponent(url.href)+(consent?'&consent=1':'')}:{host};
 }catch{return {blocked:true}}
}

export default function SecureImage({src,alt='',consent=false,onConsent,...props}){
 const [allowed,setAllowed]=useState(null),[failed,setFailed]=useState(null);
 const media=mediaSource(src,consent||allowed===src);
 if(media.blocked||failed===src)return <span className="mediaUnavailable">{alt||'Image unavailable'}</span>;
 if(media.host)return <button type="button" className="mediaConsent" onClick={event=>{
  event.stopPropagation();setAllowed(src);onConsent?.(src);
 }}>Load image · {media.host}</button>;
 return <img {...props} src={media.src} alt={alt} referrerPolicy="no-referrer" onError={event=>{
  setFailed(src);props.onError?.(event);
 }}/>;
}
