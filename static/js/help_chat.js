function $(id){ return document.getElementById(id); }

const chatBox = $("chatBox");
const helpId = parseInt($("helpId").value);
const me = $("me").value;
const peer = $("peer").value;
const input = $("msgInput");
const sendBtn = $("sendBtn");

let lastRenderCount = 0;

async function fetchMessages(){
  try{
    const q = new URLSearchParams({help_id: helpId, me, peer});
    const res = await fetch(`/api/messages?${q.toString()}`);
    const data = await res.json();
    if(Array.isArray(data)){
      if(data.length !== lastRenderCount){
        chatBox.innerHTML = "";
        data.forEach(m => {
          const mine = m.sender === me;
          const wrap = document.createElement('div');
          wrap.className = `my-1 flex ${mine ? 'justify-end' : 'justify-start'}`;
          const bubble = document.createElement('div');
          bubble.className = `max-w-[75%] px-3 py-2 rounded-2xl ${mine ? 'bg-blue-600 text-white' : 'bg-gray-100'}`;
          bubble.innerText = m.content;
          wrap.appendChild(bubble);
          chatBox.appendChild(wrap);
        });
        chatBox.scrollTop = chatBox.scrollHeight;
        lastRenderCount = data.length;
      }
    }
  }catch(e){ console.error(e); }
}

async function sendMessage(){
  const content = input.value.trim();
  if(!content) return;
  try{
    await fetch('/api/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({help_id: helpId, sender: me, receiver: peer, content})
    });
    input.value = "";
    fetchMessages();
  }catch(e){ console.error(e); }
}

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e)=>{ if(e.key === 'Enter') sendMessage(); });

fetchMessages();
setInterval(fetchMessages, 2000);