import React,{useEffect,useState} from 'react';

export default function DiscordDestinationSettings({api,profileId}){
 const [options,setOptions]=useState(null),[draft,setDraft]=useState(null);
 const [busy,setBusy]=useState(false),[feedback,setFeedback]=useState('');
 const path='/communications/destination';
 useEffect(()=>{
  setOptions(null);setDraft(null);setFeedback('');
  let live=true;
  const refresh=()=>api(path).then(value=>{if(live)setOptions(value)}).catch(e=>{if(live)setFeedback(e.message)});
  refresh();const timer=setInterval(refresh,3000);
  return()=>{live=false;clearInterval(timer)};
 },[api,profileId]);
 const selected=draft||options;
 const guild=options?.guilds.find(item=>item.id===selected?.guild_id);
 const channel=guild?.channels.find(item=>item.id===selected?.channel_id);
 async function save(){
  setBusy(true);setFeedback('');
  try{
   setOptions(await api(path,{profile_id:options.profile_id,guild_id:guild.id,channel_id:channel.id}));
   setDraft(null);setFeedback('Discord destination saved.');
  }catch(error){setFeedback(error.message)}
  finally{setBusy(false)}
 }
 return <section className="discordDestinationSettings" aria-label="Discord destination">
  <h3>Feed destination</h3>
  <div className="discordDestinationFields">
   <label>Server <select value={guild?.id||''} disabled={busy||!options?.guilds.length}
    onChange={event=>setDraft({guild_id:event.target.value,channel_id:''})}>
    <option value="" disabled>{options?.guilds.length?'Choose a server':'No servers available'}</option>
    {options?.guilds.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
   </select></label>
   <label>Channel <select value={channel?.id||''} disabled={busy||!guild}
    onChange={event=>setDraft({guild_id:guild.id,channel_id:event.target.value})}>
    <option value="" disabled>Choose a channel</option>
    {guild&&!guild.channels.length&&<option disabled>No visible text channels</option>}
    {guild?.channels.map(item=><option key={item.id} value={item.id}>{item.thread?'Thread: ':'#'}{item.name}</option>)}
   </select></label>
   <button disabled={busy||!guild||!channel} onClick={save}>Apply destination</button>
  </div>
  {options?.channel_id&&!draft&&!channel&&<p role="status">The configured channel is currently unavailable.</p>}
  {channel?.history===false&&<p role="status">The incoming profile can see live messages here. It cannot load channel history.</p>}
  {feedback&&<p role="status">{feedback}</p>}
 </section>;
}
