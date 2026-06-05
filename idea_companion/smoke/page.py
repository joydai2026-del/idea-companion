"""The smoke-test Mini App page, served as a single self-contained HTML string.

Kept as a Python module (not a static file) so Modal includes it automatically
when it serializes app.py's imports. No secrets here: the page fetches a
short-lived ephemeral token from /session and never sees the real OpenAI key.
"""

VERSION = "smoke-v1"

PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Idea Companion - mic test</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; padding: 16px 16px 40px;
    font: 16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0d1117; color: #e6edf3;
    max-width: 560px; margin-left: auto; margin-right: auto;
  }
  h1 { font-size: 20px; margin: 4px 0 2px; }
  .sub { color: #9aa4b2; font-size: 13px; margin: 0 0 14px; }
  #verdict {
    border-radius: 14px; padding: 16px; text-align: center; font-weight: 700;
    font-size: 18px; margin-bottom: 16px; background: #1b2430; color: #9aa4b2;
    border: 1px solid #2a3543;
  }
  #verdict.go   { background: #0f2e1b; color: #57d98a; border-color: #1c7a44; }
  #verdict.nogo { background: #3a1620; color: #ff8095; border-color: #8a2540; }
  #verdict .small { display:block; font-weight: 500; font-size: 13px; margin-top: 6px; opacity: .9; }
  button {
    width: 100%; padding: 18px; font-size: 18px; font-weight: 700;
    border: none; border-radius: 14px; background: #2f81f7; color: white;
    cursor: pointer; margin-bottom: 16px;
  }
  button:disabled { background: #30363d; color: #6e7681; }
  button.secondary { background: #21262d; color: #e6edf3; font-size: 15px; font-weight: 600; padding: 14px; }
  .meter-wrap { margin: 4px 0 16px; }
  .meter-label { font-size: 12px; color: #9aa4b2; margin-bottom: 6px; }
  .meter { height: 18px; background: #161b22; border-radius: 9px; overflow: hidden; border: 1px solid #2a3543; }
  .meter > div { height: 100%; width: 0%; background: linear-gradient(90deg,#2f81f7,#57d98a); transition: width .06s linear; }
  .checks { list-style: none; padding: 0; margin: 0 0 16px; }
  .checks li { display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid #161b22; align-items: flex-start; }
  .ic { width: 20px; text-align: center; flex: 0 0 20px; font-size: 15px; }
  .nm { font-weight: 600; flex: 0 0 132px; }
  .dt { color: #9aa4b2; font-size: 13px; word-break: break-word; flex: 1; }
  .pending .ic { color: #6e7681; } .ok .ic { color: #57d98a; }
  .fail .ic { color: #ff8095; } .warn .ic { color: #e3b341; }
  #log {
    background: #010409; border: 1px solid #21262d; border-radius: 10px;
    padding: 10px; font: 11px/1.4 ui-monospace, Menlo, monospace; color: #8b949e;
    height: 150px; overflow-y: auto; white-space: pre-wrap; margin-bottom: 12px;
  }
  audio { display: none; }
</style>
</head>
<body>
  <h1>Idea Companion - mic smoke test</h1>
  <p class="sub" id="ctx">checking environment...</p>

  <div id="verdict">Tap Start, allow the mic, then say hello.<span class="small" id="verdictSmall">This proves the live voice path on your phone.</span></div>

  <button id="start">Start 30s voice test</button>

  <div class="meter-wrap">
    <div class="meter-label">Your mic input (should move when you talk):</div>
    <div class="meter"><div id="meterFill"></div></div>
  </div>

  <ul class="checks" id="checks"></ul>

  <button class="secondary" id="copy">Copy diagnostics</button>
  <div id="log"></div>
  <audio id="bot" autoplay playsinline></audio>

<script>
const VERSION = "__VERSION__";
const CHECKS = [
  ["context","Environment"],
  ["secure","Secure (HTTPS)"],
  ["api","Mic API present"],
  ["mic","Mic permission"],
  ["meter","Mic capturing"],
  ["token","Token minted"],
  ["webrtc","Live connection"],
  ["audioout","Bot audio in"],
  ["heard","Bot heard you"],
  ["spoke","Bot spoke"],
];
const state = {};
const el = (id)=>document.getElementById(id);
const checksEl = el("checks");
CHECKS.forEach(([id,name])=>{
  const li=document.createElement("li"); li.id="row-"+id; li.className="pending";
  li.innerHTML=`<span class="ic">&bull;</span><span class="nm">${name}</span><span class="dt" id="dt-${id}"></span>`;
  checksEl.appendChild(li); state[id]="pending";
});
function setStatus(id,st,detail){
  state[id]=st;
  const li=el("row-"+id); if(!li) return;
  li.className=st;
  const ic={pending:"&bull;",ok:"&check;",fail:"&times;",warn:"!"}[st]||"&bull;";
  li.querySelector(".ic").innerHTML=ic;
  if(detail!=null) el("dt-"+id).textContent=detail;
  refreshVerdict();
}
function log(m){
  const t=new Date().toLocaleTimeString();
  const d=el("log"); d.textContent+=`[${t}] ${m}\n`; d.scrollTop=d.scrollHeight;
}
function refreshVerdict(){
  const v=el("verdict"), s=el("verdictSmall");
  if(state.mic==="fail"){
    v.className="nogo"; v.firstChild.textContent="NO-GO: mic blocked here.";
    s.textContent="The microphone did not open in this app. We will use a fallback (voice notes or a Safari home-screen app).";
  } else if(state.mic==="ok" && state.audioout==="ok"){
    v.className="go"; v.firstChild.textContent="GO: live voice works on your phone.";
    s.textContent="Mic opened and the bot's voice came through. The Telegram voice tutor is viable.";
  } else if(state.mic==="ok"){
    v.className=""; v.firstChild.textContent="Mic is open - connecting the voice...";
    s.textContent="Say hello and listen for a reply.";
  }
}

// Environment detection
const tg = window.Telegram && window.Telegram.WebApp;
let inTelegram=false;
try {
  if(tg){ tg.ready(); tg.expand(); inTelegram = !!(tg.platform && tg.platform!=="unknown"); }
} catch(e){}
const ctxText = inTelegram
  ? `Inside Telegram (${tg.platform}, app v${tg.version}) - build ${VERSION}`
  : `Plain browser (Safari/PWA) - build ${VERSION}`;
el("ctx").textContent = ctxText;
setStatus("context","ok", inTelegram ? `Telegram ${tg.platform} v${tg.version}` : "Browser (not Telegram)");
setStatus("secure", window.isSecureContext ? "ok":"fail", window.isSecureContext ? "yes":"NOT secure - mic will fail");
const hasMic = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
setStatus("api", hasMic ? "ok":"fail", hasMic ? "available" : "getUserMedia missing in this WebView");
log("loaded "+ctxText);
log("userAgent: "+navigator.userAgent);

let pc=null, micStream=null, audioCtx=null, timer=null, secsLeft=30;

async function run(){
  el("start").disabled=true; el("start").textContent="Testing... (talk to it)";
  log("start tapped");

  // 1) Mic permission - the go/no-go. Called first, inside the user gesture.
  if(!hasMic){ setStatus("mic","fail","no getUserMedia in this app"); finish("API unavailable"); return; }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    setStatus("mic","ok","granted");
    log("MIC GRANTED");
  } catch(e){
    setStatus("mic","fail", (e.name||"error")+": "+(e.message||""));
    log("MIC FAILED: "+(e.name||"")+" "+(e.message||""));
    finish("mic blocked"); return;
  }

  // Unlock audio output inside the gesture (iOS autoplay policy)
  try {
    audioCtx = new (window.AudioContext||window.webkitAudioContext)();
    await audioCtx.resume();
    startMeter(micStream);
    const b=el("bot"); b.muted=false; b.play().catch(()=>{});
  } catch(e){ log("audio unlock warn: "+e); }

  // 2) Ephemeral token from our server (real key stays server-side)
  let tok;
  try {
    const r=await fetch("/session",{method:"POST"});
    tok=await r.json();
    if(!r.ok || !tok.value){ setStatus("token","fail", JSON.stringify(tok).slice(0,180)); log("TOKEN FAIL "+r.status); finish("token error"); return; }
    setStatus("token","ok","model "+(tok.model||"?"));
    log("token minted, model "+(tok.model||"?"));
  } catch(e){ setStatus("token","fail",String(e)); finish("token error"); return; }

  // 3) WebRTC to OpenAI Realtime
  try {
    pc=new RTCPeerConnection();
    pc.oniceconnectionstatechange=()=>log("ice: "+pc.iceConnectionState);
    pc.onconnectionstatechange=()=>{
      log("conn: "+pc.connectionState);
      if(pc.connectionState==="connected") setStatus("webrtc","ok","connected");
      if(pc.connectionState==="failed") setStatus("webrtc","fail","connection failed");
    };
    pc.ontrack=(ev)=>{
      const b=el("bot"); b.srcObject=ev.streams[0]; b.play().catch(err=>log("play() warn: "+err));
      setStatus("audioout","ok","receiving bot voice");
      log("remote audio track received");
    };
    micStream.getTracks().forEach(t=>pc.addTrack(t,micStream));
    const dc=pc.createDataChannel("oai-events");
    dc.onopen=()=>{
      log("data channel open - asking bot to greet");
      try { dc.send(JSON.stringify({type:"response.create", response:{instructions:"Greet me warmly: one short sentence in English, then one short sentence in Chinese (中文). Then ask what topic I want to learn about on my walk. Keep it under 8 seconds."}})); } catch(e){ log("greet send err: "+e); }
    };
    dc.onmessage=(e)=>{ try{ handleEvent(JSON.parse(e.data)); }catch(_){ } };

    const offer=await pc.createOffer();
    await pc.setLocalDescription(offer);
    log("posting SDP offer to OpenAI...");
    const resp=await fetch("https://api.openai.com/v1/realtime/calls",{
      method:"POST", body:offer.sdp,
      headers:{ "Authorization":"Bearer "+tok.value, "Content-Type":"application/sdp" }
    });
    if(!resp.ok){ const t=await resp.text(); setStatus("webrtc","fail","SDP "+resp.status); log("SDP FAIL "+resp.status+": "+t.slice(0,200)); finish("webrtc error"); return; }
    const answer=await resp.text();
    await pc.setRemoteDescription({type:"answer", sdp:answer});
    setStatus("webrtc","ok","negotiated - say hello!");
    log("connected. Talk now. Auto-stops in 30s.");
    startCountdown();
  } catch(e){ setStatus("webrtc","fail",String(e)); log("webrtc error: "+e); finish("webrtc error"); }
}

function handleEvent(ev){
  const t=ev.type||"";
  if(t.indexOf("speech_started")>=0){ setStatus("heard","ok","it heard you talk"); log("event: "+t); }
  else if(t.indexOf("audio")>=0 && t.indexOf("delta")>=0){ if(state.spoke!=="ok"){ setStatus("spoke","ok","bot is speaking"); log("bot audio output started"); } }
  else if(t==="response.done"){ log("bot finished a turn"); }
  else if(t==="error"){ setStatus("spoke","warn","oai event error"); log("OAI error event: "+JSON.stringify(ev.error||ev).slice(0,240)); }
  else { /* keep log readable */ if(["session.created","session.updated","response.created"].includes(t)) log("event: "+t); }
}

function startMeter(stream){
  try{
    const src=audioCtx.createMediaStreamSource(stream);
    const an=audioCtx.createAnalyser(); an.fftSize=256; src.connect(an);
    const data=new Uint8Array(an.fftSize);
    let peakHold=0;
    (function loop(){
      an.getByteTimeDomainData(data);
      let peak=0; for(const v of data){ const d=Math.abs(v-128); if(d>peak)peak=d; }
      const level=peak/128;
      el("meterFill").style.width=Math.min(100, Math.round(level*220))+"%";
      if(level>0.05){ peakHold++; if(peakHold>2) setStatus("meter","ok","capturing your voice"); }
      requestAnimationFrame(loop);
    })();
  }catch(e){ log("meter err: "+e); }
}

function startCountdown(){
  secsLeft=30; el("start").textContent="Listening... 30s";
  timer=setInterval(()=>{
    secsLeft--; el("start").textContent="Listening... "+secsLeft+"s";
    if(secsLeft<=0) finish("done");
  },1000);
}

function finish(reason){
  if(timer){ clearInterval(timer); timer=null; }
  try{ if(pc) pc.close(); }catch(e){}
  try{ if(micStream) micStream.getTracks().forEach(t=>t.stop()); }catch(e){}
  el("start").disabled=false; el("start").textContent="Run again";
  log("stopped ("+reason+")");
  el("meterFill").style.width="0%";
}

el("start").addEventListener("click", run);
el("copy").addEventListener("click", ()=>{
  const summary=CHECKS.map(([id,nm])=>`${nm}: ${state[id]} ${el("dt-"+id).textContent}`).join("\n");
  const text=`Idea Companion smoke test\n${ctxText}\n\n${summary}\n\n--- log ---\n${el("log").textContent}`;
  navigator.clipboard.writeText(text).then(()=>{ el("copy").textContent="Copied! paste it to JJ"; setTimeout(()=>el("copy").textContent="Copy diagnostics",2500); }).catch(()=>{ el("copy").textContent="copy failed - screenshot instead"; });
});
</script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("__VERSION__", VERSION)
