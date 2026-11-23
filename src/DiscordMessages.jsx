import React,{useEffect,useRef,useState} from 'react';
import {CornerUpLeft,Forward,ExternalLink,Reply,SmilePlus,X} from 'lucide-react';
import {messageGroups} from './discordGroups.js';
import SecureImage from './SecureImage.jsx';
import DiscordEmoji from './DiscordEmoji.jsx';
import DiscordMentionText,{TEAM_COLORS} from './DiscordMentionText.jsx';

export const authorName=author=>author.nickname||author.display_name||author.username;
export const messageExcerpt=message=>message.content?.trim().slice(0,140)||
 (message.forwarded?'Forwarded message':message.attachments?.length?'Attachment':'Message');

function ImageViewer({image,onDismiss}){
 const dialog=useRef(null);
 const [actual,setActual]=useState(false);
 useEffect(()=>{
  const element=dialog.current;
  const opener=document.activeElement;
  element.showModal();
  return()=>{element.close();opener?.focus()};
 },[]);
 return <dialog className="discordImageViewer" ref={dialog}
  onCancel={event=>{event.preventDefault();onDismiss()}}
  onClick={event=>{
   if(event.target===event.currentTarget||event.target.classList.contains('discordImageCanvas'))onDismiss();
  }} aria-label={image.name}>
  <div className="discordImageToolbar">
   <strong>{image.name}</strong>
   <button type="button" onClick={()=>setActual(!actual)}>{actual?'Fit':'100%'}</button>
   <button type="button" autoFocus aria-label="Close image" onClick={onDismiss}><X size={18}/></button>
  </div>
  <div className={`discordImageCanvas ${actual?'actual':''}`} tabIndex={0}>
   <SecureImage src={image.url} alt={image.name} consent/>
  </div>
 </dialog>;
}

function imageUrl(value){
 if(typeof value!=='string')return null;
 try{
  const url=new URL(value);
  return url.protocol==='https:'?url.href:null;
 }catch{return null}
}

function embedImage(embed){
 const media=embed.image||embed.thumbnail;
 return imageUrl(media?.proxy_url)||imageUrl(media?.url)||
  (embed.type==='image'?imageUrl(embed.url):null);
}

function MessageBody({message,onImage,known,colorFor}){
 const attachments=message.attachments||[];
 const images=[];
 const seen=new Set();
 function addImage(id,name,url){
  if(!url||seen.has(url))return;
  seen.add(url);images.push({id,name,url});
 }
 for(const item of attachments){
  if(item.content_type?.startsWith('image/')||(!item.content_type&&/\.(avif|gif|jpe?g|png|webp)$/i.test(item.name))){
   addImage(`attachment:${item.id}`,item.name,item.url);
  }
 }
 for(const [index,embed] of (message.embeds||[]).entries()){
  addImage(`embed:${index}`,embed.title||'Embedded image',embedImage(embed));
 }
 for(const sticker of message.stickers||[]){
  if(!sticker.url.endsWith('.json'))addImage(`sticker:${sticker.id}`,sticker.name,imageUrl(sticker.url));
 }
 const [consented,setConsented]=useState(new Set());
 return <>
  {message.content&&<p><DiscordMentionText text={message.content} known={known} colorFor={colorFor}/></p>}
  {images.length>0&&<div className="commImageGrid" aria-label="Message images">
   {images.map(item=><div className="secureImageTile" key={item.id} tabIndex={0} role="button" aria-label={`Open ${item.name}`}
    onClick={()=>onImage(item)} onKeyDown={event=>{if(event.key==='Enter'&&event.target===event.currentTarget)onImage(item)}}>
    <SecureImage src={item.url} alt={item.name} loading="lazy" consent={consented.has(item.url)}
     onConsent={url=>setConsented(current=>new Set([...current,url]))}/>
   </div>)}
  </div>}
  {attachments.filter(item=>!seen.has(item.url)).map(item=>
   <a key={item.id} href={item.url} target="_blank" rel="noreferrer">{item.name}</a>)}
  {(message.embeds||[]).map((embed,index)=>{
   if(!embed.title&&!embed.description&&!embed.fields?.length&&!embed.footer?.text)return null;
   const link=imageUrl(embed.url);
   return <blockquote key={index}>
    {embed.title&&(link?<a href={link} target="_blank" rel="noreferrer">{embed.title}</a>:<strong>{embed.title}</strong>)}
    {embed.description&&<p>{embed.description}</p>}
    {embed.fields?.map((field,fieldIndex)=><div key={fieldIndex}><strong>{field.name}</strong><p>{field.value}</p></div>)}
    {embed.footer?.text&&<small>{embed.footer.text}</small>}
   </blockquote>;
  })}
 </>;
}

const clock=new Intl.DateTimeFormat(undefined,{
 hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'
});

function Avatar({author}){
 const [failed,setFailed]=useState(false);
 return author.avatar_url&&!failed
  ?<SecureImage className="commAvatar" src={author.avatar_url} alt="" onError={()=>setFailed(true)}/>
  :<span className="commAvatar commAvatarPlaceholder" aria-hidden="true">{authorName(author)?.slice(0,1)}</span>;
}

export default function DiscordMessages({messages,focused,teams,teamColors,onReply,onJump,jumping,highlight,gap,
 slots,canReact,onReact}){
 const [image,setImage]=useState(null),[picker,setPicker]=useState(null);
 const [reactionError,setReactionError]=useState(null),[reactionPending,setReactionPending]=useState(null);
 const trigger=useRef(null),pickerNode=useRef(null);
 useEffect(()=>{
  if(!picker)return;
  pickerNode.current?.querySelector('button')?.focus();
  const dismiss=event=>{
   if(!pickerNode.current?.contains(event.target)&&!trigger.current?.contains(event.target))setPicker(null);
  };
  document.addEventListener('pointerdown',dismiss);
  return()=>document.removeEventListener('pointerdown',dismiss);
 },[picker]);
 const pending=useRef(false);
 const teamMap=new Map(teams.map(item=>[item.user_id,item.team]));
 const colorFor=member=>(teamColors&&TEAM_COLORS[teamMap.get(member.id)])||member.role_color;
 const known=new Map(messages.flatMap(message=>[{kind:'user',...message.author},...(message.mentions||[]),
  ...(message.forwarded_messages||[]).flatMap(snapshot=>snapshot.mentions||[])]).map(item=>[
   `${item.kind}:${item.id}`,item
 ]));
 const byId=new Map(messages.map(message=>[message.id,message]));
 const boundary=gap&&messages.find(message=>BigInt(message.id)>=BigInt(gap.boundary))?.id;
 const groups=messageGroups(messages,undefined,boundary);
 function closePicker(){
  setPicker(null);
  trigger.current?.focus();
 }
 async function addReaction(message,emoji){
  if(pending.current)return;
  pending.current=true;setReactionPending(message.id);setReactionError(null);
  try{await onReact(message,emoji);closePicker()}
  catch(error){setReactionError({id:message.id,text:error.message})}
  finally{pending.current=false;setReactionPending(null)}
 }
 return <>
  {groups.map(group=><React.Fragment key={group.id}>
   {boundary===group.id&&<div className="commHistoryGap" role="status">{gap.failed?'Some intervening history is unavailable':'Loading intervening messages…'}</div>}
   <section className={`commMessageGroup ${focused.size&&!focused.has(group.author.id)?'commDimmed':''}`}
    style={{'--author-color':colorFor(group.author)||'var(--discord-name-default)'}}>
    <div className="commGroupAvatar"><Avatar key={group.author.avatar_url} author={group.author}/></div>
    {group.messages.map((message,index)=>{
     const parent=byId.get(message.reply_to);
     const date=new Date(message.timestamp);
     const stamp=Number.isNaN(date.getTime())?'':clock.format(date);
     return <article tabIndex={0} key={message.id} data-message-id={message.id}
      className={`commMessage ${highlight===message.id?'commJumpHighlight':''}`}
      onDoubleClick={event=>{if(!event.target.closest('a,button,input,select,textarea,time'))onReply(message)}}
      onKeyDown={event=>{if(event.key==='Escape'&&picker===message.id){event.stopPropagation();closePicker()}}}>
      <div className="commMessageContent">
       {message.reply_to&&<button type="button" className="commReplyContext" onClick={()=>onJump(message)}>
        <CornerUpLeft size={13} aria-hidden="true"/>
        {parent&&<Avatar key={parent.author.avatar_url} author={parent.author}/>}
        {parent&&<strong>{authorName(parent.author)}</strong>}
        <span>{jumping===message.reply_to?'Loading original…':parent?<DiscordMentionText text={messageExcerpt(parent)} known={known} colorFor={colorFor}/>:'Jump to original message'}</span>
       </button>}
       {index===0&&<strong className="commMessageAuthor" title={authorName(group.author)}>{authorName(group.author)}</strong>}
       <MessageBody message={message} onImage={setImage} known={known} colorFor={colorFor}/>
       {message.forwarded&&<div className="commForwarded">
        <div className="commForwardLabel"><Forward size={13}/> Forwarded</div>
        {message.forwarded_messages?.length?message.forwarded_messages.map((snapshot,index)=>
         <div className="commForwardSnapshot" key={index}>
          {snapshot.timestamp&&<time dateTime={snapshot.timestamp}>{new Date(snapshot.timestamp).toLocaleString()}</time>}
          <MessageBody message={snapshot} onImage={setImage} known={known} colorFor={colorFor}/>
         </div>):<small>Forwarded content unavailable</small>}
       </div>}
       {!!message.reactions?.length&&<div className="commReactionCounts">
        {message.reactions.map(reaction=><small key={reaction.emoji}><DiscordEmoji text={reaction.emoji}/> {reaction.count}</small>)}
       </div>}
       {reactionError?.id===message.id&&<small className="suiteError" role="alert">{reactionError.text}</small>}
      </div>
      {stamp&&<time className="commTimestamp" dateTime={message.timestamp} title={date.toLocaleString()}
       aria-label={date.toLocaleString()} tabIndex={0}>{stamp}</time>}
      <div className={`commMessageActions ${picker===message.id?'open':''}`}>
       <button type="button" onClick={()=>onReply(message)}><Reply size={13}/> Reply</button>
       <button type="button" aria-expanded={picker===message.id} title={canReact?'Quick reactions':'The active profile cannot react in this channel'}
        aria-disabled={!canReact||!slots.length} onClick={event=>{
         if(!canReact||!slots.length)return;
         if(picker===message.id){closePicker();return}
         trigger.current=event.currentTarget;setPicker(message.id);
        }}><SmilePlus size={13}/> React</button>
       <a href={message.url} aria-label="Open message in Discord" target="_blank" rel="noreferrer"><ExternalLink size={12}/></a>
       {picker===message.id&&<div ref={pickerNode} className="commReactionPicker" role="group" aria-label="Quick reactions"
        onBlur={event=>{if(!event.currentTarget.parentElement.contains(event.relatedTarget))setPicker(null)}}>
        {slots.map((emoji,slot)=><button type="button" key={slot} aria-label={`React with ${emoji}`}
         disabled={reactionPending===message.id} onClick={()=>addReaction(message,emoji)}><DiscordEmoji text={emoji}/></button>)}
       </div>}
      </div>
     </article>;
    })}
   </section>
  </React.Fragment>)}
  {image&&<ImageViewer image={image} onDismiss={()=>setImage(null)}/>}
 </>;
}
