const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch();
 const page=await browser.newPage({viewport:{width:412,height:820},isMobile:true,hasTouch:true});
 await page.goto(process.env.PLANNER_TEST_URL+'/planner.html');
 // A task detail remains selected in the inactive Tasks page.
 await page.locator('[data-page="calendar"]').click();
 await page.evaluate(()=>{document.getElementById('tasksDetail').hidden=false;});
 await page.waitForTimeout(400);
 for(const [width,height] of [[412,820],[320,568],[844,390]]){
  await page.setViewportSize({width,height});
  await page.evaluate(()=>{
   const body=document.querySelector('.cal-agenda-body');body.innerHTML='';
   for(let i=0;i<20;i++){const task=document.createElement('div');task.className='cal-agenda-task-item';task.textContent='Задача '+i;body.append(task);}
   window.scrollTo(0,0);
  });
  await page.waitForTimeout(100);
  await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
  await page.waitForTimeout(400);
  assert(await page.locator('#nav').evaluate(e=>e.classList.contains('nav-hidden')),'nav must hide when scrolling calendar with a selected task');
  await page.evaluate(()=>document.dispatchEvent(new PointerEvent('pointermove',{pointerType:'touch',clientY:innerHeight-2,bubbles:true})));
  assert(await page.locator('#nav').evaluate(e=>e.classList.contains('nav-hidden')),'touch movement must not reveal nav');
  // Even when navigation is revealed, the last task must be above it.
  await page.locator('#nav').evaluate(e=>e.classList.remove('nav-hidden'));
  await page.waitForTimeout(400);
  const task=await page.locator('.cal-agenda-task-item').last().boundingBox();
  const nav=await page.locator('#nav').boundingBox();
  assert(task.y+task.height<nav.y,'last task overlaps navigation');
  await page.evaluate(()=>window.scrollBy(0,-100));await page.waitForTimeout(400);
  assert(await page.locator('#nav').evaluate(e=>!e.classList.contains('nav-hidden')),'upward scroll restores nav');
 }
 await browser.close();console.log('PASS: calendar nav hides with inactive task detail; touch does not reveal it; final task clears visible nav at 320–844 px');
})();
