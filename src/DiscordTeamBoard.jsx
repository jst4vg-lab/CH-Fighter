import React,{useEffect,useMemo,useRef,useState} from 'react';
import {ChevronDown,Users} from 'lucide-react';
import {authorName} from './DiscordMessages.jsx';

export const LANES=[['pool','Unassigned'],['red','Alpha'],['blue','Bravo'],['yellow','Charlie']];
const MEMBER_TYPE='application/x-clan-hub-discord-member';

export default function DiscordTeamBoard({guildId,messages,focused,onFocus,onClear,api,onAssignments,teamColors,onColorView}){
 const [assignments,setAssignments]=useState([]),[expanded,setExpanded]=useState(true);
 const [over,setOver]=useState(''),[error,setError]=useState('');
 const drag=useRef(null),scope=useRef(guildId),moving=useRef(false),suppressClick=useRef(false);
 scope.current=guildId;
 useEffect(()=>{
  if(!/^[0-9]{1,24}$/.test(guildId||''))return;
  let live=true;
  api(`/communications/teams?guild=${guildId}`).then(value=>{if(live){setAssignments(value);onAssignments(guildId,value)}})
   .catch(e=>{if(live)setError(e.message)});
  return()=>{live=false};
 },[guildId,api]);
 const members=useMemo(()=>{
  const list=new Map(assignments.map(item=>[item.user_id,{id:item.user_id,name:item.name,team:item.team}]));
  for(const message of messages){
   if(message.guild_id!==guildId)continue;
   const author=message.author;
   list.set(author.id,{...list.get(author.id),id:author.id,name:authorName(author)});
  }
  return [...list.values()].sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
 },[assignments,messages,guildId]);
 async function move(member,lane,restoreFocus=false){
  if(!member||moving.current||!guildId||(member.team||'pool')===lane)return;
  moving.current=true;setError('');
  try{
   const value=await api('/communications/teams',{guild_id:guildId,user_id:member.id,name:member.name,
    team:lane==='pool'?null:lane});
   if(scope.current===guildId){
    setAssignments(value);onAssignments(guildId,value);
    if(restoreFocus)requestAnimationFrame(()=>document.querySelector(`[data-team-member="${member.id}"]`)?.focus());
   }
  }catch(e){if(scope.current===guildId)setError(e.message)}
  finally{moving.current=false}
 }
 function endDrag(){
  setOver('');drag.current=null;
  setTimeout(()=>{suppressClick.current=false},0);
 }
 return <section className="teamBoard" aria-label="Discord team board">
  <div className="teamBoardHeader">
   <button type="button" className="teamBoardToggle" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>
    <Users size={14}/> Teams <ChevronDown size={12}/>
   </button>
   <button type="button" aria-pressed={teamColors} onClick={()=>onColorView(!teamColors)}>Team colors</button>
   {!!focused.size&&<><small>{focused.size} focused</small><button type="button" onClick={onClear}>Clear focus</button></>}
  </div>
  {expanded&&<>
   <div className="teamBoardLanes">
    {LANES.map(([lane,label])=>{
     const people=members.filter(member=>(member.team||'pool')===lane);
     return <section key={lane} className={`teamLane teamLane-${lane} ${over===lane?'dropTarget':''}`}
      onDragOver={event=>{
       if(!drag.current)return;
       event.preventDefault();event.dataTransfer.dropEffect='move';setOver(lane);
      }}
      onDragLeave={event=>{if(!(event.relatedTarget instanceof Node)||!event.currentTarget.contains(event.relatedTarget))setOver(current=>current===lane?'':current)}}
      onDrop={event=>{
       if(!drag.current)return;
       event.preventDefault();
       const id=event.dataTransfer.getData(MEMBER_TYPE);
       if(id===drag.current)move(members.find(member=>member.id===id),lane);
       endDrag();
      }}>
      <h4>{label} <span>{people.length}</span></h4>
      <div className="teamMembers">
       {people.map(member=><button key={member.id} data-team-member={member.id} type="button" draggable
        title={`${member.name} · Alt+Left/Right to move`} aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
        onKeyDown={event=>{
         if(!event.altKey||!['ArrowLeft','ArrowRight'].includes(event.key))return;
         event.preventDefault();const offset=event.key==='ArrowLeft'?-1:1;
         const target=LANES[LANES.findIndex(([id])=>id===lane)+offset];
         if(target)move(member,target[0],true);
        }}
        className={focused.size&&!focused.has(member.id)?'dimMember':''}
        aria-pressed={focused.has(member.id)}
        onDragStart={event=>{
         drag.current=member.id;suppressClick.current=true;
         event.dataTransfer.setData(MEMBER_TYPE,member.id);event.dataTransfer.effectAllowed='move';
        }}
        onDragEnd={endDrag} onClick={()=>{if(!suppressClick.current)onFocus(member.id)}}>
        {member.name}
       </button>)}
      </div>
     </section>;
    })}
   </div>
   {error&&<p className="suiteError" role="alert">{error}</p>}
  </>}
 </section>;
}
