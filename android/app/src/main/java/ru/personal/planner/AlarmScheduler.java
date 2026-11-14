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
            JSONObject sent=object(c,SENT),dismissed=object(c,DISMISSED),done=object(c,DONE);
            ReminderCalculator.resetForEdits(object(c,CONFIG),config,sent,dismissed,done);
            String sounding=prefs(c).getString("sounding",null);if(sounding!=null&&!sounding.startsWith("alarm-test|")&&!sent.has(sounding))c.stopService(new Intent(c,AlarmSoundService.class));
            prefs(c).edit().putString(CONFIG,json).putString(SENT,sent.toString()).putString(DISMISSED,dismissed.toString()).putString(DONE,done.toString()).apply();
            AlarmManager manager=(AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
            JSONArray previous=new JSONArray(prefs(c).getString(SCHEDULED,"[]"));
            for(int i=0;i<previous.length();i++){JSONObject record=previous.getJSONObject(i);manager.cancel(pending(c,"FIRE",record.getString("id"),record.getString("date")));}
            JSONArray scheduled=new JSONArray();
            if(config.optBoolean("enabled")&&((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).areNotificationsEnabled()){
                long now=System.currentTimeMillis();
                for(int i=0;i<tasks.length();i++){
                    JSONObject task=tasks.optJSONObject(i);
                    JSONObject next=ReminderCalculator.next(task,ZoneId.systemDefault(),now,sent,dismissed,done);
                    if(next==null)continue;
                    String id=task.getString("id"),nextDate=next.getString("date");long earliest=next.getLong("due");
                    PendingIntent alarm=pending(c,"FIRE",id,nextDate);
                    schedule(c,manager,earliest,alarm);
                    scheduled.put(new JSONObject().put("id",id).put("date",nextDate).put("due",earliest).put("title",task.optString("title","Задача")));
                }
            }else {
                String active=prefs(c).getString("sounding","");
                if(!active.startsWith("alarm-test|")){c.stopService(new Intent(c,AlarmSoundService.class));((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).cancelAll();}
                else for(int i=0;i<previous.length();i++){JSONObject record=previous.getJSONObject(i);((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(key(record.getString("id"),record.getString("date")).hashCode());}
            }
            prefs(c).edit().putString(SCHEDULED,scheduled.toString()).putString("scheduleError","").apply();
        }catch(Exception e){prefs(c).edit().putString("scheduleError",e.toString()).apply();android.util.Log.w("Planner","Could not update reminders",e);}
    }
    static synchronized JSONArray pendingCompletions(Context c){JSONObject pending=object(c,PENDING);JSONArray values=new JSONArray();Iterator<String> keys=pending.keys();while(keys.hasNext()){String key=keys.next();JSONObject record=pending.optJSONObject(key);if(record!=null)values.put(record);}return values;}
    static synchronized void acknowledge(Context c,String key){JSONObject pending=object(c,PENDING);pending.remove(key);prefs(c).edit().putString(PENDING,pending.toString()).apply();}
    static synchronized void action(Context c,String action,String id,String date){
        try{SystemTest.event(c,id,"notification_action",action);String key=key(id,date);JSONObject config=object(c,CONFIG),tasksDone=object(c,DONE);
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
            prefs(c).edit().putString("lastFire",date+" · "+task.optString("title")+" · "+java.time.ZonedDateTime.now().toString()).apply();
            deliver(c,id,date,task.optString("title","Задача"),task.optString("time"));
            reconcile(c,config.toString());
        }catch(Exception e){android.util.Log.w("Planner","Could not show reminder",e);}
    }
    static void schedule(Context c,AlarmManager manager,long due,PendingIntent alarm){
        try{if(Build.VERSION.SDK_INT<31||manager.canScheduleExactAlarms())manager.setAlarmClock(new AlarmManager.AlarmClockInfo(due,PendingIntent.getActivity(c,0,new Intent(c,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE)),alarm);else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,due,alarm);}
        catch(SecurityException e){manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,due,alarm);}
    }
    static void test(Context c){
        String previous=prefs(c).getString("testDate",null);if(previous!=null)((AlarmManager)c.getSystemService(Context.ALARM_SERVICE)).cancel(pending(c,"TEST","alarm-test",previous));
        String date=java.time.LocalDate.now().toString();long due=System.currentTimeMillis()+15000;
        schedule(c,(AlarmManager)c.getSystemService(Context.ALARM_SERVICE),due,pending(c,"TEST","alarm-test",date));
        prefs(c).edit().putLong("testDue",due).putString("testDate",date).apply();
    }
    static void fireTest(Context c){
        prefs(c).edit().putLong("testDue",0).putString("lastFire","Тест · "+java.time.ZonedDateTime.now().toString()).apply();
        deliver(c,"alarm-test",java.time.LocalDate.now().toString(),"Проверка будильника",java.time.LocalTime.now().withSecond(0).withNano(0).toString());
    }
    static void deliver(Context c,String id,String date,String title,String time){
        String key=key(id,date);
            NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
            Notification notification=notification(c,id,date,title,time);
            try{manager.notify(key.hashCode(),notification);SystemTest.event(c,id,"notification_posted","NotificationManager.notify returned; visibility must be confirmed by user");}catch(SecurityException e){prefs(c).edit().putString("notificationError",e.toString()).apply();SystemTest.event(c,id,"notification_error",e.toString());}
            prefs(c).edit().putString("audioState","запрошен запуск фонового звука · "+java.time.ZonedDateTime.now()).apply();
            try{c.startForegroundService(new Intent(c,AlarmSoundService.class).putExtra("taskId",id).putExtra("date",date).putExtra("title",title).putExtra("time",time));SystemTest.event(c,id,"service_start_requested","startForegroundService returned");}
            catch(RuntimeException e){
                prefs(c).edit().putString("audioState","запуск службы запрещён: "+e).apply();SystemTest.event(c,id,"service_start_error",e.toString());
                android.util.Log.w("Planner","Android blocked alarm audio service; using notification sound",e);
                NotificationChannel fallback=new NotificationChannel("planner_alarm_fallback_v1","Напоминания без фоновой службы",NotificationManager.IMPORTANCE_HIGH);
                fallback.setSound(android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_ALARM),new android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ALARM).build());manager.createNotificationChannel(fallback);
                try{manager.notify(key.hashCode(),Notification.Builder.recoverBuilder(c,notification).setChannelId("planner_alarm_fallback_v1").build());}catch(SecurityException ignored){}
            }
    }
    static String diagnostics(Context c){
        StringBuilder text=new StringBuilder();
        NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
        text.append("Время телефона: ").append(java.time.ZonedDateTime.now()).append("\n");
        text.append("Разрешение уведомлений: ").append(manager.areNotificationsEnabled()?"да":"НЕТ").append("\n");
        NotificationChannel channel=manager.getNotificationChannel("planner_alarms_v2");
        text.append("Канал будильников: ").append(channel==null?"ещё не создан":channel.getImportance()==NotificationManager.IMPORTANCE_NONE?"ЗАБЛОКИРОВАН":"разрешён").append("\n");
        text.append("Точные будильники: ").append(Build.VERSION.SDK_INT<31||((AlarmManager)c.getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms()?"да":"НЕТ").append("\n");
        text.append("Без оптимизации батареи: ").append(((android.os.PowerManager)c.getSystemService(Context.POWER_SERVICE)).isIgnoringBatteryOptimizations(c.getPackageName())?"да":"НЕТ").append("\n");
        JSONObject config=object(c,CONFIG);text.append("Напоминания в самом планёре: ").append(config.optBoolean("enabled")?"включены":"ВЫКЛЮЧЕНЫ").append("\n");
        JSONArray tasks=config.optJSONArray("tasks");text.append("Задач передано Android: ").append(tasks==null?0:tasks.length()).append("\n");
        try{JSONArray alarms=new JSONArray(prefs(c).getString(SCHEDULED,"[]"));text.append("Сохранённых назначений: ").append(alarms.length()).append("\n");long earliest=Long.MAX_VALUE;JSONObject next=null;for(int i=0;i<alarms.length();i++){JSONObject alarm=alarms.getJSONObject(i);long due=alarm.optLong("due",Long.MAX_VALUE);if(due<earliest){earliest=due;next=alarm;}}if(next!=null)text.append("Ближайшее: ").append(next.optString("title")).append(" · ").append(java.time.Instant.ofEpochMilli(earliest).atZone(java.time.ZoneId.systemDefault())).append("\n");}catch(Exception ignored){}
        text.append("Последний сигнал от Android: ").append(prefs(c).getString("lastReceive","не зарегистрирован")).append("\n");
        text.append("Последняя доставка: ").append(prefs(c).getString("lastFire","не зарегистрирована")).append("\n");
        android.media.AudioManager audio=(android.media.AudioManager)c.getSystemService(Context.AUDIO_SERVICE);
        text.append("Громкость будильника: ").append(audio.getStreamVolume(android.media.AudioManager.STREAM_ALARM)).append(" / ").append(audio.getStreamMaxVolume(android.media.AudioManager.STREAM_ALARM)).append("\n");
        text.append("Звук: ").append(prefs(c).getString("audioState","ещё не запускался")).append("\n");
        String notifyError=prefs(c).getString("notificationError","");if(!notifyError.isEmpty())text.append("Ошибка уведомления: ").append(notifyError).append("\n");
        String error=prefs(c).getString("scheduleError","");if(!error.isEmpty())text.append("Ошибка расписания: ").append(error).append("\n");
        text.append("Автозапуск realme: Android не сообщает состояние.\nТест проверяет системный будильник независимо от переключателя в планёре.");
        return text.toString();
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
