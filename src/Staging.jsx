import {apiFetch} from './api.js';
import React,{useEffect,useState} from 'react';
import {ArrowUpFromLine,Check,Clipboard,ClipboardCopy,FolderOpen,RotateCcw,Send,Trash2,TriangleAlert,X} from 'lucide-react';

async function post(path,body={}){const r=await apiFetch('/api'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'Action failed');return v}
export function HotStage({snapshot,onChanged}){
 const hot=snapshot.hot, reserve=snapshot.reserve||[];
 const [submission,setSubmission]=useState(''),[copied,setCopied]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[pendingRemove,setPendingRemove]=useState(null);
 const itemKey=hot?.items.map(item=>item.id).join(',')||'';
 useEffect(()=>{setPendingRemove(null);setCopied(0)},[itemKey]);
 useEffect(()=>{const cancel=e=>{if(!e.target.closest?.('.hotItem'))setPendingRemove(null)};document.addEventListener('pointerdown',cancel);return()=>document.removeEventListener('pointerdown',cancel)},[]);
 function tapHot(id){if(pendingRemove===id){setPendingRemove(null);run(`/staging/hot/items/${id}/remove`)}else setPendingRemove(id)}
 useEffect(()=>{setSubmission(hot?.submission||'');setCopied(0)},[hot?.id]);
 useEffect(()=>{if(!hot||submission===hot.submission)return;const timer=setTimeout(()=>post(`/staging/packages/${hot.id}/submission`,{submission}).then(onChanged).catch(e=>setError(e.message)),450);return()=>clearTimeout(timer)},[submission,hot?.id,hot?.submission]);
 async function run(path,body={}){setBusy(true);setError('');try{if(hot&&submission!==hot.submission)await post(`/staging/packages/${hot.id}/submission`,{submission});await post(path,body);setCopied(0);await onChanged()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function copyAll(){if(!hot||hot.missing_count)return;setBusy(true);setError('');try{if(!window.chDesktop?.copyHotPackage)throw Error('Package clipboard requires the desktop app');if(submission!==hot.submission)await post(`/staging/packages/${hot.id}/submission`,{submission});const result=await window.chDesktop.copyHotPackage(hot.id);setCopied(result.count);setError(`${result.count} crea copied as files. Paste into Discord, then confirm after posting.`)}catch(e){setError(`Clipboard failed: ${e.message}. Use the Dolphin folder instead.`)}finally{setBusy(false)}}
 async function copyText(){try{await (window.chDesktop?.copyText?window.chDesktop.copyText(submission):navigator.clipboard.writeText(submission));setError('Submission text copied. Paste it into Discord.')}catch(e){setError(e.message)}}
 async function openInFiles(){if(!hot||!window.chDesktop)return;setBusy(true);setError('');try{await window.chDesktop.openPackageInFiles(hot.id);setError('In Files, select the images and drag them into Discord. Confirm here after posting.')}catch(e){setError(e.message)}finally{setBusy(false)}}
 function dragHot(e){if(!hot)return;setPendingRemove(null);e.dataTransfer.setData('application/x-ch-package',hot.id);e.dataTransfer.effectAllowed='move'}
 function dropHot(e){e.preventDefault();const pid=e.dataTransfer.getData('application/x-ch-package');if(reserve.some(p=>p.id===pid))run(`/staging/reserve/${pid}/activate`)}
 return <section className="hotStage" aria-label="Hot Staging" onDragOver={e=>e.preventDefault()} onDrop={dropHot}>
  {error&&<div className="stageError" role="status">{error}</div>}
  {hot?<><div className="hotStageRow"><div className="hotItems">{hot.items.map(i=><div className={`hotItem ${i.missing?'missing':''} ${pendingRemove===i.id?'removePending':''}`} key={i.id} draggable role="button" tabIndex={0} aria-label={pendingRemove===i.id?`Tap again to remove ${i.relpath}`:`Select ${i.relpath} for removal`} onClick={()=>tapHot(i.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tapHot(i.id)}}} onDragStart={dragHot}><img src={`/api/image/${i.id}/thumb?rev=${i.render_key||''}`} alt=""/>{pendingRemove===i.id&&<span className="trashBadge" aria-hidden="true"><Trash2 size={19}/></span>}{Boolean(i.missing)&&<span className="missingBadge" role="img" aria-label="Missing crea; remove and replace" title="Missing crea; remove and replace"><TriangleAlert size={15}/></span>}</div>)}</div><div className="hotControls"><div className="submissionBox"><textarea aria-label="Package submission" placeholder="Submission for Discord…" value={submission} onChange={e=>setSubmission(e.target.value)}/><button className="copySubmission" title="Copy submission text" aria-label="Copy submission text" onClick={copyText}><Clipboard size={16}/></button></div><div className="hotActions"><div className="sendOutbox" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();e.stopPropagation();if(e.dataTransfer.getData('application/x-ch-package')===hot.id)copyAll()}}>{copied<hot.items.length?<button title="Send all staged crea to desktop clipboard" aria-label="Send all staged crea to desktop clipboard" disabled={busy||!!hot.missing_count} onClick={copyAll}><ClipboardCopy size={19}/></button>:<button title="Confirm sent" aria-label="Confirm sent" disabled={busy} onClick={()=>run('/staging/hot/confirm')}><Check size={19}/></button>}</div><button title="Move package to Reserve" aria-label="Move package to Reserve" disabled={busy} onClick={()=>run('/staging/hot/reserve')}><ArrowUpFromLine size={19}/></button></div>{window.chDesktop&&<button className="openInFiles" title="Open Hot package in Files to drag into Discord" aria-label="Open Hot package in Files" disabled={busy||!!hot.missing_count} onClick={openInFiles}><FolderOpen size={18}/></button>}</div></div>{copied>0&&<small className="copyStatus">{copied} crea copied as files. Paste into Discord; confirm only after posting. <button disabled={busy} onClick={copyAll}>Copy again</button></small>}</>:<div className="hotEmpty">Click gallery images to fill Hot Staging.</div>}
 </section>
}

export function ReserveStage({snapshot,onChanged,used,usedOpen,onCloseUsed}){
 const hot=snapshot.hot, reserve=snapshot.reserve||[];
 const [preview,setPreview]=useState(null),[usedIds,setUsedIds]=useState(new Set()),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [transfer,setTransfer]=useState(null);
 async function exportUsed(){
  try{
   const response=await apiFetch('/api/used/export');
   if(!response.ok)throw Error('Unable to export Used Crea');
   const url=URL.createObjectURL(await response.blob());
   const link=document.createElement('a');
   link.href=url;link.download='used-crea.json';link.click();
   setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){setTransfer({error:e.message})}
 }
 async function importUsed(event){
  const file=event.target.files[0];event.target.value='';
  if(!file)return;
  setBusy(true);setTransfer(null);
  try{
   const result=await post('/used/import',JSON.parse(await file.text()));
   setTransfer(result);await onChanged();
  }catch(e){setTransfer({error:e.message})}
  finally{setBusy(false)}
 }
 const active=reserve.find(p=>p.id===preview);
 async function run(path,body={}){setBusy(true);setError('');try{await post(path,body);await onChanged();return true}catch(e){setError(e.message);return false}finally{setBusy(false)}}
 function dragDeck(e,id){e.dataTransfer.setData('application/x-ch-package',id);e.dataTransfer.effectAllowed='move'}
 function dropReserve(e){e.preventDefault();if(e.dataTransfer.getData('application/x-ch-package')===hot?.id){
  const submission=e.dataTransfer.types.includes('application/x-ch-submission')?e.dataTransfer.getData('application/x-ch-submission'):undefined;
  const selected=e.dataTransfer.getData('application/x-ch-mentions');
  let mentions;
  try{mentions=selected?JSON.parse(selected):undefined}catch{return}
  run('/staging/hot/reserve',{package_id:hot.id,submission,mentions});
 }}
 return <section className="reserveShelf" aria-label="Reserve Staging" onDragOver={e=>e.preventDefault()} onDrop={dropReserve}>
  {error&&<div className="stageError" role="status">{error}</div>}
  <div className="deckScroll"><div className="deckGrid">{reserve.map((p,index)=><button className="deck" key={p.id} draggable onDragStart={e=>dragDeck(e,p.id)} onClick={()=>setPreview(p.id)}><div className="deckStack">{p.items.slice(0,3).map((i,n)=><img key={i.id} className={`deckLayer layer${n} ${i.missing?'missingLayer':''}`} src={`/api/image/${i.id}/thumb?rev=${i.render_key||''}`}/>)}</div><b>{index+1}</b><span>{p.items.length} crea</span>{(p.needs_review||p.missing_count)?<TriangleAlert className="deckWarning" size={15}/>:null}</button>)}</div>{!reserve.length&&<div className="reserveEmpty">Drag the Hot package here or use its Reserve control.</div>}</div>
  {active&&<div className="stageOverlay" onClick={()=>setPreview(null)}><div className="stagePanel" onClick={e=>e.stopPropagation()}><div className="stagePanelHead"><strong>Reserve package {reserve.indexOf(active)+1}</strong><button title="Close preview" aria-label="Close preview" onClick={()=>setPreview(null)}><X size={18}/></button></div><div className="previewGrid">{active.items.map(i=><div key={i.id} className={`previewItem ${i.missing?'missing':''}`}><img src={`/api/image/${i.id}/thumb?rev=${i.render_key||''}`} alt=""/><span>{i.type.toUpperCase()} · {i.creator}{i.bp!=null?` · ${i.bp} BP`:''}</span>{Boolean(i.missing)&&<span className="missingBadge" role="img" aria-label="Missing crea; activate and replace" title="Missing crea; activate and replace"><TriangleAlert size={15}/></span>}</div>)}</div><p className="submissionPreview">{active.submission||'No submission text'}</p>{active.needs_review>0&&<button onClick={()=>run(`/staging/packages/${active.id}/acknowledge`)}><TriangleAlert size={16}/> Acknowledge BP review</button>}<button disabled={busy} onClick={async()=>{if(await run(`/staging/reserve/${active.id}/activate`))setPreview(null)}}><Send size={16}/> Activate package</button></div></div>}
  {usedOpen&&<div className="stageOverlay" onClick={()=>onCloseUsed()}><div className="stagePanel" onClick={e=>e.stopPropagation()}><div className="stagePanelHead"><strong>Used Crea</strong><button aria-label="Close Used Crea" onClick={()=>onCloseUsed()}><X size={18}/></button></div><button disabled={!snapshot.can_undo||busy} onClick={()=>run('/staging/deployments/undo')}><RotateCcw size={15}/> Undo last deployment</button><button disabled={!used?.length} onClick={()=>run('/used/restore',{all:true})}><RotateCcw size={15}/> Restore all</button><button disabled={busy} onClick={exportUsed}>Export Used</button><label>Import Used <input type="file" accept=".json,application/json" disabled={busy} onChange={importUsed}/></label>{transfer&&<div role="status">{transfer.error||`${transfer.marked} marked Used · ${transfer.unchanged} already Used`}{transfer.missing?.length>0&&<p>Missing: {transfer.missing.join(', ')}</p>}{transfer.ambiguous?.length>0&&<p>Ambiguous: {transfer.ambiguous.join(', ')}</p>}</div>}<div className="usedGrid">{used?.map(a=><label key={a.id}><input type="checkbox" checked={usedIds.has(a.id)} onChange={()=>setUsedIds(prev=>{const next=new Set(prev);next.has(a.id)?next.delete(a.id):next.add(a.id);return next})}/><img src={`/api/image/${a.id}/thumb?rev=${a.render_key||''}`}/><span>{a.type.toUpperCase()} · {a.creator}</span><button title="Restore crea" aria-label={`Restore ${a.relpath}`} onClick={e=>{e.preventDefault();run('/used/restore',{asset_ids:[a.id]})}}><RotateCcw size={15}/></button></label>)}</div><button disabled={!usedIds.size} onClick={async()=>{await run('/used/restore',{asset_ids:[...usedIds]});setUsedIds(new Set())}}><RotateCcw size={15}/> Restore selected</button></div></div>}
 </section>
}
