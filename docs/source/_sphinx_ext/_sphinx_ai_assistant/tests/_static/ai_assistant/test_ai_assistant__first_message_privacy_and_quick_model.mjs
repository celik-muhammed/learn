// Run 171 — first-message privacy status + quick answer-menu model switcher.
import fs from 'node:fs';
const src = fs.readFileSync(process.argv[2], 'utf8');
const css = fs.readFileSync(process.argv[3], 'utf8');
let passed = 0, failed = 0;
function ok(cond, name) { if (cond) passed++; else { failed++; console.error('FAIL ' + name); } }
function extract(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('missing ' + name);
  let depth = 0, began = false, quote = '', esc = false, line = false, block = false;
  for (let i = start; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (line) { if (c === '\n') line = false; continue; }
    if (block) { if (c === '*' && n === '/') { block = false; i++; } continue; }
    if (quote) { if (esc) { esc = false; continue; } if (c === '\\') { esc = true; continue; } if (c === quote) quote = ''; continue; }
    if (c === '/' && n === '/') { line = true; i++; continue; }
    if (c === '/' && n === '*') { block = true; i++; continue; }
    if (c === '"' || c === "'" || c === '`') { quote = c; continue; }
    if (c === '{') { depth++; began = true; }
    else if (c === '}' && --depth === 0 && began) return src.slice(start, i + 1);
  }
  throw new Error('unterminated ' + name);
}

const append = extract('_appendPanelMessage');
const replay = extract('_replayTranscript');
const banner = extract('_buildFirstMessagePrivacyBanner');
const more = extract('_buildBubbleMore');
const close = extract('_closeBubbleMoreWrapper');
const position = extract('_positionBubbleMoreMenuWithinPanelBody');
const select = extract('_selectQuickModel');
const candidates = extract('_quickModelCandidates');

ok(append.includes("body.querySelector('.ai-assistant-pagehelp')") && append.includes('pageHelp.remove()'), 'first send removes stale Explain-this-page onboarding');
ok(append.includes('var firstRealMessage = _transcript.length === 0') && append.includes('_ensureFirstMessagePrivacyBanner(body)'), 'privacy row is installed at first real message commit');
ok(replay.includes('if (_transcript.length) _ensureFirstMessagePrivacyBanner(body)'), 'restored transcript restores its top privacy status row');
ok(banner.includes("banner.setAttribute('role', 'note')"), 'privacy row has semantic note role');
ok(banner.includes("copy.appendChild(document.createTextNode(_firstMessagePrivacyText() + ' '))"), 'privacy copy is inserted as text rather than trusted HTML');
ok(banner.includes("'ai-assistant-open-privacy'"), 'More information routes to existing privacy sheet');
ok(src.includes(".addEventListener('ai-assistant-open-privacy'"), 'panel owns internal privacy-sheet routing event');
ok(src.includes(".addEventListener('ai-assistant-open-model-configuration'"), 'panel owns model-configuration routing event');

ok(more.indexOf("modelToggleLabel.textContent = 'Change model'") < more.indexOf("retryMenuLbl.textContent = 'Retry'"), 'Change model is first answer-menu action before Retry');
ok(more.includes("modelHeading.textContent = 'Try a different model'"), 'expanded list uses requested try-a-different-model heading');
ok(more.includes('if (quickDisplayModels.length >= 6) return') && more.includes('if (activeQuickModel) quickDisplayModels.push(activeQuickModel)'), 'quick menu is bounded to six choices while keeping the active model visible');
ok(more.includes("'View all ' + quickModels.length + ' models…'") && more.includes("'Model configuration…'"), 'full model sheet remains escape hatch for long/short lists');
ok(more.includes("modelBtn.setAttribute('role', 'menuitemradio')") && more.includes("modelBtn.setAttribute('aria-checked'"), 'model choices expose radio semantics and active state');
ok(more.includes("providerLabel + ' · ' + modelWire"), 'quick rows include provider and wire-model metadata');
ok(more.includes('var currentModels = _quickModelCandidates(_cfg())') && more.includes("modelList.addEventListener('keydown'") && more.includes("'ArrowDown'") && more.includes("'Home'") && more.includes("'End'"), 'quick model list refreshes active state and supports keyboard traversal');
ok(close.includes("'.ai-assistant-panel-bubble-action--model-toggle'") && close.includes("'.ai-assistant-panel-bubble-model-list'"), 'closing More also collapses model disclosure');
ok(position.includes('minWidth: hasModels ? 224 : 144') && position.includes('maxWidth: hasModels ? 320 : 220'), 'boundary coordinator grants model menu a wider bounded surface');
ok(select.includes('_setActiveModelId(m.id)') && select.includes("'ai-assistant-model-change'") && select.includes('_syncInlinePickers(m.id)') && select.includes('_syncModelSheet(m.id)'), 'quick selection uses canonical model state and sync event');
ok(candidates.includes('!m.disabled') && candidates.includes('!_MODEL_STORE.isHiddenBuiltin(m.id)') && candidates.includes('_MODEL_STORE.listCustom()'), 'quick list excludes disabled/removed models and includes custom models');
ok(css.includes('.ai-assistant-panel-chat-privacy') && css.includes('.ai-assistant-panel-chat-privacy-more'), 'privacy status has dedicated responsive styling');
ok(css.includes('.ai-assistant-panel-bubble-model-option') && css.includes('[aria-checked="true"]'), 'quick model rows and active checkmark are styled');

// Runtime: provider display labels are stable and human-readable.
const providerLabel = (0, eval)('(' + extract('_quickModelProviderLabel') + ')');
ok(providerLabel('openai') === 'OpenAI' && providerLabel('huggingface') === 'Hugging Face' && providerLabel('acme') === 'acme', 'provider label normalization preserves unknown custom providers');

// Runtime: candidate filtering mirrors canonical override/tombstone authority.
const candidateFactory = new Function(`
  const _MODEL_STORE = {
    registerBuiltin(){},
    applyOverrides(xs){ return xs.map(x => Object.assign({}, x)); },
    isHiddenBuiltin(id){ return id === 'hidden'; },
    listCustom(){ return [{id:'custom',label:'Custom',provider:'custom',model:'wire/custom'}]; }
  };
  ${candidates}
  return _quickModelCandidates;
`);
const list = candidateFactory()({panelApiModels:[
  {id:'a',label:'A',provider:'openai',model:'gpt-a'},
  {id:'disabled',disabled:true},
  {id:'hidden'}
]});
ok(list.map(x => x.id).join(',') === 'a,custom', 'runtime candidate list filters disabled/tombstoned rows and appends custom rows');

// Runtime: defaults never fabricate zero-retention/no-training guarantees.
const privacyTextSource = extract('_firstMessagePrivacyText');
function privacyText(cfg, localFallback) {
  return new Function('_cfg','_getActiveModel','_stubUsesLocalFallback', `return (${privacyTextSource})();`)(
    () => cfg, () => ({id:'m'}), () => localFallback
  );
}
ok(privacyText({panelChatPrivacyText:'Verified private route'}, false) === 'Verified private route', 'operator verified plain-text privacy copy can override default');
ok(privacyText({panelApiEnabled:false,panelChatPrivacyText:''}, false).startsWith('Local chat.'), 'local default clearly says local chat');
ok(privacyText({panelApiEnabled:true,panelChatPrivacyText:''}, false).includes('depend on that provider'), 'API default defers retention/training claims to provider policy');
ok(!privacyText({panelApiEnabled:true,panelChatPrivacyText:''}, false).includes('Zero data retention'), 'API default does not invent a zero-retention claim');

console.log(`${passed} passed, ${failed} failed`);
if (failed) process.exit(1);
