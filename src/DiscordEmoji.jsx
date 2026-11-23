import React,{useState} from 'react';
import SecureImage from './SecureImage.jsx';

function CustomEmoji({name,id,animated}){
 const [failed,setFailed]=useState(false);
 if(failed)return <span>:{name}:</span>;
 return <SecureImage className="discordEmoji" src={`https://cdn.discordapp.com/emojis/${id}.${animated?'gif':'webp'}?size=32`}
  alt={`:${name}:`} title={`:${name}:`} onError={()=>setFailed(true)}/>;
}

export default function DiscordEmoji({text=''}){
 return text.split(/(<a?:[A-Za-z0-9_]{2,32}:[0-9]{1,24}>)/g).map((part,index)=>{
  const match=/^<(a?):([A-Za-z0-9_]{2,32}):([0-9]{1,24})>$/.exec(part);
  return match?<CustomEmoji key={`${index}:${part}`} name={match[2]} id={match[3]} animated={Boolean(match[1])}/>:part;
 });
}
