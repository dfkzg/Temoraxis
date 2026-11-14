package ru.personal.planner;
import org.json.*;
import java.time.*;
import java.util.*;

/** Pure scheduling rules; tested on the JVM independently from Android services. */
public final class ReminderCalculator {
 /** Reset delivery marks only when a task's schedule is deliberately edited. */
 public static String scheduleSignature(JSONObject task){
  JSONObject r=task.optJSONObject("reminder");if(r==null)r=new JSONObject();
  TreeSet<Integer> days=new TreeSet<>();JSONArray raw=task.optJSONArray("repeatDays");if(raw!=null)for(int i=0;i<raw.length();i++)days.add(raw.optInt(i));
  return task.optString("date")+"|"+task.optString("time")+"|"+task.optString("repeat")+"|"+days+"|"+r.optBoolean("enabled")+"|"+r.optInt("minutesBefore",5)+"|"+r.optBoolean("repeatUntilDone")+"|"+r.optInt("repeatInterval",5);
 }
 static void clearTask(JSONObject marks,String id){
  ArrayList<String> remove=new ArrayList<>();Iterator<String> keys=marks.keys();while(keys.hasNext()){String key=keys.next();if(key.startsWith(id+"|"))remove.add(key);}for(String key:remove)marks.remove(key);
 }
 public static void resetForEdits(JSONObject previous,JSONObject config,JSONObject sent,JSONObject dismissed,JSONObject done){
  JSONArray oldTasks=previous.optJSONArray("tasks"),tasks=config.optJSONArray("tasks");if(oldTasks==null||tasks==null)return;
  Map<String,JSONObject> old=new HashMap<>();for(int i=0;i<oldTasks.length();i++){JSONObject t=oldTasks.optJSONObject(i);if(t!=null)old.put(t.optString("id"),t);}
  for(int i=0;i<tasks.length();i++){
   JSONObject task=tasks.optJSONObject(i);if(task==null)continue;String id=task.optString("id");JSONObject before=old.get(id);if(before==null)continue;
   boolean reopened="done".equals(before.optString("status"))&&!"done".equals(task.optString("status"));
   if(!scheduleSignature(before).equals(scheduleSignature(task))||reopened){clearTask(sent,id);clearTask(dismissed,id);}
   if(reopened)clearTask(done,id);
   JSONObject occurrences=before.optJSONObject("occurrences"),current=task.optJSONObject("occurrences");
   if(occurrences!=null){Iterator<String> dates=occurrences.keys();while(dates.hasNext()){String date=dates.next();JSONObject prev=occurrences.optJSONObject(date),next=current==null?null:current.optJSONObject(date);if(prev!=null&&"done".equals(prev.optString("status"))&&(next==null||!"done".equals(next.optString("status")))){String key=id+"|"+date;sent.remove(key);dismissed.remove(key);done.remove(key);}}}
  }
 }
 public static JSONObject next(JSONObject task,ZoneId zone,long now,JSONObject sent,JSONObject dismissed,JSONObject done) throws JSONException {
  if(task==null||task.optBoolean("deleted"))return null;
  String id=task.optString("id"),time=task.optString("time");
  if(!id.matches("[A-Za-z0-9_-]{1,128}")||!time.matches("([01]\\d|2[0-3]):[0-5]\\d"))return null;
  JSONObject reminder=task.optJSONObject("reminder");if(reminder==null||!reminder.optBoolean("enabled"))return null;
  boolean recurring=Arrays.asList("daily","weekly").contains(task.optString("repeat"));
  if(!recurring&&Arrays.asList("done","missed").contains(task.optString("status")))return null;
  LocalDate today=Instant.ofEpochMilli(now).atZone(zone).toLocalDate(),start;
  try{start=LocalDate.parse(task.optString("date"));}catch(Exception e){if(!recurring)return null;start=today;}
  LocalDate first=recurring?today.minusDays(1):start;if(first.isBefore(start))first=start;
  TreeSet<LocalDate> dates=new TreeSet<>();
  for(int day=0;day<(recurring?16:1);day++)dates.add(first.plusDays(day));
  if(recurring&&reminder.optBoolean("repeatUntilDone")){
   Iterator<String> keys=sent.keys();String prefix=id+"|";
   while(keys.hasNext()){String key=keys.next();if(!key.startsWith(prefix)||done.optBoolean(key)||dismissed.optBoolean(key))continue;try{LocalDate date=LocalDate.parse(key.substring(prefix.length()));if(!date.isBefore(today.minusDays(93))&&!date.isBefore(start))dates.add(date);}catch(Exception ignored){}}
  }
  long earliest=Long.MAX_VALUE;String nextDate=null;
  for(LocalDate date:dates){
   String dateKey=date.toString(),key=id+"|"+dateKey;
   if("weekly".equals(task.optString("repeat"))){JSONArray weekdays=task.optJSONArray("repeatDays");boolean match=false;if(weekdays==null||weekdays.length()==0)match=date.getDayOfWeek()==start.getDayOfWeek();else for(int n=0;n<weekdays.length();n++)if(weekdays.optInt(n)==date.getDayOfWeek().getValue())match=true;if(!match)continue;}
   JSONObject records=task.optJSONObject("occurrences"),record=records==null?null:records.optJSONObject(dateKey);
   if(record!=null&&Arrays.asList("done","missed").contains(record.optString("status")))continue;
   if(done.optBoolean(key)||dismissed.optBoolean(key))continue;
   long due=date.atTime(LocalTime.parse(time)).atZone(zone).toInstant().toEpochMilli()-Math.max(0,Math.min(1440,reminder.optInt("minutesBefore",5)))*60000L;
   long last=sent.optLong(key,0);
   if(last>0){if(!reminder.optBoolean("repeatUntilDone"))continue;due=last+Math.max(1,Math.min(1440,reminder.optInt("repeatInterval",5)))*60000L;}
   else if(due<now-10*60000L)continue;
   due=Math.max(now+1000,due);
   if(due<earliest){earliest=due;nextDate=dateKey;}
  }
  return nextDate==null?null:new JSONObject().put("date",nextDate).put("due",earliest);
 }
}
