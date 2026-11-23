const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

test('desktop privilege injection is scoped and navigation is restricted',()=>{
 const handlers={},callbacks={};
 const frame={url:'http://127.0.0.1:8765/'};
 const contents={id:7,mainFrame:frame,session:{
  setPermissionCheckHandler:fn=>callbacks.permission=fn,
  setPermissionRequestHandler:fn=>callbacks.permissionRequest=fn,
  webRequest:{onBeforeSendHeaders:(_,fn)=>callbacks.headers=fn}
 },on:(name,fn)=>handlers[name]=fn,setWindowOpenHandler:fn=>callbacks.open=fn};
 const mod={exports:{}};
 vm.runInNewContext(fs.readFileSync('desktop/security.cjs','utf8'),{
  module:mod,URL,require:()=>({shell:{openExternal:()=>Promise.resolve()}})
 });
 mod.exports.hardenWindow({webContents:contents},'http://127.0.0.1:8765','fixture-secret');
 let result;
 callbacks.headers({webContentsId:7,frame,requestHeaders:{}},value=>result=value);
 assert.equal(result.requestHeaders['X-CH-Desktop'],'fixture-secret');
 callbacks.headers({webContentsId:8,frame,requestHeaders:{'X-CH-Desktop':'spoof'}},value=>result=value);
 assert.deepEqual(Object.keys(result.requestHeaders),[]);
 assert.equal(callbacks.permission(),false);
 let prevented=false;
 handlers['will-navigate']({preventDefault:()=>prevented=true},'http://evil.example');
 assert.equal(prevented,true);
});
