// Run 172 — observable activity + latest-revision generated-file preview.
import fs from 'node:fs';
const src = fs.readFileSync(process.argv[2], 'utf8');
const css = fs.readFileSync(process.argv[3], 'utf8');
let passed = 0, failed = 0;
function ok(cond, name) { if (cond) passed++; else { failed++; console.error('FAIL ' + name); } }
function extract(name) {
  const start = src.indexOf('function ' + name + '('); if (start < 0) throw new Error('missing ' + name);
  let depth=0,began=false,quote='',esc=false,line=false,block=false;
  for (let i=start;i<src.length;i++) { const c=src[i],n=src[i+1];
    if(line){if(c==='\n')line=false;continue;} if(block){if(c==='*'&&n==='/'){block=false;i++;}continue;}
    if(quote){if(esc){esc=false;continue;}if(c==='\\'){esc=true;continue;}if(c===quote)quote='';continue;}
    if(c==='/'&&n==='/'){line=true;i++;continue;} if(c==='/'&&n==='*'){block=true;i++;continue;}
    if(c==='"'||c==="'"||c==='`'){quote=c;continue;} if(c==='{'){depth++;began=true;} else if(c==='}'&&--depth===0&&began)return src.slice(start,i+1);
  } throw new Error('unterminated '+name);
}
const start=extract('_startTurnActivity'), finish=extract('_activityFinish'), completed=extract('_activityResponseCompleted');
const wire=extract('_activityIngestWireEvent'), metadata=extract('_activityIngestResponseMetadata');
const artifact=extract('_registerGeneratedArtifact'), bind=extract('_generatedArtifactBindLatest');
const openLatest=extract('_generatedArtifactOpenLatest'), downloadLatest=extract('_generatedArtifactDownloadLatest');
const sync=extract('_syncExplicitCodeArtifacts'), changed=extract('_appendChangedFileSummary');
const fence=extract('_parseCodeFenceInfo'), safePathSrc=extract('_generatedArtifactSafePath');
const submit=extract('handleAIPanelSubmit'), clear=extract('clearConversation');
const stopActive=extract('_stopActivePanelResponse'), ensureActive=extract('_panelTurnEnsureActive');
const apiCall=extract('_panelApiCall'), streamCall=extract('_panelApiCallStreaming');
const delay=extract('_panelTurnDelay'), sessionBudget=extract('_generatedArtifactEnsureSessionBudget');
const retentionUnavailable=extract('_generatedArtifactMakeRetentionUnavailable');
const fetchFallback=extract('_fetchWithReasoningFallback');

ok(src.includes('_TURN_ACTIVITY_MAX_STEPS = 48')&&src.includes('_TURN_ACTIVITY_LABEL_MAX_CHARS = 180')&&src.includes('_TURN_ACTIVITY_DETAIL_MAX_CHARS = 2000'),'activity metadata has explicit bounded limits');
ok(src.includes('_TURN_ACTIVITY_FILE_MAX_BYTES = 256 * 1024')&&src.includes('_TURN_ACTIVITY_FILE_TOTAL_MAX_BYTES = 1024 * 1024')&&src.includes('_TURN_ACTIVITY_FILE_SESSION_TOTAL_MAX_BYTES = 8 * 1024 * 1024')&&src.includes('_TURN_ACTIVITY_FILE_MAX_COUNT = 24'),'file previews have per-file/per-turn/session/count bounds');
ok(start.includes('Hidden model reasoning is never displayed.'),'surface distinguishes public activity from hidden reasoning');
ok(start.includes("stop.textContent = 'Stop'")&&start.includes('_stopActivePanelResponse()')&&stopActive.includes('controller.abort()')&&stopActive.includes("reader.cancel('AI_REQUEST_CANCELLED')"),'visible stop tears down fetch and stream reader');
ok(stopActive.includes('_panelUnlockComposerAfterCancel()'),'Stop immediately unlocks composer instead of waiting on transport teardown');
ok(finish.includes('panelActivityAutoCollapse')&&finish.includes('_activitySetOpen(st, false)'),'completed activity auto-collapses');
ok(completed.includes("st.state !== 'running'"),'late completion cannot overwrite stopped state');
ok(start.includes("panelActivityTimeline === false")&&start.includes("_activeTurnActivity = st")&&submit.includes("!turnActivity.root"),'timeline-off mode retains headless turn state and legacy typing fallback');
ok(src.includes('_panelActiveRequestToken')&&ensureActive.includes('_panelActiveRequestToken !== token')&&submit.includes('requestToken = { id: ++_panelRequestTokenSeq'),'turn ownership is independent of AbortController and visualization');
ok(delay.includes('_panelActiveRequestToken !== requestToken')&&delay.includes("activity.state === 'cancelled'"),'local slow work observes turn-owned cancellation');
ok(apiCall.includes('requestController ? requestController.signal : undefined')&&!apiCall.includes('_fetchAbortController ? _fetchAbortController.signal'),'non-stream request uses captured controller, not replaceable global controller');
ok(streamCall.includes('_panelActiveStreamOwner = { reader: reader, activity: activity }')&&streamCall.includes('_panelTurnEnsureActive(activity, requestController, requestToken)'),'stream reader is turn-owned and guarded before continuation');
ok(streamCall.includes('streamBubble.parentNode.removeChild(streamBubble)')&&streamCall.includes("throw new Error('AI_STREAM_BROKEN_PIPE')"),'broken-pipe/reader fallback paths remove orphan provisional bubbles');
ok(fetchFallback.includes('shouldContinue')&&fetchFallback.includes('ensureContinuation()'),'reasoning fallback cannot launch retry after turn cancellation');
ok(clear.includes('_panelActiveRequestToken.cancelled = true')&&clear.includes("reader.cancel('AI_CONVERSATION_CLEARED')"),'conversation clear invalidates token and active reader');

ok(wire.includes("kind === 'thinking'")&&wire.includes("kind === 'reasoning'")&&wire.includes("kind === 'chain_of_thought'")&&wire.includes("kind = 'summary'"),'reasoning-shaped kinds normalize to public summary');
ok(wire.includes('_redactSecrets(String(payload.label')&&wire.includes('_redactSecrets(String(payload.detail'),'public activity is secret-redacted');
ok(wire.includes('Sensitive token pattern redacted from activity metadata'),'redaction warning is bounded');
ok(!wire.includes('payload.chain_of_thought')&&!wire.includes('payload.thinking')&&!wire.includes('payload.reasoning'),'raw hidden reasoning fields are never rendered');
ok(metadata.includes('data.activity')&&metadata.includes('data.artifacts')&&metadata.includes('_TURN_ACTIVITY_MAX_STEPS')&&metadata.includes('_TURN_ACTIVITY_FILE_MAX_COUNT'),'buffered sidecars are bounded');
ok(src.includes("sseEventType === 'activity' || sseEventType === 'assistant.activity'")&&src.includes("sseEventType === 'artifact' || sseEventType === 'assistant.artifact'"),'SSE supports public activity/artifact event forms');
ok(src.includes('_activityIngestWireEvent(activity, publicEvent)')&&src.includes('_activityIngestArtifactEvent(activity, publicEvent)'),'SSE events feed bounded registries');

ok(artifact.includes('old ? old.revision + 1 : 1'),'changed content increments revision');
ok(artifact.includes('_generatedArtifactIsAvailable(old)')&&artifact.includes('old.content === content')&&artifact.includes('return old'),'identical currently-available content reuses revision');
ok(artifact.includes('_generatedArtifactLedger[path] = entry'),'ledger is keyed by canonical path');
ok(bind.includes('_generatedArtifactOpenLatest(key, el)')&&bind.includes('_generatedArtifactRefs[key]'),'historical controls bind by key');
ok(openLatest.includes('var entry = _generatedArtifactLedger[key]'),'preview resolves latest at click');
ok(downloadLatest.includes('var entry = _generatedArtifactLedger[key]'),'download resolves latest at click');
ok(changed.includes("title.textContent = 'Changed files'")&&changed.includes('every link opens the latest revision'),'answer gets separate latest-revision Changed files section');
ok(changed.includes("all.textContent = 'Download all latest files'")&&changed.includes('var entry = _generatedArtifactLedger[key]'),'bulk download re-resolves latest files');
ok(changed.includes('_attachmentPathAlias(entry.path)')&&changed.includes('aliasCollision')&&changed.includes('portable filesystem'),'bulk download fails closed on portable path collisions');
ok(sessionBudget.includes('_generatedArtifactMakeRetentionUnavailable')&&sessionBudget.includes('Released older file preview'),'session pressure evicts oldest retained previews instead of silently exceeding memory');
ok(retentionUnavailable.includes("entry.state = 'unavailable'")&&retentionUnavailable.includes('entry.content = null')&&!retentionUnavailable.includes('entry.revision + 1'),'local retention eviction invalidates bytes without inventing a file revision');
ok(sync.includes(".ai-md-pre[data-artifact-path]")&&sync.includes('_registerGeneratedArtifact'),'annotated fences feed ledger');
ok(src.includes('_syncExplicitCodeArtifacts(streamBubble, activity)'),'stream registers completed file fences before finish');
ok(src.includes('data-artifact-path=')&&src.includes('_parseCodeFenceInfo(info ||'),'markdown preserves safe file metadata');
ok(fence.includes('(?:file|filename|path)=')&&fence.includes('_generatedArtifactSafePath'),'fence aliases pass through safe path validation');
ok(submit.includes('_startTurnActivity(body')&&submit.includes('_activityFinish(turnActivity'),'submit owns one activity per turn');
ok(clear.includes('_generatedArtifactLedger = Object.create(null)')&&clear.includes('_generatedArtifactRefs = Object.create(null)'),'clear resets file revision authority');
ok(src.includes('browser preview/download entry; it does not mean the file was applied to a repository.'),'preview is never represented as write authority');

ok(css.includes('.ai-assistant-panel-activity')&&css.includes('.ai-assistant-panel-activity-stop')&&css.includes('.ai-assistant-panel-activity-step'),'activity has dedicated styles');
ok(css.includes('.ai-assistant-panel-changed-files')&&css.includes('.ai-assistant-panel-changed-file-preview'),'changed files have dedicated styles');
ok(css.includes('@media (prefers-reduced-motion: reduce)')&&css.includes('animation: none'),'reduced motion is respected');
ok(css.includes('@media (max-width: 560px)')&&css.includes('.ai-assistant-panel-changed-file {'),'mobile layout exists');
ok(css.includes('[data-artifact-unavailable]'),'unavailable latest-state controls have visible warning styling');

const safePathFactory = new Function(`
  var _ATTACHMENT_IMPORT_MAX_PATH_CHARS = 1024;
  ${extract('_attachmentSafeRelativePath')}
  ${safePathSrc}
  return _generatedArtifactSafePath;
`);
const safePath=safePathFactory();
ok(safePath('src/example.py')==='src/example.py'&&safePath('a/b/config.toml')==='a/b/config.toml','normal relative paths accepted');
ok(safePath('../secret')===''&&safePath('/etc/passwd')===''&&safePath('C:/x')===''&&safePath('a\\b')==='','traversal/absolute/drive/backslash rejected');
ok(safePath('a/./b')===''&&safePath('a//b')===''&&safePath('a/\u202esecret')==='','dot/empty/bidi aliases rejected');
ok(fence.includes('file|filename|path')||fence.includes('(?:file|filename|path)'),'fence parser recognizes file metadata aliases');

const stepSrc=extract('_activityAddStep');
ok(stepSrc.includes('else if (detail)')&&stepSrc.includes("ai-assistant-panel-activity-step-detail"),'running step can gain detail when a later update completes it');
ok(src.includes("reviewed.action === 'cancel' || opConversationId !== boundConversationId || opConversationId !== _getConversationId()"),'share review conversation-race guard remains intact');
ok(src.includes('localActiveModel, turnActivity')&&src.includes("'assistant', undefined, { activity: activity }"),'browser-local replies remain attached to the turn activity surface');

// Run-time latest-state safety: execute the real registration/state functions
// with only DOM-free dependencies stubbed.
const latestFactory = new Function(`
  var _generatedArtifactLedger = Object.create(null);
  var _generatedArtifactRefs = Object.create(null);
  var _TURN_ACTIVITY_FILE_MAX_BYTES = 262144;
  var _TURN_ACTIVITY_FILE_TOTAL_MAX_BYTES = 1048576;
  var _TURN_ACTIVITY_FILE_SESSION_TOTAL_MAX_BYTES = 8 * 1024 * 1024;
  var _TURN_ACTIVITY_FILE_MAX_COUNT = 24;
  function _cfg(){ return {panelGeneratedFilePreview:true}; }
  function _generatedArtifactSafePath(v){
    if (typeof v !== 'string') return '';
    var p=v.trim(); if(!p || p[0]==='/' || p.includes('\\\\') || /^[A-Za-z]:/.test(p)) return '';
    var a=p.split('/'); if(a.some(x=>!x||x==='.'||x==='..')) return ''; return p;
  }
  function _activityBoundedText(v,n){ return String(v == null ? '' : v).slice(0,n); }
  function _utf8ByteLength(v){ return Buffer.byteLength(String(v),'utf8'); }
  function _activityAddStep(){}
  function _activityAddArtifactStep(){}
  function _generatedArtifactRefreshRefs(){}
  ${extract('_generatedArtifactIsAvailable')}
  ${extract('_generatedArtifactSessionBytes')}
  ${retentionUnavailable}
  ${sessionBudget}
  ${extract('_generatedArtifactPublishState')}
  ${extract('_registerGeneratedArtifact')}
  return {ledger:_generatedArtifactLedger, register:_registerGeneratedArtifact};
`);
function turnState(){ return {fileBytesByKey:Object.create(null),filePreviewBytes:0,changedFileKeys:Object.create(null),fileRevisionCount:0}; }
const rt=latestFactory(), st=turnState();
let e=rt.register({path:'src/a.py',content:'one',mediaType:'text/plain',source:'endpoint'},st);
ok(e&&e.revision===1&&e.state==='available'&&e.content==='one','r1 is retained as available latest revision');
e=rt.register({path:'src/a.py',content:'x'.repeat(262145),source:'endpoint'},st);
ok(e&&e.revision===2&&e.state==='unavailable'&&e.content===null,'oversized r2 invalidates stale r1');
e=rt.register({path:'src/a.py',content:'three',source:'endpoint'},st);
ok(e&&e.revision===3&&e.state==='available'&&e.content==='three','later valid r3 restores previewability');
e=rt.register({path:'src/a.py',operation:'remove',source:'endpoint'},st);
ok(e&&e.revision===4&&e.state==='removed'&&e.content===null,'remove creates authoritative latest tombstone');
e=rt.register({path:'src/a.py',content:'five',source:'endpoint'},st);
ok(e&&e.revision===5&&e.state==='available','path becomes available again after tombstone');
const dup=rt.register({path:'src/a.py',content:'five',source:'endpoint'},st);
ok(dup.revision===5,'exact currently-available duplicate does not invent revision');
const empty=rt.register({path:'src/empty.txt',content:'',source:'endpoint'},st);
ok(empty&&empty.state==='available'&&empty.content==='','empty complete file remains a valid latest revision');
const missing=rt.register({path:'src/a.py',source:'endpoint'},st);
ok(missing&&missing.revision===6&&missing.state==='unavailable'&&missing.content===null,'missing newer content invalidates prior retained bytes');
const rt2=latestFactory(), st2=turnState();
let agg=rt2.register({path:'src/a.txt',content:'old'},st2);
st2.filePreviewBytes=1048576; st2.fileBytesByKey['src/a.txt']=3;
agg=rt2.register({path:'src/a.txt',content:'1234'},st2);
ok(agg&&agg.revision===2&&agg.state==='unavailable'&&agg.content===null,'aggregate-budget rejection invalidates stale existing revision');

const rt3=latestFactory(), st3=turnState();
for (let i=0;i<32;i++) rt3.register({path:`old/${i}.txt`,content:'z'.repeat(262144),source:'endpoint'},turnState());
const beforeOldRevision=rt3.ledger['old/0.txt'].revision;
const newest=rt3.register({path:'newest.txt',content:'n'.repeat(1024),source:'endpoint'},st3);
ok(newest&&newest.state==='available','session budget admits newest preview by releasing older retained bytes');
ok(rt3.ledger['old/0.txt'].state==='unavailable'&&rt3.ledger['old/0.txt'].content===null&&rt3.ledger['old/0.txt'].revision===beforeOldRevision,'session eviction makes old preview unavailable without inventing revision');

console.log(`${passed} passed, ${failed} failed`); if(failed)process.exit(1);
