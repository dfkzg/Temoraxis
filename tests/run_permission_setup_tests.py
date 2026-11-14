"""Exercise the real permission wizard against small Android API fakes (no device claims)."""
import argparse,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--compiler-jar');args=p.parse_args()
sources={
'android/Manifest.java':'''package android; public class Manifest {public static class permission {public static String POST_NOTIFICATIONS="notifications";}}''',
'android/content/Context.java':'''package android.content; public class Context {public static String ALARM_SERVICE="alarm",POWER_SERVICE="power";}''',
'android/content/Intent.java':'''package android.content; public class Intent {public String action;public Intent(String a){action=a;}public Intent(String a,android.net.Uri u){action=a;}public Intent putExtra(String k,String v){return this;}}''',
'android/content/ActivityNotFoundException.java':'''package android.content; public class ActivityNotFoundException extends RuntimeException {}''',
'android/content/DialogInterface.java':'''package android.content; public interface DialogInterface {interface OnClickListener {void onClick(DialogInterface d,int w);}interface OnCancelListener {void onCancel(DialogInterface d);}}''',
'android/content/SharedPreferences.java':'''package android.content; public class SharedPreferences {java.util.Map<String,Object> data=new java.util.HashMap<>();public int getInt(String k,int d){return (int)data.getOrDefault(k,d);}public boolean getBoolean(String k,boolean d){return (boolean)data.getOrDefault(k,d);}public Editor edit(){return new Editor();}public class Editor {public Editor putInt(String k,int v){data.put(k,v);return this;}public Editor putBoolean(String k,boolean v){data.put(k,v);return this;}public void apply(){}}}''',
'android/content/pm/PackageManager.java':'''package android.content.pm;public class PackageManager {public static int PERMISSION_GRANTED=0;public int version=9;public Info getPackageInfo(String n,int f)throws NameNotFoundException{return new Info(version);}public static class Info{public int versionCode;Info(int v){versionCode=v;}}public static class NameNotFoundException extends Exception{}}''',
'android/net/Uri.java':'''package android.net;public class Uri {public static Uri parse(String s){return new Uri();}}''',
'android/os/Build.java':'''package android.os;public class Build {public static String MANUFACTURER="realme",BRAND="realme";public static class VERSION{public static int SDK_INT=36;}}''',
'android/os/PowerManager.java':'''package android.os;public class PowerManager {public boolean exempt;public boolean isIgnoringBatteryOptimizations(String n){return exempt;}}''',
'android/app/AlarmManager.java':'''package android.app;public class AlarmManager {public boolean exact;public boolean canScheduleExactAlarms(){return exact;}}''',
'android/app/AlertDialog.java':'''package android.app;import android.content.*;public class AlertDialog {public static Builder last;public static int shown;public static class Builder {public String title;public DialogInterface.OnClickListener yes,no;public DialogInterface.OnCancelListener cancel;public Builder(Object a){}public Builder setTitle(String t){title=t;return this;}public Builder setMessage(String m){return this;}public Builder setPositiveButton(String t,DialogInterface.OnClickListener l){yes=l;return this;}public Builder setNegativeButton(String t,DialogInterface.OnClickListener l){no=l;return this;}public Builder setOnCancelListener(DialogInterface.OnCancelListener l){cancel=l;return this;}public void show(){last=this;shown++;}}}''',
'android/provider/Settings.java':'''package android.provider;public class Settings {public static String ACTION_APP_NOTIFICATION_SETTINGS="notifications",EXTRA_APP_PACKAGE="package",ACTION_REQUEST_SCHEDULE_EXACT_ALARM="exact",ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS="battery",ACTION_APPLICATION_DETAILS_SETTINGS="details";}''',
'android/widget/Toast.java':'''package android.widget;public class Toast {public static int LENGTH_LONG=1;public static Toast makeText(Object a,String s,int i){return new Toast();}public void show(){}}''',
'ru/personal/planner/MainActivity.java':'''package ru.personal.planner;import android.content.*;public class MainActivity extends Context {public boolean enabled,rationale,finishing,failSettings;public int permission=-1,requests;public Intent opened;public android.app.AlarmManager alarm=new android.app.AlarmManager();public android.os.PowerManager power=new android.os.PowerManager();public android.content.pm.PackageManager pm=new android.content.pm.PackageManager();public SharedPreferences prefs=new SharedPreferences();public boolean notificationsEnabled(){return enabled;}public Object getSystemService(String s){return s.equals(ALARM_SERVICE)?alarm:power;}public String getPackageName(){return "ru.personal.planner";}public SharedPreferences getSharedPreferences(String s,int i){return prefs;}public android.content.pm.PackageManager getPackageManager(){return pm;}public boolean isFinishing(){return finishing;}public boolean isDestroyed(){return false;}public int checkSelfPermission(String p){return permission;}public boolean shouldShowRequestPermissionRationale(String p){return rationale;}public void requestPermissions(String[] p,int r){requests++;}public void startActivity(Intent i){if(failSettings&&!i.action.equals("details"))throw new ActivityNotFoundException();opened=i;}public View getWindow(){return new View();}public static class View {public View getDecorView(){return this;}public void post(Runnable r){r.run();}}}''',
'ru/personal/planner/PermissionSetupTest.java':'''package ru.personal.planner;import android.app.AlertDialog;public class PermissionSetupTest {
static void check(boolean b,String m){if(!b)throw new AssertionError(m);}
static void title(String n){check(AlertDialog.last.title.startsWith(n),"Expected step "+n+", got "+AlertDialog.last.title);}
static void yes(){AlertDialog.last.yes.onClick(null,0);}static void skip(){AlertDialog.last.no.onClick(null,0);}
public static void main(String[] args){
 MainActivity a=new MainActivity();PermissionSetup w=new PermissionSetup(a);w.offerAfterUpdate();title("1");yes();check(a.requests==1,"runtime request missing");w.onResult();title("2");yes();check(a.opened.action.equals("exact"),"exact settings missing");w.onResume();title("3");yes();check(a.opened.action.equals("battery"),"direct battery request missing");w.onResume();title("4");yes();check(a.opened.action.equals("details"),"OEM settings missing");w.onResume();check(!w.active,"wizard did not finish after refusals");
 int shown=AlertDialog.shown;w.offerAfterUpdate();check(AlertDialog.shown==shown,"same version nags again");a.pm.version++;w.offerAfterUpdate();title("1");yes();check(a.opened.action.equals("notifications"),"permanent refusal must open settings");w.onResume();title("2");skip();title("3");skip();title("4");skip();check(!w.active,"skip must finish");
 a.enabled=true;a.alarm.exact=true;a.power.exempt=true;a.pm.version++;w.offerAfterUpdate();title("4");check(w.step==4,"granted permissions must be skipped");skip();
 a.enabled=false;w.start();title("1");a.failSettings=true;yes();check(a.opened.action.equals("details"),"missing OEM screen must fall back");w.onResume();title("4");AlertDialog.last.cancel.onCancel(null);check(!w.active,"cancel must stop wizard");
 android.os.Build.VERSION.SDK_INT=26;android.os.Build.BRAND="generic";android.os.Build.MANUFACTURER="generic";a.enabled=true;a.power.exempt=false;w.start();title("3");skip();check(!w.active,"old Android must skip unsupported exact request and OEM step");
 System.out.println("PASS: revoked permissions after update, sequential runtime/settings requests, permanent denial fallback, skips, version gating, live grants, OEM unknown, older Android");
}}
'''
}
with tempfile.TemporaryDirectory() as temp:
 folder=Path(temp);files=[]
 for name,text in sources.items():
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text);files.append(target)
 files.append(ROOT/'android/app/src/main/java/ru/personal/planner/PermissionSetup.java')
 compiler=['java','-jar',str(Path(args.compiler_jar).resolve()),'-8'] if args.compiler_jar else ['javac','-source','8','-target','8']
 subprocess.run([*compiler,'-encoding','UTF-8','-d',str(folder),*map(str,files)],check=True)
 subprocess.run(['java','-cp',str(folder),'ru.personal.planner.PermissionSetupTest'],check=True)
