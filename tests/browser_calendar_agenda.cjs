const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.PLANNER_TEST_URL+'/planner.html');
 await page.evaluate(()=>{
  const today=todayKey(),tomorrow=new Date(today+'T12:00:00');tomorrow.setDate(tomorrow.getDate()+1);
  createTask({id:'agenda-late',title:'Вечерняя задача',date:today,time:'18:30'});
  createTask({id:'agenda-no-time',title:'Задача без времени с длинным названием для проверки узкого экрана',date:today});
  createTask({id:'agenda-early',title:'Утренняя задача',date:today,time:'09:00'});
  createTask({id:'agenda-daily',title:'Повторяющаяся задача',date:today,time:'07:30',repeat:'daily'});
  createTask({id:'agenda-tomorrow',title:'Только завтра',date:toDateKey(tomorrow),time:'12:00'});
  setTaskDone('agenda-early',today);
  CalState.agendaDate=new Date(today+'T12:00:00');renderAgenda();
 });
 await page.click('[data-page="calendar"]');
 const rows=page.locator('#calAgenda .cal-agenda-task-item');
 assert.deepEqual(await rows.evaluateAll(items=>items.map(x=>x.dataset.taskId)),['agenda-daily','agenda-early','agenda-late','agenda-no-time']);
 assert.match(await rows.nth(0).innerText(),/Ежедневно/);assert.match(await rows.nth(1).innerText(),/Выполнено/);assert.match(await rows.last().innerText(),/Без времени/);
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal page overflow at '+width);
  for(const row of await rows.all())assert.equal(await row.evaluate(e=>e.scrollWidth>e.clientWidth),false,'No clipped task rows');
 }
 await page.click('#calAgendaNext');
 assert.deepEqual(await rows.evaluateAll(items=>items.map(x=>x.dataset.taskId)),['agenda-daily','agenda-tomorrow']);
 await rows.first().focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('#tasksDetail').isVisible(),true);assert.match(await page.locator('.tasks-detail-title').innerText(),/Повторяющаяся/);
 await page.click('[data-page="clock"]');
 assert.equal(await page.locator('#clockTaskList').count(),0);assert.equal(await page.locator('#clockTaskTitle').count(),0);
 assert.equal(await page.locator('#clockHours').isVisible(),true);assert.equal(await page.locator('#clockSummary').count(),1);
 await page.click('[data-page="calendar"]');await page.click('#calAgendaPrev');
 if(process.env.PLANNER_AGENDA_SCREENSHOT){await page.setViewportSize({width:390,height:844});await page.locator('#calAgenda').screenshot({path:process.env.PLANNER_AGENDA_SCREENSHOT});}
 assert.deepEqual(errors,[]);await browser.close();
 console.log('PASS: calendar day tasks sorted by time, undated-time tasks last, recurring/completed labels, date navigation, keyboard opening, removed duplicate clock list and narrow-screen layout.');
})().catch(e=>{console.error(e);process.exit(1);});
