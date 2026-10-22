import assert from "node:assert/strict";
import {attachmentGroups,photoSignature} from "../web/app/photo-groups.ts";
for(const count of [1,2,9,10,11,20,21,50]){
 const photos=Array.from({length:count},(_,i)=>({id:String(i),kind:"photo"}));
 const groups=attachmentGroups(photos);
 assert.deepEqual(groups.map(group=>group.length),Array.from({length:Math.ceil(count/10)},(_,i)=>Math.min(10,count-i*10)));
 assert.deepEqual(groups.flat(),photos);
}
const mixed=[{id:"a",kind:"photo"},{id:"b",kind:"file"},{id:"c",kind:"photo"}];
assert.deepEqual(attachmentGroups(mixed).map(group=>group.map(item=>item.id)),[["a"],["b"],["c"]]);
assert(photoSignature(Uint8Array.from([255,216,255,224])));
assert(photoSignature(Uint8Array.from([137,80,78,71,13,10,26,10])));
assert(!photoSignature(new TextEncoder().encode("renamed-image.png")));
assert(!photoSignature(new TextEncoder().encode("GIF89a")));
assert(!photoSignature(new Uint8Array()));
console.log("Photo grouping, order, overflow, and content signatures passed.");
