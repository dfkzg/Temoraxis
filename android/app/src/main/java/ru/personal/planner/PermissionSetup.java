package ru.personal.planner;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.widget.Toast;

/** Guided setup, offered once per installed version; permission states are always read live. */
final class PermissionSetup {
    static final int NOTIFICATIONS=504;
    final MainActivity activity;
    boolean active,waitingSettings,waitingRuntime;
    int step;
    PermissionSetup(MainActivity activity){this.activity=activity;}
    void offerAfterUpdate(){
        try{
            int version=activity.getPackageManager().getPackageInfo(activity.getPackageName(),0).versionCode;
            android.content.SharedPreferences prefs=activity.getSharedPreferences("permission-prompts",0);
            if(prefs.getInt("setup-version",0)==version)return;
            prefs.edit().putInt("setup-version",version).apply();
            start();
        }catch(PackageManager.NameNotFoundException ignored){}
    }
    void start(){if(active)return;active=true;step=0;next();}
    void next(){
        if(!active||activity.isFinishing()||activity.isDestroyed())return;
        while(step<4){
            int current=step++;
            if(current==0){
                if(activity.notificationsEnabled())continue;
                show("1 из 4 · Уведомления","Разрешите уведомления, чтобы видеть задачи и кнопки остановки будильника. Если Android больше не показывает запрос после отказов, откроются настройки уведомлений.",()->{
                    android.content.SharedPreferences prefs=activity.getSharedPreferences("permission-prompts",0);
                    if(Build.VERSION.SDK_INT>=33&&activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED&&(!prefs.getBoolean("notification-requested",false)||activity.shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS))){
                        prefs.edit().putBoolean("notification-requested",true).apply();waitingRuntime=true;
                        activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFICATIONS);
                    }else open(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,activity.getPackageName()));
                });return;
            }
            if(current==1){
                if(Build.VERSION.SDK_INT<31||((AlarmManager)activity.getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms())continue;
                show("2 из 4 · Точные будильники","Разрешите Temoraxis устанавливать точные будильники, чтобы сигнал не откладывался при выключенном экране.",()->open(new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+activity.getPackageName()))));return;
            }
            if(current==2){
                if(((PowerManager)activity.getSystemService(Context.POWER_SERVICE)).isIgnoringBatteryOptimizations(activity.getPackageName()))continue;
                show("3 из 4 · Работа в фоне","Разрешите работу без оптимизации батареи, чтобы Android меньше ограничивал напоминания после закрытия приложения. Это может увеличить расход батареи.",()->open(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,Uri.parse("package:"+activity.getPackageName()))));return;
            }
            if(current==3){
                String brand=(Build.MANUFACTURER+" "+Build.BRAND).toLowerCase(java.util.Locale.ROOT);
                if(!brand.contains("realme")&&!brand.contains("oppo")&&!brand.contains("oneplus"))continue;
                show("4 из 4 · Автозапуск телефона","В настройках Temoraxis разрешите автозапуск и фоновую активность, если эти пункты есть. Для кнопки «Закрыть все» также закрепите карточку приложения замком в недавних. Android не позволяет приложению проверить эти настройки realme — здесь нельзя автоматически подтвердить, что они включены.",()->open(details()));return;
            }
        }
        active=false;
        Toast.makeText(activity,"Проверка завершена. Повторить можно в настройках через «Меню приложения».",Toast.LENGTH_LONG).show();
    }
    void show(String title,String message,Runnable request){
        new AlertDialog.Builder(activity).setTitle(title).setMessage(message)
            .setPositiveButton("Настроить",(d,w)->request.run())
            .setNegativeButton("Пропустить",(d,w)->later())
            .setOnCancelListener(d->{active=false;}).show();
    }
    Intent details(){return new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+activity.getPackageName()));}
    void open(Intent intent){
        waitingSettings=true;
        try{activity.startActivity(intent);}
        catch(ActivityNotFoundException|SecurityException e){
            try{activity.startActivity(details());}
            catch(ActivityNotFoundException|SecurityException ignored){waitingSettings=false;later();}
        }
    }
    void later(){activity.getWindow().getDecorView().post(()->next());}
    void onResume(){if(active&&waitingSettings){waitingSettings=false;later();}}
    void onResult(){if(active&&waitingRuntime){waitingRuntime=false;later();}}
}
