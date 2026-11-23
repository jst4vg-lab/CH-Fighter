export function orderedCodes(codes,preferred=[]){
 const ranks=new Map(preferred.map((code,index)=>[code,index]));
 return [...codes].sort((a,b)=>(ranks.get(a)??Infinity)-(ranks.get(b)??Infinity)||a.localeCompare(b));
}
