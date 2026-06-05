"""Idea Companion v1 - the tutor page, served as a self-contained HTML string.

Kept as a Python module so Modal includes it when it serializes app.py's imports.
No secrets here: the page fetches a short-lived ephemeral token from /session.
"""

VERSION = "tutor-v11"

PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<title>Idea Companion</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; -webkit-user-select: none; user-select: none; }
  html, body { height: 100%; }
  body {
    margin: 0; padding: 0;
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    color: #f2f5f9;
    background: radial-gradient(120% 90% at 50% 0%, #1b2a4a 0%, #0c1322 55%, #080b14 100%);
    display: flex; flex-direction: column; height: 100dvh; overflow: hidden;
  }
  header { padding: 18px 20px 6px; text-align: center; flex: 0 0 auto; }
  header h1 { font-size: 21px; margin: 0; font-weight: 700; letter-spacing: .2px; }
  header p { margin: 3px 0 0; font-size: 13px; color: #93a3bd; }

  .orbwrap { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; padding: 10px 0 6px; }
  .orb {
    width: 150px; height: 150px; border-radius: 50%; position: relative; cursor: pointer;
    background: radial-gradient(circle at 35% 30%, #46527a, #2a3650 55%, #1d2740);
    box-shadow: 0 0 0 0 rgba(76,156,255,.45), 0 10px 40px rgba(20,60,140,.5);
    transition: transform .08s ease-out, box-shadow .3s ease; display: grid; place-items: center; text-align: center;
  }
  .orb .lbl { font-size: 15px; font-weight: 600; padding: 0 14px; pointer-events: none; }
  .orb.listening { background: radial-gradient(circle at 35% 30%, #4c9cff, #2f6fe0 55%, #1d3f8c); }
  .orb.connecting { animation: pulse 1.1s ease-in-out infinite; }
  .orb.speaking { background: radial-gradient(circle at 35% 30%, #57d98a, #2bb673 55%, #178a52); }
  @keyframes pulse { 0%,100%{ box-shadow:0 0 0 0 rgba(76,156,255,.5),0 10px 40px rgba(20,60,140,.5);} 50%{ box-shadow:0 0 0 18px rgba(76,156,255,0),0 10px 40px rgba(20,60,140,.5);} }
  .hint { font-size: 12.5px; color: #8294b2; margin-top: 12px; height: 16px; }

  .transcript {
    flex: 1 1 auto; overflow-y: auto; padding: 8px 16px 4px; margin: 6px 10px 0;
    display: flex; flex-direction: column; gap: 8px; -webkit-overflow-scrolling: touch; user-select: text;
  }
  .bubble { max-width: 84%; padding: 9px 13px; border-radius: 15px; font-size: 15px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
  .bubble.you { align-self: flex-end; background: #2f6fe0; border-bottom-right-radius: 5px; }
  .bubble.tutor { align-self: flex-start; background: #1b2536; border: 1px solid #283449; border-bottom-left-radius: 5px; }
  .bubble.note { align-self: center; background: #14241c; border: 1px solid #1f5a3a; color: #8fe7b4; font-size: 13.5px; max-width: 92%; text-align: center; }
  .bubble .who { display:block; font-size: 11px; opacity: .65; margin-bottom: 2px; }
  .empty { color: #6f80a0; text-align: center; font-size: 13.5px; margin-top: 14px; }

  footer { flex: 0 0 auto; padding: 10px 20px calc(16px + env(safe-area-inset-bottom)); }
  button#end {
    width: 100%; padding: 14px; font-size: 15px; font-weight: 600; border-radius: 13px;
    background: #2a1620; color: #ff97a9; border: 1px solid #5a2738; cursor: pointer; display: none;
  }
  .err { color:#ff8095; font-size:12.5px; text-align:center; padding:0 16px; min-height:16px; }
</style>
</head>
<body>
  <header>
    <h1>Idea Companion</h1>
    <p>Your walking tutor · 你的步行私教</p>
  </header>

  <div class="orbwrap">
    <div class="orb" id="orb"><span class="lbl" id="orbLbl">Tap to start</span></div>
    <div class="hint" id="hint">Tap, allow the mic, then just talk.</div>
  </div>

  <div class="transcript" id="transcript">
    <div class="empty" id="empty">Your conversation will appear here. Try: "Explain X", or "write me a deep report on X and save it to Notion".</div>
  </div>

  <div class="err" id="err"></div>
  <footer><button id="end">End session</button></footer>
  <audio id="bot" autoplay playsinline></audio>

<script>
const VERSION="__VERSION__";
const $=(id)=>document.getElementById(id);
const orb=$("orb"), orbLbl=$("orbLbl"), hint=$("hint"), tr=$("transcript"), endBtn=$("end"), errEl=$("err");

const tg=window.Telegram&&window.Telegram.WebApp;
try{ if(tg){ tg.ready(); tg.expand(); tg.setHeaderColor&&tg.setHeaderColor("#0c1322"); } }catch(e){}
function tgInit(){ return (tg&&tg.initData)?tg.initData:""; }

let pc=null, dc=null, micStream=null, audioCtx=null, live=false, botBubble=null, rafId=null;
let curBotText="", startedAt=0;
const transcriptLog=[];   // [{role:'you'|'tutor', text}]
const requests=[];        // captured voice commands [{type, ...}]

function setState(s, label){ orb.className="orb "+s; if(label!=null) orbLbl.textContent=label; }
function setHint(t){ hint.textContent=t; }
function setErr(t){ errEl.textContent=t||""; }
function clearEmpty(){ const e=$("empty"); if(e) e.remove(); }

function addBubble(role, who, text){
  clearEmpty();
  const d=document.createElement("div"); d.className="bubble "+role;
  if(who){ const w=document.createElement("span"); w.className="who"; w.textContent=who; d.appendChild(w); }
  const span=document.createElement("span"); span.textContent=text; d.appendChild(span);
  tr.appendChild(d); tr.scrollTop=tr.scrollHeight; return span;
}
function addUser(text){ if(text&&text.trim()){ addBubble("you","You · 你",text.trim()); transcriptLog.push({role:"you",text:text.trim()}); } }
function addNote(text){ addBubble("note","",text); }
function botDelta(delta){ if(!botBubble){ botBubble=addBubble("tutor","Tutor · 私教",""); curBotText=""; } botBubble.textContent+=delta; curBotText+=delta; tr.scrollTop=tr.scrollHeight; }
function botDone(){ if(curBotText.trim()) transcriptLog.push({role:"tutor",text:curBotText.trim()}); botBubble=null; curBotText=""; }

// Voice-issued commands arrive as function (tool) calls. Capture, show, confirm.
let lastReportAt=0;
function ack(call_id, out){
  // Always confirm with tool_choice:none so the follow-up turn can't re-fire a tool.
  try{
    dc.send(JSON.stringify({type:"conversation.item.create", item:{type:"function_call_output", call_id:call_id, output:out}}));
    dc.send(JSON.stringify({type:"response.create", response:{tool_choice:"none"}}));
  }catch(e){}
}
function handleToolCall(item){
  let args={}; try{ args=JSON.parse(item.arguments||"{}"); }catch(e){}
  const reportLike=(item.name==="request_report"||item.name==="make_infographic");
  // The model sometimes fires the same ask twice (reworded) within a few seconds. Collapse it.
  if(reportLike && (Date.now()-lastReportAt)<15000){
    ack(item.call_id, "Already being prepared, no need to create another one.");
    return;
  }
  let out="Saved to your Notion for after the walk.";
  if(item.name==="request_report"){
    lastReportAt=Date.now();
    const depth=args.depth||"deep"; const vis=!!args.visuals; requests.push({type:"report", topic:args.topic||"", depth, visuals:vis});
    addNote("📌 "+(depth==="deep"?"Deep report":"Report")+(vis?" + pictures":"")+": "+(args.topic||"")+"  →  saving to Notion");
    out="Got it. I'll prepare a "+depth+" report"+(vis?" with pictures":"")+" on "+(args.topic||"that")+" in your Notion for after the walk.";
  } else if(item.name==="make_infographic"){
    lastReportAt=Date.now();
    requests.push({type:"infographic", topic:args.topic||""});
    addNote("🖼️ Infographic: "+(args.topic||"")+"  →  saving to Notion");
    out="I'll have an infographic on "+(args.topic||"that")+" waiting in your Notion.";
  } else if(item.name==="save_insight"){
    requests.push({type:"insight", note:args.note||""});
    addNote("💡 Saved: "+(args.note||""));
    out="Saved that to your Notion.";
  } else { return; }
  ack(item.call_id, out);
}

async function start(){
  if(live) return;
  setErr(""); setState("connecting","..."); setHint("Connecting your tutor...");
  try{ micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}}); }
  catch(e){ setState("","Tap to start"); setHint("Tap, allow the mic, then just talk."); setErr("Mic blocked: "+(e.name||e)); return; }

  try{ audioCtx=new (window.AudioContext||window.webkitAudioContext)(); await audioCtx.resume(); meter(micStream); const b=$("bot"); b.muted=false; b.play().catch(()=>{}); }catch(e){}

  let tok;
  try{
    const r=await fetch("/session",{method:"POST", headers:{"X-Telegram-Init-Data":tgInit()}}); tok=await r.json();
    if(!r.ok||!tok.value) throw new Error((tok&&tok.error)?String(tok.error).slice(0,120):("HTTP "+r.status));
  }catch(e){ stop("error"); setErr("Could not start session: "+e.message); return; }

  try{
    pc=new RTCPeerConnection();
    pc.onconnectionstatechange=()=>{ if(pc.connectionState==="failed"){ setErr("Connection lost."); stop("failed"); } };
    pc.ontrack=(ev)=>{ const b=$("bot"); b.srcObject=ev.streams[0]; b.play().catch(()=>{}); };
    micStream.getTracks().forEach(t=>pc.addTrack(t,micStream));
    dc=pc.createDataChannel("oai-events");
    dc.onopen=()=>{ try{ dc.send(JSON.stringify({type:"response.create"})); }catch(e){} };
    dc.onmessage=(e)=>{ try{ onEvent(JSON.parse(e.data)); }catch(_){ } };

    const offer=await pc.createOffer(); await pc.setLocalDescription(offer);
    const resp=await fetch("https://api.openai.com/v1/realtime/calls",{ method:"POST", body:offer.sdp, headers:{ "Authorization":"Bearer "+tok.value, "Content-Type":"application/sdp" } });
    if(!resp.ok) throw new Error("voice connect "+resp.status);
    const answer=await resp.text(); await pc.setRemoteDescription({type:"answer", sdp:answer});
    live=true; startedAt=Date.now(); endBtn.style.display="block"; setState("listening","Listening"); setHint("Just talk. Tap the orb or End to stop.");
  }catch(e){ stop("error"); setErr("Voice connect failed: "+e.message); }
}

function onEvent(ev){
  const t=ev.type||"";
  if(t==="response.output_item.done" && ev.item && ev.item.type==="function_call"){ handleToolCall(ev.item); }
  else if(t==="conversation.item.input_audio_transcription.completed"){ addUser(ev.transcript||""); }
  else if(t.indexOf("audio_transcript")>=0 && t.indexOf("delta")>=0){ setState("speaking","Speaking"); botDelta(ev.delta||""); }
  else if(t.indexOf("audio_transcript")>=0 && t.indexOf("done")>=0){ botDone(); }
  else if(t==="response.done"){ botDone(); if(live) setState("listening","Listening"); }
  else if(t==="input_audio_buffer.speech_started"){ if(live) setState("listening","Listening"); }
  else if(t==="error"){ setErr("Tutor error: "+JSON.stringify(ev.error||ev).slice(0,140)); }
}

function meter(stream){
  try{
    const src=audioCtx.createMediaStreamSource(stream);
    const an=audioCtx.createAnalyser(); an.fftSize=256; src.connect(an);
    const data=new Uint8Array(an.fftSize);
    (function loop(){
      an.getByteTimeDomainData(data);
      let peak=0; for(const v of data){ const d=Math.abs(v-128); if(d>peak)peak=d; }
      const level=Math.min(1, (peak/128)*1.8);
      if(!orb.classList.contains("speaking")) orb.style.transform="scale("+(1+level*0.16).toFixed(3)+")";
      rafId=requestAnimationFrame(loop);
    })();
  }catch(e){}
}

async function saveConversation(){
  if(!transcriptLog.length && !requests.length) return;
  try{
    await fetch("/save",{ method:"POST", headers:{"Content-Type":"application/json","X-Telegram-Init-Data":tgInit()},
      body:JSON.stringify({ transcript:transcriptLog, requests, started_at:startedAt, ended_at:Date.now() }) });
  }catch(e){}
}

function stop(reason){
  const wasLive=live; live=false;
  if(rafId) cancelAnimationFrame(rafId);
  try{ if(pc) pc.close(); }catch(e){} pc=null; dc=null;
  try{ if(micStream) micStream.getTracks().forEach(t=>t.stop()); }catch(e){} micStream=null;
  orb.style.transform="scale(1)"; setState("","Tap to start"); endBtn.style.display="none";
  if(reason==="user"){
    setHint("Session ended.");
    const n=requests.length;
    addBubble("tutor","Idea Companion", n ? ("Nice walk. "+n+" item"+(n>1?"s":"")+" will be waiting in your Notion. 下次见!") : "Nice walk. I'll save this conversation to your Notion. 下次见!");
  } else { setHint("Tap, allow the mic, then just talk."); }
  if(wasLive) saveConversation();
}

orb.addEventListener("click", ()=>{ if(live) stop("user"); else start(); });
endBtn.addEventListener("click", ()=>stop("user"));
</script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("__VERSION__", VERSION)
