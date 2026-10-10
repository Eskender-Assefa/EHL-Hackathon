import {api,setCsrf} from './api.js';
const $=selector=>document.querySelector(selector);
const state={tab:'feedback',page:1,pageSize:20,total:0,items:[],categories:[],selected:null,detailEpoch:0,epoch:0,controller:null,canDecide:false};
const labels={DE:'Germany',GB:'United Kingdom',US:'United States',CN:'China',JP:'Japan',KR:'South Korea',SE:'Sweden',FI:'Finland',AU:'Australia',FR:'France',DK:'Denmark',NO:'Norway',CA:'Canada',LV:'Latvia',ES:'Spain',ZA:'South Africa',EU:'EU aggregate'};
const contentFields=['title','statement','baseline_value','target_value','unit','conditions','acceptance_test','owner'];
// All source text goes through textContent; templates below contain no evidence.
function node(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=String(text);if(className)el.className=className;return el;}
function message(parent,text,kind='subtle'){parent.replaceChildren(node('p',text,kind));}
function option(select,value,text){const el=node('option',text);el.value=value;select.append(el);}
function category(id){return state.categories.find(x=>x.id===id)?.label||'Unmapped · needs review';}
function params(){const p=new URLSearchParams({model_code:$('#derivative').value||'G60',page:String(state.page),page_size:String(state.pageSize),sort:$('#sort').value,direction:$('#direction').value});
  const market=$('#market').value;if(market==='unknown')p.set('unknown_market_only','true');else if(market)p.set('market_code',market);
  for(const [id,key] of [['dataset','version_id'],['category','category_id'],['scope','scope_layer'],['origin','data_origin'],['review','review_status'],['kind','evidence_kind'],['search','q']]){if($('#'+id).value)p.set(key,$('#'+id).value);}
  return p;
}
function metricParams(){const all=params();const p=new URLSearchParams();for(const key of ['model_code','market_code','unknown_market_only','version_id','data_origin'])if(all.has(key))p.set(key,all.get(key));return p;}
function metricsApplicable(){return !['category','scope','review','search','kind'].some(id=>$('#'+id).value);}
function clearDetail(){state.selected=null;state.detailEpoch++;$('#decision-label').textContent='';message($('#detail'),'Select a record to inspect its sources or draft a requirement.');message($('#audit'),'Select a requirement to load its saved history.');$('#export-audit').disabled=true;}
function unavailable(error){$('#connection').textContent=error.message;$('#connection').classList.remove('success');message($('#list-status'),error.message,'error-box');$('#scope-table-body').replaceChildren();for(const id of ['k-feedback','k-catalogue','k-requirements','k-sessions'])$('#'+id).textContent='—';message($('#configurator-summary'),'No database results available.');clearDetail();}
async function initialize(){
  try {const h=await api('/health');setCsrf(h.csrf_token);state.canDecide=h.identity.enabled;
    $('#connection').textContent=`PostgreSQL connected · ${h.identity.enabled?h.identity.label:'Read-only; development PM identity disabled'}`;$('#connection').classList.add('success');
    const [models,markets,categories,datasets]=await Promise.all(['/models','/markets','/categories','/datasets'].map(x=>api(x)));
    state.categories=categories.items;$('#derivative').replaceChildren();for(const m of models.items)option($('#derivative'),m.id,`${m.id} · BMW`);$('#derivative').value='G60';
    $('#market').replaceChildren();option($('#market'),'','All markets');option($('#market'),'unknown','Unknown applicability only');for(const m of markets.items)option($('#market'),m.id,`${labels[m.id]||m.id} (${m.id})`);
    for(const c of categories.items)option($('#category'),c.id,`${c.id} ${c.label}`);
    for(const d of datasets.items)option($('#dataset'),d.id,`${d.source_filename} · v${d.id} · ${d.data_origin}${d.is_current?' · current':''}`);
    $('#derivative').disabled=false;$('#market').disabled=false;await refresh();
  }catch(error){unavailable(error);}
}
async function refresh(){
  const epoch=++state.epoch;state.controller?.abort();state.controller=new AbortController();const signal=state.controller.signal;clearDetail();
  message($('#list-status'),'Loading database records…');$('#scope-table-body').replaceChildren();const p=params();
  try {
    const h=await api('/health',{signal});setCsrf(h.csrf_token);state.canDecide=h.identity.enabled;
    const [feedback,catalogue,requirements,list,metrics]=await Promise.all([
      api(`/feedback?${p}`,{signal}),api(`/catalogue-facts?${p}`,{signal}),api(`/requirements?${p}`,{signal}),
      api(`/${state.tab}?${p}${state.tab==='evidence'&&!p.has('evidence_kind')?'&evidence_kind=derived_assessment':''}`,{signal}),metricsApplicable()?api(`/configurator/metrics?${metricParams()}`,{signal}):Promise.resolve(null)]);
    if(epoch!==state.epoch)return;
    $('#connection').textContent=`PostgreSQL connected · ${h.identity.enabled?h.identity.label:'Read-only; development PM identity disabled'}`;$('#connection').classList.add('success');
    $('#k-feedback').textContent=feedback.total;$('#k-catalogue').textContent=catalogue.total;
    const include=$('#unscored').checked;$('#k-requirements').textContent=include?requirements.total:0;
    const suppress=!include&&['requirements','problems'].includes(state.tab);
    state.items=suppress?[]:list.items;state.total=suppress?0:list.total;
    $('#k-sessions').textContent=metrics?metrics.completion.denominator:'—';
    renderList();$('#list-status').replaceChildren();if(!state.items.length)message($('#list-status'),suppress?'Unscored records are hidden. Enable Include Unscored requirements.':'No records match these filters. Missing records do not prove absence of customer needs.','empty');
    $('#cohort').textContent=`${p.get('model_code')} · ${$('#market').selectedOptions[0]?.textContent} · ${list.effective_filters.version_policy} · versions ${list.effective_filters.version_ids.join(', ')||'none'} · source records, not unique customers`;
    renderMetrics(metrics);
  }catch(error){if(error.name!=='AbortError'&&epoch===state.epoch)unavailable(error);}
}
function renderList(){const tbody=$('#scope-table-body');tbody.replaceChildren();
  for(const item of state.items){const tr=node('tr');tr.className='scope-row';const first=node('td');const btn=node('button',item.title,'record-button');btn.type='button';btn.dataset.recordId=item.id;btn.onclick=()=>selectRecord(item.id);first.append(btn);first.append(node('small',`ID ${item.id}${item.tag_count?` · ${item.tag_count} original tag rows`:''}`));tr.append(first);
    for(const text of [category(item.category_id),item.market_code||'Unknown',item.data_origin||item.data_origins?.join(', ')||'unknown',item.status||item.review_status,'Unscored'])tr.append(node('td',text));tbody.append(tr);}
  const pages=Math.max(1,Math.ceil(state.total/state.pageSize));$('#list-count').textContent=`${state.total} records · page ${state.page} of ${pages}`;$('#previous').disabled=state.page<=1;$('#next').disabled=state.page*state.pageSize>=state.total;
}
async function selectRecord(id){const epoch=++state.detailEpoch;const tab=state.tab;message($('#detail'),'Loading source details…');
  try {const item=await api(`/${tab}/${id}`);if(epoch!==state.detailEpoch)return;state.selected={tab,id,item};renderDetail(item,tab);
    if(tab==='requirements'){const result=await api(`/requirements/${id}/audit`);if(epoch===state.detailEpoch)renderAudit(result.items);}
    else {message($('#audit'),'Draft a requirement to begin a persistent decision history.');$('#export-audit').disabled=true;}
  }catch(error){if(epoch===state.detailEpoch)message($('#detail'),error.message,'error-box');}
}
function sourceCard(item){const box=node('section',undefined,'source');box.append(node('strong',item.source_filename||item.title));box.append(node('p',item.statement));
  const locations=(item.source_locations||[]).map(l=>l.page?`page ${l.page}`:`${l.sheet||'record'} ${l.cell_range||l.row_number}`);
  box.append(node('p',`${item.model_code} · market ${item.market_code||'unknown'} · variant ${item.variant_id||'unknown'} · version ${item.version_id} · ${item.data_origin} · ${item.review_status} · ${item.scope_layer} · ${locations.join(', ')}`,'finding-meta'));
  box.append(node('p',`Published: ${item.publication_date||'undated'} · Captured: ${item.captured_at} · ${item.evidence_kind} · source platform ${item.source_platform||'not recorded'}`,'finding-meta'));
  const meta=item.dataset_context||{};if(meta.edition_text)box.append(node('p',`Edition: ${meta.edition_text}`,'finding-meta'));
  if(item.safety_review)box.append(node('p','Potential safety report — requires human review.','uncertainty'));
  box.append(node('p',`Category mapping: ${item.mapping_status} · ${item.category_mapping_version||'not mapped'}`,'finding-meta'));
  if(item.source_url){try{const url=new URL(item.source_url);if(['http:','https:'].includes(url.protocol)){const link=node('a',url.href);link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';box.append(link);}}catch{}}
  if(item.tags?.length){const details=node('details');details.append(node('summary',`${item.tags.length} original tags / mentions`));for(const tag of item.tags)details.append(node('p',`${tag.sheet} row ${tag.row_number}: ${JSON.stringify(tag.original_tags)}`));box.append(details);}
  if(item.context?.taxonomy_note)box.append(node('p',item.context.taxonomy_note,'uncertainty'));
  return box;
}
function renderDetail(item,tab){const detail=$('#detail');detail.replaceChildren();detail.append(node('h2',item.title));$('#decision-label').textContent=tab==='requirements'?`${item.status} · revision ${item.current_revision}`:'Unreviewed source context';
  if(tab==='requirements'){detail.append(node('p',item.statement,'reqtext'));detail.append(node('p',`${item.specification_status} · ${item.priority_status}: ${item.priority_reason}`,'uncertainty'));
    detail.append(node('p',`Target: ${item.target_value??'missing'} ${item.unit||''} · Conditions: ${item.conditions||'missing'} · Acceptance: ${item.acceptance_test||'missing'} · Owner: ${item.owner||'missing'}`));
    if(item.status==='postponed')detail.append(node('p',item.review_date?`Review date: ${item.review_date}`:'Postponed without a scheduled review date.'));
    detail.append(node('p',item.permission_note,'subtle'));for(const evidence of item.evidence)detail.append(sourceCard(evidence));renderActionForm(detail,item);$('#export-audit').disabled=false;
  }else if(tab==='problems'){detail.append(node('p',item.summary,'reqtext'));for(const evidence of item.evidence)detail.append(sourceCard(evidence));detail.append(node('p','Manual proposal · Unscored · linked requirement appears in the Requirements register.','subtle'));
  }else {detail.append(sourceCard(item));if(state.canDecide){const btn=node('button','Draft a requirement from this evidence','btn primary');btn.id='draft-requirement';btn.onclick=()=>renderDraftForm(detail,item);detail.append(btn);}else detail.append(node('p','Drafting requires the enabled development PM identity.','subtle'));}
}
function field(form,name,label,type='text',value='',wide=false){const wrap=node('label',label,wide?'wide':undefined);const input=node(type==='textarea'?'textarea':'input');input.name=name;if(type!=='textarea')input.type=type;input.value=value??'';if(type==='number')input.step='any';if(['title','statement'].includes(name))input.required=true;wrap.append(input);form.append(wrap);return input;}
function contentInputs(form,item={}){field(form,'title','Requirement title','text',item.title||'',true);field(form,'statement','Measurable requirement wording','textarea',item.statement||'',true);field(form,'baseline_value','Baseline value (optional)','text',item.baseline_value||'');field(form,'target_value','Target value','number',item.target_value??'');field(form,'unit','Unit','text',item.unit||'');field(form,'owner','Owner','text',item.owner||'');field(form,'conditions','Conditions','textarea',item.conditions||'',true);field(form,'acceptance_test','Acceptance test','textarea',item.acceptance_test||'',true);}
function readContent(form){return Object.fromEntries(contentFields.map(key=>[key,form.elements.namedItem(key).value.trim()||null]));}
function renderDraftForm(parent,evidence){$('#draft-requirement')?.remove();const form=node('form');form.id='draft-form';const grid=node('div',undefined,'form-grid');form.append(node('h3','Draft requirement'));contentInputs(grid);
  const catLabel=node('label','Requirement category');const select=node('select');select.name='category_id';select.required=true;option(select,'','Select category');for(const c of state.categories)option(select,c.id,`${c.id} ${c.label}`);select.value=evidence.category_id||'';catLabel.append(select);grid.append(catLabel);
  const rationale=field(grid,'rationale','Why this evidence supports the draft','textarea','',true);rationale.required=true;form.append(grid);form.append(node('p',`Evidence ID ${evidence.id} · ${evidence.model_code} / ${evidence.market_code||'unknown'} · ${evidence.data_origin}. Missing targets remain needs_specification.`,'subtle'));
  const save=node('button','Save draft to database','btn primary');save.type='submit';const status=node('p','', 'form-status');form.append(save,status);parent.append(form);
  form.onsubmit=async event=>{event.preventDefault();save.disabled=true;status.textContent='Saving…';try{const stored=await api('/requirements',{method:'POST',body:{...readContent(form),model_code:evidence.model_code,market_code:evidence.market_code,scope_layer:evidence.scope_layer,category_id:select.value,evidence_ids:[evidence.id],rationale:rationale.value}});setTab('requirements');await refresh();await selectRecord(stored.id);}catch(error){status.textContent=error.message;save.disabled=false;}};
}
function renderActionForm(parent,item){if(!state.canDecide){parent.append(node('p','PM actions disabled for this server identity.','subtle'));return;}const form=node('form');form.id='action-form';form.append(node('h3','PM decision'));
  const grid=node('div',undefined,'form-grid');const actionLabel=node('label','Action');const select=node('select');select.name='action';select.id='pm-action';for(const [v,t] of [['approve','Approve'],['edit','Edit / reopen'],['reject','Reject'],['postpone','Postpone']])option(select,v,t);actionLabel.append(select);grid.append(actionLabel);
  const rationale=field(grid,'rationale','Required decision rationale','textarea','',true);rationale.required=true;const scheduling=node('div',undefined,'wide form-grid');scheduling.hidden=true;field(scheduling,'review_date','Review date','date');const unschedLabel=node('label','Explicitly unscheduled');const unsched=node('input');unsched.name='unscheduled';unsched.type='checkbox';unschedLabel.append(unsched);scheduling.append(unschedLabel);
  const edit=node('div',undefined,'wide form-grid');edit.hidden=true;contentInputs(edit,item);for(const input of edit.querySelectorAll('[required]'))input.required=false;
  grid.append(scheduling,edit);form.append(grid);const submit=node('button','Save decision','btn primary');submit.type='submit';const status=node('p','','form-status');form.append(submit,status);parent.append(form);
  select.onchange=()=>{scheduling.hidden=select.value!=='postpone';edit.hidden=select.value!=='edit';};
  form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;status.textContent='Saving…';const payload={action:select.value,expected_revision:item.current_revision,rationale:rationale.value};if(select.value==='edit')payload.content=readContent(form);if(select.value==='postpone'){payload.review_date=form.elements.namedItem('review_date').value||null;payload.unscheduled=unsched.checked;}
    try{const saved=await api(`/requirements/${item.id}/actions`,{method:'POST',body:payload});await refresh();await selectRecord(saved.id);}catch(error){submit.disabled=false;status.textContent=error.status===409?'This requirement changed in another window. Your form has not been saved. Reload the stored revision before deciding again.':error.message;
      if(error.status===409){submit.disabled=true;const retry=node('button','Reload stored revision','btn');retry.type='button';retry.onclick=()=>selectRecord(item.id);status.append(retry);}}};
}
function renderAudit(items){const box=$('#audit');box.replaceChildren();for(const e of items){const event=node('div',undefined,'event');event.append(node('time',e.created_at),node('strong',`${e.action} · revision ${e.revision} · ${e.actor}`),node('p',e.rationale));box.append(event);}if(!items.length)message(box,'No audit entries.');}
function renderMetrics(metrics){const box=$('#configurator-summary');box.replaceChildren();if(!metrics){message(box,'Configurator context is hidden because the active evidence filters cannot be applied to unresolved option mappings.');return;}
  box.append(node('h3',metrics.label));const c=metrics.completion;box.append(node('p',c.percentage===null?`Completion unavailable: ${c.unavailable_reason}`:`Synthetic completion: ${c.numerator} / ${c.denominator} sessions = ${c.percentage}%`));
  box.append(node('p',`Versions ${metrics.version_ids.join(', ')||'none'} · ${metrics.effective_filters.model_code} · ${metrics.effective_filters.market_code||($('#market').value==='unknown'?'unknown market':'all markets')} · ${metrics.period.source_timestamp_min||'no period'} to ${metrics.period.source_timestamp_max||'no period'} · timestamp meaning unknown`,'subtle'));
  const table=node('table',undefined,'metric-table');const head=node('tr');for(const title of ['Unresolved option','Selecting / viewing sessions','Selection among viewers'])head.append(node('th',title));table.append(head);for(const o of metrics.options){const tr=node('tr');for(const value of [o.option_code,`${o.numerator} / ${o.denominator}`,`${o.percentage}%`])tr.append(node('td',value));table.append(tr);}const scroll=node('div',undefined,'metric-scroll');scroll.append(table);box.append(scroll);box.append(node('p',metrics.final_stages.map(s=>`${s.final_stage}: ${s.count}`).join(' · '),'subtle'));box.append(node('p',metrics.limitations.join('. '),'subtle'));
}
function setTab(tab){state.tab=tab;state.page=1;for(const btn of document.querySelectorAll('[data-tab]'))btn.classList.toggle('active',btn.dataset.tab===tab);$('#table-heading').textContent=({feedback:'Customer feedback register','catalogue-facts':'Published catalogue context',evidence:'Collected source evidence · provisional assessments',problems:'Manual problem proposals',requirements:'Requirements register'})[tab];}
for(const el of document.querySelectorAll('[data-tab]'))el.onclick=()=>{setTab(el.dataset.tab);refresh();};
for(const id of ['derivative','market','dataset','category','scope','origin','review','kind','sort','direction','unscored'])$('#'+id).onchange=()=>{state.page=1;refresh();};
let searchTimer;$('#search').oninput=()=>{clearTimeout(searchTimer);state.epoch++;state.controller?.abort();clearDetail();searchTimer=setTimeout(()=>{state.page=1;refresh();},250);};
$('#refresh').onclick=()=>$('#derivative').disabled?initialize():refresh();$('#previous').onclick=()=>{state.page--;refresh();};$('#next').onclick=()=>{state.page++;refresh();};
$('#export-audit').onclick=async()=>{const selected=state.selected;if(selected?.tab!=='requirements')return;try{const result=await api(`/requirements/${selected.id}/export`);const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=node('a');link.href=url;link.download=`requirement-${selected.id}-audit.json`;link.click();URL.revokeObjectURL(url);}catch(error){message($('#audit'),error.message,'error-box');}};
initialize();
