const {chromium}=require('playwright');const assert=require('node:assert/strict');const BASE=process.env.PLANNER_TEST_URL;
(async()=>{
 const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:320,height:700}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(BASE+'/planner.html');assert.equal(await page.locator('#themeWelcome').isVisible(),true);
 await page.evaluate(()=>createTask({id:'theme-data',title:'Данные сохраняются',date:todayKey()}));const snapshot=await page.evaluate(()=>JSON.stringify(PlannerSync.documentSnapshot()));
 await page.locator('#themeWelcome [data-planner-theme="light"]').focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('html').getAttribute('data-theme'),'light');assert.equal(await page.locator('meta[name="theme-color"]').getAttribute('content'),'#f4f5fa');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.click('#themeWelcomeContinue');assert.equal(await page.locator('#themeWelcome').isVisible(),false);
 await page.reload();assert.equal(await page.locator('#themeWelcome').isVisible(),false);assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
 await page.click('[data-page="settings"]');await page.click('#settingsTheme [data-planner-theme="space"]');assert.equal(await page.locator('html').getAttribute('data-theme'),'space');assert.equal(await page.locator('#settingsTheme [data-planner-theme="space"]').getAttribute('aria-pressed'),'true');
 assert.equal(await page.evaluate(()=>JSON.stringify(PlannerSync.documentSnapshot())),snapshot,'Theme remains a local preference and never edits shared planner data');
 await page.goto(BASE+'/Start_page.html');assert.equal(await page.locator('html').getAttribute('data-theme'),'space');await page.click('#themeSwitch [data-theme="light"]');
 await page.goto(BASE+'/planner.html');assert.equal(await page.locator('html').getAttribute('data-theme'),'light');assert.equal(await page.locator('#themeWelcome').isVisible(),false);assert.equal(await page.evaluate(()=>getTask('theme-data').title),'Данные сохраняются');assert.deepEqual(errors,[]);await context.close();
 const fresh=await browser.newContext();const plain=await fresh.newPage();await plain.goto(BASE+'/planner.html');await plain.click('#themeWelcomeContinue');await plain.reload();assert.equal(await plain.locator('#themeWelcome').isVisible(),false);assert.equal(await plain.locator('html').getAttribute('data-theme'),'dark');await fresh.close();
 const native=await browser.newContext();await native.addInitScript(()=>{window.themes=[];window.PlannerAndroid={setTheme:theme=>themes.push(theme),scheduleReminders:()=>{},pendingCompletions:()=> '[]',acknowledgeCompletion:()=>{}};});const phone=await native.newPage();await phone.goto(BASE+'/planner.html');await phone.locator('#themeWelcome [data-planner-theme="light"]').click();assert.equal(await phone.evaluate(()=>themes.at(-1)),'light');await native.close();
 await browser.close();console.log('PASS: first-entry theme choice, keyboard and 320px layout, persistent settings, default confirmation, shared start-page theme, unchanged user data and native theme bridge.');
})().catch(e=>{console.error(e);process.exit(1);});
