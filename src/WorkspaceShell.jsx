import React,{useEffect,useRef,useState} from 'react';
import {Check,ExternalLink,Save} from 'lucide-react';
import './workspace.css';

async function api(path,body){const response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'Workspace request failed');return data}

const discordHome='https://discord.com/channels/@me';
const stateLabels={draft:'Draft',prepared:'Prepared',handoff_pending:'Handoff pending',sent_confirmed:'Sent confirmed',failed_unverified:'Failed or unverified'};

function TestSendPanel({draft,dirty,busy,replyTo,setReplyTo,assetIds,onReorder}){
 const [provider,setProvider]=useState(null),[result,setResult]=useState(null),[sending,setSending]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let live=true;const update=()=>api('/communications/write-status').then(v=>{if(live)setProvider(v)}).catch(()=>{});update();const timer=setInterval(update,5000);return()=>{live=false;clearInterval(timer)}},[]);
 useEffect(()=>{setResult(null);if(draft?.id)api('/communications/test-send').then(setResult).catch(()=>{})},[draft?.id]);
 async function send(){if(sending||!draft)return;setSending(true);setError('');try{const value=await api('/communications/test-send',{draft_id:draft.id});setResult(value);if(!value.ok)setError(value.error||value.status||value.code||'Send not confirmed')}catch(e){setError(e.message)}finally{setSending(false)}}
 const available=provider?.capabilities?.send;
 return <div className="suiteTestSend"><div className="suiteDraftHead"><strong>Bot test send</strong><span>{provider?.state||'Loading'}</span></div><small>{available?`Bot ${provider.sender_id} → test channel ${provider.channel_id}`:provider?.reason||'Write provider unavailable'}</small><div className="suiteTestAssets">{assetIds.map((id,index)=><div key={id}><img src={`/api/image/${id}/thumb`} alt={`Selected crea ${index+1}`}/><button disabled={index===0} title="Move earlier" onClick={()=>onReorder(index,index-1)}>←</button><button disabled={index===assetIds.length-1} title="Move later" onClick={()=>onReorder(index,index+1)}>→</button></div>)}</div><div className="suiteDraftAssets"><input aria-label="Reply to Discord message ID" placeholder="Reply message ID (optional)" value={replyTo} onChange={e=>setReplyTo(e.target.value)}/><button disabled={!replyTo} onClick={()=>setReplyTo('')}>Clear reply</button></div><div className="suiteDraftActions"><button disabled={!available||dirty||busy||sending||!draft||result?.status==='confirmed'||result?.status==='pending'||result?.status==='unverified'} onClick={send}>{sending?'Sending…':'Send to test channel'}</button>{dirty&&<small>Save the draft before sending.</small>}</div>{result?.status==='confirmed'&&<a href={`https://discord.com/channels/${(result.guild_id||'@me')}/${result.channel_id}/${result.message_id}`} target="_blank" rel="noreferrer">Confirmed message {result.message_id} · sender {result.sender_id}</a>}{result?.status==='unverified'&&<small>Outcome unknown. Check Discord before sending again.</small>}{error&&<small role="alert">{error}</small>}</div>
}

export default function WorkspaceShell({children}){
 const [width,setWidth]=useState(62),[tab,setTab]=useState('crea'),[draft,setDraft]=useState(null),[text,setText]=useState(''),[assetIds,setAssetIds]=useState([]),[channelUrl,setChannelUrl]=useState(''),[dirty,setDirty]=useState(false),[hot,setHot]=useState(null),[assets,setAssets]=useState([]),[status,setStatus]=useState('idle'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [comm,setComm]=useState(null),[channel,setChannel]=useState(''),[messages,setMessages]=useState([]),[focus,setFocus]=useState(''),[onlyFocus,setOnlyFocus]=useState(false),[webFallback,setWebFallback]=useState(false);
 const [nameColors,setNameColors]=useState({});
 const [replyTo,setReplyToRaw]=useState('');
 const surface=useRef(null);
 const feedGeneration=useRef(null);
 function acceptDraft(value){setDraft(value);setText(value.text);setAssetIds(value.asset_ids);setChannelUrl(value.channel_url);setReplyToRaw(value.reply_to_id||'');setDirty(false)}
 async function refresh(){try{const [item,stage,ready]=await Promise.all([api('/workspace/draft'),api('/staging'),api('/assets')]);acceptDraft(item);setHot(stage.hot);setAssets(ready)}catch(e){setError(e.message)}}
 useEffect(()=>{refresh();const timer=setInterval(()=>api('/staging').then(stage=>setHot(stage.hot)).catch(()=>{}),2000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{api('/communications/colors').then(setNameColors).catch(()=>{})},[]);
 useEffect(()=>{let alive=true;let sequence=0;const poll=async()=>{try{const result=await api(`/communications?after=${sequence}${channel?`&channel=${channel}`:''}`);if(!alive)return;if(feedGeneration.current!==result.generation){
 const initial=feedGeneration.current===null;
 feedGeneration.current=result.generation;
 sequence=0;setComm(result);setMessages([]);setFocus('');
 const next=result.channels.some(c=>c.id===channel)?channel:
  result.channels.find(c=>c.id===result.start_channel_id)?.id||result.channels[0]?.id||'';
 if(next!==channel){setChannel(next);return}
 if(!initial)return;
 }
 if(result.state==='connected'&&channel&&!result.channels.some(c=>c.id===channel)){
  setMessages([]);setChannel(result.channels[0]?.id||'');return;
 }
 setComm(result);sequence=result.sequence;if(!channel&&result.channels.length){setMessages([]);setChannel(result.channels.find(c=>c.id===result.start_channel_id)?.id||result.channels[0].id);return}if(result.events.length)setMessages(prev=>{const map=new Map(prev.map(m=>[m.id,m]));for(const event of result.events){if(event.type==='delete')map.delete(event.message_id);else if(event.message)map.set(event.message_id,event.message)}return [...map.values()].sort((a,b)=>a.id.localeCompare(b.id))})}catch(e){if(alive)setError(e.message)}};poll();const timer=setInterval(poll,2000);return()=>{alive=false;clearInterval(timer)}},[channel]);
 useEffect(()=>{
  if(!channel)return;
  let active=true;
  api(`/communications/history?channel=${channel}`).then(v=>{
   if(active&&v.generation===feedGeneration.current)setMessages(prev=>{
    const merged=new Map((v.messages||[]).map(message=>[message.id,message]));
    for(const message of prev)merged.set(message.id,message);
    return [...merged.values()].sort((a,b)=>a.id.localeCompare(b.id));
   });
  }).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[channel,comm?.generation,comm?.state]);
 useEffect(()=>{if(!window.chDesktop?.onCommunicationsStatus)return;const off=window.chDesktop.onCommunicationsStatus(setStatus);window.chDesktop.communicationsCapabilities().then(value=>setStatus(value.status)).catch(()=>{});return off},[]);
 useEffect(()=>{
  if(!window.chDesktop?.setCommunicationsBounds||!surface.current||!webFallback)return;
  const node=surface.current;
  const update=()=>{const rect=node.getBoundingClientRect();window.chDesktop.setCommunicationsBounds(rect.width&&rect.height?{x:rect.x,y:rect.y,width:rect.width,height:rect.height}:null).then(setStatus).catch(e=>setStatus(`failed: ${e.message}`))};
  const observer=new ResizeObserver(update);observer.observe(node);addEventListener('resize',update);update();
  return()=>{observer.disconnect();removeEventListener('resize',update);window.chDesktop.setCommunicationsBounds(null).catch(()=>{})};
 },[webFallback]);
 function change(field,value){field(value);setDirty(true)}
 async function save(){if(!draft||busy)return;setBusy(true);setError('');try{acceptDraft(await api('/workspace/draft',{text,asset_ids:assetIds,channel_url:channelUrl,reply_to_id:replyTo}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 function setReplyTo(value){change(setReplyToRaw,value)}
 function reorderAsset(from,to){const next=[...assetIds];next.splice(to,0,next.splice(from,1)[0]);change(setAssetIds,next)}
 async function transition(next){if(!draft||busy||dirty)return;setBusy(true);setError('');try{acceptDraft(await api('/workspace/draft/transition',{status:next,manual_confirmation:next==='sent_confirmed'}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function newDraft(){if(busy)return;setBusy(true);setError('');try{acceptDraft(await api('/workspace/draft/new',{}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 function useHot(){if(!hot)return;change(setAssetIds,hot.items.map(item=>item.id))}
 async function navigate(){const target=channelUrl.trim()||discordHome;try{const result=window.chDesktop?.navigateDiscord?await window.chDesktop.navigateDiscord(target):{ok:false};if(!result.ok)await external(target)}catch(e){setError(e.message)}}
 async function external(target=channelUrl.trim()||discordHome){try{if(window.chDesktop?.openDiscordExternally){const result=await window.chDesktop.openDiscordExternally(target);if(!result.ok)throw Error('Enter a Discord channel link')}else window.open(target,'_blank','noopener,noreferrer')}catch(e){setError(e.message)}}
 function resizeStart(event){event.currentTarget.setPointerCapture(event.pointerId)}
 function resizeMove(event){if(event.currentTarget.hasPointerCapture(event.pointerId))setWidth(Math.max(45,Math.min(75,Math.round(event.clientX/window.innerWidth*100))))}
 const editable=draft&&['draft','prepared','failed_unverified'].includes(draft.status);
 const known=new Map(assets.map(a=>[a.id,a]));
 return <div className="suiteShell" style={{'--crea-width':`${width}vw`}}><nav className="suiteTabs" aria-label="Workspace regions"><button className={tab==='crea'?'active':''} onClick={()=>setTab('crea')}>Crea Manager</button><button className={tab==='communications'?'active':''} onClick={()=>setTab('communications')}>Communications</button></nav><div className={`suiteCrea ${tab==='crea'?'suiteTabActive':''}`}>{children}</div><div className="suiteDivider" role="separator" aria-label="Resize workspace" aria-orientation="vertical" onPointerDown={resizeStart} onPointerMove={resizeMove}/><aside className={`suiteCommunications ${tab==='communications'?'suiteTabActive':''}`} aria-label="Communications workspace"><div className="suiteCommHeader"><strong>COMMUNICATIONS</strong><button onClick={()=>setWebFallback(!webFallback)}>{webFallback?'Live feed':'Discord web'}</button><button onClick={()=>external()} title="Open Discord externally"><ExternalLink size={16}/></button></div><div className="suiteDraft"><div className="suiteDraftHead"><strong>Local submission</strong><span>{stateLabels[draft?.status]||'Loading'}</span></div>{error&&<p role="alert" className="suiteError">{error}</p>}<textarea aria-label="Local submission draft" placeholder="Submission…" value={text} disabled={!editable} onChange={e=>change(setText,e.target.value)}/><div className="suiteDraftAssets"><button disabled={!editable||!hot} onClick={useHot}>Use Hot selection</button>{assetIds.map(id=><button key={id} disabled={!editable} title="Remove selection" onClick={()=>change(setAssetIds,assetIds.filter(item=>item!==id))}>{known.get(id)?.type?.toUpperCase()||id.slice(0,8)} ×</button>)}</div><div className="suiteDraftActions"><button disabled={!editable||!dirty||busy} onClick={save}><Save size={14}/> Save</button>{draft?.status==='draft'&&<button disabled={dirty||busy} onClick={()=>transition('prepared')}>Prepare</button>}{draft?.status==='prepared'&&<><button disabled={dirty||busy} onClick={()=>transition('handoff_pending')}>Handoff pending</button><button disabled={dirty||busy} onClick={()=>transition('draft')}>Edit</button></>}{draft?.status==='handoff_pending'&&<><button disabled={busy} onClick={()=>transition('sent_confirmed')}><Check size={14}/> Confirm sent</button><button disabled={busy} onClick={()=>transition('failed_unverified')}>Failed / unverified</button></>}{draft?.status==='failed_unverified'&&<button disabled={dirty||busy} onClick={()=>transition('handoff_pending')}>Retry handoff</button>}{draft?.status==='sent_confirmed'&&<button disabled={busy} onClick={newDraft}>New draft</button>}</div><TestSendPanel draft={draft} dirty={dirty} busy={busy} replyTo={replyTo} setReplyTo={setReplyTo} assetIds={assetIds} onReorder={reorderAsset}/><div className="suiteChannel"><input aria-label="Discord channel link" placeholder="Discord channel link" value={channelUrl} disabled={!editable} onChange={e=>change(setChannelUrl,e.target.value)}/><button onClick={navigate}>Open</button></div></div>{!webFallback?<><div className="suiteDiscordStatus">{comm?.state||'Loading'} · {comm?.reason||'Read only · sending unavailable'}</div><div className="commChannels">{comm?.channels.map(c=><button key={c.id} className={channel===c.id?'active':''} onClick={()=>{if(channel!==c.id){setMessages([]);setChannel(c.id)}}}># {c.name}</button>)}</div><div className="commFocus"><select value={focus} onChange={e=>setFocus(e.target.value)}><option value="">All participants</option>{[...new Map(messages.map(m=>[m.author.id,m.author])).values()].map(a=><option key={a.id} value={a.id}>{a.nickname||a.display_name||a.username}</option>)}</select><label><input type="checkbox" checked={onlyFocus} onChange={e=>setOnlyFocus(e.target.checked)} disabled={!focus}/> Focus only</label></div><div className="commFeed">{messages.filter(m=>!onlyFocus||!focus||m.author.id===focus||messages.some(p=>p.id===m.reply_to&&p.author.id===focus)).map(m=><article className={focus&&m.author.id===focus?'focused':''} key={m.id}><img src={m.author.avatar_url} alt=""/><div><div><strong style={{color:nameColors[m.author.id]||m.author.role_color||undefined}}>{m.author.nickname||m.author.display_name||m.author.username}</strong> <input className="commColor" type="color" title="Set local name color" value={nameColors[m.author.id]||m.author.role_color||'#F0EEE5'} onChange={e=>api('/communications/color',{user_id:m.author.id,color:e.target.value}).then(setNameColors).catch(err=>setError(err.message))}/> <time>{new Date(m.timestamp).toLocaleString()}</time> <a href={m.url} target="_blank" rel="noreferrer">↗</a></div>{m.reply_to&&<small>Reply to {m.reply_to}</small>}<p>{m.content}</p>{m.attachments.map(a=><a key={a.id} href={a.url} target="_blank" rel="noreferrer">{a.content_type?.startsWith('image/')?<img className="commAttachment" src={a.url} alt={a.name}/>:a.name}</a>)}{m.embeds.map((e,i)=><blockquote key={i}>{e.title||e.description||'Embed'}</blockquote>)}<small>{m.reactions.map(r=>`${r.emoji} ${r.count}`).join('  ')}</small></div></article>)}</div></>:<><div className="suiteDiscordStatus">Discord web view: {status}. Manual use only.</div><div className="suiteDiscordSurface" ref={surface}><button onClick={()=>external()}>Open Discord externally</button></div></>}</aside></div>
}
