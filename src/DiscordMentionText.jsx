import React from 'react';
import DiscordEmoji from './DiscordEmoji.jsx';

export const TEAM_COLORS={red:'#c47670',blue:'#7199bd',yellow:'#d3ba76'};
export const mentionName=item=>item?.nickname||item?.display_name||item?.username||item?.name;

export default function DiscordMentionText({text='',known=new Map(),colorFor}){
 return text.split(/(<@(?:!|&)?[0-9]{1,24}>)/g).map((part,index)=>{
  const match=/^<@([!&]?)([0-9]{1,24})>$/.exec(part);
  if(!match)return <DiscordEmoji key={index} text={part}/>;
  const kind=match[1]==='&'?'role':'user';
  const target=known.get(`${kind}:${match[2]}`);
  const color=target&&(kind==='user'?colorFor(target):target.role_color);
  return <span key={index} className="discordMention" style={{'--mention-color':color||'#b7beb0'}}>
   @{mentionName(target)||(kind==='role'?'Unknown role':'Unknown member')}
  </span>;
 });
}
