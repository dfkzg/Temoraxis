/* Shared reminder rules for the planner, native bridge and start page. */
(function(){
'use strict';
const units={minutes:1,hours:60,days:1440},maxMinutes=365*1440;
function lead(reminder={}){reminder=reminder||{};const value=Number(reminder.minutesBefore);return Number.isFinite(value)?Math.max(0,Math.min(maxMinutes,Math.round(value))):5;}
function time(task){const value=task.time||task.reminder?.atTime||'09:00';return /^([01]\d|2[0-3]):[0-5]\d$/.test(value)?value:null;}
function unit(reminder={}){reminder=reminder||{};const minutes=lead(reminder);if(units[reminder.beforeUnit]&&minutes%units[reminder.beforeUnit]===0)return reminder.beforeUnit;return minutes&&minutes%1440===0?'days':minutes&&minutes%60===0?'hours':'minutes';}
function specialTasks(entries){return entries.filter(entry=>/^[A-Za-z0-9_-]{1,120}$/.test(entry.id||'')&&/^\d{4}-\d{2}-\d{2}$/.test(entry.date||'')).map(entry=>({id:'event_'+entry.id,source:'special-date',specialDateId:entry.id,title:entry.name,date:entry.date,time:entry.reminder?.atTime||'09:00',status:'todo',repeat:null,repeatDays:[],occurrences:{},subtasks:[],tags:[],priority:'mid',reminder:{enabled:false,...entry.reminder,repeatUntilDone:false,minutesBefore:lead(entry.reminder)}}));}
function nativeTasks(tasks,entries){const ids=new Set(tasks.map(task=>task.id));return tasks.map(task=>({...task,time:time(task)})).concat(specialTasks(entries).filter(task=>!ids.has(task.id)));}
function candidates(task,now,log){
 if(!['daily','weekly'].includes(task.repeat))return /^\d{4}-\d{2}-\d{2}$/.test(task.date||'')?[task.date]:[];
 const today=new Date(now);today.setHours(12,0,0,0);today.setDate(today.getDate()+Math.floor(lead(task.reminder)/1440)-1);
 const dates=new Set();
 const key=date=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
 // Two weeks cover every weekday even when the reminder is months ahead of the event.
 for(let i=0;i<17;i++){const d=new Date(today);d.setDate(d.getDate()+i);dates.add(key(d));}
 if(task.reminder?.repeatUntilDone)for(const record of Object.keys(log)){const prefix=task.id+'|';if(record.startsWith(prefix)){const date=record.slice(prefix.length);if(/^\d{4}-\d{2}-\d{2}$/.test(date))dates.add(date);}}
 return [...dates].sort();
}
window.PlannerReminderRules={units,maxMinutes,lead,time,unit,specialTasks,nativeTasks,candidates};
})();
