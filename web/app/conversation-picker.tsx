"use client";

import {useRef,useState} from "react";
import {Combobox} from "@base-ui/react/combobox";
import {Check, ChevronDown} from "lucide-react";

type Chat={id:string;name:string};

export default function ConversationPicker({chats,value,onChange,disabled}:{chats:Chat[];value:string;onChange:(id:string)=>void;disabled:boolean}){
 const [search,setSearch]=useState(""),[open,setOpen]=useState(false);
 const anchor=useRef<HTMLDivElement>(null);
 const selected=chats.find(chat=>chat.id===value)??null;
 return <Combobox.Root items={chats} value={selected} onValueChange={chat=>{onChange(chat?.id??"");setOpen(false);}} itemToStringLabel={chat=>chat.name} isItemEqualToValue={(a,b)=>a.id===b.id} inputValue={open?search:selected?.name??""} onInputValueChange={setSearch} open={open} onOpenChange={next=>{setOpen(next);setSearch("");}} autoHighlight disabled={disabled}>
  <div ref={anchor} className="conversation-control" data-open={open||undefined}>
   <Combobox.Input id="recipient" aria-label="Choose a conversation" placeholder={open?"Find a conversation…":"Choose a conversation"} autoComplete="off"/>
   <Combobox.Trigger className="conversation-toggle" aria-label={open?"Close conversations":"Open conversations"}><ChevronDown size={15}/></Combobox.Trigger>
  </div>
  <Combobox.Portal>
   <Combobox.Positioner anchor={anchor} sideOffset={-1} align="start" side="bottom" collisionAvoidance={{side:"none",align:"shift"}} className="conversation-positioner">
    <Combobox.Popup className="conversation-popup" initialFocus={false}>
     <Combobox.Empty className="conversation-empty">{chats.length?"No conversations found.":"No conversations available. Refresh to try again."}</Combobox.Empty>
     <Combobox.List className="conversation-list">
      {(chat:Chat)=><Combobox.Item key={chat.id} value={chat} className="conversation-option"><span>{chat.name}</span><Combobox.ItemIndicator><Check size={15}/></Combobox.ItemIndicator></Combobox.Item>}
     </Combobox.List>
    </Combobox.Popup>
   </Combobox.Positioner>
  </Combobox.Portal>
 </Combobox.Root>;
}
