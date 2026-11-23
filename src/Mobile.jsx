import {apiFetch} from './api.js';
import {orderedCodes} from './galleryOrder.js';
import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import useEmblaCarousel from 'embla-carousel-react';
import {DndContext,DragOverlay,KeyboardSensor,MouseSensor,TouchSensor,useDraggable,useDroppable,useSensor,useSensors} from '@dnd-kit/core';
import {Search,ClipboardCopy,Check,Trash2,TriangleAlert,X,ArrowDown,ArrowUp,ChevronDown,ChevronRight} from 'lucide-react';
import './mobile.css';

const branches={af:'Air',ar:'Army',de:'Defense',ex:'Expedition',hf:'Space',mi:'Missiles',nf:'Naval'};
const defaultBranchIds=Object.keys(branches);
const imageUrl=item=>`/api/image/${item.id}/thumb?rev=${item.render_key||''}`;
const hotKey=hot=>hot?JSON.stringify([hot.id,hot.items.map(item=>[item.id,item.missing])]):'';
const packageSignature=stage=>JSON.stringify([stage.hot&&[stage.hot.id,stage.hot.items.map(i=>i.id)],stage.reserve.map(p=>[p.id,p.items.map(i=>i.id)])]);
async function api(path,body){const response=await apiFetch('/api'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});if(!response.ok)throw Error((await response.json().catch(()=>({}))).error||`Request failed (${response.status})`);return response.json()}

function PackageImages({items}){return <span className="mobilePackageImages" aria-hidden="true">{items.slice(0,3).map((item,index)=><img key={`${item.id}-${index}`} src={imageUrl(item)} alt=""/>)}</span>}

function HotCard({item,packageId,offline,pending,onTap}){
 const {attributes,listeners,setNodeRef,isDragging}=useDraggable({id:`hot:${packageId}:${item.id}`,data:{source:'hot',packageId},disabled:offline});
 return <button ref={setNodeRef} {...attributes} {...listeners} className={`mobileHotCard ${pending?'removePending':''} ${isDragging?'mobileDragging':''}`} disabled={offline} aria-label={pending?`Tap again to remove ${item.relpath}`:`Select ${item.relpath} for removal; hold to move package to Reserve`} onClick={()=>onTap(item.id)}><img src={imageUrl(item)} alt=""/>{pending?<Trash2 className="mobileTrash" size={19}/>:null}{item.missing?<TriangleAlert className="mobileWarning" size={16}/>:null}</button>
}

function ReserveDeck({pack,index,offline,onOpen}){
 const {attributes,listeners,setNodeRef,isDragging}=useDraggable({id:`reserve:${pack.id}`,data:{source:'reserve',packageId:pack.id},disabled:offline});
 return <button ref={setNodeRef} {...attributes} {...listeners} className={`mobileDeck ${isDragging?'mobileDragging':''}`} aria-label={`Reserve package ${index+1}, ${pack.items.length} crea; tap to preview or hold to move to Hot`} onClick={()=>onOpen(pack.id)}><PackageImages items={pack.items}/><span className="mobileDeckCount">{index+1} · {pack.items.length}</span>{pack.needs_review||pack.missing_count?<TriangleAlert className="mobileDeckWarning" size={14}/>:null}</button>
}

function HotDrop({active,over,children}){
 const {setNodeRef}=useDroppable({id:'hot-drop',disabled:active?.source!=='reserve'});
 return <section ref={setNodeRef} className={`mobileHot ${active?.source==='reserve'?'mobileDropReady':''} ${over==='hot-drop'?'mobileDropOver':''}`} aria-label="Hot Staging">{children}</section>
}

function ReserveDrop({active,over,children}){
 const {setNodeRef}=useDroppable({id:'reserve-drop',disabled:active?.source!=='hot'});
 return <section ref={setNodeRef} className={`mobileReserve ${active?.source==='hot'?'mobileDropReady':''} ${over==='reserve-drop'?'mobileDropOver':''}`} aria-label="Reserve Staging">{children}</section>
}

function BranchSlide({branchId,typeOrder,assets,hot,full,offline,query,type,creator,onToggle}){
 const [collapsed,setCollapsed]=useState({});
 const groups=useMemo(()=>{
  const result={};
  for(const asset of assets){
   if(asset.branch!==branchId||(type!=='all'&&asset.type!==type)||(creator!=='all'&&asset.creator!==creator)||
      (query&&!`${asset.relpath} ${asset.type} ${asset.bp??''}`.toLowerCase().includes(query.toLowerCase())))continue;
   (result[asset.type]??=[]).push(asset);
  }
  return orderedCodes(Object.keys(result),typeOrder).map(key=>[key,result[key]]);
 },[assets,branchId,query,type,creator,typeOrder]);
 const selected=new Set(hot?.items.map(i=>i.id)||[]);
 return <div className="mobileBranchSlide" aria-label={`${branches[branchId]} crea`}><div className="mobileBranchScroll">{groups.map(([code,items])=><section className="mobileTypeSection" key={code}><button className="mobileTypeHead" aria-expanded={!collapsed[code]} onClick={()=>setCollapsed(prev=>({...prev,[code]:!prev[code]}))}>{collapsed[code]?<ChevronRight size={17}/>:<ChevronDown size={17}/>}<strong>{code.toUpperCase()}</strong><span>{items.length}</span></button>{!collapsed[code]&&<div className="mobileTypeGrid">{items.map(a=><button key={a.id} className={`mobileCrea ${selected.has(a.id)?'mobileSelected':full?'mobileFull':''}`} disabled={offline||(full&&!selected.has(a.id))} aria-label={selected.has(a.id)?`Remove ${a.relpath} from Hot`:`Add ${a.relpath} to Hot`} onClick={()=>onToggle(a.id)}><img loading="lazy" src={imageUrl(a)} alt=""/></button>)}</div>}</section>)}{!groups.length&&<p className="mobileNoMatch">No crea match.</p>}</div></div>
}

export default function Mobile(){
 const [paired,setPaired]=useState(null),[code,setCode]=useState(''),[error,setError]=useState(''),[offline,setOffline]=useState(false);
 const [assets,setAssets]=useState([]),[creators,setCreators]=useState([]),[stage,setStage]=useState({hot:null,reserve:[]});
 const [galleryOrder,setGalleryOrder]=useState(null);
 const branchIds=galleryOrder?.branches||defaultBranchIds;
 const [branch,setBranch]=useState('af'),[type,setType]=useState('all'),[creator,setCreator]=useState('all'),[query,setQuery]=useState(''),[reserveOpen,setReserveOpen]=useState(null),[submission,setSubmission]=useState(''),[editing,setEditing]=useState(false),[pendingRemove,setPendingRemove]=useState(null);
 const [copyBusy,setCopyBusy]=useState(false),[copiedPackage,setCopiedPackage]=useState(null),[activeDrag,setActiveDrag]=useState(null),[overDrop,setOverDrop]=useState(null);
 const [emblaRef,emblaApi]=useEmblaCarousel({axis:'x',align:'start',containScroll:'trimSnaps',watchDrag:true});
 const sensors=useSensors(useSensor(TouchSensor,{activationConstraint:{delay:250,tolerance:6}}),useSensor(MouseSensor,{activationConstraint:{distance:8}}),useSensor(KeyboardSensor));
 const stageRef=useRef(stage),offlineRef=useRef(offline),dragRef=useRef(null),suppressTapUntil=useRef(0);
 const signature=packageSignature(stage);
 const currentHotKey=hotKey(stage.hot);
 const readyToConfirm=!!copiedPackage&&!offline&&copiedPackage.key===currentHotKey;
 stageRef.current=stage;offlineRef.current=offline;
 const itemKey=stage.hot?.items.map(item=>item.id).join(',')||'';
 useEffect(()=>setPendingRemove(null),[itemKey]);
 useEffect(()=>{if(offline||(copiedPackage&&copiedPackage.key!==currentHotKey))setCopiedPackage(null)},[offline,currentHotKey,copiedPackage]);
 useEffect(()=>{if(activeDrag&&(offline||activeDrag.signature!==signature)){dragRef.current=null;setActiveDrag(null);setOverDrop(null)}},[activeDrag,offline,signature]);
 useEffect(()=>{const cancel=e=>{if(!e.target.closest?.('.mobileHotCard'))setPendingRemove(null)};document.addEventListener('pointerdown',cancel);return()=>document.removeEventListener('pointerdown',cancel)},[]);
 const selectBranch=useCallback(index=>{setBranch(branchIds[index]);setType('all')},[branchIds]);
 useEffect(()=>{if(!emblaApi)return;const onSelect=()=>selectBranch(emblaApi.selectedScrollSnap());emblaApi.on('select',onSelect);return()=>emblaApi.off('select',onSelect)},[emblaApi,selectBranch]);
 useEffect(()=>{if(emblaApi){emblaApi.reInit();const index=branchIds.indexOf(branch);if(index>=0)emblaApi.scrollTo(index,true)}},[branchIds,emblaApi]);
 function tapHot(id){if(Date.now()<suppressTapUntil.current)return;if(pendingRemove===id){setPendingRemove(null);setCopiedPackage(null);action(`/staging/hot/items/${id}/remove`)}else setPendingRemove(id)}
 async function refresh(){try{const session=await api('/mobile/session');setPaired(session.paired);if(!session.paired)return;const [a,s,t]=await Promise.all([api('/assets'),api('/state'),api('/staging')]);setAssets(a);setCreators(s.creators.filter(c=>c.enabled!==0));setGalleryOrder(previous=>JSON.stringify(previous)===JSON.stringify(s.gallery_order)?previous:s.gallery_order);setStage(t);setOffline(false)}catch(e){setOffline(true);setError(e.message)}}
 useEffect(()=>{if('serviceWorker' in navigator)navigator.serviceWorker.register('/mobile-sw.js').catch(()=>{});refresh();const timer=setInterval(refresh,2000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{if(!editing)setSubmission(stage.hot?.submission||'')},[stage.hot?.id,stage.hot?.submission,editing]);
 async function pair(e){e.preventDefault();try{await api('/mobile/pair',{code});setCode('');setError('');await refresh()}catch(e){setError(e.message)}}
 async function action(path,body={}){if(offlineRef.current)return;try{setError('');await api(path,body);await refresh()}catch(e){setError(e.message);await refresh()}}
 async function toggleHot(id){setCopiedPackage(null);if(stage.hot?.items.some(i=>i.id===id))return action(`/staging/hot/items/${id}/remove`);if((stage.hot?.items.length||0)>=10)return;return action('/staging/hot/items',{asset_ids:[id]})}
 async function sendClipboard(){if(!stage.hot||offline||copyBusy)return;const packageId=stage.hot.id,assetIds=stage.hot.items.map(item=>item.id),key=hotKey(stage.hot);setCopyBusy(true);setCopiedPackage(null);setError('');try{const {id}=await api('/mobile/clipboard',{package_id:packageId});for(let attempt=0;attempt<40;attempt++){await new Promise(resolve=>setTimeout(resolve,500));const result=await api(`/mobile/clipboard/${id}`);if(result.status==='done'){if(result.count!==assetIds.length)throw Error('Clipboard count did not match Hot');const latest=await api('/staging');setStage(latest);if(offlineRef.current||hotKey(latest.hot)!==key)throw Error('Hot package changed; copy it again');setCopiedPackage({key,packageId,assetIds});setError(`${result.count} crea copied to the Framework clipboard. Paste in Discord, then tap the check button to mark them used.`);return}if(result.status==='error')throw Error(result.error||'Clipboard failed')}throw Error('Desktop clipboard did not respond')}catch(e){setError(`${e.message}. Use the Dolphin folder instead.`)}finally{setCopyBusy(false)}}
 async function confirmSent(){if(!readyToConfirm||copyBusy||offlineRef.current)return;setCopyBusy(true);setError('');try{await api('/staging/hot/confirm',{package_id:copiedPackage.packageId,asset_ids:copiedPackage.assetIds});setCopiedPackage(null);await refresh()}catch(e){setCopiedPackage(null);setError(e.message);await refresh()}finally{setCopyBusy(false)}}
 function dragStart({active}){const {source,packageId}=active.data.current||{};const current=stageRef.current;const pack=source==='hot'&&current.hot?.id===packageId?current.hot:source==='reserve'?current.reserve.find(p=>p.id===packageId):null;if(!pack||offlineRef.current)return;const drag={source,packageId,items:pack.items,signature:packageSignature(current)};dragRef.current=drag;setActiveDrag(drag);setPendingRemove(null);suppressTapUntil.current=Date.now()+600}
 function dragOver({over}){setOverDrop(over?.id||null)}
 function dragCancel(){dragRef.current=null;setActiveDrag(null);setOverDrop(null);suppressTapUntil.current=Date.now()+350}
 function dragEnd({over}){const drag=dragRef.current;dragCancel();if(!drag||offlineRef.current||drag.signature!==packageSignature(stageRef.current))return;
  if(drag.source==='hot'&&over?.id==='reserve-drop'&&stageRef.current.hot?.id===drag.packageId)action('/staging/hot/reserve',{package_id:drag.packageId});
  if(drag.source==='reserve'&&over?.id==='hot-drop'&&stageRef.current.reserve.some(p=>p.id===drag.packageId))action(`/staging/reserve/${drag.packageId}/activate`);
 }
 const types=useMemo(()=>orderedCodes(new Set(assets.filter(a=>a.branch===branch).map(a=>a.type)),galleryOrder?.types[branch]),[assets,branch,galleryOrder]);
 const hot=stage.hot,full=(hot?.items.length||0)>=10;
 if(paired===null)return <div className="mobileState">{offline?<>Framework unavailable<button onClick={refresh}>Retry</button></>:'Connecting…'}</div>;
 if(!paired)return <div className="mobilePair"><img src="/icons/bird-mark.png" alt=""/><h1>Clan Hub</h1><p>Enter the pairing code from desktop Settings.</p><form onSubmit={pair}><input inputMode="numeric" pattern="[0-9]{6}" maxLength="6" value={code} onChange={e=>setCode(e.target.value)} aria-label="Pairing code"/><button>Connect</button></form>{error&&<p role="alert">{error}</p>}</div>;
 return <DndContext sensors={sensors} onDragStart={dragStart} onDragOver={dragOver} onDragEnd={dragEnd} onDragCancel={dragCancel}><div className="mobileApp"><div className="mobileTop"><img src="/icons/bird-mark.png" alt=""/><strong>CLAN HUB</strong>{offline&&<span role="status">Disconnected</span>}</div>
  <HotDrop active={activeDrag} over={overDrop}><div className="mobileHotRow">{hot?.items.map(i=><HotCard item={i} packageId={hot.id} key={i.id} offline={offline} pending={pendingRemove===i.id} onTap={tapHot}/>)}{!hot&&<span className="mobileHint">Tap crea below to stage them</span>}</div><span className="mobileCount">{hot?.items.length||0}/10</span>{hot&&<div className="mobileHotTools"><textarea aria-label="Package submission" placeholder="Submission…" value={submission} onFocus={()=>setEditing(true)} onChange={e=>setSubmission(e.target.value)} onBlur={()=>{setEditing(false);if(submission!==hot.submission)action(`/staging/packages/${hot.id}/submission`,{submission})}}/><button disabled={offline||copyBusy||!!hot.missing_count} title={readyToConfirm?'Mark copied Hot crea as used':'Send all Hot crea to Framework clipboard'} aria-label={readyToConfirm?'Mark copied Hot crea as used':'Send all Hot crea to Framework clipboard'} onClick={readyToConfirm?confirmSent:sendClipboard}>{readyToConfirm?<Check size={19}/>:<ClipboardCopy size={19}/>}</button><button disabled={offline} title="Move to Reserve" aria-label="Move to Reserve" onClick={async()=>{try{if(submission!==hot.submission)await api(`/staging/packages/${hot.id}/submission`,{submission});await action('/staging/hot/reserve',{package_id:hot.id})}catch(e){setError(e.message)}}}><ArrowDown size={19}/></button></div>}</HotDrop>
  {error&&<div className="mobileError" role="alert">{error}</div>}
  <main className="mobileGallery" ref={emblaRef}><div className="mobileBranchTrack">{branchIds.map(id=><BranchSlide key={id} branchId={id} typeOrder={galleryOrder?.types[id]} assets={assets} hot={hot} full={full} offline={offline} query={query} type={type} creator={creator} onToggle={toggleHot}/>)}</div></main>
  <div className="mobileBottom"><ReserveDrop active={activeDrag} over={overDrop}>{stage.reserve.map((p,n)=><ReserveDeck key={p.id} pack={p} index={n} offline={offline} onOpen={id=>{if(Date.now()>=suppressTapUntil.current)setReserveOpen(id)}}/>)}{!stage.reserve.length&&<span className="mobileHint">Reserve</span>}</ReserveDrop><div className="mobileFilters"><label><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search" aria-label="Search crea"/></label><select aria-label="Branch" value={branch} onChange={e=>emblaApi?.scrollTo(branchIds.indexOf(e.target.value))}>{branchIds.map(id=><option value={id} key={id}>{branches[id]}</option>)}</select><select aria-label="Type" value={type} onChange={e=>setType(e.target.value)}><option value="all">All types</option>{types.map(t=><option key={t} value={t}>{t.toUpperCase()}</option>)}</select><select aria-label="Creator" value={creator} onChange={e=>setCreator(e.target.value)}><option value="all">All creators</option>{creators.map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select></div></div>
  {reserveOpen&&(()=>{const p=stage.reserve.find(x=>x.id===reserveOpen);return p?<div className="mobileOverlay" onClick={()=>setReserveOpen(null)}><div className="mobilePreview" onClick={e=>e.stopPropagation()}><button className="mobileClose" aria-label="Close" onClick={()=>setReserveOpen(null)}><X/></button><div className="mobilePreviewGrid">{p.items.map(i=><div key={i.id}><img src={imageUrl(i)} alt={i.relpath}/>{i.missing?<TriangleAlert size={16}/>:null}</div>)}</div><p>{p.submission}</p>{p.needs_review||p.missing_count?<p role="alert">This package needs review on desktop.</p>:null}<button disabled={offline} onClick={()=>{action(`/staging/reserve/${p.id}/activate`);setReserveOpen(null)}}><ArrowUp size={17}/> Activate in Hot</button></div></div>:null})()}
 </div><DragOverlay dropAnimation={{duration:180,easing:'ease-out'}}>{activeDrag?<div className="mobileDragPreview"><PackageImages items={activeDrag.items}/><span>{activeDrag.items.length} crea</span></div>:null}</DragOverlay></DndContext>
}
