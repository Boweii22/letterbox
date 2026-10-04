'use strict';
const sponsorAudio=new Audio();let sponsorAudioURL=null;
function stopSponsorAudio(){sponsorAudio.pause();sponsorAudio.removeAttribute('src');if(sponsorAudioURL){URL.revokeObjectURL(sponsorAudioURL);sponsorAudioURL=null}}
function sponsorDialog(id,title,description){
 const dialog=node('dialog');dialog.id=id;const heading=node('div','dialog-heading');heading.append(node('h2',null,title));const close=node('button','close-dialog','×');close.type='button';close.setAttribute('aria-label','Close');close.addEventListener('click',()=>dialog.close());heading.append(close);dialog.append(heading,node('p',null,description));document.body.append(dialog);return dialog;
}
const speechDialog=sponsorDialog('voice-dialog','A voice that works for you.','Use an installed device voice, or choose ElevenLabs. The ElevenLabs option sends the explanation text to their service. Their data handling applies.');
const deviceVoice=node('button','secondary-button','Use device voice');deviceVoice.addEventListener('click',()=>{speechDialog.close();readAloud()});
const voiceConsent=node('label','confirm-check');const voiceCheck=node('input');voiceCheck.type='checkbox';voiceConsent.append(voiceCheck,document.createTextNode('I approve sending this explanation to ElevenLabs.'));
const cloudVoice=node('button','primary-button','Listen with ElevenLabs');cloudVoice.disabled=true;voiceCheck.addEventListener('change',()=>cloudVoice.disabled=!voiceCheck.checked);
cloudVoice.addEventListener('click',async()=>{
 if(!state.result||!voiceCheck.checked)return;cloudVoice.disabled=true;cloudVoice.textContent='Preparing your audio…';
 try{const response=await fetch('/api/speech',{method:'POST',headers:{'Content-Type':'application/json','X-Letterbox-Token':state.token},body:JSON.stringify({text:state.result.details.map(d=>d.explanation).join('. '),speechConsent:true})});if(!response.ok){const r=await response.json();throw new Error(r.error)}stopSponsorAudio();sponsorAudioURL=URL.createObjectURL(await response.blob());sponsorAudio.src=sponsorAudioURL;await sponsorAudio.play();speechDialog.close()}catch(e){toast(e.message||'Audio could not play. Try your device voice.')}finally{cloudVoice.disabled=!voiceCheck.checked;cloudVoice.textContent='Listen with ElevenLabs'}
});speechDialog.append(deviceVoice,voiceConsent,cloudVoice);
const readButton=$('read-button');const updatedRead=readButton.cloneNode(true);readButton.replaceWith(updatedRead);
updatedRead.addEventListener('click',async()=>{if(!state.result)return;if(!sponsorAudio.paused){stopSponsorAudio();return}await refreshStatus();if(state.status?.integrations?.elevenlabs){voiceCheck.checked=false;cloudVoice.disabled=true;speechDialog.showModal()}else readAloud()});
$('clear-button').addEventListener('click',stopSponsorAudio);
$('analyze-button').addEventListener('click',stopSponsorAudio);
window.addEventListener('pagehide',stopSponsorAudio);
const sourcesDialog=sponsorDialog('official-dialog','Find an official contact.','Enter an organisation name only. This optional search sends that name to SerpApi. It does not send the letter or establish that the letter is genuine.');
const label=node('label',null,'Organisation name');label.htmlFor='official-name';const org=node('input');org.id='official-name';org.maxLength=80;org.placeholder='For example: HMRC';
const consent=node('label','confirm-check');const checked=node('input');checked.type='checkbox';consent.append(checked,document.createTextNode('Share this organisation name with SerpApi.'));
const search=node('button','primary-button','Find official websites');search.disabled=true;const resultList=node('div','official-results');checked.addEventListener('change',()=>search.disabled=!checked.checked);
search.addEventListener('click',async()=>{search.disabled=true;resultList.replaceChildren();try{const result=await api('/api/official-sources',{organisation:org.value.trim(),searchConsent:checked.checked});resultList.append(node('p','fine-print',result.notice));for(const r of result.results){const a=node('a','official-link',r.title);a.href=r.url;a.target='_blank';a.rel='noopener noreferrer';resultList.append(a,node('p','fine-print',r.snippet))}if(!result.results.length)resultList.append(node('p',null,'No matching government or NHS websites found. Check the organisation independently.'))}catch(e){toast(e.message)}finally{search.disabled=!checked.checked}});
sourcesDialog.append(label,org,consent,search,resultList);
const sourceButton=node('button','text-button','Find an official contact ↗');sourceButton.addEventListener('click',async()=>{await refreshStatus();if(!state.status?.integrations?.serpapi)return toast('Official-source lookup is awaiting the developer’s SerpApi connection.');checked.checked=false;search.disabled=true;resultList.replaceChildren();sourcesDialog.showModal()});document.querySelector('.page-footer').append(sourceButton);
