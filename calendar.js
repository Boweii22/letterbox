'use strict';
/** Prepared-event links, not OAuth access or a claim that an event was saved. */
function buildCalendarUrl(provider, event) {
  if (event.confirmed !== true) throw new Error('Check the date against the original first.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(event.date)) throw new Error('Choose a complete calendar date.');
  const start = new Date(event.date + 'T00:00:00Z');
  if (isNaN(start) || start.toISOString().slice(0, 10) !== event.date) throw new Error('Choose a valid calendar date.');
  const end = new Date(start.getTime() + 86400000);
  const title = String(event.title || '').trim().slice(0, 200);
  if (!title) throw new Error('Give the reminder a name.');
  let description = 'All-day reminder. Date checked against the original letter. Created with Letterbox.';
  if (event.includeQuote === true) description += '\nSource excerpt: ' + String(event.quote || '').slice(0, 1000);
  let url;
  if (provider === 'google') {
    url = new URL('https://calendar.google.com/calendar/render');
    url.search = new URLSearchParams({action:'TEMPLATE',text:title,dates:event.date.replaceAll('-','')+'/'+end.toISOString().slice(0,10).replaceAll('-',''),details:description}).toString();
  } else if (provider === 'outlook' || provider === 'microsoft365') {
    url = new URL(provider === 'outlook' ? 'https://outlook.live.com/calendar/0/deeplink/compose' : 'https://outlook.office.com/calendar/0/deeplink/compose');
    url.search = new URLSearchParams({path:'/calendar/action/compose',rru:'addevent',subject:title,startdt:start.toISOString(),enddt:end.toISOString(),allday:'true',body:description}).toString();
  } else throw new Error('This calendar uses the standard calendar-file option.');
  return url.href;
}
if (typeof module !== 'undefined') module.exports = {buildCalendarUrl};
