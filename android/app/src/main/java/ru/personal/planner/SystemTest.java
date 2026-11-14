package ru.personal.planner;

import android.app.*;
import android.content.*;
import android.media.AudioManager;
import android.os.*;
import android.text.InputFilter;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.nio.charset.StandardCharsets;

/** User-run diagnostic: device facts, native delivery events and explicit user observations. */
final class SystemTest {
    static final String REPORT="system_test_report";
    static JSONObject read(Context c){return AlarmScheduler.object(c,REPORT);}
    static void write(Context c,JSONObject report){AlarmScheduler.prefs(c).edit().putString(REPORT,report.toString()).commit();}
    static JSONObject snapshot(Context c){
        JSONObject value=new JSONObject();
        try{
            NotificationManager notifications=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
            AlarmManager alarms=(AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
            PowerManager power=(PowerManager)c.getSystemService(Context.POWER_SERVICE);
            AudioManager audio=(AudioManager)c.getSystemService(Context.AUDIO_SERVICE);
            android.content.pm.PackageInfo app=c.getPackageManager().getPackageInfo(c.getPackageName(),0);
            value.put("appVersion",app.versionName).put("versionCode",app.versionCode).put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("androidRelease",Build.VERSION.RELEASE).put("androidSdk",Build.VERSION.SDK_INT);
            value.put("capturedAt",java.time.ZonedDateTime.now().toString()).put("timezone",java.time.ZoneId.systemDefault().toString()).put("notificationsAllowed",notifications.areNotificationsEnabled());
            NotificationChannel channel=notifications.getNotificationChannel("planner_alarms_v2");
            value.put("alarmChannelImportance",channel==null?JSONObject.NULL:channel.getImportance());
            value.put("exactAlarmsAllowed",Build.VERSION.SDK_INT<31||alarms.canScheduleExactAlarms()).put("batteryOptimizationExempt",power.isIgnoringBatteryOptimizations(c.getPackageName())).put("batterySaver",power.isPowerSaveMode()).put("screenInteractive",power.isInteractive());
            value.put("backgroundRestricted",Build.VERSION.SDK_INT>=28&&((ActivityManager)c.getSystemService(Context.ACTIVITY_SERVICE)).isBackgroundRestricted());
            value.put("deviceLocked",((KeyguardManager)c.getSystemService(Context.KEYGUARD_SERVICE)).isKeyguardLocked());
            value.put("alarmVolume",audio.getStreamVolume(AudioManager.STREAM_ALARM)).put("alarmVolumeMax",audio.getStreamMaxVolume(AudioManager.STREAM_ALARM)).put("interruptionFilter",notifications.getCurrentInterruptionFilter());
            JSONObject config=AlarmScheduler.object(c,AlarmScheduler.CONFIG);JSONArray tasks=config.optJSONArray("tasks");
            value.put("plannerRemindersEnabled",config.optBoolean("enabled")).put("tasksPassedToAndroid",tasks==null?0:tasks.length());
            JSONArray scheduled=new JSONArray(AlarmScheduler.prefs(c).getString(AlarmScheduler.SCHEDULED,"[]"));
            value.put("savedScheduleCount",scheduled.length());long earliest=Long.MAX_VALUE;
            for(int i=0;i<scheduled.length();i++)earliest=Math.min(earliest,scheduled.getJSONObject(i).optLong("due",Long.MAX_VALUE));
            value.put("savedNextDue",earliest==Long.MAX_VALUE?JSONObject.NULL:java.time.Instant.ofEpochMilli(earliest).atZone(java.time.ZoneId.systemDefault()).toString());
            value.put("scheduleError",AlarmScheduler.prefs(c).getString("scheduleError","")).put("oemAutostart","not_observable_by_android_api");
        }catch(Exception e){try{value.put("snapshotError",e.toString());}catch(JSONException ignored){}}
        return value;
    }
    static synchronized void event(Context c,String id,String stage,String detail){
        if(!"alarm-test".equals(id))return;
        JSONObject report=read(c);if(!report.has("startedAt"))return;
        try{
            JSONArray events=report.optJSONArray("events");if(events==null)events=new JSONArray();
            if(events.length()<100)events.put(new JSONObject().put("at",java.time.ZonedDateTime.now().toString()).put("stage",stage).put("detail",detail).put("device",snapshot(c)));
            report.put("events",events);write(c,report);
        }catch(JSONException ignored){}
    }
    static void open(MainActivity a){
        JSONObject report=read(a);
        if(!report.has("startedAt")){confirmStart(a);return;}
        new AlertDialog.Builder(a).setTitle("Тест системы").setMessage("Можно запустить новый тест, записать наблюдения или открыть последний отчёт.")
            .setPositiveButton("Новый тест",(d,w)->confirmStart(a)).setNeutralButton("Записать результат",(d,w)->observations(a)).setNegativeButton("Отчёт",(d,w)->showReport(a)).show();
    }
    static void confirmStart(MainActivity a){
        new AlertDialog.Builder(a).setTitle("Тест системы · 15 секунд")
            .setMessage("Приложение проверит разрешения и назначит системный будильник через 15 секунд. Выберите состояние телефона для проверки: оставьте приложение открытым, выключите экран или нажмите «Закрыть все». Затем откройте Temoraxis и запишите, были ли звук и уведомление.\n\nВ отчёте будут модель телефона, настройки разрешений, этапы доставки и ваши ответы. Содержимое задач и аккаунт не включаются. Отчёт отправляете вы сами.")
            .setPositiveButton("Начать тест",(d,w)->start(a)).setNegativeButton("Отмена",null).show();
    }
    static void start(MainActivity a){
        try{
            JSONObject report=new JSONObject().put("format","temoraxis-system-test-v1").put("startedAt",java.time.ZonedDateTime.now().toString()).put("state","running").put("before",snapshot(a)).put("events",new JSONArray());
            write(a,report);
            AlarmScheduler.test(a);
            report=read(a);report.put("dueAtMillis",AlarmScheduler.prefs(a).getLong("testDue",0));write(a,report);
            event(a,"alarm-test","scheduled","AlarmManager; 15 seconds; inexact fallback if exact permission unavailable");
            Toast.makeText(a,"Тест начат: ожидайте сигнал через 15 секунд. После проверки запишите результат.",Toast.LENGTH_LONG).show();
            a.getWindow().getDecorView().postDelayed(()->offerResult(a),18000);
        }catch(Exception e){event(a,"alarm-test","schedule_error",e.toString());observations(a);}
    }
    static void offerResult(MainActivity a){
        JSONObject report=read(a);
        if(!a.foreground||a.isFinishing()||a.isDestroyed()||!a.hasWindowFocus()||a.permissionSetup.active)return;
        if("running".equals(report.optString("state"))&&System.currentTimeMillis()>=report.optLong("dueAtMillis",Long.MAX_VALUE)+2000)observations(a);
    }
    static RadioGroup answer(MainActivity a,LinearLayout layout,String question,String[] choices){
        TextView title=new TextView(a);title.setText(question);layout.addView(title);
        RadioGroup group=new RadioGroup(a);
        for(String choice:choices){RadioButton button=new RadioButton(a);button.setText(choice);button.setId(View.generateViewId());group.addView(button);}
        group.check(group.getChildAt(choices.length-1).getId());layout.addView(group);return group;
    }
    static void restore(RadioGroup group,String value){for(int i=0;i<group.getChildCount();i++){RadioButton button=(RadioButton)group.getChildAt(i);if(button.getText().toString().equals(value))group.check(button.getId());}}
    static String selected(RadioGroup group){RadioButton button=group.findViewById(group.getCheckedRadioButtonId());return button==null?"Не указано":button.getText().toString();}
    static void observations(MainActivity a){
        JSONObject current=read(a);if(!current.has("startedAt")){confirmStart(a);return;}
        long due=current.optLong("dueAtMillis",0);
        if(due>System.currentTimeMillis()){
            new AlertDialog.Builder(a).setTitle("Тест ещё идёт").setMessage("До назначенного времени осталось примерно "+Math.max(1,(due-System.currentTimeMillis())/1000)+" секунд. Вернитесь после сигнала или если он не сработает.").setPositiveButton("Понятно",null).show();return;
        }
        try{current.put("state","awaiting_observations");write(a,current);}catch(JSONException ignored){}
        LinearLayout content=new LinearLayout(a);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(a.dp(20),a.dp(12),a.dp(20),a.dp(12));
        RadioGroup notification=answer(a,content,"Было уведомление?",new String[]{"Да","Нет","Не уверен"});
        RadioGroup sound=answer(a,content,"Был слышен будильник?",new String[]{"Да","Нет","Не уверен"});
        RadioGroup mode=answer(a,content,"В каком состоянии был телефон?",new String[]{"Приложение открыто, экран включён","Приложение свёрнуто, экран выключен","После «Закрыть все»","Другое / не указано"});
        EditText notes=new EditText(a);notes.setHint("Что произошло? Дополнительные наблюдения");notes.setMinLines(2);notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(5000)});content.addView(notes);
        JSONObject saved=current.optJSONObject("observations");if(saved!=null){restore(notification,saved.optString("notificationSeen"));restore(sound,saved.optString("alarmHeard"));restore(mode,saved.optString("phoneState"));notes.setText(saved.optString("notes"));}
        ScrollView scroll=new ScrollView(a);scroll.addView(content);
        new AlertDialog.Builder(a).setTitle("Результат теста системы").setView(scroll)
            .setPositiveButton("Составить отчёт",(d,w)->{
                try{JSONObject report=read(a);report.put("observations",new JSONObject().put("notificationSeen",selected(notification)).put("alarmHeard",selected(sound)).put("phoneState",selected(mode)).put("notes",notes.getText().toString())).put("after",snapshot(a)).put("state","recorded");write(a,report);}catch(JSONException ignored){}
                showReport(a);
            }).setNegativeButton("Позже",null).show();
    }
    static String reportText(Context c){
        try{return "Temoraxis · Тест системы\nАвтоматические события не доказывают, что пользователь видел уведомление или слышал звук; это записано в observations.\nСохранённые назначения не гарантируют доставку Android.\n\n"+read(c).toString(2);}
        catch(JSONException e){return read(c).toString();}
    }
    static void showReport(MainActivity a){
        TextView text=new TextView(a);text.setText(reportText(a));text.setTextIsSelectable(true);text.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));
        ScrollView scroll=new ScrollView(a);scroll.addView(text);
        new AlertDialog.Builder(a).setTitle("Отчёт теста системы").setView(scroll)
            .setPositiveButton("Сохранить файл",(d,w)->{
                a.pendingExport=reportText(a).getBytes(StandardCharsets.UTF_8);
                Intent save=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("text/plain").putExtra(Intent.EXTRA_TITLE,"temoraxis-system-test-"+System.currentTimeMillis()+".txt");
                try{a.startActivityForResult(save,503);}catch(ActivityNotFoundException e){a.pendingExport=null;Toast.makeText(a,"Сохранение недоступно — используйте копирование отчёта",Toast.LENGTH_LONG).show();}
            }).setNeutralButton("Скопировать",(d,w)->{((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Temoraxis system test",reportText(a)));Toast.makeText(a,"Отчёт скопирован",Toast.LENGTH_SHORT).show();}).setNegativeButton("Закрыть",null).show();
    }
}
