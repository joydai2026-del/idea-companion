"""Idea Companion v1 - the tutor page, served as a self-contained HTML string.

Kept as a Python module so Modal includes it when it serializes app.py's imports.
No secrets here: the page fetches a short-lived ephemeral token from /session.
"""

VERSION = "tutor-v16"

PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<title>Idea Companion</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root { color-scheme: light; --ring: #9fe6cd; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; -webkit-user-select: none; user-select: none; }
  html, body { height: 100%; }
  body {
    margin: 0; padding: 0;
    font: 16px/1.5 "Quicksand", "SF Pro Rounded", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    color: #27413a;
    background: linear-gradient(178deg, #f0fbf6 0%, #e7f7f0 58%, #dcf2e9 100%);
    display: flex; flex-direction: column; height: 100dvh; overflow: hidden;
  }
  header { padding: 18px 20px 6px; text-align: center; flex: 0 0 auto; }
  header h1 { font-size: 22px; margin: 0; font-weight: 700; letter-spacing: .2px; color: #27413a; }
  header p { margin: 3px 0 0; font-size: 13px; color: #3fae8c; font-weight: 600; }
  .notion-line { margin-top: 7px; font-size: 12px; color: #7fa99a; }

  .orbwrap { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; padding: 12px 0 4px; }
  .orb {
    width: 156px; height: 156px; border-radius: 50%; position: relative; cursor: pointer;
    display: grid; place-items: center; transition: transform .08s ease-out;
  }
  .rings { position: absolute; inset: 0; border-radius: 50%; display: none; pointer-events: none; }
  .rings:before, .rings:after {
    content: ""; position: absolute; inset: 10px; border-radius: 50%;
    border: 2px solid var(--ring); opacity: 0; animation: ping 2.6s ease-out infinite;
  }
  .rings:after { animation-delay: 1.3s; }
  @keyframes ping { 0%{ transform: scale(.78); opacity: .55; } 80%{ opacity: 0; } 100%{ transform: scale(1.3); opacity: 0; } }
  .orb.listening .rings, .orb.speaking .rings { display: block; }
  .orb.speaking { --ring: #86e0b0; }
  .robo {
    width: 150px; height: 150px; position: relative; z-index: 2;
    filter: drop-shadow(0 10px 16px rgba(40,90,70,.16));
    animation: float 3.4s ease-in-out infinite;
  }
  @keyframes float { 0%,100%{ transform: translateY(0); } 50%{ transform: translateY(-5px); } }
  .robo .eyes { transform-box: fill-box; transform-origin: center; animation: blink 4.2s infinite; }
  @keyframes blink { 0%,93%,100%{ transform: scaleY(1); } 96%{ transform: scaleY(.12); } }
  /* per-state expressions: idle shows .eyes + .mouth-smile; others swap in via the orb state class */
  .robo .eye-happy, .robo .eye-think, .robo .mouth-listen, .robo .mouth-talk, .robo .mouth-think { display: none; }
  .orb.listening .robo .mouth-smile { display: none; }
  .orb.listening .robo .mouth-listen { display: block; }
  .orb.speaking .robo .eyes, .orb.speaking .robo .mouth-smile { display: none; }
  .orb.speaking .robo .eye-happy, .orb.speaking .robo .mouth-talk { display: block; }
  .orb.connecting .robo .eyes, .orb.connecting .robo .mouth-smile { display: none; }
  .orb.connecting .robo .eye-think, .orb.connecting .robo .mouth-think { display: block; }
  .robo .mouth-talk { transform-box: fill-box; transform-origin: center; animation: talk .42s ease-in-out infinite alternate; }
  @keyframes talk { from { transform: scaleY(.3); } to { transform: scaleY(1); } }
  .orb.connecting .robo .eye-think { transform-box: fill-box; transform-origin: center; animation: look 1.6s ease-in-out infinite; }
  @keyframes look { 0%,100%{ transform: translateX(-3px); } 50%{ transform: translateX(3px); } }
  .statepill {
    margin-top: 10px; font-size: 12.5px; font-weight: 700; padding: 4px 14px;
    border-radius: 999px; background: #d6f4e8; color: #1d9b76; min-height: 26px;
  }
  .hint { font-size: 12.5px; color: #86ab9d; margin-top: 10px; height: 16px; }

  .transcript {
    flex: 1 1 auto; overflow-y: auto; padding: 8px 16px 4px; margin: 6px 10px 0;
    display: flex; flex-direction: column; gap: 8px; -webkit-overflow-scrolling: touch; user-select: text;
  }
  .bubble { max-width: 84%; padding: 9px 13px; border-radius: 16px; font-size: 15px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
  .bubble.you { align-self: flex-end; background: #19b88a; color: #fff; border-bottom-right-radius: 5px; }
  .bubble.tutor { align-self: flex-start; background: #ffffff; color: #3a4f48; box-shadow: 0 2px 8px rgba(60,140,110,.12); border-bottom-left-radius: 5px; }
  .bubble.note { align-self: center; background: #e7f7f0; border: 1px solid #c8ecdc; color: #178a68; font-size: 13.5px; max-width: 92%; text-align: center; }
  .bubble .who { display:block; font-size: 11px; opacity: .7; margin-bottom: 2px; font-weight: 700; }
  .bubble.tutor .who { color: #19b88a; opacity: 1; }
  .empty {
    color: #8aa99d; text-align: center; font-size: 13.5px; margin: 14px auto 0;
    max-width: min(92vw, 680px); padding: 0 10px; overflow-wrap: anywhere;
  }

  footer { flex: 0 0 auto; padding: 10px 20px calc(16px + env(safe-area-inset-bottom)); }
  button#end {
    width: 100%; padding: 14px; font-size: 15px; font-weight: 700; border-radius: 14px;
    background: #ffffff; color: #159a73; border: 1px solid #cdeede;
    box-shadow: 0 2px 8px rgba(60,140,110,.14); cursor: pointer; display: none; font-family: inherit;
  }
  .err { color:#e0556a; font-size:12.5px; text-align:center; padding:0 16px; min-height:16px; }
</style>
</head>
<body>
  <header>
    <h1>Idea Companion</h1>
    <p>Your walking tutor</p>
    <div class="notion-line">Talk now. Notion remembers, organizes, and writes the follow-up.</div>
  </header>

  <div class="orbwrap">
    <div class="orb" id="orb">
      <div class="rings"></div>
      <svg class="robo" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <line x1="100" y1="40" x2="100" y2="22" stroke="#19b88a" stroke-width="5" stroke-linecap="round"/>
        <circle cx="100" cy="17" r="6.5" fill="#19b88a"/>
        <rect x="30" y="84" width="13" height="30" rx="6.5" fill="#bfeede"/>
        <rect x="157" y="84" width="13" height="30" rx="6.5" fill="#bfeede"/>
        <rect x="42" y="44" width="116" height="112" rx="42" fill="#ffffff" stroke="#e3ece8" stroke-width="2"/>
        <rect x="56" y="62" width="88" height="74" rx="32" fill="#f1f8f5"/>
        <ellipse cx="66" cy="113" rx="8" ry="5" fill="#ffd2da"/>
        <ellipse cx="134" cy="113" rx="8" ry="5" fill="#ffd2da"/>
        <g class="eyes">
          <ellipse cx="82" cy="94" rx="11" ry="13.5" fill="#263b34"/>
          <ellipse cx="118" cy="94" rx="11" ry="13.5" fill="#263b34"/>
          <circle cx="86" cy="89" r="3.4" fill="#ffffff"/>
          <circle cx="122" cy="89" r="3.4" fill="#ffffff"/>
        </g>
        <path class="mouth-smile" d="M91 114 Q100 122 109 114" stroke="#263b34" stroke-width="3.4" fill="none" stroke-linecap="round"/>
        <g class="eye-happy">
          <path d="M72 95 Q82 86 92 95" stroke="#263b34" stroke-width="4" fill="none" stroke-linecap="round"/>
          <path d="M108 95 Q118 86 128 95" stroke="#263b34" stroke-width="4" fill="none" stroke-linecap="round"/>
        </g>
        <g class="eye-think">
          <circle cx="82" cy="90" r="7" fill="#263b34"/>
          <circle cx="118" cy="90" r="7" fill="#263b34"/>
          <circle cx="84.5" cy="87" r="2.3" fill="#ffffff"/>
          <circle cx="120.5" cy="87" r="2.3" fill="#ffffff"/>
        </g>
        <ellipse class="mouth-listen" cx="100" cy="116" rx="5" ry="4" fill="#c27c84"/>
        <ellipse class="mouth-talk" cx="100" cy="115" rx="7" ry="6.5" fill="#c27c84"/>
        <line class="mouth-think" x1="94" y1="116" x2="106" y2="116" stroke="#263b34" stroke-width="3" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="statepill" id="orbLbl">Tap to start</div>
    <div class="hint" id="hint">Tap, allow the mic, then ask for a Notion report.</div>
  </div>

  <div class="transcript" id="transcript">
    <div class="empty" id="empty">Demo prompt: "Teach me why Notion is useful as a personal product backend. Then create a Notion lesson with pictures, concept cards, glossary terms, and a quiz."</div>
  </div>

  <div class="err" id="err"></div>
  <footer><button id="end">End session</button></footer>
  <audio id="bot" autoplay playsinline></audio>

<script>
const VERSION="__VERSION__";
const $=(id)=>document.getElementById(id);
const orb=$("orb"), orbLbl=$("orbLbl"), hint=$("hint"), tr=$("transcript"), endBtn=$("end"), errEl=$("err");

const tg=window.Telegram&&window.Telegram.WebApp;
try{ if(tg){ tg.ready(); tg.expand(); tg.setHeaderColor&&tg.setHeaderColor("#eaf7f1"); tg.setBackgroundColor&&tg.setBackgroundColor("#eaf7f1"); } }catch(e){}
function tgInit(){ return (tg&&tg.initData)?tg.initData:""; }

let pc=null, dc=null, micStream=null, audioCtx=null, live=false, connecting=false, botBubble=null, rafId=null;
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
function addUser(text){ if(text&&text.trim()){ addBubble("you","You",text.trim()); transcriptLog.push({role:"you",text:text.trim()}); } }
function addNote(text){ addBubble("note","",text); }
function botDelta(delta){ if(!botBubble){ botBubble=addBubble("tutor","Tutor",""); curBotText=""; } botBubble.textContent+=delta; curBotText+=delta; tr.scrollTop=tr.scrollHeight; }
function botDone(){ if(curBotText.trim()) transcriptLog.push({role:"tutor",text:curBotText.trim()}); botBubble=null; curBotText=""; }

// Voice-issued commands arrive as function (tool) calls. Capture, show, confirm.
let lastReportAt=0;
let pendingContinue=false;
function ack(call_id, out){
  // Send only the tool output now; fire ONE response.create after the model's response
  // settles (on response.done), so two tool calls in one turn cannot collide with an
  // active response. tool_choice:none on that turn stops an immediate re-fire.
  try{
    dc.send(JSON.stringify({type:"conversation.item.create", item:{type:"function_call_output", call_id:call_id, output:out}}));
    pendingContinue=true;
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
  if(live||connecting) return;
  connecting=true;
  setErr(""); setState("connecting","..."); setHint("Connecting your tutor...");
  try{ micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}}); }
  catch(e){ connecting=false; setState("","Tap to start"); setHint("Allow the mic in Settings, then tap again."); setErr("Mic blocked: "+(e.name||e)); return; }

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
    live=true; connecting=false; startedAt=Date.now(); endBtn.style.display="block"; setState("listening","Listening"); setHint("Just talk. Tap the orb or End to stop.");
  }catch(e){ stop("error"); setErr("Voice connect failed: "+e.message); }
}

function onEvent(ev){
  const t=ev.type||"";
  if(t==="response.output_item.done" && ev.item && ev.item.type==="function_call"){ handleToolCall(ev.item); }
  else if(t==="conversation.item.input_audio_transcription.completed"){ addUser(ev.transcript||""); }
  else if(t.indexOf("audio_transcript")>=0 && t.indexOf("delta")>=0){ setState("speaking","Speaking"); botDelta(ev.delta||""); }
  else if(t.indexOf("audio_transcript")>=0 && t.indexOf("done")>=0){ botDone(); }
  else if(t==="response.done"){ botDone(); if(pendingContinue){ pendingContinue=false; try{ dc.send(JSON.stringify({type:"response.create", response:{tool_choice:"none"}})); }catch(e){} } if(live) setState("listening","Listening"); }
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
  const wasLive=live; live=false; connecting=false;
  if(rafId) cancelAnimationFrame(rafId);
  try{ if(pc) pc.close(); }catch(e){} pc=null; dc=null;
  try{ if(micStream) micStream.getTracks().forEach(t=>t.stop()); }catch(e){} micStream=null;
  orb.style.transform="scale(1)"; setState("","Tap to start"); endBtn.style.display="none";
  if(reason==="user"){
    setHint("Session ended.");
    const n=requests.length;
    addBubble("tutor","Idea Companion", n ? ("Nice walk. "+n+" item"+(n>1?"s":"")+" will be waiting in your Notion.") : "Nice walk. I'll save this conversation to your Notion.");
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
