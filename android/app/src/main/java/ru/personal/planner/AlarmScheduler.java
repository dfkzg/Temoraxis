package ru.personal.planner;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Build;
import org.json.*;
import java.time.*;
import java.util.*;

final class AlarmScheduler {
    static final String PREFS="planner_native_v1", CONFIG="config", SCHEDULED="scheduled", SENT="sent", DISMISSED="dismissed", DONE="done", PENDING="pending";
    static android.content.SharedPreferences prefs(Context c){return c.getSharedPreferences(PREFS,Context.MODE_PRIVATE);}
    static JSONObject object(Context c,String key){try{return new JSONObject(prefs(c).getString(key,"{}"));}catch(Exception e){return new JSONObject();}}
    static String key(String id,String date){return id+"|"+date;}
    static Intent intent(Context c,String action,String id,String date){return new Intent(c,AlarmReceiver.class).setAction(action).setData(Uri.parse("planner://alarm/"+Uri.encode(key(id,date)))).putExtra("taskId",id).putExtra("date",date);}
    static PendingIntent pending(Context c,String action,String id,String date){return PendingIntent.getBroadcast(c,0,intent(c,action,id,date),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
    static synchronized void reconcile(Context c,String json){
        try{
            JSONObject config=new JSONObject(json);JSONArray tasks=config.optJSONArray("tasks");if(tasks==null)return;
            prefs(c).edit().putString(CONFIG,json).apply();
            AlarmManager manager=(AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
            JSONArray previous=new JSONArray(prefs(c).getString(SCHEDULED,"[]"));
            for(int i=0;i<previous.length();i++){JSONObject record=previous.getJSONObject(i);manager.cancel(pending(c,"FIRE",record.getString("id"),record.getString("date")));}
            JSONArray scheduled=new JSONArray();
            if(config.optBoolean("enabled")&&((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).areNotificationsEnabled()){
                JSONObject sent=object(c,SENT),dismissed=object(c,DISMISSED),done=object(c,DONE);long now=System.currentTimeMillis();
                for(int i=0;i<tasks.length();i++){
                    JSONObject task=tasks.optJSONObject(i);
                    JSONObject next=ReminderCalculator.next(task,ZoneId.systemDefault(),now,sent,dismissed,done);
                    if(next==null)continue;
                    String id=task.getString("id"),nextDate=next.getString("date");long earliest=next.getLong("due");
                    PendingIntent alarm=pending(c,"FIRE",id,nextDate);
                    try{if(Build.VERSION.SDK_INT<31||manager.canScheduleExactAlarms())manager.setAlarmClock(new AlarmManager.AlarmClockInfo(earliest,PendingIntent.getActivity(c,0,new Intent(c,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE)),alarm);else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,earliest,alarm);}catch(SecurityException e){manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,earliest,alarm);}
                    scheduled.put(new JSONObject().put("id",id).put("date",nextDate));
                }
            }else {c.stopService(new Intent(c,AlarmSoundService.class));((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).cancelAll();}
            prefs(c).edit().putString(SCHEDULED,scheduled.toString()).apply();
        }catch(Exception e){android.util.Log.w("Planner","Could not update reminders",e);}
    }
    static synchronized JSONArray pendingCompletions(Context c){JSONObject pending=object(c,PENDING);JSONArray values=new JSONArray();Iterator<String> keys=pending.keys();while(keys.hasNext()){String key=keys.next();JSONObject record=pending.optJSONObject(key);if(record!=null)values.put(record);}return values;}
    static synchronized void acknowledge(Context c,String key){JSONObject pending=object(c,PENDING);pending.remove(key);prefs(c).edit().putString(PENDING,pending.toString()).apply();}
    static synchronized void action(Context c,String action,String id,String date){
        try{String key=key(id,date);JSONObject config=object(c,CONFIG),tasksDone=object(c,DONE);
            if("DONE".equals(action)){tasksDone.put(key,true);JSONObject queue=object(c,PENDING);queue.put(key,new JSONObject().put("key",key).put("id",id).put("date",date));prefs(c).edit().putString(DONE,tasksDone.toString()).putString(PENDING,queue.toString()).apply();}
            if("DISMISS".equals(action)){JSONObject dismissed=object(c,DISMISSED);dismissed.put(key,true);prefs(c).edit().putString(DISMISSED,dismissed.toString()).apply();}
            if(key.equals(prefs(c).getString("sounding",null)))c.stopService(new Intent(c,AlarmSoundService.class));((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(key.hashCode());reconcile(c,config.toString());
        }catch(Exception ignored){}
    }
    static void fire(Context c,String id,String date){
        try{
            JSONObject config=object(c,CONFIG);if(!config.optBoolean("enabled"))return;JSONArray tasks=config.optJSONArray("tasks");if(tasks==null)return;
            JSONObject task=null;for(int i=0;i<tasks.length();i++){JSONObject candidate=tasks.optJSONObject(i);if(candidate!=null&&id.equals(candidate.optString("id"))){task=candidate;break;}}
            if(task==null||task.optBoolean("deleted"))return;
            String key=key(id,date);if(object(c,DONE).optBoolean(key)||object(c,DISMISSED).optBoolean(key))return;
            JSONObject record=task.optJSONObject("occurrences");record=record==null?null:record.optJSONObject(date);
            if(record!=null&&"done".equals(record.optString("status")))return;
            JSONObject sent=object(c,SENT);sent.put(key,System.currentTimeMillis());prefs(c).edit().putString(SENT,sent.toString()).apply();
            NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
            Notification notification=notification(c,id,date,task.optString("title","Задача"),task.optString("time"));
            try{manager.notify(key.hashCode(),notification);}catch(SecurityException ignored){}
            try{c.startForegroundService(new Intent(c,AlarmSoundService.class).putExtra("taskId",id).putExtra("date",date).putExtra("title",task.optString("title","Задача")).putExtra("time",task.optString("time")));}
            catch(RuntimeException e){
                android.util.Log.w("Planner","Android blocked alarm audio service; using notification sound",e);
                NotificationChannel fallback=new NotificationChannel("planner_alarm_fallback_v1","Напоминания без фоновой службы",NotificationManager.IMPORTANCE_HIGH);
                fallback.setSound(android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_ALARM),new android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ALARM).build());manager.createNotificationChannel(fallback);
                try{manager.notify(key.hashCode(),Notification.Builder.recoverBuilder(c,notification).setChannelId("planner_alarm_fallback_v1").build());}catch(SecurityException ignored){}
            }
            reconcile(c,config.toString());
        }catch(Exception e){android.util.Log.w("Planner","Could not show reminder",e);}
    }
    static Notification notification(Context c,String id,String date,String title,String time){
        NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
        NotificationChannel channel=new NotificationChannel("planner_alarms_v2","Будильники задач",NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Звук будильника воспроизводится отдельно до остановки или в течение минуты");
        channel.setSound(null,null);manager.createNotificationChannel(channel);
        String key=key(id,date);
        Intent open=new Intent(c,MainActivity.class).putExtra("taskId",id).putExtra("date",date).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content=PendingIntent.getActivity(c,key.hashCode(),open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(c,"planner_alarms_v2").setSmallIcon(R.drawable.ic_notification).setContentTitle(title).setContentText(date+" · "+time)
            .setContentIntent(content).setAutoCancel(false).setCategory(Notification.CATEGORY_ALARM)
            .setDeleteIntent(pending(c,"DISMISS",id,date))
            .addAction(new Notification.Action.Builder(null,"Выполнено",pending(c,"DONE",id,date)).build())
            .addAction(new Notification.Action.Builder(null,"Остановить",pending(c,"DISMISS",id,date)).build()).build();
    }

}
