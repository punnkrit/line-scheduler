"use client";
import {useEffect,useRef,useState} from "react";
import {LoaderCircle,X} from "lucide-react";

type Attempt={id:string;status:string;deadline:number;kind?:string;qr?:string;pin?:string};
const active=(attempt:Attempt|null)=>!!attempt&&["starting","waiting"].includes(attempt.status);
const storageKey="line-login-attempt";
export default function LineLogin({connected,onStarted,onConnected}:{connected:boolean;onStarted:()=>void;onConnected:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),polling=useRef(false),handled=useRef("");
 const [open,setOpen]=useState(false),[attempt,setAttempt]=useState<Attempt|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const [now,setNow]=useState(()=>Date.now()/1000);
 async function request(action:string,id:string){
  const response=await fetch("/api/scheduler",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,id}),cache:"no-store",signal:AbortSignal.timeout(15000)});
  const data=await response.json() as {error?:string;login:Attempt};if(!response.ok)throw Object.assign(new Error(data.error||"Login unavailable."),{status:response.status});return data.login;
 }
 useEffect(()=>{const id=sessionStorage.getItem(storageKey);if(id&&/^[a-f0-9]{32}$/.test(id)){setAttempt({id,status:"starting",deadline:Date.now()/1000+150});setOpen(true)}},[]);
 useEffect(()=>{if(open)dialog.current?.showModal();else dialog.current?.close()},[open]);
 useEffect(()=>{if(!open)return;const timer=setInterval(()=>setNow(Date.now()/1000),1000);return()=>clearInterval(timer)},[open]);
 useEffect(()=>{
  if(!open||!active(attempt))return;
  let stopped=false;
  const poll=async()=>{
   if(polling.current)return;polling.current=true;
   try{const next=await request("login_status",attempt!.id);if(!stopped){setAttempt(next);setError("");}}
   catch{if(!stopped){setError("Could not check login. Retrying…");if(Date.now()/1000>=attempt!.deadline)setAttempt({...attempt!,status:"expired",qr:undefined,pin:undefined})}}
   finally{polling.current=false}
  };
  void poll();const timer=setInterval(poll,2000);return()=>{stopped=true;clearInterval(timer)};
 },[open,attempt?.id,attempt?.status]);
 useEffect(()=>{
  if(!attempt||active(attempt))return;
  sessionStorage.removeItem(storageKey);
  if(attempt.status==="connected"&&handled.current!==attempt.id){handled.current=attempt.id;onConnected()}
 },[attempt,onConnected]);
 async function start(){
  if(busy)return;setBusy(true);setError("");
  const id=crypto.randomUUID().replaceAll("-","");
  // Retain only an opaque attempt ID, never a QR/PIN or LINE session.
  sessionStorage.setItem(storageKey,id);
  setAttempt({id,status:"starting",deadline:Date.now()/1000+150});onStarted();
  try{setAttempt(await request("login_start",id))}
  catch(e){setError(e instanceof Error?e.message:"Could not start login.");if((e as {status?:number}).status===409||(e as {status?:number}).status===400){setAttempt(null);sessionStorage.removeItem(storageKey)}}
  finally{setBusy(false)}
 }
 async function close(){
  if(busy)return;setBusy(true);setError("");
  try{
   if(active(attempt)){const next=await request("login_cancel",attempt!.id);setAttempt(next);if(next.status==="connected")onConnected();}
   sessionStorage.removeItem(storageKey);setAttempt(null);setOpen(false);
  }catch{setError("Could not confirm cancellation. The login will expire automatically.")}
  finally{setBusy(false)}
 }
 const expires=attempt?Math.max(0,Math.ceil(attempt.deadline-now)):0;
 const showSecrets=active(attempt)&&expires>0;
 const status=attempt?.status;
 const progress:Record<string,string>={scanned:"Scanned. Approve the login on your phone.",pin:"Enter this code in LINE on your phone.",phone_accepted:"Securing your session…",approved:"Securing your session…",expired:"Getting a new QR code…"};
 return <>
  <button className="line-login-button" onClick={()=>{setError("");setOpen(true)}}>{connected?"Reconnect LINE":"Connect LINE"}</button>
  <dialog ref={dialog} className="login-dialog" aria-labelledby="login-title" onCancel={e=>{e.preventDefault();void close()}}>
   <div className="section-heading"><h2 id="login-title">{connected?"Reconnect LINE":"Connect LINE"}</h2><button className="icon-button" aria-label="Close LINE login" disabled={busy} onClick={close}><X size={18}/></button></div>
   {error&&<p className="login-error" role="alert">{error}</p>}
   {!attempt&&<><p>Scan the QR code using LINE on your phone, then approve the login.</p><p className="login-note">Use the same LINE account. Scheduled sends wait briefly during login. This may replace an existing LINE Chrome session.</p><button className="schedule-button" onClick={start} disabled={busy}>Show QR code</button></>}
   {active(attempt)&&<div className="login-progress">
    {showSecrets&&attempt?.qr?<><img className="login-qr" src={attempt.qr} alt="Scan with LINE on your phone"/><p>LINE → Add friends → QR code</p></>:showSecrets&&attempt?.pin?<><p>{progress.pin}</p><strong className="login-pin">{attempt.pin}</strong></>:<><LoaderCircle className="spinning" size={26}/><p role="status">{!expires?"Login expired. Checking final status…":progress[attempt?.kind||""]||"Preparing QR code…"}</p></>}
    <p className="login-note">{expires>0?`Expires in ${expires}s. Keep this dialog open.`:"The QR code is no longer available."}</p>
    <button className="cancel" disabled={busy} onClick={close}>Cancel login</button>
   </div>}
   {attempt&&!active(attempt)&&<><p role="status">{status==="connected"?"Connected. Refreshing conversations…":status==="cancelled"?"Login cancelled.":status==="expired"?"Login expired. Try again.":"Login could not finish. Approve the same account and try again."}</p>{status!=="connected"&&<button className="schedule-button" disabled={busy} onClick={start}>Try again</button>}<button className="cancel" onClick={close}>Close</button></>}
  </dialog>
 </>
}
