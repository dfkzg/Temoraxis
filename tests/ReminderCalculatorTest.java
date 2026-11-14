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
  System.out.println("PASS: native reminder lead, expiration, daily/weekly recurrence, per-date completion, repeat interval, dismissal, distant schedule, timezone");
 }
}
