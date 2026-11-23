import {apiFetch} from './api.js';
import React,{useEffect,useRef,useState} from 'react';
import {Check,GripVertical,Plus,Send,X} from 'lucide-react';
import DiscordMentionText,{mentionName,TEAM_COLORS} from './DiscordMentionText.jsx';
import {mentionQuery,shiftSelections} from './mentionDraft.js';

async function api(path,body){
 const response=await apiFetch('/api'+path,body===undefined?undefined:{
  method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
 });
 const value=await response.json();
 if(!response.ok)throw Error(value.error||'Discord request failed');
 return value;
}

export default function DiscordComposer({snapshot,onChanged,reply,onClearReply,mentionMembers=[],teams=[],teamColors=false}){
 const hot=snapshot.hot, items=hot?.items||[];
 const [text,setText]=useState(hot?.submission||''),[provider,setProvider]=useState(null);
 const [active,setActive]=useState(null),[busy,setBusy]=useState(false),[menu,setMenu]=useState(false);
 const [error,setError]=useState(''),[copied,setCopied]=useState(null);
 const [mentions,setMentions]=useState(hot?.mentions||[]);
 const [query,setQuery]=useState(null),[directory,setDirectory]=useState([]),[cursor,setCursor]=useState(0);
 const teamMap=new Map(teams.map(item=>[item.user_id,item.team]));
 const colorFor=member=>(teamColors&&TEAM_COLORS[teamMap.get(member.id)])||member.role_color;
 const choices=query?[...new Map([...directory,...mentionMembers].map(item=>[`${item.kind}:${item.id}`,item])).values()]
  .filter(item=>mentionName(item)?.toLocaleLowerCase().includes(query.query.toLocaleLowerCase()))
  .slice(0,12):[];
 const replyNames=new Map([...mentionMembers,...(reply?.mentions||[])].map(item=>[`${item.kind}:${item.id}`,item]));
 useEffect(()=>{
  setDirectory([]);setCursor(0);
  if(!query||!provider?.guild_id)return;
  let live=true;
  const timer=setTimeout(()=>{
   api(`/communications/mentions?guild=${provider.guild_id}&q=${encodeURIComponent(query.query)}`)
    .then(items=>{if(live&&Array.isArray(items))setDirectory(items)}).catch(()=>{});
  },140);
  return()=>{live=false;clearTimeout(timer)};
 },[query?.query,provider?.guild_id]);
 useEffect(()=>{setQuery(null)},[provider?.channel_id]);
 const previousPackage=useRef(hot?.id),dirty=useRef(false),operation=useRef(false),request=useRef(null);
 const preserveText=useRef(false);
 const textarea=useRef(null);
 useEffect(()=>{if(reply)textarea.current?.focus()},[reply]);
 const itemKey=JSON.stringify([hot?.id,items.map(item=>item.id)]);
 useEffect(()=>{
  if(previousPackage.current!==hot?.id){
   if(!preserveText.current&&(previousPackage.current||!dirty.current)){
    setText(hot?.submission||'');setMentions(hot?.mentions||[]);setQuery(null);dirty.current=false;
   }
   preserveText.current=false;previousPackage.current=hot?.id;
  }else if(!dirty.current){setText(hot?.submission||'');setMentions(hot?.mentions||[])}
 },[hot?.id,hot?.submission,JSON.stringify(hot?.mentions)]);
 useEffect(()=>{setCopied(null)},[itemKey]);
 useEffect(()=>{
  let live=true;
  async function refresh(){
   try{
    const [writer,send]=await Promise.all([
     api('/communications/write-status'),api('/communications/composer')
    ]);
    if(live){setProvider(writer);setActive(send)}
   }catch(e){if(live)setError(e.message)}
  }
  refresh();const timer=setInterval(refresh,3000);
  return()=>{live=false;clearInterval(timer)};
 },[]);
 const locked=busy||Boolean(active);
 const replyMismatch=reply&&(reply.channel_id!==provider?.channel_id||reply.guild_id!==provider?.guild_id);
 const ready=provider?.capabilities?.send&&!replyMismatch&&
  (!reply||provider.capabilities.reply)&&(!items.length||provider.capabilities.attach);
 const canSend=ready&&!locked&&!hot?.missing_count&&Boolean(text.trim()||items.length);
 async function action(run){
  if(operation.current)return;
  operation.current=true;setBusy(true);setError('');
  try{await run()}
  catch(e){setError(e.message)}
  finally{operation.current=false;setBusy(false)}
 }
 function clear(){
  setText('');setMentions([]);setQuery(null);dirty.current=false;setCopied(null);
 }
 async function send(event){
  event?.preventDefault();
  if(!canSend&&!request.current)return;
  await action(async()=>{
   const payload=request.current||{
    id:crypto.randomUUID(),text,package_id:items.length?hot.id:null,asset_ids:items.map(item=>item.id),
    test_mode:provider.test_mode,mentions,
    reply:reply?{id:reply.id,guild_id:reply.guild_id,channel_id:reply.channel_id}:null,
    destination:{provider:provider.provider,sender_id:provider.sender_id,guild_id:provider.guild_id,channel_id:provider.channel_id}
   };
   request.current=payload;
   let response;
   try{
    response=await apiFetch('/api/communications/composer',{
     method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
    });
   }catch{
    throw Error('Connection lost. Check send status before trying a new message.');
   }
   const result=await response.json();
   if(response.status>=500)throw Error('Check send status before trying a new message.');
   request.current=null;
   if(!response.ok)throw Error(result.error);
   if(result.status==='pending'||result.status==='unverified'){
    setActive({id:payload.id,status:result.status,error:result.error});
   }else if(result.ok){
    onClearReply?.();
    if(!result.error)clear();
   }
   setError(result.error||'');
   await onChanged();
  });
 }
 async function resolve(posted){
  await action(async()=>{
   await api('/communications/composer/resolve',{id:active.id,posted});
   request.current=null;setActive(null);
   if(posted){clear();onClearReply?.()}
   await onChanged();
  });
 }
 function saveText(){
  if(hot&&dirty.current&&(text!==hot.submission||JSON.stringify(mentions)!==JSON.stringify(hot.mentions||[]))){
   return api(`/staging/packages/${hot.id}/submission`,{submission:text,mentions});
  }
 }
 useEffect(()=>{
  if(!hot||!dirty.current||locked||request.current)return;
  const timer=setTimeout(()=>Promise.resolve(saveText()).catch(e=>setError(e.message)),450);
  return()=>clearTimeout(timer);
 },[hot?.id,hot?.submission,text,mentions,locked]);
 function moveToReserve(){
  if(locked||!hot||request.current)return;
  action(async()=>{
   await api('/staging/hot/reserve',{package_id:hot.id,submission:text,mentions});
   clear();await onChanged();
  });
 }
 function dragPackage(event){
  if(!hot||locked||request.current){event.preventDefault();return}
  event.dataTransfer.setData('application/x-ch-package',hot.id);
  event.dataTransfer.setData('application/x-ch-submission',text);
  event.dataTransfer.setData('application/x-ch-mentions',JSON.stringify(mentions));
  event.dataTransfer.effectAllowed='move';
 }
 function dropPackage(event){
  const id=event.dataTransfer.getData('application/x-ch-package');
  if(!snapshot.reserve.some(item=>item.id===id)||locked||request.current)return;
  event.preventDefault();
  action(async()=>{await saveText();await api(`/staging/reserve/${id}/activate`,{});await onChanged()});
 }
 function fallback(run){
  setMenu(false);
  action(run);
 }
 function chooseMention(item){
  if(!query||!item||!provider?.guild_id||!provider.channel_id)return;
  const name=mentionName(item),label='@'+name;
  const next=text.slice(0,query.start)+label+' '+text.slice(query.end);
  const selected={kind:item.kind,id:item.id,name,start:query.start,end:query.start+label.length,
   guild_id:provider.guild_id,channel_id:provider.channel_id};
  setMentions([...shiftSelections(text,next,mentions),selected].sort((a,b)=>a.start-b.start));
  dirty.current=true;setText(next);setQuery(null);
  requestAnimationFrame(()=>{
   textarea.current?.focus();textarea.current?.setSelectionRange(selected.end+1,selected.end+1);
  });
 }
 function updateQuery(value,caret){
  const next=provider?.guild_id&&provider?.channel_id?mentionQuery(value,caret):null;
  setQuery(current=>current?.start===next?.start&&current?.end===next?.end&&current?.query===next?.query?current:next);
 }
 function handleKeys(event){
  if(event.nativeEvent.isComposing||event.keyCode===229)return;
  if(query){
   if(event.key==='Escape'){event.preventDefault();setQuery(null);return}
   if(choices.length&&['ArrowDown','ArrowUp'].includes(event.key)){
    event.preventDefault();const step=event.key==='ArrowDown'?1:-1;
    setCursor(current=>(current+step+choices.length)%choices.length);return;
   }
   if(event.key==='Enter'&&!event.shiftKey){
    event.preventDefault();
    if(choices.length&&!event.repeat)chooseMention(choices[Math.min(cursor,choices.length-1)]);
    return;
   }
  }
  if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();if(!event.repeat)send()}
 }
 return <form className="discordComposer" onSubmit={send} onDragOver={e=>e.preventDefault()} onDrop={dropPackage}>
  {provider&&!provider.capabilities?.send&&<small className="composerUnavailable" role="status">{provider.reason||'Sending unavailable'}</small>}
  {items.length>0&&<div className="composerAttachments" aria-label="Selected crea">
   {items.map(item=><div className="composerAttachment" key={item.id}>
    <img src={`/api/image/${item.id}/thumb?rev=${item.render_key||''}`} alt={item.relpath}/>
    <button type="button" disabled={locked||!!request.current} aria-label={`Remove ${item.relpath}`}
     onClick={()=>action(async()=>{
      await api(`/staging/hot/items/${item.id}/remove`,{});
      if(items.length===1){preserveText.current=true;dirty.current=Boolean(text)}
      await onChanged();
     })}><X size={14}/></button>
    {!!item.missing&&<small>Missing</small>}
   </div>)}
  </div>}
  {reply&&<div className="composerReply">
   <span><strong>Replying to {reply.author}</strong> · <DiscordMentionText text={reply.excerpt} known={replyNames} colorFor={colorFor}/></span>
   <button type="button" aria-label="Cancel reply" disabled={locked||!!request.current}
    onClick={()=>{onClearReply?.();textarea.current?.focus()}}><X size={15}/></button>
  </div>}
  <div className="composerEntry">
   <div className="composerActions">
    <button type="button" aria-label="Manual handoff actions" aria-expanded={menu} disabled={locked||!!request.current}
     onClick={()=>setMenu(!menu)}><Plus size={18}/></button>
    {menu&&<div className="composerMenu">
     <button type="button" disabled={!text} onClick={()=>fallback(()=>window.chDesktop?.copyText?window.chDesktop.copyText(text):navigator.clipboard.writeText(text))}>Copy text</button>
     <button type="button" disabled={!hot||!!hot.missing_count||!window.chDesktop?.copyHotPackage} onClick={()=>fallback(async()=>{
      await saveText();await window.chDesktop.copyHotPackage(hot.id);setCopied(itemKey);
     })}>Copy crea files</button>
     <button type="button" disabled={!hot||!!hot.missing_count||!window.chDesktop?.openPackageInFiles} onClick={()=>fallback(async()=>{
      await saveText();await window.chDesktop.openPackageInFiles(hot.id);
     })}>Open in Files</button>
    </div>}
   </div>
   <button className="composerDrag" type="button" draggable={!!hot&&!locked&&!request.current}
    title="Drag to Reserve or activate to move the package" aria-label="Move package to Reserve"
    disabled={!hot||locked||!!request.current} onDragStart={dragPackage} onClick={moveToReserve}><GripVertical size={17}/></button>
   <textarea ref={textarea} aria-label="Discord message" placeholder={provider?.channel_name?`#${provider.channel_name}`:'Channel unavailable'}
    rows={1} maxLength={2000} value={text} disabled={locked||!!request.current}
    aria-autocomplete="list" aria-controls={query?'discord-mention-suggestions':undefined}
    aria-activedescendant={query&&choices.length?`discord-mention-${Math.min(cursor,choices.length-1)}`:undefined}
    onBlur={()=>setQuery(null)}
    onSelect={event=>updateQuery(event.currentTarget.value,event.currentTarget.selectionStart)}
    onChange={event=>{
     const next=event.currentTarget.value;dirty.current=true;
     setMentions(shiftSelections(text,next,mentions));setText(next);
     updateQuery(next,event.currentTarget.selectionStart);
    }} onKeyDown={handleKeys}/>
   {query&&<div className="composerMentionPicker" id="discord-mention-suggestions" role="listbox" aria-label="Mention member or role">
    {choices.map((item,index)=><button key={`${item.kind}:${item.id}`} id={`discord-mention-${index}`} type="button" role="option"
     aria-selected={index===Math.min(cursor,choices.length-1)} onMouseDown={event=>event.preventDefault()}
     onClick={()=>chooseMention(item)}
     style={{color:item.kind==='role'?item.role_color:colorFor(item)}}>@{mentionName(item)} <small>{item.kind==='role'?'Role':'Member'}</small></button>)}
    {!choices.length&&<small>No matching mentions</small>}
   </div>}
   {provider?.test_mode&&<small className="composerTestBadge" title="Test mode">Test</small>}
   <button className="composerSend" type="submit" aria-label="Send message" title="Send message" disabled={!canSend&&!request.current||locked}><Send size={16}/></button>
  </div>
  {request.current&&!active&&!busy&&<button type="button" onClick={()=>send()}>Check send status</button>}
  {copied===itemKey&&<button type="button" disabled={locked} onClick={()=>action(async()=>{
   await api('/staging/hot/confirm',{package_id:hot.id,asset_ids:items.map(item=>item.id)});
   clear();await onChanged();
  })}><Check size={15}/> Confirm manual handoff</button>}
  {items.length>0&&provider?.capabilities?.send&&!provider.capabilities.attach&&<small>The profile cannot attach files in this channel.</small>}
  {replyMismatch&&<small>This reply is outside the configured send channel.</small>}
  {reply&&!replyMismatch&&provider?.capabilities?.send&&!provider.capabilities.reply&&<small>This profile cannot send replies.</small>}
  {!!hot?.needs_review&&<small>Reserve replacement needs BP review</small>}
  {!!hot?.missing_count&&<small>Remove missing crea before sending.</small>}
  {error&&<p role="alert" className="suiteError">{error}</p>}
  {active?.status==='pending'&&<p role="status">Waiting for Discord confirmation…</p>}
  {active?.status==='unverified'&&<div role="status">
   <p>{active.error||'Check whether the message appeared in Discord.'}</p>
   <button type="button" disabled={busy} onClick={()=>resolve(true)}>I found the message</button>
   <button type="button" disabled={busy} onClick={()=>resolve(false)}>I verified it was not sent</button>
  </div>}
 </form>;
}
