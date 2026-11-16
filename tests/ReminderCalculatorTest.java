import org.json.*;
import ru.personal.planner.ReminderCalculator;
import java.time.*;
public final class ReminderCalculatorTest {
 static long stamp(String time){return Instant.parse(time).toEpochMilli();}
 static void check(boolean good,String message){if(!good)throw new AssertionError(message);}
 static JSONObject task(String repeat)throws Exception{return new JSONObject().put("id","task1").put("title","Test").put("date","2026-11-14").put("time","09:00").put("status","todo").put("repeat",repeat).put("reminder",new JSONObject().put("enabled",true).put("minutesBefore",5).put("repeatUntilDone",false).put("repeatInterval",5));}
 static JSONObject next(JSONObject task,String now,JSONObject sent,JSONObject dismissed,JSONObject done)throws Exception{return ReminderCalculator.next(task,ZoneId.of("UTC"),stamp(now),sent,dismissed,done);}
 public static void main(String[]args)throws Exception{
  JSONObject empty=new JSONObject(),one=task("none");
  check(next(one,"2026-11-14T08:00:00Z",empty,empty,empty).getLong("due")==stamp("2026-11-14T08:55:00Z"),"five minute lead");
  check(next(one,"2026-11-14T09:20:00Z",empty,empty,empty)==null,"no stale reminders");
  JSONObject daily=task("daily").put("occurrences",new JSONObject().put("2026-11-14",new JSONObject().put("status","done")));
  check(next(daily,"2026-11-14T08:00:00Z",empty,empty,empty).getString("date").equals("2026-11-15"),"completion affects one date");
  JSONObject weekly=task("weekly").put("repeatDays",new JSONArray().put(1).put(3));
  check(next(weekly,"2026-11-14T08:00:00Z",empty,empty,empty).getString("date").equals("2026-11-16"),"weekly Monday selected");
  JSONObject sent=new JSONObject().put("task1|2026-11-14",stamp("2026-11-14T08:55:00Z"));
  check(next(task("daily"),"2026-11-14T09:00:00Z",sent,empty,empty).getString("date").equals("2026-11-15"),"one reminder once");
  JSONObject repeated=task("daily");repeated.getJSONObject("reminder").put("repeatUntilDone",true);
  check(next(repeated,"2026-11-14T08:56:00Z",sent,empty,empty).getLong("due")==stamp("2026-11-14T09:00:00Z"),"repeat interval");
  check(next(repeated,"2026-11-14T08:56:00Z",sent,new JSONObject().put("task1|2026-11-14",true),empty).getString("date").equals("2026-11-15"),"dismiss only this date");
  check(next(task("none").put("status","done"),"2026-11-14T08:00:00Z",empty,empty,empty)==null,"completed task skipped");
  JSONObject future=task("weekly").put("date","2027-03-01").put("repeatDays",new JSONArray().put(1));
  check(next(future,"2026-11-14T08:00:00Z",empty,empty,empty).getString("date").equals("2027-03-01"),"distant series scheduled");
  JSONObject moscow=ReminderCalculator.next(one,ZoneId.of("Europe/Moscow"),stamp("2026-11-14T05:00:00Z"),empty,empty,empty);
  check(moscow.getLong("due")==stamp("2026-11-14T05:55:00Z"),"device timezone");
  JSONObject before=task("none"),edited=new JSONObject(before.toString()).put("time","09:30");
  JSONObject oldConfig=new JSONObject().put("tasks",new JSONArray().put(before)),config=new JSONObject().put("tasks",new JSONArray().put(edited));
  JSONObject delivery=new JSONObject().put("task1|2026-11-14",stamp("2026-11-14T08:55:00Z")),stopped=new JSONObject().put("task1|2026-11-14",true),completed=new JSONObject();
  ReminderCalculator.resetForEdits(oldConfig,oldConfig,delivery,stopped,completed);
  check(delivery.has("task1|2026-11-14")&&stopped.has("task1|2026-11-14"),"resume and permission changes do not replay alarms");
  ReminderCalculator.resetForEdits(oldConfig,config,delivery,stopped,completed);
  check(!delivery.has("task1|2026-11-14")&&!stopped.has("task1|2026-11-14"),"changing time re-arms fired and dismissed task");
  check(next(edited,"2026-11-14T09:00:00Z",delivery,stopped,completed).getLong("due")==stamp("2026-11-14T09:25:00Z"),"edited task gets new due time");
  delivery.put("task1|2026-11-14",1);stopped.put("task1|2026-11-14",true);
  ReminderCalculator.resetForEdits(oldConfig,new JSONObject().put("tasks",new JSONArray().put(new JSONObject(before.toString()).put("title","Renamed"))),delivery,stopped,completed);
  check(delivery.has("task1|2026-11-14")&&stopped.has("task1|2026-11-14"),"title edit does not replay alarm");
  before.put("status","done");edited.put("status","done");completed.put("task1|2026-11-14",true);
  ReminderCalculator.resetForEdits(oldConfig,config,delivery,stopped,completed);
  check(completed.has("task1|2026-11-14")&&next(edited,"2026-11-14T09:00:00Z",delivery,stopped,completed)==null,"time edit never reopens completed task");
  edited.put("status","todo");ReminderCalculator.resetForEdits(oldConfig,config,delivery,stopped,completed);
  check(!completed.has("task1|2026-11-14")&&next(edited,"2026-11-14T09:00:00Z",delivery,stopped,completed)!=null,"explicit reopening removes native done mark");
  JSONObject birthday=task("none").put("date","2026-12-10").put("time","");
  birthday.getJSONObject("reminder").put("minutesBefore",7*1440).put("atTime","09:00");
  check(next(birthday,"2026-12-03T08:00:00Z",empty,empty,empty).getLong("due")==stamp("2026-12-03T09:00:00Z"),"untimed birthday reminds a week before without a task time");
  birthday.getJSONObject("reminder").put("minutesBefore",4*1440);
  check(next(birthday,"2026-12-03T08:00:00Z",empty,empty,empty).getLong("due")==stamp("2026-12-06T09:00:00Z"),"four-day lead is not clamped to one day");
  JSONObject far=task("daily");far.getJSONObject("reminder").put("minutesBefore",30*1440);
  JSONObject ahead=next(far,"2026-11-14T08:00:00Z",empty,empty,empty);
  check(ahead.getString("date").equals("2026-12-14")&&ahead.getLong("due")==stamp("2026-11-14T09:00:00Z"),"daily reminder searches beyond the old sixteen-day horizon");
  far.put("repeat","weekly").put("repeatDays",new JSONArray().put(3));
  ahead=next(far,"2026-11-14T08:00:00Z",empty,empty,empty);
  check(ahead.getString("date").equals("2026-12-16")&&ahead.getLong("due")==stamp("2026-11-16T09:00:00Z"),"weekly long-lead reminder retains weekday");
  JSONObject inHours=task("none");inHours.getJSONObject("reminder").put("minutesBefore",120);
  check(next(inHours,"2026-11-14T06:00:00Z",empty,empty,empty).getLong("due")==stamp("2026-11-14T07:00:00Z"),"two-hour lead");
  System.out.println("PASS: week/day/hour lead, untimed event time, long-lead recurrence horizon, native reminder lead, expiration, daily/weekly recurrence, per-date completion, repeat interval, dismissal, distant schedule, timezone, edited time re-arms without replay on resume/title edits, completed task protection");
 }
}
