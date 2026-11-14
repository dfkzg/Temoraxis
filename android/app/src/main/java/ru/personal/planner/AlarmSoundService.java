package ru.personal.planner;

import android.app.*;
import android.content.*;
import android.media.*;
import android.os.*;

/** Only runs while an alarm is sounding; scheduled alarms belong to AlarmManager. */
public final class AlarmSoundService extends Service {
    MediaPlayer player;
    String activeKey;
    final Handler handler=new Handler(Looper.getMainLooper());
    final Runnable timeout=()->stopSelf();
    @Override public IBinder onBind(Intent intent){return null;}
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        String id=intent.getStringExtra("taskId"),date=intent.getStringExtra("date");
        if(id==null||date==null){stopSelf();return START_NOT_STICKY;}
        SystemTest.event(this,id,"service_received","onStartCommand reached");
        activeKey=AlarmScheduler.key(id,date);
        AlarmScheduler.prefs(this).edit().putString("sounding",activeKey).apply();
        // Promote before touching audio, including when launched with the screen off.
        startForeground(activeKey.hashCode(),AlarmScheduler.notification(this,id,date,intent.getStringExtra("title"),intent.getStringExtra("time")));
        releasePlayer();
        try{
            player=new MediaPlayer();
            player.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            android.net.Uri sound=RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            if(sound==null)sound=RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
            player.setDataSource(this,sound);player.setLooping(true);player.setWakeMode(this,PowerManager.PARTIAL_WAKE_LOCK);
            player.setOnErrorListener((p,what,extra)->{SystemTest.event(this,id,"audio_error",what+" / "+extra);AlarmScheduler.prefs(this).edit().putString("audioState","ошибка плеера: "+what+" / "+extra).apply();stopSelf();return true;});
            player.prepare();player.start();SystemTest.event(this,id,"audio_started","MediaPlayer.start returned; audibility must be confirmed by user");AlarmScheduler.prefs(this).edit().putString("audioState","воспроизведение запущено · "+java.time.ZonedDateTime.now()).apply();
        }catch(Exception e){SystemTest.event(this,id,"audio_error",e.toString());AlarmScheduler.prefs(this).edit().putString("audioState",e.toString()).apply();android.util.Log.w("Planner","Could not play alarm",e);stopSelf();}
        handler.removeCallbacks(timeout);handler.postDelayed(timeout,60000);
        return START_NOT_STICKY;
    }
    void releasePlayer(){if(player!=null){player.release();player=null;}}
    @Override public void onDestroy(){if(activeKey!=null&&activeKey.startsWith("alarm-test|"))SystemTest.event(this,"alarm-test","audio_stopped","Service destroyed: action, timeout or system stop");handler.removeCallbacks(timeout);releasePlayer();if(activeKey!=null&&activeKey.equals(AlarmScheduler.prefs(this).getString("sounding",null)))AlarmScheduler.prefs(this).edit().remove("sounding").apply();stopForeground(STOP_FOREGROUND_DETACH);super.onDestroy();}
}
