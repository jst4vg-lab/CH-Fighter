const {test} = require('node:test');
const assert = require('node:assert/strict');

test('mention selections keep their identity on edits outside the label', async () => {
 const {shiftSelections,mentionQuery} = await import('../src/mentionDraft.js');
 const selected={id:'1',name:'Alice',start:0,end:6};
 assert.deepEqual(shiftSelections('@Alice review','🔥 @Alice review',[selected]),[{...selected,start:3,end:9}]);
 assert.deepEqual(shiftSelections('@Alice review','@Alina review',[selected]),[]);
 assert.deepEqual(mentionQuery('hi @Ali',7),{start:3,end:7,query:'Ali'});
 assert.equal(mentionQuery('name@example',12),null);
});
