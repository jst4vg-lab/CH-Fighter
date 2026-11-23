const {test} = require('node:test');
const assert = require('node:assert/strict');

test('consecutive authors share a group across prepended history', async () => {
 const {messageGroups} = await import('../src/discordGroups.js');
 const messages = ['a','a','b','a','a'].map((id,index)=>({id:String(index),author:{id}}));
 assert.deepEqual(messageGroups(messages).map(group=>group.messages.map(item=>item.id)),
  [['0','1'],['2'],['3','4']]);
 assert.deepEqual(messageGroups(messages,item=>item.author.id==='a').map(group=>group.messages.map(item=>item.id)),
  [['0','1'],['3','4']]);
});
