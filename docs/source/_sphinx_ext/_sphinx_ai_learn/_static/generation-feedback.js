/* Reviewed feedback for accepted AI Learn section generations. */
(() => {
  'use strict';
  const one=(root,selector)=>root?.querySelector?.(selector)||null;
  const all=(root,selector)=>root?.querySelectorAll?[...root.querySelectorAll(selector)]:[];
  function pageData(root){
    const page=root.closest?.('[data-learn-page]')||document.querySelector('[data-learn-page]');
    try{return JSON.parse(one(page,'.learn-page-data')?.textContent||'{}');}catch{return{};}
  }
  function feedbackId(){
    const crypto=globalThis.crypto;
    if(crypto?.randomUUID){
      return 'feedback-'+crypto.randomUUID().replace(/-/g,'').toLowerCase();
    }
    if(crypto?.getRandomValues){
      const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
      return 'feedback-'+[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');
    }
    return '';
  }
  function bind(root){
    const section=root.closest('.learn-section'),data=pageData(root),subject=data.subject||{};
    const generationId=String(root.dataset.generationId||section?.dataset.activeGenerationId||'').trim();
    const sectionId=String(root.dataset.feedbackSectionId||section?.dataset.section||'').trim();
    if(!generationId||!sectionId||!subject.id)return;
    const quick=all(root,'[data-learn-feedback-quick]'),expand=one(root,'[data-learn-feedback-expand]'),detail=one(root,'[data-learn-feedback-detail]'),ratings=all(root,'[data-learn-feedback-rating]'),submit=one(root,'[data-learn-feedback-submit]'),comment=one(root,'[data-learn-feedback-comment]'),contributor=one(root,'[data-learn-feedback-contributor]'),status=one(root,'[data-learn-feedback-status]'),historyOrder=one(root,'[data-learn-generation-order]'),historyList=one(root,'[data-learn-generation-history-list]');
    const pendingKey='learn-ai-feedback-pending:v1:'+String(subject.id)+':'+sectionId+':'+generationId;
    const quickKey='learn-ai-feedback-quick:v1:'+String(subject.id)+':'+sectionId+':'+generationId;
    function readPending(){
      try{
        const row=JSON.parse(sessionStorage.getItem(pendingKey)||'null'),request=row?.request;
        if(!row||typeof row.fingerprint!=='string'||!request||request.action!=='feedback'||request.subject_id!==String(subject.id)||request.section_id!==sectionId||request.generation_id!==generationId||!/^feedback-[0-9a-f]{32}$/.test(String(request.feedback_id||'')))return null;
        return row;
      }catch{return null;}
    }
    function writePending(value){try{if(value)sessionStorage.setItem(pendingKey,JSON.stringify(value));else sessionStorage.removeItem(pendingKey);}catch{}}
    function readQuick(){try{const value=Number(sessionStorage.getItem(quickKey));return value===-1||value===1?value:null;}catch{return null;}}
    function writeQuick(value){try{if(value===-1||value===1)sessionStorage.setItem(quickKey,String(value));else sessionStorage.removeItem(quickKey);}catch{}}
    let selected=null,busy=false,pending=readPending();
    const priorQuick=readQuick();if(priorQuick!==null)quick.forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.learnFeedbackQuick)===priorQuick)));
    const announce=value=>{if(status)status.textContent=String(value||'');};
    function setBusy(value){busy=value;quick.forEach(button=>button.disabled=value);ratings.forEach(button=>button.disabled=value);if(submit)submit.disabled=value||selected===null;if(expand)expand.disabled=value;}
    function orderHistory(mode){
      if(!historyList)return;
      const rows=[...historyList.children];
      const score=row=>Number(row.dataset.generationHistoryScore||0);
      const ratingsCount=row=>Number(row.dataset.generationHistoryRatings||0);
      const created=row=>String(row.dataset.generationHistoryCreatedAt||'');
      const id=row=>String(row.dataset.generationHistoryId||'');
      const active=row=>row.dataset.generationHistoryActive==='true';
      rows.sort((a,b)=>{
        if(mode==='newest')return created(b).localeCompare(created(a))||id(a).localeCompare(id(b));
        if(mode==='rating')return score(b)-score(a)||ratingsCount(b)-ratingsCount(a)||created(b).localeCompare(created(a))||id(a).localeCompare(id(b));
        return Number(active(b))-Number(active(a))||score(b)-score(a)||created(b).localeCompare(created(a))||id(a).localeCompare(id(b));
      });
      rows.forEach(row=>historyList.appendChild(row));
    }
    function select(value){selected=value;ratings.forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.learnFeedbackRating)===value)));if(submit)submit.disabled=busy;}
    async function send(rating,textValue='',credit='',mode='detailed'){
      if(busy)return;
      if(!Number.isInteger(rating)||rating < -5||rating > 5){announce('Choose a rating from -5 to +5.');return;}
      const ui=window.AI_LEARN_GENERATION_UI;
      if(!ui?.submitPublication){announce('Reviewed feedback transport is unavailable.');return;}
      const clean=String(textValue||'').trim().slice(0,2000);
      let displayName='';
      try{displayName=ui.normalizePublicationCredit?ui.normalizePublicationCredit(credit):String(credit||'').replace(/\s+/g,' ').trim();}
      catch(error){announce(String(error?.message||'Invalid public credit.'));return;}
      if(displayName.length>80){announce('Contributor credit must be plain text of at most 80 characters.');return;}
      const fingerprint=JSON.stringify([rating,clean,displayName,mode]);
      // Reuse the exact envelope after an ambiguous transport failure.  The
      // repository treats feedback_id as an idempotency key, so retrying cannot
      // double-count a request whose PR dispatch succeeded but whose response
      // was lost.  Editing the rating/comment/credit intentionally creates a
      // fresh event instead.
      if(!pending||pending.fingerprint!==fingerprint){
        const id=feedbackId();
        if(!id){announce('Secure feedback identity is unavailable in this browser.');return;}
        const request={contract:'learn.publication-request.v1',action:'feedback',base_revision:String(data.revision||''),subject_id:String(subject.id),section_id:sectionId,generation_id:generationId,feedback_id:id,rating,feedback_mode:mode,contributor:{display_name:displayName}};
        if(clean)request.comment=clean;
        pending={fingerprint,request};writePending(pending);
      }
      setBusy(true);announce('Sending feedback for repository review…');
      try{
        const receipt=await ui.submitPublication(pending.request);
        pending=null;writePending(null);
        announce(ui.publicationReceiptMessage?.(receipt)||String(receipt?.message||'Feedback queued for review.'));
        if(receipt?.mode==='stub'){
          announce('Feedback validated in stub mode; no repository write occurred.');
        }else if(mode==='quick'){
          quick.forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.learnFeedbackQuick)===rating)));writeQuick(rating);
        }
        if(detail&&!detail.hidden){detail.hidden=true;if(expand)expand.setAttribute('aria-expanded','false');}
        if(comment)comment.value='';if(contributor)contributor.value='';select(null);
      }catch(error){announce('Unable to send feedback: '+String(error?.message||error)+' Retry will reuse the same feedback id.');}
      finally{setBusy(false);}
    }
    quick.forEach(button=>button.addEventListener('click',()=>{
      if(button.getAttribute('aria-pressed')==='true'){announce('This quick feedback is already selected for this page session.');return;}
      send(Number(button.dataset.learnFeedbackQuick),'','','quick');
    }));
    expand?.addEventListener('click',()=>{const open=detail?.hidden!==false;if(detail)detail.hidden=!open;expand.setAttribute('aria-expanded',String(open));if(open)ratings[5]?.focus();});
    ratings.forEach(button=>button.addEventListener('click',()=>select(Number(button.dataset.learnFeedbackRating))));
    submit?.addEventListener('click',()=>{if(selected===null)return;send(selected,comment?.value||'',contributor?.value||'','detailed');});
    historyOrder?.addEventListener('change',()=>orderHistory(String(historyOrder.value||'active')));
    orderHistory(String(historyOrder?.value||'active'));
    setBusy(false);
  }
  all(document,'[data-learn-generation-feedback]').forEach(bind);
})();
