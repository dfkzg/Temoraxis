const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch();const page=await browser.newPage();
 await page.clock.install({time:new Date('2026-11-14T10:00:00Z')});
 await page.goto(process.env.PLANNER_TEST_URL+'/planner.html');
 await page.evaluate(()=>{
  window.alarmCount=0;window.showTaskReminder=()=>window.alarmCount++;
  savePlannerSettings({notifications:true});
  const date=todayKey(),time=new Date().toTimeString().slice(0,5);
  createTask({id:'edited-alarm',date,time,title:'Будильник',repeat:'none',reminder:{enabled:true,minutesBefore:0,repeatUntilDone:false}});
  checkTaskReminders();
 });
 assert.equal(await page.evaluate(()=>window.alarmCount),1,'initial reminder must fire');
 await page.evaluate(()=>{updateTask('edited-alarm',{title:'Новое название'});checkTaskReminders();});
 assert.equal(await page.evaluate(()=>window.alarmCount),1,'title edit must not repeat reminder');
 await page.evaluate(()=>{
  const log=Store.get(STORAGE_KEYS.reminderLog,{});log['edited-alarm|'+todayKey()].dismissed=true;log['another|'+todayKey()]={at:Date.now(),dismissed:true};Store.set(STORAGE_KEYS.reminderLog,log);
  const time=new Date(Date.now()+5*60000).toTimeString().slice(0,5);updateTask('edited-alarm',{time});
 });
 assert(await page.evaluate(()=>!!Store.get(STORAGE_KEYS.reminderLog,{})['another|'+todayKey()]),'other task delivery marks must survive');
 await page.clock.fastForward(5*60000);await page.evaluate(()=>checkTaskReminders());
 assert.equal(await page.evaluate(()=>window.alarmCount),2,'edited time must re-arm a previously dismissed reminder');
 await page.evaluate(()=>{
  const time=new Date().toTimeString().slice(0,5);createTask({id:'fresh-alarm',date:todayKey(),time,title:'Новая задача',reminder:{enabled:true,minutesBefore:0,repeatUntilDone:false}});checkTaskReminders();
 });
 assert.equal(await page.evaluate(()=>window.alarmCount),3,'new task reminder must be independent');
 await browser.close();console.log('PASS: fired/dismissed task re-arms after time edit, no replay on title change, independent new task and retained marks');
})();
