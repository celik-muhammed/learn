/* Shared AI Learn text-generation runtime helpers. */
(() => {
  'use strict';
  const CHAT_CONTRACT='scikitplot-chat-v1';
  const modelApi=()=>window.AI_ASSISTANT_MODEL_API||null;
  const endpointApi=()=>window.AI_ASSISTANT_ENDPOINT_API||null;
  function activeModel(){
    try{const api=modelApi(),state=api&&typeof api.getState==='function'?api.getState():null,active=state&&state.active;if(active&&(active.model||active.id))return{model:String(active.model||active.id),label:String(active.label||active.model||active.id),effort:state.effort||null};}catch{}
    try{const rows=Array.isArray(window.AI_ASSISTANT_CONFIG?.panelApiModels)?window.AI_ASSISTANT_CONFIG.panelApiModels:[];if(rows.length)return{model:String(rows[0].model||rows[0].id||''),label:String(rows[0].label||rows[0].model||rows[0].id||''),effort:null};}catch{}
    return{model:'',label:'Not selected',effort:null};
  }
  function chatEndpoint(){
    try{const api=endpointApi();if(api&&typeof api.resolveEndpoint==='function'){const direct=api.resolveEndpoint('chat');if(direct)return String(direct).replace(/\/+$/,'');}}catch{}
    try{const rows=Array.isArray(window.AI_ASSISTANT_CONFIG?.panelApiModels)?window.AI_ASSISTANT_CONFIG.panelApiModels:[];if(rows.length&&rows[0].endpoint)return String(rows[0].endpoint).replace(/\/+$/,'');}catch{}
    return'';
  }
  function extractReply(data){
    data=data&&typeof data==='object'?data:{};
    if(Array.isArray(data.choices)&&data.choices.length){const msg=data.choices[0]&&data.choices[0].message;if(msg&&typeof msg.content==='string'&&msg.content.trim())return msg.content.trim();}
    if(Array.isArray(data.content)){const value=data.content.filter(x=>x&&x.type==='text'&&typeof x.text==='string').map(x=>x.text).join('\n').trim();if(value)return value;}
    for(const key of ['reply','answer','text'])if(typeof data[key]==='string'&&data[key].trim())return data[key].trim();
    return'';
  }
  async function run({userMessage,pageText,pageDescriptor,maxTokens=1400,signal}){
    const endpoint=chatEndpoint(),model=activeModel();
    if(!endpoint)throw new Error('The active Assistant profile has no chat endpoint.');
    if(!model.model)throw new Error('Select an Assistant model before generating.');
    const request={contract:CHAT_CONTRACT,model:model.model,user_message:String(userMessage||'').slice(0,20000),context:{page_text:String(pageText||'').slice(0,32000),page_descriptor:String(pageDescriptor||'AI Learn text generation').slice(0,1000)},max_tokens:maxTokens,stream:false};
    const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(request),credentials:'omit',cache:'no-store',signal});
    const raw=await res.text();if(raw.length>1024*1024)throw new Error('The AI response exceeded the bounded response limit.');
    let payload={};try{payload=JSON.parse(raw||'{}');}catch{throw new Error('The AI runtime returned invalid JSON.');}
    if(!res.ok)throw new Error(String(payload?.error?.message||payload?.detail||('HTTP '+res.status)));
    const reply=extractReply(payload);if(!reply)throw new Error('The AI runtime returned no text.');
    return{reply,payload,request,model,endpoint};
  }
  function openModelPicker(button){try{const api=modelApi();return !!(api&&typeof api.openPicker==='function'&&api.openPicker(button));}catch{return false;}}
  window.AI_LEARN_TEXT_GENERATION_API={CHAT_CONTRACT,activeModel,chatEndpoint,extractReply,run,openModelPicker};
  window.dispatchEvent(new CustomEvent('ai-learn-text-generation-api-ready'));
})();
