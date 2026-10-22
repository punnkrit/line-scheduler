"use client";

import {Search, X} from "lucide-react";
import {Popover} from "radix-ui";
import {useRef} from "react";

export const messageStatusLabels:Record<string,string>={queued:"Confirming schedule",scheduled:"Scheduled",sending:"Sending",sent:"Sent",cancelled:"Cancelled",failed:"Not sent",unknown:"Check LINE",expired:"Missed send time"};
export type HistoryFilters={person:string;query:string;from:string;to:string;status:string};
export const emptyHistoryFilters:HistoryFilters={person:"",query:"",from:"",to:"",status:""};
type HistoryItem={chat_name:string;text:string;due_at:number;status:string;attachment?:{name:string}};

export function matchesHistory(job:HistoryItem,filters:HistoryFilters,zone:string){
 if(filters.person&&job.chat_name!==filters.person)return false;
 if(filters.status&&job.status!==filters.status)return false;
 const query=filters.query.trim().normalize("NFKC").toLocaleLowerCase();
 if(query&&!`${job.text}\n${job.attachment?.name??""}`.normalize("NFKC").toLocaleLowerCase().includes(query))return false;
 if(filters.from||filters.to){
  const parts=Object.fromEntries(new Intl.DateTimeFormat("en-CA",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(job.due_at*1000).map(part=>[part.type,part.value]));
  const date=`${parts.year}-${parts.month}-${parts.day}`;
  if((filters.from&&date<filters.from)||(filters.to&&date>filters.to))return false;
 }
 return true;
}

export default function HistoryControls({jobs,filters,onChange,resultCount}:{jobs:HistoryItem[];filters:HistoryFilters;onChange:(filters:HistoryFilters)=>void;resultCount:number}){
 const queryInput=useRef<HTMLInputElement>(null);
 const people=Array.from(new Set([...jobs.map(job=>job.chat_name),...(filters.person?[filters.person]:[])])).sort((a,b)=>a.localeCompare(b));
 const statuses=Array.from(new Set([...jobs.map(job=>job.status),...(filters.status?[filters.status]:[])])).sort((a,b)=>(messageStatusLabels[a]??a).localeCompare(messageStatusLabels[b]??b));
 const active=Object.values(filters).some(value=>value.trim());
 return <div className="history-toolbar">
  <span className="history-result-count" role="status">{active?`${resultCount} of ${jobs.length}`:jobs.length} message{jobs.length===1?"":"s"}</span>
  <Popover.Root>
   <Popover.Trigger className="history-filter-trigger" data-active={active||undefined}><Search size={14}/><span>Search history</span>{active&&<span className="history-filter-indicator" aria-label="Filters applied"/>}</Popover.Trigger>
   <Popover.Portal>
    <Popover.Content align="end" sideOffset={8} collisionPadding={17} className="history-filter-popup" aria-label="Search history" onOpenAutoFocus={event=>{event.preventDefault();queryInput.current?.focus();}}>
     <div className="history-popup-heading"><h3>Search history</h3><Popover.Close className="icon-button" aria-label="Close history search"><X size={16}/></Popover.Close></div>
     <div className="history-filters" role="search" aria-label="Search message history">
  <label className="history-query"><Search size={16} aria-hidden="true"/><span className="sr-only">Search messages or files</span><input ref={queryInput} type="search" placeholder="Search messages or files…" value={filters.query} onChange={event=>onChange({...filters,query:event.target.value})}/></label>
  <div className="history-filter-row">
   <label>Person<select aria-label="Filter history by person" value={filters.person} onChange={event=>onChange({...filters,person:event.target.value})}><option value="">Everyone</option>{people.map(person=><option key={person} value={person}>{person}</option>)}</select></label>
   <label>Status<select aria-label="Filter history by status" value={filters.status} onChange={event=>onChange({...filters,status:event.target.value})}><option value="">All statuses</option>{statuses.map(status=><option key={status} value={status}>{messageStatusLabels[status]??status}</option>)}</select></label>
  </div>
  <fieldset className="history-dates"><legend>Send date</legend><div className="history-filter-row">
   <label>From<input type="date" aria-label="History from date" value={filters.from} max={filters.to||undefined} onChange={event=>onChange({...filters,from:event.target.value})}/></label>
   <label>To<input type="date" aria-label="History to date" value={filters.to} min={filters.from||undefined} onChange={event=>onChange({...filters,to:event.target.value})}/></label>
  </div></fieldset>
  <div className="history-filter-summary"><span>{resultCount} of {jobs.length} message{jobs.length===1?"":"s"}</span><button type="button" disabled={!active} onClick={()=>onChange({...emptyHistoryFilters})}><X size={12}/>Clear filters</button></div>
     </div>
    </Popover.Content>
   </Popover.Portal>
  </Popover.Root>
 </div>;
}
