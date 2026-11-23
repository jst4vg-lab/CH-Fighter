import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {createPortal} from 'react-dom';
import {Search, RefreshCw, ChevronDown, ChevronRight, SlidersHorizontal, AlertTriangle, Archive, Menu, Minus, Plus, ArrowLeft, Info} from 'lucide-react';
import {ReserveStage} from './Staging.jsx';
import './style.css';
import Mobile from './Mobile.jsx';
import WorkspaceShell from './WorkspaceShell.jsx';
import DiscordComposer from './DiscordComposer.jsx';
import GalleryOrderSettings from './GalleryOrderSettings.jsx';
import {orderedCodes} from './galleryOrder.js';
import QuickReactionsSettings from './QuickReactionsSettings.jsx';
import DiscordDestinationSettings from './DiscordDestinationSettings.jsx';

const BRANCHES={af:'Air Corps',ar:'Army',de:'Defense',ex:'Expeditionary Force',hf:'Space',mi:'Missiles',nf:'Naval'};
const TYPES={afs:'Air Force Support',avi:'Helicopter',fgt:'Fighter',stk:'Strike Aircraft',ada:'Air Defence',art:'Artillery',asu:'Army Support',def:'Defences',fpv:'Drone',inf:'Infantry',mbt:'Tank',mob:'Mobility',frt:'Fortress',aas:'Air Assault',lan:'Orbital Drop',par:'Paratrooper',sct:'Space Combat',ses:'Space Escort',ssu:'Space Support',mis:'Missile',car:'Carrier',cbt:'Combat Ship',esc:'Escort',sub:'Submarine',tsb:'Transport',tsp:'Transport'};
async function api(path,body){const r=await fetch('/api'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}

function ColorRow({creator,save,toggle,saving}){
 const [value,setValue]=useState(creator.color||'#6B7754');
 useEffect(()=>setValue(creator.color||'#6B7754'),[creator.color]);
 return <div className="colorrow"><span className="creatorName">{creator.name}</span>{toggle&&<label className="creatorToggle"><input type="checkbox" checked={creator.enabled!==0} disabled={saving} onChange={e=>toggle(creator.name,e.target.checked)}/><span>Show</span></label>}<input aria-label={`${creator.name} color`} type="color" value={value} onChange={e=>setValue(e.target.value)}/><span className="hex">{value.toUpperCase()}</span><button disabled={saving||value.toUpperCase()===(creator.color||'').toUpperCase()} onClick={()=>save(creator.name,value)}>{creator.color?'Save':'Set color'}</button></div>
}

function MobileSettings(){
 const [config,setConfig]=useState(null),[pair,setPair]=useState(null),[message,setMessage]=useState('');
 useEffect(()=>{api('/mobile/config').then(setConfig).catch(e=>setMessage(e.message))},[]);
 async function newCode(){try{setPair(await api('/mobile/pair-code'));setMessage('')}catch(e){setMessage(e.message)}}
 async function revoke(){try{await api('/mobile/revoke',{});setPair(null);setMessage('Paired phones disconnected.')}catch(e){setMessage(e.message)}}
 return <section className="settingsCard"><h2>Mobile companion</h2><p>{config?.url?<>Open <strong>{config.url}</strong> on your iPhone through Tailscale, then add it to the Home Screen.</>:'Connect Tailscale on the Framework, enable MagicDNS and HTTPS, then restart Clan Hub.'}</p><p>Serve the local app privately with <code>tailscale serve --bg {config?.port||8765}</code>. Keep the desktop app open while using the phone.</p><button onClick={newCode}>Generate pairing code</button>{pair&&<p>Pairing code: <strong>{pair.code}</strong> (valid for five minutes)</p>}<button onClick={revoke}>Disconnect paired phones</button>{message&&<p role="status">{message}</p>}</section>
}
function DiscordConnections(){
 const [info,setInfo]=useState(null),[selection,setSelection]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [testMode,setTestMode]=useState(null);
 useEffect(()=>{api('/communications/test-mode').then(value=>setTestMode(value.enabled)).catch(e=>setError(e.message))},[]);
 async function changeTestMode(enabled){
  setBusy(true);setError('');
  try{setTestMode((await api('/communications/test-mode',{enabled})).enabled)}
  catch(e){setError(e.message)}
  finally{setBusy(false)}
 }
 const endpoint='/communications/profiles';
 useEffect(()=>{
  let active=true;
  async function refresh(){
   try{const value=await api(endpoint);if(active)setInfo(value)}
   catch(e){if(active)setError(e.message)}
  }
  refresh();
  const timer=setInterval(refresh,3000);
  return()=>{active=false;clearInterval(timer)};
 },[]);
 async function update(action,body){
  setBusy(true);setError('');
  try{setInfo(await api(endpoint+action,body));setSelection(null)}
  catch(e){setError(e.message)}
  finally{setBusy(false)}
 }
 const selected=selection??info?.active.read??'';
 return <section className="settingsCard"><h2>Discord Connections</h2>
 <label><input type="checkbox" checked={testMode===true} disabled={busy||testMode===null}
  onChange={e=>changeTestMode(e.target.checked)}/> Test mode</label>
 {info&&<div className="discordConnectionRow">
  <label>Discord profile <select value={selected} disabled={busy} onChange={e=>setSelection(e.target.value)}>
   <option value="">Disabled</option>
   {selected&&!info.profiles.some(profile=>profile.id===selected&&profile.read_enabled)&&
    <option value={selected}>Unavailable profile</option>}
   {info.profiles.filter(profile=>profile.read_enabled).map(profile=>
    <option key={profile.id} value={profile.id}>{profile.name}{profile.write_enabled?'':' (read only)'}</option>)}
  </select></label>
  <button disabled={busy||selection===null&&info.active.read===info.active.write}
   onClick={()=>update('/shared',{profile_id:selected})}>Apply profile</button>
  <button disabled={busy||!info.active.read} onClick={()=>update('/reconnect',{profile_id:info.active.read})}>Reconnect</button>
  <p>{[info.read.state?.replaceAll('_',' '),info.read.account?.name,info.read.reason].filter(Boolean).join(' · ')}</p>
  {info.write?.delivery?.channel_name&&<p>Outgoing channel: #{info.write.delivery.channel_name}</p>}
  {info.write?.delivery?.reason&&info.active.write&&<p>{info.write.delivery.reason}</p>}
 </div>}
 {(error||info?.error)&&<p role="alert">{error||info.error}</p>}
 <DiscordDestinationSettings api={api} profileId={info?.active.read}/>
 <QuickReactionsSettings api={api}/></section>
}

function LibrarySettings({onChanged}){
 const [info,setInfo]=useState(null),[path,setPath]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api('/library').then(v=>{setInfo(v);setPath(v.path)}).catch(e=>setMessage(e.message))},[]);
 async function run(endpoint,body){setBusy(true);setMessage('');try{const v=await api(endpoint,body);setInfo(v);setPath(v.path);if(endpoint==='/library/rescan')onChanged();setMessage(endpoint==='/library/rescan'?`${v.scanned} files scanned`:'Library location saved')}catch(e){setMessage(e.message)}finally{setBusy(false)}}
 return <section className="settingsCard librarySettings"><div className="settingsTitle"><h2>Crea Library</h2></div><div className="librarySettingsBody"><label htmlFor="libraryPath">Library Location</label><div className="libraryPathRow"><input id="libraryPath" value={path} onChange={e=>setPath(e.target.value)} spellCheck="false"/><button disabled={!window.chDesktop?.chooseCreaLibrary||busy} onClick={async()=>{const selected=await window.chDesktop.chooseCreaLibrary();if(selected)setPath(selected)}}>Browse</button><button disabled={busy||!path} onClick={()=>run('/library/apply',{path})}>Apply</button></div><div className="libraryStatus"><span>{info?.available?'Available':'Library Unavailable'}</span><span>{info?.indexed_count??0} indexed assets</span><button disabled={busy} onClick={()=>run('/library/rescan',{})}>Rescan Library</button></div>{message&&<p role="status">{message}</p>}</div></section>
}

function App({hotDock,reply,onClearReply,mentionMembers,teams,teamColors}){
 const [state,setState]=useState({creators:[],counts:{},busy:false}),[assets,setAssets]=useState([]),[review,setReview]=useState([]),[stage,setStage]=useState({hot:null,reserve:[],used_count:0}),[used,setUsed]=useState([]);
 const [branch,setBranch]=useState('af'),[query,setQuery]=useState(''),[creator,setCreator]=useState('all'),[selected,setSelected]=useState(null),[collapsed,setCollapsed]=useState({});
 const [error,setError]=useState(''),[saving,setSaving]=useState(false),[route,setRoute]=useState(location.pathname==='/settings'?'settings':'gallery');
 const [menuOpen,setMenuOpen]=useState(false),[usedOpen,setUsedOpen]=useState(false),[zoom,setZoom]=useState(()=>Number(localStorage.getItem('ch-ui-zoom'))||1);
 const menuRef=useRef(null);
 useEffect(()=>{if(!error)return;const timer=setTimeout(()=>setError(''),4000);return()=>clearTimeout(timer)},[error]);
 useEffect(()=>{const onPop=()=>setRoute(location.pathname==='/settings'?'settings':'gallery');addEventListener('popstate',onPop);return()=>removeEventListener('popstate',onPop)},[]);
 function navigate(to){history.pushState({},'',to==='settings'?'/settings':'/');setRoute(to);setSelected(null);setMenuOpen(false)}
 function changeZoom(next){setZoom(Math.min(1.5,Math.max(.7,Math.round(next*10)/10)))}
 useEffect(()=>{document.documentElement.style.zoom=String(zoom);localStorage.setItem('ch-ui-zoom',String(zoom))},[zoom]);
 useEffect(()=>{function close(e){if(!menuRef.current?.contains(e.target))setMenuOpen(false)}function key(e){if(e.key==='Escape')setMenuOpen(false);if((e.ctrlKey||e.metaKey)&&['+','=','-','0'].includes(e.key)){e.preventDefault();changeZoom(e.key==='0'?1:zoom+(e.key==='-'?-.1:.1))}}document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key)}},[zoom]);
 async function refresh(){try{const [s,a,r,t,u]=await Promise.all([api('/state'),api('/assets'),api('/assets?status=review'),api('/staging'),api('/assets?status=used')]);setState(s);setAssets(a);setReview(r);setStage(t);setUsed(u);setSelected(prev=>prev&&!prev.review?a.find(x=>x.id===prev.id)||prev:prev)}catch(e){setError(e.message)}}
 useEffect(()=>{refresh();const id=setInterval(refresh,2000);return()=>clearInterval(id)},[]);
 async function action(path,body){setSaving(true);setError('');try{await api(path,body);await refresh();return true}catch(e){setError(e.message);return false}finally{setSaving(false)}}
 async function toggleHot(id){if(stage.hot?.items.some(i=>i.id===id))return action(`/staging/hot/items/${id}/remove`,{});if((stage.hot?.items.length||0)>=10)return;return action('/staging/hot/items',{asset_ids:[id]})}
 const saveColor=(name,color)=>action(`/creators/${name}/color`,{color});
 const toggleCreator=(name,enabled)=>action(`/creators/${name}/enabled`,{enabled});
 useEffect(()=>{if(creator!=='all'&&!state.creators.some(c=>c.name===creator&&c.enabled!==0))setCreator('all')},[creator,state.creators]);
 const missing=state.creators.filter(c=>c.enabled!==0&&!c.color);
 const shown=useMemo(()=>assets.filter(a=>a.branch===branch&&(creator==='all'||a.creator===creator)&&(!query||`${a.relpath} ${TYPES[a.type]} ${a.bp??''}`.toLowerCase().includes(query.toLowerCase()))),[assets,branch,creator,query]);
 const hotFull=(stage.hot?.items.length||0)>=10;
 const groups=shown.reduce((acc,a)=>{(acc[a.type]??=[]).push(a);return acc},{});
 return <><div className={`app ${selected&&!selected.review?'assetDetailsOpen':''}`}>
  <header><div className="headerLeft"><div className="appMenuWrap" ref={menuRef}><button className={`settingsIcon ${menuOpen?'navActive':''}`} aria-label="Open app menu" aria-expanded={menuOpen} aria-controls="appMenu" title="Menu" onClick={()=>setMenuOpen(!menuOpen)}><Menu size={21}/></button>{menuOpen&&<div className="appMenu" id="appMenu"><button onClick={()=>navigate('settings')}><SlidersHorizontal size={16}/> Settings</button><button onClick={()=>{setMenuOpen(false);navigate('gallery');setSelected({review:true})}}><AlertTriangle size={16}/> Review <span>{review.length}</span></button><button disabled={saving||state.busy} onClick={()=>{setMenuOpen(false);action('/import',{})}}><RefreshCw size={16}/> Scan collection</button><button onClick={()=>{setMenuOpen(false);navigate('gallery');setUsedOpen(true)}}><Archive size={16}/> Used Crea <span>{stage.used_count||0}</span></button><div className="menuZoom" aria-label="App zoom"><span>Zoom</span><button aria-label="Zoom out" disabled={zoom<=.7} onClick={()=>changeZoom(zoom-.1)}><Minus size={15}/></button><button className="zoomValue" aria-label="Reset zoom" onClick={()=>changeZoom(1)}>{Math.round(zoom*100)}%</button><button aria-label="Zoom in" disabled={zoom>=1.5} onClick={()=>changeZoom(zoom+.1)}><Plus size={15}/></button></div></div>}</div><button className="brand" onClick={()=>navigate('gallery')}><img src="/icons/bird-mark.png" alt=""/><span><strong>CLAN HUB</strong><small>CREA MANAGER</small></span></button></div><div className="headerRight"><span className="count">{assets.length} READY · {state.counts.pending||0} PENDING</span></div></header>
  {error&&<div className="error">{error}</div>}
  {route==='settings'?<main className="settingsPage"><button className="back" onClick={()=>navigate('gallery')}><ArrowLeft size={16}/> Gallery</button><h1>Settings</h1><LibrarySettings onChanged={refresh}/><DiscordConnections/><GalleryOrderSettings order={state.gallery_order} branches={BRANCHES} types={TYPES} api={api} onChanged={refresh}/><section className="settingsCard"><div className="settingsTitle"><h2>Creator colors</h2></div><div className="settingsRows">{state.creators.map(c=><ColorRow key={c.name} creator={c} save={saveColor} toggle={toggleCreator} saving={saving}/>)}</div></section><MobileSettings/></main>:<>
   {missing.length>0&&<section className="colors"><div><strong>Assign creator colors</strong><p>Choose a color before formatting each creator’s images.</p></div><div className="colorrows">{missing.map(c=><ColorRow key={c.name} creator={c} save={saveColor} saving={saving}/>)}</div></section>}
   <div className="toolbar"><div className="search"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search crea, code, BP…"/></div><select value={creator} onChange={e=>setCreator(e.target.value)}><option value="all">All creators</option>{state.creators.filter(c=>c.enabled!==0).map(c=><option key={c.name}>{c.name}</option>)}</select></div>

   <nav className="branches">{(state.gallery_order?.branches||Object.keys(BRANCHES)).map(code=><button key={code} className={branch===code?'active':''} onClick={()=>setBranch(code)}>{BRANCHES[code]}<small>{assets.filter(a=>a.branch===code).length}</small></button>)}</nav>
   <main>{orderedCodes(Object.keys(groups),state.gallery_order?.types[branch]).map(code=><section className="typeSection" key={code}><button className="typeHead" onClick={()=>setCollapsed({...collapsed,[code]:!collapsed[code]})}>{collapsed[code]?<ChevronRight size={18}/>:<ChevronDown size={18}/>}<strong>{TYPES[code]||code.toUpperCase()}</strong><span>{groups[code].length}</span></button>{!collapsed[code]&&<div className="grid">{groups[code].map(a=><div className={`card ${stage.hot?.items.some(i=>i.id===a.id)?'selectedCard':hotFull?'fullCard':''}`} key={a.id} role="button" tabIndex={hotFull&&!stage.hot?.items.some(i=>i.id===a.id)?-1:0} aria-disabled={hotFull&&!stage.hot?.items.some(i=>i.id===a.id)} aria-label={stage.hot?.items.some(i=>i.id===a.id)?`Remove ${a.relpath} from Hot Staging`:hotFull?`Hot Staging full; details for ${a.relpath} available`:`Add ${a.relpath} to Hot Staging`} onClick={()=>toggleHot(a.id)} onKeyDown={e=>{if(e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();toggleHot(a.id)}}}><img loading="lazy" src={`/api/image/${a.id}/thumb?rev=${a.render_key||''}`}/><span className="selectMark">{stage.hot?.items.some(i=>i.id===a.id)?'✓':'+'}</span><button className="cardInfo" title="Asset details" aria-label={`Details for ${a.relpath}`} onClick={e=>{e.stopPropagation();setSelected(a)}}><Info size={16}/></button></div>)}</div>}</section>)}{!shown.length&&<div className="empty">{state.busy?'Formatting collection…':missing.length?'Choose creator colors to start formatting.':'No crea match this view.'}</div>}</main>
   <ReserveStage snapshot={stage} onChanged={refresh} used={used} usedOpen={usedOpen} onCloseUsed={()=>setUsedOpen(false)}/>
   {selected&&<div className="overlay" onClick={()=>setSelected(null)}><aside className="panel" onClick={e=>e.stopPropagation()}><div className="panelHead"><strong>{selected.review?'Import review':TYPES[selected.type]}</strong><button onClick={()=>setSelected(null)}>Close</button></div>{selected.review?<div className="reviewList">{review.length?review.map(a=><div key={a.id}><b>{a.relpath}</b><p>{a.issue}</p></div>):'No issues.'}</div>:<><img className="preview" src={`/api/image/${selected.id}/formatted?rev=${selected.render_key||''}`}/><div className="details"><b>{selected.relpath}</b><span>{selected.width}×{selected.height} source · {selected.bp==null?'No BP':`${selected.bp} BP`}</span></div><div className="editor"><h3><SlidersHorizontal size={17}/> Image placement</h3><div className="segmented"><button className={selected.mode==='fit'?'active':''} onClick={()=>action(`/assets/${selected.id}/format`,{mode:'fit'})}>Fit full image</button><button className={selected.mode==='crop'?'active':''} onClick={()=>action(`/assets/${selected.id}/format`,{mode:'crop',focal_x:.5,focal_y:.5})}>Crop to fill</button></div>{selected.mode==='crop'&&<><label>Horizontal crop <input type="range" min="0" max="1" step=".01" defaultValue={selected.focal_x} onPointerUp={e=>action(`/assets/${selected.id}/format`,{mode:'crop',focal_x:Number(e.currentTarget.value),focal_y:selected.focal_y})}/></label><label>Vertical crop <input type="range" min="0" max="1" step=".01" defaultValue={selected.focal_y} onPointerUp={e=>action(`/assets/${selected.id}/format`,{mode:'crop',focal_x:selected.focal_x,focal_y:Number(e.currentTarget.value)})}/></label></>}</div></>}</aside></div>}
  </>}
 </div>{hotDock&&createPortal(<DiscordComposer snapshot={stage} onChanged={refresh} reply={reply} onClearReply={onClearReply} mentionMembers={mentionMembers} teams={teams} teamColors={teamColors}/>,hotDock)}</>
}
createRoot(document.getElementById('root')).render(location.pathname==='/mobile'?<Mobile/>:<WorkspaceShell>{(hotDock,reply,onClearReply,mentionMembers,teams,teamColors)=><App hotDock={hotDock} reply={reply} onClearReply={onClearReply} mentionMembers={mentionMembers} teams={teams} teamColors={teamColors}/>}</WorkspaceShell>);
