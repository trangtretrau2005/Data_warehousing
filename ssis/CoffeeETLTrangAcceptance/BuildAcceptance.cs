// SDK16 build only. Parent executes child packages through supported project references.
using System;
using System.IO;
using System.Collections.Generic;
using System.Xml;
using Microsoft.SqlServer.Dts.Runtime;
using Microsoft.SqlServer.Dts.Tasks.ExecuteSQLTask;

public class BuildAcceptance {
  static string Q(string text) {return "N'"+text.Replace("'","''")+"'";}
  static Package Fresh(string name) {
    Package p=new Package();p.Name=name;p.ProtectionLevel=DTSProtectionLevel.DontSaveSensitive;
    p.CreatorName="Coffee DW team";p.CreatorComputerName="Local development";return p;
  }
  static TaskHost SQL(Package p,ConnectionManager cm,string name,string command) {
    TaskHost t=(TaskHost)p.Executables.Add("STOCK:SQLTask");t.Name=name;t.FailPackageOnFailure=true;
    ExecuteSQLTask s=(ExecuteSQLTask)t.InnerObject;s.Connection=cm.ID;s.BypassPrepare=true;s.SqlStatementSource=command;return t;
  }
  public static int Main(string[] args) {
    if(args.Length!=3) return 2;
    string dir=Path.GetFullPath(args[0]), template=Path.GetFullPath(args[1]);
    XmlDocument doc=new XmlDocument();doc.Load(args[2]);XmlElement input=doc.DocumentElement;
    string suite=input.GetAttribute("SuiteID"), db=input.GetAttribute("Database"), manifestHash=input.GetAttribute("ManifestSHA256");
    Application app=new Application();Package parent=Fresh("00_AcceptAll");
    parent.Description="Eight native CSV DataFlow acceptance cases, sequenced with real Execute Package Tasks and SQL assertions. Build is not execution evidence.";
    parent.Variables.Add("ServerName",false,"User",".");parent.Variables.Add("DatabaseName",false,"User",db);
    ConnectionManager cm=parent.Connections.Add("OLEDB");cm.Name="Acceptance_Isolated_SQL";
    cm.ConnectionString="Provider=MSOLEDBSQL;Data Source=.;Initial Catalog="+db+";Integrated Security=SSPI;TrustServerCertificate=True;";
    cm.SetExpression("ConnectionString","\"Provider=MSOLEDBSQL;Data Source=\" + @[User::ServerName] + \";Initial Catalog=\" + @[User::DatabaseName] + \";Integrated Security=SSPI;TrustServerCertificate=True;\"");
    string guard="IF DB_NAME()<>"+Q(db)+" THROW 50300,'Wrong acceptance database',1; ";
    TaskHost last=SQL(parent,cm,"EST_00_Preflight",guard+@"
IF (SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance)<>0 THROW 50301,'Acceptance requires empty fact; use a fresh initialized DB, do not delete data',1;
IF OBJECT_ID('audit.SSISAcceptanceSuite') IS NULL
 CREATE TABLE audit.SSISAcceptanceSuite(SuiteID uniqueidentifier NOT NULL PRIMARY KEY,ManifestSHA256 char(64) NOT NULL,StartedAtUTC datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),FinishedAtUTC datetime2 NULL,Status varchar(20) NOT NULL);
IF OBJECT_ID('audit.SSISAcceptanceCase') IS NULL
 CREATE TABLE audit.SSISAcceptanceCase(SuiteID uniqueidentifier NOT NULL,CaseNumber int NOT NULL,BatchID uniqueidentifier NOT NULL,VerifiedAtUTC datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),WarehouseRows bigint NOT NULL,WarehouseSales decimal(19,4) NOT NULL,PRIMARY KEY(SuiteID,CaseNumber));
INSERT audit.SSISAcceptanceSuite(SuiteID,ManifestSHA256,Status) VALUES(CONVERT(uniqueidentifier,"+Q(suite)+"),"+Q(manifestHash)+",'RUNNING');");
    using(Project project=Project.CreateProject()) {
      project.Name="CoffeeETLTrangAcceptance";project.Description=parent.Description;
      project.CreatorName="Coffee DW team";project.CreatorComputerName="Local development";
      project.TargetServerVersion=DTSTargetServerVersion.SQLServer2022;project.ProtectionLevel=DTSProtectionLevel.DontSaveSensitive;
      foreach(XmlElement c in input.SelectNodes("Case")) {
        string file=c.GetAttribute("package"), id=c.GetAttribute("batch_id"), number=c.GetAttribute("number");
        Package child=app.LoadPackage(template,null);child.RegenerateID();child.Name=Path.GetFileNameWithoutExtension(file);
        child.Description="Acceptance case "+number+"; SuiteID "+suite+"; configured but not executed at generation";
        child.Variables["User::ServerName"].Value=".";child.Variables["User::DatabaseName"].Value=db;
        child.Variables["User::BatchID"].Value=id;child.Variables["User::SourceFilePath"].Value=c.GetAttribute("source_path");
        child.Variables["User::SourceFileName"].Value=c.GetAttribute("source_filename");
        child.Variables["User::SourceChecksum"].Value=c.GetAttribute("source_sha256");
        child.Variables["User::SourceCount"].Value=Int32.Parse(c.GetAttribute("source_count"));
        project.PackageItems.Add(child,file);project.PackageItems[file].EntryPoint=false;
        TaskHost invoke=(TaskHost)parent.Executables.Add("STOCK:ExecutePackageTask");invoke.Name="EPT_"+number.PadLeft(2,'0')+"_"+Path.GetFileNameWithoutExtension(file);
        invoke.Properties["UseProjectReference"].SetValue(invoke,true);
        invoke.Properties["PackageName"].SetValue(invoke,file);
        invoke.Properties["ExecuteOutOfProcess"].SetValue(invoke,false);
        invoke.FailPackageOnFailure=true;invoke.DelayValidation=true;
        parent.PrecedenceConstraints.Add(last,invoke);
        string verify=guard+"DECLARE @b uniqueidentifier=CONVERT(uniqueidentifier,"+Q(id)+@");
IF NOT EXISTS(SELECT 1 FROM audit.LoadBatch WHERE BatchID=@b AND Status='COMPLETED'
 AND SourceCount="+c.GetAttribute("source_count")+" AND AcceptedCount="+c.GetAttribute("expected_accepted")+" AND RejectedCount="+c.GetAttribute("expected_rejected")+
" AND InsertedCount="+c.GetAttribute("expected_inserted")+" AND UpdatedCount="+c.GetAttribute("expected_updated")+" AND UnchangedCount="+c.GetAttribute("expected_unchanged")+@") THROW 50302,'Batch counts mismatch',1;
IF (SELECT COUNT_BIG(*) FROM stg.CoffeeRaw WHERE BatchID=@b)<>"+c.GetAttribute("source_count")+@" THROW 50303,'Staging count mismatch',1;
IF (SELECT COUNT_BIG(*) FROM audit.RejectedRow WHERE BatchID=@b)<>"+c.GetAttribute("expected_rejected")+@" THROW 50304,'Reject count mismatch',1;
IF NOT EXISTS(SELECT 1 FROM stg.CoffeeRaw WHERE BatchID=@b AND RejectReason IS NULL HAVING SUM(Sales)="+c.GetAttribute("expected_valid_sales")+@") THROW 50305,'Batch accepted Sales mismatch or NULL sum',1;
IF (SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance)<>"+c.GetAttribute("expected_warehouse_rows")+@" THROW 50306,'Warehouse row count mismatch',1;
IF NOT EXISTS(SELECT 1 FROM dw.FactSalesPerformance HAVING SUM(Sales)="+c.GetAttribute("expected_warehouse_sales")+@") THROW 50307,'Warehouse Sales mismatch or NULL sum',1;
IF NOT EXISTS(SELECT 1 FROM dw.FactSalesPerformance HAVING SUM(BudgetSales)="+c.GetAttribute("expected_warehouse_budget")+@") THROW 50308,'Warehouse Budget mismatch or NULL sum',1;
IF NOT EXISTS(SELECT 1 FROM dw.FactSalesPerformance HAVING SUM(Profit)="+c.GetAttribute("expected_warehouse_profit")+@") THROW 50309,'Warehouse Profit mismatch or NULL sum',1;
INSERT audit.SSISAcceptanceCase(SuiteID,CaseNumber,BatchID,WarehouseRows,WarehouseSales)
VALUES(CONVERT(uniqueidentifier,"+Q(suite)+"),"+number+",@b,"+c.GetAttribute("expected_warehouse_rows")+","+c.GetAttribute("expected_warehouse_sales")+");";
        TaskHost check=SQL(parent,cm,"EST_"+number.PadLeft(2,'0')+"_Verify",verify);
        parent.PrecedenceConstraints.Add(invoke,check);last=check;
      }
      TaskHost complete=SQL(parent,cm,"EST_99_Complete",guard+"IF (SELECT COUNT(*) FROM audit.SSISAcceptanceCase WHERE SuiteID=CONVERT(uniqueidentifier,"+Q(suite)+"))<>8 THROW 50310,'Eight case receipts required',1; UPDATE audit.SSISAcceptanceSuite SET Status='PASS',FinishedAtUTC=SYSUTCDATETIME() WHERE SuiteID=CONVERT(uniqueidentifier,"+Q(suite)+");");
      parent.PrecedenceConstraints.Add(last,complete);
      DtsEventHandler error=(DtsEventHandler)parent.EventHandlers.Add("OnError");
      TaskHost fail=(TaskHost)error.Executables.Add("STOCK:SQLTask");fail.Name="EST_OnError_MarkSuiteFailed";
      ExecuteSQLTask failed=(ExecuteSQLTask)fail.InnerObject;failed.Connection=cm.ID;failed.BypassPrepare=true;
      failed.SqlStatementSource="IF DB_NAME()="+Q(db)+" AND OBJECT_ID('audit.SSISAcceptanceSuite') IS NOT NULL UPDATE audit.SSISAcceptanceSuite SET Status='FAILED',FinishedAtUTC=SYSUTCDATETIME() WHERE SuiteID=CONVERT(uniqueidentifier,"+Q(suite)+") AND Status='RUNNING';";
      project.PackageItems.Add(parent,"00_AcceptAll.dtsx");project.PackageItems["00_AcceptAll.dtsx"].EntryPoint=true;
      project.SaveTo(Path.Combine(dir,"CoffeeETLTrangAcceptance.ispac"));
    }
    Console.WriteLine("Built acceptance ispac with native ExecutePackageTask project references; not executed. SuiteID="+suite);return 0;
  }
}
