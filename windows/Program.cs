using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Temoraxis;
static class Program {
 [STAThread] static void Main(string[] args) {
  ApplicationConfiguration.Initialize();
  Application.Run(new PlannerWindow(args.Contains("--smoke-test")));
 }
}
sealed class PlannerWindow : Form {
 const string Origin="https://temoraxis.example";
 readonly WebView2 web=new(){Dock=DockStyle.Fill};
 readonly NotifyIcon tray;
 readonly bool smoke;
 bool quitting;
 string profile="";
 int smokeStep;
 public PlannerWindow(bool smokeTest) {
  smoke=smokeTest;Text="Temoraxis";Width=1250;Height=850;MinimumSize=new Size(390,600);StartPosition=FormStartPosition.CenterScreen;
  Icon=System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
  Controls.Add(web);
  var menu=new ContextMenuStrip();menu.Items.Add("Открыть Temoraxis",null,(_,_)=>Restore());menu.Items.Add("Лицензии",null,(_,_)=>{using var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("DependencyNotices")!;using var reader=new StreamReader(input);using var dialog=new Form{Text="Лицензии Temoraxis Windows",Width=800,Height=600};dialog.Controls.Add(new TextBox{Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Both,Dock=DockStyle.Fill,Text=reader.ReadToEnd()});dialog.ShowDialog(this);});menu.Items.Add("Выход",null,(_,_)=>{quitting=true;Close();});
  tray=new NotifyIcon{Text="Temoraxis",Icon=Icon,ContextMenuStrip=menu,Visible=!smoke};tray.DoubleClick+=(_,_)=>Restore();
  FormClosing+=(_,e)=>{if(!quitting&&!smoke){e.Cancel=true;Hide();}};
  FormClosed+=(_,_)=>{tray.Dispose();web.Dispose();};
  Shown+=async(_,_)=>await Initialize();
 }
 void Restore(){Show();WindowState=FormWindowState.Normal;Activate();}
 static bool Internal(string value)=>Uri.TryCreate(value,UriKind.Absolute,out var u)&&u.Scheme=="https"&&u.Host=="temoraxis.example"&&u.IsDefaultPort;
 static void External(string value){if(Uri.TryCreate(value,UriKind.Absolute,out var u)&&(u.Scheme=="https"||u.Scheme=="http"))Process.Start(new ProcessStartInfo(u.AbsoluteUri){UseShellExecute=true});}
 async Task Initialize(){
  try{
   if(Environment.OSVersion.Version.Build<22000&&!smoke)throw new InvalidOperationException("Эта версия предназначена для Windows 11.");
   profile=smoke?Path.Combine(Path.GetTempPath(),"TemoraxisSmoke",Guid.NewGuid().ToString("N")):Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Temoraxis");
   Directory.CreateDirectory(profile);
   var assembly=Assembly.GetExecutingAssembly();var assets=Path.Combine(profile,"web",assembly.GetName().Version!.ToString());Directory.CreateDirectory(assets);
   foreach(var resource in assembly.GetManifestResourceNames().Where(n=>n.StartsWith("Web."))){if(File.Exists(Path.Combine(assets,resource[4..])))continue;using var input=assembly.GetManifestResourceStream(resource)!;using var output=File.Create(Path.Combine(assets,resource[4..]));input.CopyTo(output);}
   var env=await CoreWebView2Environment.CreateAsync(null,Path.Combine(profile,"WebView2"));await web.EnsureCoreWebView2Async(env);
   var core=web.CoreWebView2;core.SetVirtualHostNameToFolderMapping("temoraxis.example",assets,CoreWebView2HostResourceAccessKind.DenyCors);
   core.Settings.AreHostObjectsAllowed=false;core.Settings.IsWebMessageEnabled=true;
   core.NavigationStarting+=(_,e)=>{if(!Internal(e.Uri)){e.Cancel=true;External(e.Uri);}};
   core.NewWindowRequested+=(_,e)=>{e.Handled=true;if(e.IsUserInitiated)External(e.Uri);};
   core.PermissionRequested+=(_,e)=>{
    e.State=CoreWebView2PermissionState.Deny;
    if(!Internal(e.Uri))return;
    if(e.PermissionKind==CoreWebView2PermissionKind.Notifications){var allowed=File.Exists(Path.Combine(profile,"notifications-enabled"));if(!allowed&&!smoke){allowed=MessageBox.Show(this,"Разрешить уведомления Temoraxis? Они доступны, пока приложение запущено, в том числе в трее.","Уведомления",MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes;if(allowed)File.WriteAllText(Path.Combine(profile,"notifications-enabled"),"yes");}if(allowed)e.State=CoreWebView2PermissionState.Allow;}
   };
   core.DownloadStarting+=(_,e)=>{var name=Path.GetFileName(e.ResultFilePath);using var dialog=new SaveFileDialog{FileName=name,OverwritePrompt=true};if(dialog.ShowDialog(this)==DialogResult.OK){e.ResultFilePath=dialog.FileName;e.Handled=true;}else e.Cancel=true;};
   if(smoke)core.NavigationCompleted+=async(_,e)=>await CheckSmoke(e);
   core.Navigate(Origin+"/planner.html");
  }catch(Exception error){
   if(smoke){File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"smoke-error.txt"),error.ToString());Environment.ExitCode=1;quitting=true;Close();return;}
   var missing=error is WebView2RuntimeNotFoundException;
   var message=missing?"Для запуска нужен Microsoft Edge WebView2 Runtime. Открыть официальную страницу установки?":("Не удалось запустить Temoraxis. Ваши сохранённые данные не удалены.\n\n"+error.Message);
   if(missing){if(MessageBox.Show(message,"Temoraxis",MessageBoxButtons.YesNo,MessageBoxIcon.Information)==DialogResult.Yes)External("https://developer.microsoft.com/microsoft-edge/webview2/");}else MessageBox.Show(message,"Temoraxis");
   quitting=true;Close();
  }
 }
 async Task CheckSmoke(CoreWebView2NavigationCompletedEventArgs e){
  try{
   if(!e.IsSuccess)throw new Exception("Navigation failed: "+e.WebErrorStatus);
   if(smokeStep++==0){var result=await web.CoreWebView2.ExecuteScriptAsync("localStorage.setItem('windows_smoke','persisted');JSON.stringify({planner:!!document.getElementById('page-tasks'),guide:!!document.getElementById('settingsUserGuide'),clock:typeof clockData==='function'})");var json=JsonSerializer.Deserialize<string>(result)!;using var doc=JsonDocument.Parse(json);if(doc.RootElement.EnumerateObject().Any(p=>!p.Value.GetBoolean()))throw new Exception("Planner initialization failed");web.CoreWebView2.Navigate(Origin+"/Start_page.html");}
   else{var result=await web.CoreWebView2.ExecuteScriptAsync("localStorage.getItem('windows_smoke')");if(result!="\"persisted\"")throw new Exception("Shared local storage failed");File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"smoke-ok.txt"),"PASS: WebView2, offline planner, embedded guide, start page and shared persistent origin");quitting=true;Close();}
  }catch(Exception error){File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"smoke-error.txt"),error.ToString());Environment.ExitCode=1;quitting=true;Close();}
 }
}
