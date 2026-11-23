const { shell } = require('electron');

function hardenWindow(window, origin, secret) {
 const contents=window.webContents;
 const isolated=contents.session;
 isolated.setPermissionCheckHandler(()=>false);
 isolated.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
 isolated.webRequest.onBeforeSendHeaders({urls:[origin+'/*']},(details,callback)=>{
  const headers={...details.requestHeaders};
  for(const name of Object.keys(headers)){
   if(name.toLowerCase()==='x-ch-desktop')delete headers[name];
  }
  const frame=details.frame;
  if(details.webContentsId===contents.id&&frame&&frame===contents.mainFrame&&
     frame.url.startsWith(origin+'/'))headers['X-CH-Desktop']=secret;
  callback({requestHeaders:headers});
 });
 function navigation(event,url){
  try{
   const target=new URL(url);
   if(target.origin===origin&&!target.username&&!target.password)return;
   event.preventDefault();
   if(target.protocol==='https:'&&!target.username&&!target.password)
    shell.openExternal(target.href).catch(()=>{});
  }catch{event.preventDefault()}
 }
 contents.on('will-navigate',navigation);
 contents.on('will-redirect',navigation);
 contents.setWindowOpenHandler(({url})=>{
  try{
   const target=new URL(url);
   if(target.protocol==='https:'&&!target.username&&!target.password)
    shell.openExternal(target.href).catch(()=>{});
  }catch{}
  return {action:'deny'};
 });
}
module.exports={hardenWindow};
