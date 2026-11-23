import {apiFetch} from './api.js';
import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import './workspace.css';
import DiscordMessages,{authorName,messageExcerpt} from './DiscordMessages.jsx';
import DiscordTeamBoard from './DiscordTeamBoard.jsx';

async function api(path,body,signal){const response=await apiFetch('/api'+path,{signal,method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'Workspace request failed');return data}

function mergeMessages(older,newer){
 const byId=new Map([...older,...newer].map(message=>[message.id,message]));
 return [...byId.values()].sort((a,b)=>a.id.length-b.id.length||a.id.localeCompare(b.id));
}

export default function WorkspaceShell({children}){
 const [width,setWidth]=useState(50),[tab,setTab]=useState('crea');
 const [error,setError]=useState('');

 const [comm,setComm]=useState(null),[channel,setChannel]=useState(''),[messages,setMessages]=useState([]);
 const [focusByGuild,setFocusByGuild]=useState({});
 const guildId=comm?.guild_id;
 const focused=focusByGuild[guildId]||new Set();
 function toggleFocus(id){
  setFocusByGuild(current=>{
   const next=new Set(current[guildId]);
   if(next.has(id))next.delete(id);else next.add(id);
   return {...current,[guildId]:next};
  });
 }
 const [teamColors,setTeamColors]=useState(false),[teamState,setTeamState]=useState(null);
 const teams=teamState&&teamState.guildId===guildId?teamState.members:[];
 useEffect(()=>{api('/communications/team-colors').then(value=>setTeamColors(value.enabled)).catch(e=>setError(e.message))},[]);
 async function changeTeamColors(enabled){
  try{setTeamColors((await api('/communications/team-colors',{enabled})).enabled)}
  catch(e){setError(e.message)}
 }
 const [reply,setReply]=useState(null);
 const [hotDock,setHotDock]=useState(null);
 const feedNode=useRef(null),feedEpoch=useRef(0),historyPending=useRef(false);
 const scrollIntent=useRef(null),followLive=useRef(true);
 const [olderAvailable,setOlderAvailable]=useState(false),[newMessages,setNewMessages]=useState(false);
 const [jumping,setJumping]=useState(null),[highlight,setHighlight]=useState(null),[gap,setGap]=useState(null);
 const [readingContext,setReadingContext]=useState(false),[slots,setSlots]=useState([]),[writer,setWriter]=useState(null);
 const jumpRequest=useRef(null),jumpTarget=useRef(null),highlightTimer=useRef(null);
 const deletedMessages=useRef(new Set());
 function jumpToLatest(){
  const node=feedNode.current;
  if(node)node.scrollTop=node.scrollHeight;
  followLive.current=true;setNewMessages(false);setReadingContext(false);
 }
 function captureAnchor(){
  const node=feedNode.current;
  if(!node)return;
  const visible=[...node.querySelectorAll('[data-message-id]')].find(
   article=>article.getBoundingClientRect().bottom>node.getBoundingClientRect().top);
  if(visible)scrollIntent.current={anchor:visible.dataset.messageId,top:visible.getBoundingClientRect().top};
 }
 function itemElement(id){
  return feedNode.current?.querySelector(`[data-message-id="${id}"]`);
 }
 useLayoutEffect(()=>{
  const node=feedNode.current;
  const intent=scrollIntent.current;
  scrollIntent.current=null;
  if(!node)return;
  if(jumpTarget.current){
   const target=itemElement(jumpTarget.current);
   if(target){
    jumpTarget.current=null;
    target.focus({preventScroll:true});
    target.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
   }
   return;
  }
  if(intent?.anchor){
   const anchor=itemElement(intent.anchor);
   if(anchor)node.scrollTop+=anchor.getBoundingClientRect().top-intent.top;
  }else if(followLive.current)jumpToLatest();
 },[messages,highlight,gap]);
 async function onFeedScroll(){
  const node=feedNode.current;
  if(!node||jumpTarget.current)return;
  if(!readingContext)followLive.current=node.scrollHeight-node.clientHeight-node.scrollTop<32;
  if(followLive.current)setNewMessages(false);
  if(node.scrollTop>64||!olderAvailable||historyPending.current||!messages.length||jumpRequest.current)return;
  const before=messages[0].id,epoch=feedEpoch.current;
  historyPending.current=true;
  try{
   const page=await api(`/communications/history?channel=${channel}&before=${before}`);
   if(epoch!==feedEpoch.current||page.generation!==feedGeneration.current)return;
   if(page.error)throw Error(page.error);
   captureAnchor();
   setOlderAvailable(page.messages.length>=50&&page.messages.some(message=>BigInt(message.id)<BigInt(before)));
   setMessages(current=>mergeMessages(page.messages.filter(message=>!deletedMessages.current.has(message.id)),current));
  }catch(e){if(epoch===feedEpoch.current)setError(e.message)}
  finally{if(epoch===feedEpoch.current)historyPending.current=false}
 }
 function revealOriginal(id){
  followLive.current=false;setReadingContext(true);
  jumpTarget.current=id;
  setHighlight(null);
  requestAnimationFrame(()=>{if(jumpTarget.current===id)setHighlight(id)});
  clearTimeout(highlightTimer.current);
  highlightTimer.current=setTimeout(()=>setHighlight(null),1800);
 }
 async function jumpToOriginal(message){
  const id=message.reply_to;
  if(!/^[0-9]{1,24}$/.test(id)||message.reply_channel_id&&message.reply_channel_id!==channel){
   setError('The original message is outside this channel.');return;
  }
  if(deletedMessages.current.has(id)){setError('The original message was deleted.');return}
  setError('');
  if(messages.some(item=>item.id===id)){revealOriginal(id);return}
  jumpRequest.current?.abort();
  const request=new AbortController(),epoch=feedEpoch.current;
  jumpRequest.current=request;setJumping(id);
  const valid=()=>!request.signal.aborted&&epoch===feedEpoch.current;
  async function pageAt(key,value){
   const page=await api(`/communications/history?channel=${channel}&${key}=${value}`,undefined,request.signal);
   if(!valid()||page.generation!==feedGeneration.current){request.abort();return null}
   if(page.error)throw Error(page.error);
   return page.messages.filter(item=>!deletedMessages.current.has(item.id));
  }
  let boundary;
  try{
   const around=await pageAt('around',id);
   if(!around)return;
   if(!around.some(item=>item.id===id))throw Error('The original message was deleted or is inaccessible.');
   boundary=gap?.boundary||messages[0]?.id;
   let cursor=mergeMessages([],around).at(-1).id;
   const bridging=boundary&&BigInt(cursor)<BigInt(boundary);
   if(!bridging)boundary=null;
   setGap(boundary?{boundary}:null);
   setOlderAvailable(true);
   setJumping(null);
   revealOriginal(id);
   setMessages(current=>mergeMessages(around,gap?current.filter(item=>BigInt(item.id)>=BigInt(gap.boundary)):current));
   while(boundary&&valid()){
    const next=await pageAt('after',cursor);
    if(!next)return;
    const sorted=mergeMessages([],next).filter(item=>BigInt(item.id)>BigInt(cursor));
    const middle=sorted.filter(item=>BigInt(item.id)<BigInt(boundary));
    const reached=!sorted.length||sorted.length<50||BigInt(sorted.at(-1).id)>=BigInt(boundary);
    if((middle.length||reached)&&!followLive.current&&!jumpTarget.current)captureAnchor();
    if(middle.length)setMessages(current=>mergeMessages(middle,current));
    if(reached){
     setGap(null);break;
    }
    cursor=sorted.at(-1).id;
   }
  }catch(e){
   if(valid()){setError(e.message);if(boundary)setGap({boundary,failed:true})}
  }finally{if(jumpRequest.current===request){jumpRequest.current=null;setJumping(null)}}
 }
 useEffect(()=>{
  const update=()=>api('/communications/quick-reactions').then(value=>setSlots(value.slots)).catch(()=>{});
  update();window.addEventListener('quick-reactions-updated',update);
  return()=>window.removeEventListener('quick-reactions-updated',update);
 },[]);
 useEffect(()=>{
  let active=true;
  const update=()=>api('/communications/write-status').then(value=>{if(active)setWriter(value)}).catch(()=>{if(active)setWriter(null)});
  update();const timer=setInterval(update,3000);
  return()=>{active=false;clearInterval(timer)};
 },[channel]);
 const canReact=writer?.capabilities?.react&&writer.channel_id===channel;
 async function reactTo(message,emoji){
  const epoch=feedEpoch.current;
  const result=await api('/communications/react',{message_id:message.id,emoji,
   channel_id:message.channel_id,guild_id:message.guild_id,sender_id:writer?.sender_id});
  if(!result.ok)throw Error(result.error||'Discord could not add the reaction');
  if(epoch===feedEpoch.current&&result.message&&!deletedMessages.current.has(message.id)){
   if(!followLive.current)captureAnchor();
   setMessages(current=>mergeMessages(current,[result.message]));
  }
 }
 const feedGeneration=useRef(null);
 const activeReply=reply?.channel_id===channel&&reply?.generation===comm?.generation?reply:null;
 useEffect(()=>{
  setReply(null);setGap(null);setJumping(null);setHighlight(null);setReadingContext(false);
  jumpTarget.current=null;deletedMessages.current.clear();
  return()=>{jumpRequest.current?.abort();jumpRequest.current=null;clearTimeout(highlightTimer.current)};
 },[channel,comm?.generation]);
 function replyTo(message){
  setReply({id:message.id,guild_id:message.guild_id,channel_id:message.channel_id,
   generation:comm?.generation,author:authorName(message.author),excerpt:messageExcerpt(message),mentions:message.mentions||[]});
 }
 useEffect(()=>{let alive=true;let sequence=0;const poll=async()=>{try{const result=await api(`/communications?after=${sequence}${channel?`&channel=${channel}`:''}`);if(!alive)return;if(feedGeneration.current!==result.generation){
 const initial=feedGeneration.current===null;
 feedGeneration.current=result.generation;
 sequence=0;setComm(result);setMessages([]);
 const next=result.channels.find(c=>c.id===result.start_channel_id)?.id||(result.start_channel_id?'':result.channels[0]?.id||'');
 if(next!==channel){setChannel(next);return}
 if(!initial)return;
 }
 setComm(result);
 const configured=result.channels.find(c=>c.id===result.start_channel_id)?.id||
  (result.start_channel_id?'':result.channels[0]?.id||'');
 if(result.state==='connected'&&configured!==channel){
  setMessages([]);setChannel(configured);return;
 }
 sequence=result.sequence;
 if(result.events.length&&!followLive.current&&result.events.some(event=>event.type==='upsert'&&!event.message?.edited_at))setNewMessages(true);if(result.events.length)setMessages(prev=>{const map=new Map(prev.map(m=>[m.id,m]));for(const event of result.events){if(event.type==='delete'){deletedMessages.current.add(event.message_id);map.delete(event.message_id)}else if(event.message&&!deletedMessages.current.has(event.message_id))map.set(event.message_id,event.message)}return mergeMessages([],map.values())})}catch(e){if(alive)setError(e.message)}};poll();const timer=setInterval(poll,2000);return()=>{alive=false;clearInterval(timer)}},[channel]);
 useEffect(()=>{
  if(!channel)return;
  let active=true;
  feedEpoch.current+=1;historyPending.current=true;
  followLive.current=true;setOlderAvailable(false);setNewMessages(false);
  api(`/communications/history?channel=${channel}`).then(page=>{
   if(!active||page.generation!==feedGeneration.current)return;
   if(page.error)throw Error(page.error);
   setOlderAvailable(page.messages.length>=50);
   setMessages(current=>mergeMessages(page.messages.filter(message=>!deletedMessages.current.has(message.id)),current));
  }).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)historyPending.current=false});
  return()=>{active=false;feedEpoch.current+=1};
 },[channel,comm?.generation,comm?.state]);
 function resizeStart(event){event.currentTarget.setPointerCapture(event.pointerId)}
 function resizeMove(event){if(event.currentTarget.hasPointerCapture(event.pointerId))setWidth(Math.max(45,Math.min(75,Math.round(event.clientX/window.innerWidth*100))))}
 return <div className="suiteShell" style={{'--crea-width':`${width}vw`}}><nav className="suiteTabs" aria-label="Workspace regions"><button className={tab==='crea'?'active':''} onClick={()=>setTab('crea')}>Crea Manager</button><button className={tab==='communications'?'active':''} onClick={()=>setTab('communications')}>Communications</button></nav><div className={`suiteCrea ${tab==='crea'?'suiteTabActive':''}`}>{children(hotDock,activeReply,()=>setReply(null),[...new Map(messages.flatMap(message=>[{kind:'user',...message.author},...(message.mentions||[])]).map(item=>[`${item.kind}:${item.id}`,item])).values()],teams,teamColors)}</div><div className="suiteDivider" role="separator" aria-label="Resize workspace" aria-orientation="vertical" onPointerDown={resizeStart} onPointerMove={resizeMove}/><aside className={`suiteCommunications ${tab==='communications'?'suiteTabActive':''}`} aria-label="Communications workspace"><div className="suiteCommHeader"><strong>{comm?.channels.find(item=>item.id===channel)?.name ? '# '+comm.channels.find(item=>item.id===channel).name : 'Communications'}</strong></div><div className="suiteDiscordStatus">{comm?.state||'Loading'} · {comm?.reason||(!channel?'Select or reconnect a Discord profile in Settings':'Live feed')}</div><DiscordTeamBoard key={guildId} guildId={guildId} messages={messages} focused={focused} onAssignments={(guildId,members)=>setTeamState({guildId,members})} teamColors={teamColors} onColorView={changeTeamColors} onFocus={toggleFocus} onClear={()=>setFocusByGuild(current=>({...current,[guildId]:new Set()}))} api={api}/>{(newMessages||readingContext)&&<button className="commLatest" onClick={jumpToLatest}>{readingContext?'Back to latest':'New messages'}</button>}<div ref={feedNode} className="commFeed" tabIndex={0} onScroll={onFeedScroll}><DiscordMessages key={`${channel}:${comm?.generation}`} messages={messages} focused={focused} teams={teams} teamColors={teamColors} onReply={replyTo} onJump={jumpToOriginal} jumping={jumping} highlight={highlight} gap={gap} slots={slots} canReact={canReact} onReact={reactTo}/></div><section className="suiteComposer" aria-label="Discord composer">
 <div className="suiteHotDock" ref={setHotDock}/>
 {error&&<p className="suiteError" role="alert">{error}</p>}
</section></aside></div>
}
