export function shiftSelections(before,after,selections) {
 let start=0,end=0;
 while(start<before.length&&start<after.length&&before[start]===after[start])start++;
 while(end<before.length-start&&end<after.length-start&&before.at(-end-1)===after.at(-end-1))end++;
 const delta=after.length-before.length;
 const oldEnd=before.length-end;
 return selections.flatMap(item=>{
  if(item.end<=start)return [item];
  if(item.start>=oldEnd)return [{...item,start:item.start+delta,end:item.end+delta}];
  return [];
 });
}

export function mentionQuery(text,caret){
 const match=/(?:^|\s)@([^\s<>@]{0,100})$/.exec(text.slice(0,caret));
 return match?{start:caret-match[1].length-1,end:caret,query:match[1]}:null;
}
