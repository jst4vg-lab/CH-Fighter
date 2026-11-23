import React,{useState} from 'react';
import {ArrowDown,ArrowUp,GripVertical,RotateCcw} from 'lucide-react';

function ReorderList({items,labels,onChange}){
 const [dragged,setDragged]=useState(null);
 function move(from,to){
  if(from===to||from<0||to<0||to>=items.length)return;
  const result=[...items];
  result.splice(to,0,result.splice(from,1)[0]);
  onChange(result);
 }
 return <ul className="galleryOrderList">
  {items.map((id,index)=><li key={id} onDragOver={e=>{if(dragged)e.preventDefault()}}
   onDrop={e=>{e.preventDefault();if(dragged)move(items.indexOf(dragged),index);setDragged(null)}}>
   <button type="button" className="orderGrip" draggable aria-label={`Drag ${labels[id]}`}
    onDragStart={e=>{setDragged(id);e.dataTransfer.setData('text/plain',id);e.dataTransfer.effectAllowed='move'}}
    onDragEnd={()=>setDragged(null)}><GripVertical size={15}/></button>
   <span>{labels[id]}</span>
   <button type="button" disabled={!index} aria-label={`Move ${labels[id]} up`} onClick={()=>move(index,index-1)}><ArrowUp size={14}/></button>
   <button type="button" disabled={index===items.length-1} aria-label={`Move ${labels[id]} down`} onClick={()=>move(index,index+1)}><ArrowDown size={14}/></button>
  </li>)}
 </ul>;
}

export default function GalleryOrderSettings({order,branches,types,api,onChanged}){
 const [draft,setDraft]=useState(null),[branch,setBranch]=useState(Object.keys(branches)[0]);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const value=draft||order;
 if(!value)return null;
 const branchItems=value.branches.length?value.branches:Object.keys(branches);
 const typeItems=value.types[branch]||[];
 async function save(reset=false){
  setBusy(true);setError('');
  try{await api('/gallery/order',reset?{}:value);await onChanged();setDraft(null)}
  catch(e){setError(e.message)}
  finally{setBusy(false)}
 }
 return <section className="settingsCard"><h2>Gallery order</h2>
  <div className="galleryOrderColumns">
   <div><h3>Branches</h3><ReorderList items={branchItems} labels={branches}
    onChange={items=>setDraft({...value,branches:items})}/></div>
   <div><h3>Types</h3><select aria-label="Branch for type ordering" value={branch} onChange={e=>setBranch(e.target.value)}>
    {branchItems.map(id=><option key={id} value={id}>{branches[id]}</option>)}</select>
    <ReorderList key={branch} items={typeItems} labels={types}
     onChange={items=>setDraft({...value,types:{...value.types,[branch]:items}})}/></div>
  </div>
  <button disabled={busy||!draft} onClick={()=>save()}>Apply order</button>{' '}
  <button disabled={busy} onClick={()=>save(true)}><RotateCcw size={14}/> Reset order</button>
  {error&&<p role="alert">{error}</p>}
 </section>;
}
