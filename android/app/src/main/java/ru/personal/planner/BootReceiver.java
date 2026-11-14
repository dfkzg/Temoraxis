package ru.personal.planner;
import android.content.*;
public final class BootReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){String action=intent.getAction();if(!java.util.Arrays.asList(Intent.ACTION_BOOT_COMPLETED,Intent.ACTION_TIME_CHANGED,Intent.ACTION_TIMEZONE_CHANGED,"android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED").contains(action))return;String config=AlarmScheduler.prefs(context).getString(AlarmScheduler.CONFIG,null);if(config!=null)AlarmScheduler.reconcile(context,config);}
}
