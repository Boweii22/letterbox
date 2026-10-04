'use strict';
async function runAnalysis(){if(!$('public-consent').checked)return toast('Read the public test notice and confirm before sending text.');if(state.busy)return;if(!state.status?.models?.length){$('settings-dialog').showModal();return}const text=$('letter-text').value.trim();if(text.length<30)return toast('Add at least a few sentences from the letter.');if(text.length>9000)return toast('Use one page, up to 9,000 characters.');const language=$('language-select').value;if(language!=='English')toast('Translation is experimental. Ask a fluent reader to check important details.');clearResult();setBusy(true);try{const result=await api('/api/analyze',{text,model:$('model-select').value,language});renderResult(result)}catch(error){toast(error.message)}finally{setBusy(false)}}
async function loadSample(key){if(state.busy)return;$('sample-dialog').close();const sample=state.samples[key];if(!sample)return;state.sample=key;state.image=null;state.ocrLines=[];$('original-image').removeAttribute('src');$('letter-text').value=sample.text;$('language-select').value='English';$('source-label').textContent='FICTIONAL EXAMPLE';$('transcription-caption').textContent='EXAMPLE SOURCE TEXT';switchTab('upload');visible('source-view',true);setBusy(true,'Opening an example.','This walkthrough uses curated fictional details.');try{const result=await api('/api/demo',{sample:key});renderResult(result)}catch(error){toast(error.message)}finally{setBusy(false)}}
function datesInQuote(quote){const matches=quote.match(/\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b/gi)||[];const monthNames=['january','february','march','april','may','june','july','august','september','october','november','december'];return [...new Set(matches.map(value=>{const [day,month,year]=value.split(/\s+/);const index=monthNames.indexOf(month.toLowerCase());const candidate=`${year}-${String(index+1).padStart(2,'0')}-${day.padStart(2,'0')}`;const parsed=new Date(`${candidate}T12:00:00Z`);return !isNaN(parsed)&&parsed.toISOString().slice(0,10)===candidate?candidate:null}).filter(Boolean))]}
function openReminder(detail){
 state.reminder=detail;
 $('reminder-quote').textContent=detail.quote;
 $('reminder-title').value=/appointment/i.test(detail.quote)?'Appointment reminder':'Letter deadline';
 const dates=datesInQuote(detail.quote);
 $('reminder-date').value=dates.length===1?dates[0]:'';
 $('confirm-date').checked=false;
 $('include-calendar-quote').checked=false;
 $('date-note').textContent=dates.length===1?'Suggested from the source quote. Check it against the original. This is an all-day reminder.':'No single complete date was found. Choose a date you have checked; relative deadlines need your input.';
 updateCalendarButton();
 $('reminder-dialog').showModal();
}
function updateCalendarButton(){
 const provider=$('calendar-provider').value;
 const names={google:'Google Calendar',outlook:'Outlook',microsoft365:'Microsoft 365',apple:'Apple Calendar',other:'your calendar'};
 const cloud=['google','outlook','microsoft365'].includes(provider);
 $('download-calendar').disabled=!$('confirm-date').checked||!$('reminder-date').value||!$('reminder-date').validity.valid||!$('reminder-title').value.trim();
 $('download-calendar').textContent=cloud?'Continue to '+names[provider]+' ↗':'Save calendar file ↓';
 $('calendar-sharing').textContent=cloud?names[provider]+' receives your reminder title and date'+($('include-calendar-quote').checked?' and selected source excerpt.':'. The source excerpt is excluded.')+' The letter photograph is never included.':'Creates a local .ics file for '+names[provider]+'. Import it in your calendar app. No calendar account is connected.';
 $('calendar-result-note').textContent=cloud?'Opens a prepared event. Sign in if needed, then press Save there. Letterbox does not have account access.':'Requests a browser download; this public edition does not save reminder files on the server. Open or import the file in your calendar app.';
}
function resetCalendarConfirmation(){$('confirm-date').checked=false;updateCalendarButton()}
function download(filename,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=node('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function saveCalendar(){
 const button=$('download-calendar');
 if(button.disabled)return;
 const provider=$('calendar-provider').value;
 const event={date:$('reminder-date').value,title:$('reminder-title').value,quote:state.reminder.quote,includeQuote:$('include-calendar-quote').checked,confirmed:$('confirm-date').checked};
 if(['google','outlook','microsoft365'].includes(provider)){
   try{
     const url=buildCalendarUrl(provider,event);
     window.open(url,'_blank','noopener,noreferrer');
     const fallback=node('a',null,'Open the prepared event');fallback.href=url;fallback.target='_blank';fallback.rel='noopener noreferrer';
     $('calendar-result-note').replaceChildren(document.createTextNode('Review and press Save in your calendar. If a new tab did not open: '),fallback);
     toast('Prepared event ready. Review and save it in your calendar to finish.');
   }catch(error){toast(error.message)}
   return;
 }
 button.disabled=true;
 try{
   const saved=await api('/api/save-calendar',{...event,quote:event.includeQuote?event.quote:''});
   download(saved.file_name,saved.calendar,'text/calendar;charset=utf-8');
   $('reminder-dialog').close();
   toast('Calendar download requested. Open or import the file in your calendar app.');
 }catch(error){toast(error.message)}finally{updateCalendarButton()}
}
function exportReview(){if(!state.result)return;const r=state.result;const lines=['LETTERBOX — YOUR REVIEW',r.mode==='sample'?'Fictional curated sample. No AI was run.':`Hosted model: ${r.model}`,`Explanation language: ${r.language||'English'}`,'','Quote matching is not verification of the photograph or interpretation.','',...r.details.flatMap(d=>[d.explanation,`Source: ${d.quote}`,`Quote match: ${d.matched?'matched':'not found'} | Human review: ${state.confirmed.has(d.id)?'checked by user':'not confirmed'}`,'']),'ORIGINAL TEXT / TRANSCRIPTION',$('letter-text').value];download('letterbox-review.txt',lines.join('\n'),'text/plain;charset=utf-8');toast('Review saved to your chosen download location. It contains the letter text.')}
function info(title,paragraphs){$('info-title').textContent=title;$('info-content').replaceChildren(...paragraphs.map(([heading,text])=>{const section=node('section');section.append(node('h3',null,heading),node('p',null,text));return section}));$('info-dialog').showModal()}
function readAloud(){if(!state.result||!window.speechSynthesis)return toast('Read-aloud is unavailable in this browser.');const language=state.result.language||'English';const tags={English:'en',Spanish:'es',French:'fr',Urdu:'ur',Arabic:'ar',Polish:'pl'};const voice=window.speechSynthesis.getVoices().find(v=>v.localService&&v.lang.startsWith(tags[language]));if(!voice)return toast('No installed offline voice for this language. Install a system voice to use private read-aloud.');if(window.speechSynthesis.speaking){window.speechSynthesis.cancel();return}const utterance=new SpeechSynthesisUtterance(state.result.details.map(d=>d.explanation).join('. '));utterance.voice=voice;utterance.rate=.92;utterance.lang=voice.lang;window.speechSynthesis.speak(utterance)}
$('tab-upload').addEventListener('click',()=>switchTab('upload'));
$('tab-text').addEventListener('click',()=>switchTab('text'));
$('edit-text').addEventListener('click',()=>{switchTab('text');$('letter-text').focus()});
$('letter-text').addEventListener('input',()=>{state.sample=null;clearResult();$('source-label').textContent=state.image?'EDITED TRANSCRIPTION':'PASTED TEXT';state.ocrLines=[];updateButton()});
$('file-input').addEventListener('change',event=>upload(event.target.files[0]));
$('drop-zone').addEventListener('dragover',event=>{event.preventDefault();$('drop-zone').classList.add('drag-over')});
$('drop-zone').addEventListener('dragleave',()=>$('drop-zone').classList.remove('drag-over'));
$('drop-zone').addEventListener('drop',event=>{event.preventDefault();$('drop-zone').classList.remove('drag-over');upload(event.dataTransfer.files[0])});
$('analyze-button').addEventListener('click',runAnalysis);
$('clear-button').addEventListener('click',clearAll);
$('export-button').addEventListener('click',exportReview);
$('sample-button').addEventListener('click',()=>$('sample-dialog').showModal());
document.querySelectorAll('[data-sample]').forEach(button=>button.addEventListener('click',()=>loadSample(button.dataset.sample)));
document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
$('engine-button').addEventListener('click',()=>{$('settings-dialog').showModal();refreshStatus()});
$('refresh-engine').addEventListener('click',refreshStatus);
$('model-select').addEventListener('change',()=>{state.modelChosen=true});
$('zoom-button').addEventListener('click',()=>$('image-dialog').showModal());
$('confirm-date').addEventListener('change',updateCalendarButton);
$('reminder-date').addEventListener('input',resetCalendarConfirmation);
$('reminder-title').addEventListener('input',resetCalendarConfirmation);
$('calendar-provider').addEventListener('change',resetCalendarConfirmation);
$('include-calendar-quote').addEventListener('change',resetCalendarConfirmation);
$('download-calendar').addEventListener('click',saveCalendar);
$('read-button').addEventListener('click',readAloud);
$('language-select').addEventListener('change',()=>{if(state.result)toast('Press Explain again to apply the new language.')});
$('nav-letter').addEventListener('click',()=>document.querySelector('.workspace').scrollIntoView({behavior:'smooth'}));
$('nav-how').addEventListener('click',()=>info('From envelope to evidence.',[
['01 · Read','Upload a photo for Tesseract OCR on the Render cloud server, or paste the text. The photograph stays visible so you can check transcription errors.'],
['02 · Explain','Code selects source sentences on Render; Google-hosted Gemma rewrites them in simpler words. Code checks exact source quotations, numbers and conditions. Monitoring can record anonymous counts and timings, never letter text. ElevenLabs speech and SerpApi search are optional and ask before sharing text.'],
['03 · Review','Code checks whether each quote appears in the transcription, allowing only whitespace changes. This does not prove the interpretation is right. You compare the original and confirm.'],
['04 · Remember','Choose and confirm a date. Open a prepared event in Google Calendar or Outlook and save it there, or use a calendar file for Apple and other apps. Letterbox never books appointments, sends replies or makes payments.']]));
$('limits-button').addEventListener('click',()=>info('Clarity includes uncertainty.',[
['A quote can match and still be wrong','OCR can misread a date. A model can misunderstand a correct sentence. Quote matching is a consistency check, not independent verification. Always compare important details with the original.'],
['A deliberately small scope','One-page letters. Source-linked details. Confirmed all-day reminders. Models can miss or misinterpret important details; this is not professional advice.'],
['What the public test shares','Images are temporarily written for Tesseract OCR and deleted after reading. Input goes to Render; selected source sentences go to Google’s hosted Gemma API, whose free tier may use content to improve Google products. Letters are not intentionally saved by the app; use fictional or redacted input. Calendar links share your chosen title and date with the selected provider, and an excerpt only if you opt in. Calendar files and exports are created only when requested. The public version uses hosted Gemma; the private local version remains available separately.'],
['Samples are examples, not results','The sample walkthrough contains fictional letters and curated explanations. It does not call a model and is not evidence of model accuracy.']]));
$('language-help').addEventListener('click',()=>info('Your language, carefully.',[
['English first','English is the default supported workflow. Other explanation languages are experimental in this demo.'],
['Keep the source beside it','Supporting quotations remain in the original language. Have a fluent reader check translated dates, amounts, conditions and actions.'],
['Private read-aloud','Read-aloud only uses voices marked as installed locally by your browser. When ElevenLabs is connected, you can explicitly choose online speech and approve sharing the explanation. It never switches silently.']]));
async function init(){await refreshStatus();try{const response=await fetch('/api/samples');state.samples=await response.json()}catch{toast('Could not load the sample letters. Check the cloud connection.')}updateButton();window.speechSynthesis?.getVoices()}
init();

// Only a dismissal preference is saved; letters and tour data stay in page memory.
(()=>{
 const preference='letterbox-tour-v1';
 const steps=[
  ['.source-tabs','Start with your letter.','Upload a clear photo or paste one page of text. Photo reading happens on the Render cloud server; read the sharing notice first. Try an example if you just want to look around.'],
  ['.analyze-footer','Ask for a clearer explanation.','Press Explain my letter when your text is ready. Google-hosted Gemma simplifies selected source excerpts. Read the photo transcription first: a copied date can be wrong.'],
  ['.explanation-panel .panel-heading','Follow the evidence.','Your explanations appear here. Select a supporting quote to highlight it in the original. “Quote matched” means the words match the transcription; you still check their meaning against the letter.'],
  ['.trust-strip','Take your next step.','When a date is found, Create reminder lets you check it and choose your calendar. Google and Outlook open an event for you to save; other apps use a calendar file. You can reopen this guide with Quick tour.']
 ];
 const dialog=$('tour-dialog'),card=$('tour-card'),spot=$('tour-spotlight');
 let index=0,previousFocus,previousOverflow='',scrollX=0,scrollY=0,frame;
 function position(){
  if(!dialog.open)return;
  const target=document.querySelector(steps[index][0]);
  if(!target)return;
  const rect=target.getBoundingClientRect(),width=window.innerWidth,height=window.innerHeight,pad=6;
  const left=Math.max(8,rect.left-pad),top=Math.max(8,rect.top-pad);
  spot.style.cssText=`left:${left}px;top:${top}px;width:${Math.max(0,Math.min(width-8,rect.right+pad)-left)}px;height:${Math.max(0,Math.min(height-8,rect.bottom+pad)-top)}px;`;
  const cardHeight=card.offsetHeight,cardWidth=card.offsetWidth;
  let y=rect.bottom+18;
  if(y+cardHeight>height-12)y=rect.top-cardHeight-18;
  if(y<12)y=Math.max(12,height-cardHeight-12);
  card.style.left=Math.max(12,Math.min(width-cardWidth-12,rect.left))+'px';
  card.style.top=y+'px';
 }
 function render(){
  $('tour-progress').textContent=`A LITTLE GUIDANCE · ${index+1} OF ${steps.length}`;
  $('tour-title').textContent=steps[index][1];
  $('tour-description').textContent=steps[index][2];
  $('tour-back').disabled=index===0;
  $('tour-next').textContent=index===steps.length-1?'Got it ✓':'Next →';
  $('tour-dots').replaceChildren(...steps.map((_,i)=>node('span',i===index?'active':'')));
  document.querySelector(steps[index][0]).scrollIntoView({block:'center',behavior:'instant'});
  position();
 }
 function start(){
  if(state.busy||document.querySelector('dialog[open]'))return;
  previousFocus=document.activeElement;previousOverflow=document.body.style.overflow;
  scrollX=window.scrollX;scrollY=window.scrollY;
  document.body.style.overflow='hidden';index=0;dialog.showModal();render();$('tour-next').focus();
 }
 function finish(){dialog.close()}
 dialog.addEventListener('close',()=>{
  try{localStorage.setItem(preference,'dismissed')}catch{}
  document.body.style.overflow=previousOverflow;
  window.scrollTo({left:scrollX,top:scrollY,behavior:'instant'});
  previousFocus?.focus({preventScroll:true});
 });
 $('tour-button').addEventListener('click',start);
 $('tour-skip').addEventListener('click',finish);
 $('tour-next').addEventListener('click',()=>{if(index===steps.length-1)finish();else{index++;render()}});
 $('tour-back').addEventListener('click',()=>{if(index>0){index--;render()}});
 function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(position)}
 window.addEventListener('resize',schedule);window.addEventListener('scroll',schedule,{passive:true});
 let dismissed=false;try{dismissed=localStorage.getItem(preference)==='dismissed'}catch{}
 if(!dismissed)start();
})();

$('feedback-button').addEventListener('click',()=>$('feedback-dialog').showModal());
$('send-feedback').addEventListener('click',async()=>{
 const helpful=$('feedback-helpful').value,text=$('feedback-text').value.trim();
 if(!helpful||text.length<5)return toast('Choose an answer and add a few words of feedback.');
 $('send-feedback').disabled=true;
 try{await api('/api/feedback',{helpful,text});$('feedback-dialog').close();$('feedback-text').value='';toast('Feedback sent. Thank you for trying Letterbox.')}catch(error){toast(error.message)}finally{$('send-feedback').disabled=false}
});
