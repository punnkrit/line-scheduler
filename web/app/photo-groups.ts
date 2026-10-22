export type AttachmentKind = "photo" | "file";

// Group only consecutive photos, preserving the selection's order. Documents
// separate photo runs, and overflow always starts a fresh LINE group.
export function attachmentGroups<T extends {id:string;kind:AttachmentKind}>(files:T[]):T[][] {
 const groups:T[][]=[];
 for(const file of files){
  const last=groups[groups.length-1];
  if(file.kind==="photo"&&last?.[0].kind==="photo"&&last.length<10)last.push(file);
  else groups.push([file]);
 }
 return groups;
}

export function photoSignature(bytes:Uint8Array){
 return (bytes[0]===0xff&&bytes[1]===0xd8&&bytes[2]===0xff)||
  [137,80,78,71,13,10,26,10].every((value,index)=>bytes[index]===value);
}
