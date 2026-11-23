import React,{useEffect,useState} from 'react';
import DiscordEmoji from './DiscordEmoji.jsx';

export default function QuickReactionsSettings({api}){
 const [saved,setSaved]=useState(null),[slots,setSlots]=useState([]);
 const [busy,setBusy]=useState(false),[feedback,setFeedback]=useState('');
 const path='/communications/quick-reactions';
 function accept(value){setSaved(value);setSlots(value.slots)}
 useEffect(()=>{api(path).then(accept).catch(e=>setFeedback(e.message))},[api]);
 async function save(values){
  setBusy(true);setFeedback('');
  try{
   accept(await api(path,{slots:values}));
   window.dispatchEvent(new Event('quick-reactions-updated'));
   setFeedback('Quick reactions saved');
  }catch(e){setFeedback(e.message)}
  finally{setBusy(false)}
 }
 return <section className="quickReactionSettings">
  <h3>Quick reactions</h3>
  <div className="quickReactionSlots">{slots.map((emoji,index)=>
   <label key={index}>
    <span>Slot {index+1}</span>
    <input value={emoji} disabled={busy} maxLength={64}
     onChange={e=>setSlots(current=>current.map((value,position)=>position===index?e.target.value:value))}/>
    <span className="quickReactionPreview"><DiscordEmoji text={emoji}/></span>
   </label>)}</div>
  <button disabled={!saved||busy} onClick={()=>save(slots.map(value=>value.trim()))}>Save reactions</button>{' '}
  <button disabled={!saved||busy} onClick={()=>save(saved.defaults)}>Reset defaults</button>
  {feedback&&<p role="status">{feedback}</p>}
 </section>;
}
