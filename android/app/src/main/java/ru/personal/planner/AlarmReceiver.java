package ru.personal.planner;
import android.content.*;
public final class AlarmReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){String id=intent.getStringExtra("taskId"),date=intent.getStringExtra("date");if(id==null||date==null)return;if("FIRE".equals(intent.getAction()))AlarmScheduler.fire(context,id,date);else if("DONE".equals(intent.getAction())||"DISMISS".equals(intent.getAction()))AlarmScheduler.action(context,intent.getAction(),id,date);}
}
