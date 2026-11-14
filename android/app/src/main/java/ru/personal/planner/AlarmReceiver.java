package ru.personal.planner;
import android.content.*;
public final class AlarmReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){String id=intent.getStringExtra("taskId"),date=intent.getStringExtra("date");if(id==null||date==null)return;if("FIRE".equals(intent.getAction())||"TEST".equals(intent.getAction()))AlarmScheduler.prefs(context).edit().putString("lastReceive",intent.getAction()+" · "+java.time.ZonedDateTime.now()).apply();if("TEST".equals(intent.getAction())){SystemTest.event(context,id,"receiver_received","AlarmManager broadcast received");AlarmScheduler.fireTest(context);}else if("FIRE".equals(intent.getAction()))AlarmScheduler.fire(context,id,date);else if("DONE".equals(intent.getAction())||"DISMISS".equals(intent.getAction()))AlarmScheduler.action(context,intent.getAction(),id,date);}
}
