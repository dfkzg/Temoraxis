package ru.personal.planner;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class MainActivity extends Activity {
    static final String ORIGIN="https://appassets.androidplatform.net";
    WebView web;
    ValueCallback<Uri[]> fileCallback;
    byte[] pendingExport;
    String pendingTaskId,pendingTaskDate;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
        pendingTaskId=getIntent().getStringExtra("taskId");pendingTaskDate=getIntent().getStringExtra("date");
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(Color.rgb(10,10,18));
        root.setOnApplyWindowInsetsListener((v,insets)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.ime());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return WindowInsets.CONSUMED;}
            return insets;
        });
        LinearLayout toolbar=new LinearLayout(this); toolbar.setGravity(Gravity.CENTER_VERTICAL); toolbar.setBackgroundColor(Color.rgb(18,18,28));
        addTab(toolbar,"Temoraxis",()->load("planner.html"));addTab(toolbar,"Экспресс-панель",()->load("Start_page.html"));
        Button menu=new Button(this);menu.setText("⋮");menu.setTextColor(Color.WHITE);menu.setBackgroundColor(Color.TRANSPARENT);menu.setContentDescription("Разрешения приложения");
        menu.setOnClickListener(v->{PopupMenu popup=new PopupMenu(this,menu);popup.getMenu().add("Разрешить уведомления").setOnMenuItemClickListener(item->{requestNotifications();return true;});popup.getMenu().add("Точные напоминания").setOnMenuItemClickListener(item->{requestExactAlarms();return true;});popup.getMenu().add("Работа в фоне").setOnMenuItemClickListener(item->{new AlertDialog.Builder(this).setTitle("Напоминания после закрытия").setMessage("Для Temoraxis выберите режим батареи «Без ограничений» и разрешите автозапуск, если он есть в настройках телефона. Для будильников вовремя также разрешите «Точные напоминания» в меню приложения. Принудительная остановка приложения отключает напоминания до следующего открытия.").setPositiveButton("Настройки приложения",(d,w)->startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName())))).setNegativeButton("Понятно",null).show();return true;});popup.getMenu().add("О приложении").setOnMenuItemClickListener(item->{new AlertDialog.Builder(this).setTitle("Temoraxis · 0.1.7").setMessage("Локальные задачи и системные напоминания. Синхронизация подключается в настройках после размещения сервера. Фоновые напоминания используют системный звук будильника Android и его громкость. Сигнал звучит до остановки или в течение минуты.").setPositiveButton("Понятно",null).show();return true;});popup.show();});
        toolbar.addView(menu,new LinearLayout.LayoutParams(dp(48),dp(44)));root.addView(toolbar);
        web=new WebView(this);web.setBackgroundColor(Color.rgb(10,10,18));
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setSupportMultipleWindows(false);
        web.addJavascriptInterface(new NativeBridge(),"PlannerAndroid");
        web.setWebViewClient(new WebViewClient(){
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if("https".equals(uri.getScheme())&&"appassets.androidplatform.net".equals(uri.getHost())){
                    String path=uri.getPath();if(path==null||"/".equals(path))path="/planner.html";
                    Set<String> allowed=new HashSet<>(Arrays.asList("/planner.html","/Start_page.html","/sync.js","/sync.css","/manifest.webmanifest","/icon.svg","/icon-180.png","/icon-192.png","/icon-512.png","/sw.js"));
                    if(!allowed.contains(path))return response("text/plain","Не найдено",404);
                    try{String type=path.endsWith(".html")?"text/html":path.endsWith(".js")?"application/javascript":path.endsWith(".css")?"text/css":path.endsWith(".svg")?"image/svg+xml":path.endsWith(".png")?"image/png":"application/json";WebResourceResponse asset=new WebResourceResponse(type,path.endsWith(".png")?null:"UTF-8",getAssets().open(path.substring(1)));Map<String,String> headers=new HashMap<>();headers.put("X-Content-Type-Options","nosniff");headers.put("Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src https:; img-src 'self' data: blob: https:; media-src 'self' blob: data:; object-src 'none'; frame-src 'none'; base-uri 'self'");asset.setResponseHeaders(headers);return asset;}catch(IOException e){return response("text/plain","Не найдено",404);}
                }
                if(request.isForMainFrame())return response("text/plain","Откройте внешнюю ссылку в браузере.",403);
                return null;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if("https".equals(uri.getScheme())&&"appassets.androidplatform.net".equals(uri.getHost()))return false;
                if(request.isForMainFrame()&&("https".equals(uri.getScheme())||"http".equals(uri.getScheme()))){try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(ActivityNotFoundException e){Toast.makeText(MainActivity.this,"Нет приложения для этой ссылки",Toast.LENGTH_SHORT).show();}}
                return true;
            }
            @Override public void onPageFinished(WebView view,String url){injectNativeState();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(fileCallback!=null)fileCallback.onReceiveValue(null);fileCallback=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.setType("*/*");intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try{startActivityForResult(intent,501);}catch(ActivityNotFoundException e){callback.onReceiveValue(null);fileCallback=null;}return true;
            }
            @Override public boolean onJsConfirm(WebView view,String url,String message,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(message).setPositiveButton("Подтвердить",(d,w)->result.confirm()).setNegativeButton("Отмена",(d,w)->result.cancel()).setOnCancelListener(d->result.cancel()).show();return true;}
            @Override public boolean onJsAlert(WebView view,String url,String message,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(message).setPositiveButton("Понятно",(d,w)->result.confirm()).setOnCancelListener(d->result.confirm()).show();return true;}
        });
        root.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        if(saved==null||web.restoreState(saved)==null)load("planner.html");
        if(saved==null)web.post(()->offerNotificationPermission());
        if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(0,()->handleBack());
    }
    int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    void addTab(LinearLayout bar,String text,Runnable action){Button button=new Button(this);button.setText(text);button.setTextSize(12);button.setTextColor(Color.rgb(185,195,255));button.setAllCaps(false);button.setBackgroundColor(Color.TRANSPARENT);button.setOnClickListener(v->action.run());bar.addView(button,new LinearLayout.LayoutParams(0,dp(44),1));}
    void load(String path){web.loadUrl(ORIGIN+"/"+path);}
    static WebResourceResponse response(String type,String text,int status){return new WebResourceResponse(type,"UTF-8",status,status==404?"Not Found":"Forbidden",Collections.emptyMap(),new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));}
    boolean notificationsEnabled(){return ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).areNotificationsEnabled();}
    void openNotificationSettings(){startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName()));}
    void offerNotificationPermission(){
        SharedPreferences prefs=getSharedPreferences("permission-prompts",MODE_PRIVATE);
        if(notificationsEnabled()){offerExactAlarmPermission();return;}
        if(prefs.getBoolean("notification-intro-shown",false))return;
        prefs.edit().putBoolean("notification-intro-shown",true).apply();
        new AlertDialog.Builder(this).setTitle("Разрешить уведомления?")
            .setMessage("Temoraxis отправляет напоминания о задачах, даже когда приложение свёрнуто. Разрешите уведомления, чтобы видеть эти напоминания.")
            .setPositiveButton("Разрешить",(d,w)->requestNotifications()).setNegativeButton("Позже",null).show();
    }
    void requestNotifications(){
        SharedPreferences prefs=getSharedPreferences("permission-prompts",MODE_PRIVATE);
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){
            if(prefs.getBoolean("notification-requested",false)&&!shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)){
                new AlertDialog.Builder(this).setTitle("Уведомления отключены").setMessage("Android больше не показывает запрос. Разрешите уведомления для Temoraxis в настройках приложения.").setPositiveButton("Открыть настройки",(d,w)->openNotificationSettings()).setNegativeButton("Позже",null).show();
            }else{prefs.edit().putBoolean("notification-requested",true).apply();requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},502);}
        }else if(!notificationsEnabled())openNotificationSettings();
        else Toast.makeText(this,"Уведомления разрешены",Toast.LENGTH_SHORT).show();
    }
    void offerExactAlarmPermission(){
        if(Build.VERSION.SDK_INT<31||!notificationsEnabled()||((AlarmManager)getSystemService(ALARM_SERVICE)).canScheduleExactAlarms())return;
        SharedPreferences prefs=getSharedPreferences("permission-prompts",MODE_PRIVATE);
        if(prefs.getBoolean("exact-intro-shown",false))return;
        prefs.edit().putBoolean("exact-intro-shown",true).apply();
        new AlertDialog.Builder(this).setTitle("Будильники вовремя").setMessage("Разрешите точные будильники для Temoraxis, чтобы напоминания срабатывали при выключенном экране. В открывшихся настройках включите разрешение для приложения.").setPositiveButton("Разрешить",(d,w)->requestExactAlarms()).setNegativeButton("Позже",null).show();
    }
    void requestExactAlarms(){if(Build.VERSION.SDK_INT>=31&&!((AlarmManager)getSystemService(ALARM_SERVICE)).canScheduleExactAlarms())startActivity(new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+getPackageName())));else Toast.makeText(this,"Точные напоминания доступны",Toast.LENGTH_SHORT).show();}
    void injectNativeState(){if(web==null)return;if(pendingTaskId!=null && web.getUrl()!=null && web.getUrl().endsWith("planner.html")){String id=pendingTaskId,date=pendingTaskDate;web.evaluateJavascript("(function(){if(typeof navigateToTasks!=='function')return false;navigateToTasks("+JSONObject.quote(id)+","+JSONObject.quote(date)+");return true;})()",result->{if("true".equals(result)&&id.equals(pendingTaskId)){pendingTaskId=null;pendingTaskDate=null;}});}String pending=AlarmScheduler.pendingCompletions(this).toString();web.evaluateJavascript("window.dispatchEvent(new CustomEvent('planner-native-resume',{detail:"+pending+"}));",null);}
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);pendingTaskId=intent.getStringExtra("taskId");pendingTaskDate=intent.getStringExtra("date");if(pendingTaskId!=null)load("planner.html");}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==502){String config=AlarmScheduler.prefs(this).getString(AlarmScheduler.CONFIG,null);if(config!=null)AlarmScheduler.reconcile(this,config);injectNativeState();if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)web.post(()->offerExactAlarmPermission());if(results.length>0&&results[0]!=PackageManager.PERMISSION_GRANTED)Toast.makeText(this,"Уведомления отключены. Их можно разрешить в меню ⋮",Toast.LENGTH_LONG).show();}}
    @Override protected void onResume(){super.onResume();String config=AlarmScheduler.prefs(this).getString(AlarmScheduler.CONFIG,null);if(config!=null)AlarmScheduler.reconcile(this,config);if(web!=null){web.onResume();injectNativeState();}}
    @Override protected void onPause(){if(web!=null)web.onPause();super.onPause();}
    @Override protected void onSaveInstanceState(Bundle state){web.saveState(state);super.onSaveInstanceState(state);}
    @Override public void onBackPressed(){handleBack();}
    void handleBack(){web.evaluateJavascript("(function(){if(window.PlannerSync&&PlannerSync.closeIfOpen())return 'closed';var cal=document.getElementById('startCalendarDisclosure');if(cal&&cal.open&&matchMedia('(max-width:1100px)').matches){cal.open=false;return 'closed'}var m=document.querySelector('.modal-bg.open');if(m&&typeof closeModal==='function'){closeModal(m.id);return 'closed'}if(typeof closeTaskModal==='function'&&!document.getElementById('taskModalBg').hidden){closeTaskModal();return 'closed'}var d=document.getElementById('tasksDetail');if(d&&!d.hidden&&typeof closeTaskDetail==='function'){closeTaskDetail();return 'closed'}return 'back'})()",result->{if(!"\"closed\"".equals(result)){if(web.canGoBack())web.goBack();else new AlertDialog.Builder(this).setMessage("Закрыть планёр?").setPositiveButton("Закрыть",(d,w)->finish()).setNegativeButton("Остаться",null).show();}});}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==503){if(result==RESULT_OK&&data!=null&&data.getData()!=null&&pendingExport!=null){try(java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){out.write(pendingExport);Toast.makeText(this,"Файл сохранён",Toast.LENGTH_SHORT).show();}catch(Exception e){Toast.makeText(this,"Не удалось сохранить файл",Toast.LENGTH_SHORT).show();}}pendingExport=null;}if(request==501&&fileCallback!=null){ArrayList<Uri> uris=new ArrayList<>();if(result==RESULT_OK&&data!=null){if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)uris.add(data.getClipData().getItemAt(i).getUri());else if(data.getData()!=null)uris.add(data.getData());}fileCallback.onReceiveValue(uris.isEmpty()?null:uris.toArray(new Uri[0]));fileCallback=null;}}
    final class NativeBridge {
        @JavascriptInterface public void openExternal(String raw){Uri uri=Uri.parse(raw);if(!"https".equals(uri.getScheme()))return;runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(ActivityNotFoundException e){Toast.makeText(MainActivity.this,"Не найден браузер",Toast.LENGTH_SHORT).show();}});}
        @JavascriptInterface public void exportDocument(String name,String text){if(text.length()>10*1024*1024)return;runOnUiThread(()->{pendingExport=text.getBytes(StandardCharsets.UTF_8);Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^A-Za-z0-9_.-]","_").substring(0,Math.min(name.length(),100)));try{startActivityForResult(intent,503);}catch(ActivityNotFoundException e){pendingExport=null;Toast.makeText(MainActivity.this,"Не найден файловый менеджер",Toast.LENGTH_SHORT).show();}});}
        @JavascriptInterface public void scheduleReminders(String json){if(json.length()>5*1024*1024)return;AlarmScheduler.reconcile(MainActivity.this,json);}
        @JavascriptInterface public void requestNotifications(){runOnUiThread(()->MainActivity.this.requestNotifications());}
        @JavascriptInterface public void requestExactAlarms(){runOnUiThread(()->MainActivity.this.requestExactAlarms());}
        @JavascriptInterface public String notificationState(){boolean notifications=notificationsEnabled();boolean exact=Build.VERSION.SDK_INT<31||((AlarmManager)getSystemService(ALARM_SERVICE)).canScheduleExactAlarms();try{return new JSONObject().put("notifications",notifications).put("exact",exact).toString();}catch(JSONException e){return "{}";}}
        @JavascriptInterface public String pendingCompletions(){return AlarmScheduler.pendingCompletions(MainActivity.this).toString();}
        @JavascriptInterface public void acknowledgeCompletion(String key){AlarmScheduler.acknowledge(MainActivity.this,key);}
    }
}
