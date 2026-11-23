let bootstrap;
async function csrf(){
 bootstrap ||= fetch('/api/security',{credentials:'same-origin'}).then(async response=>{
  if(!response.ok)throw Error('Unable to initialize local security');
  return (await response.json()).csrf_token;
 }).catch(error=>{bootstrap=null;throw error});
 return bootstrap;
}

export async function apiFetch(path,options={}){
 const headers=new Headers(options.headers);
 if(options.method&&options.method.toUpperCase()!=='GET'){
  const token=await csrf();
  if(token)headers.set('X-CH-CSRF',token);
 }
 return fetch(path,{...options,headers,credentials:'same-origin'});
}
