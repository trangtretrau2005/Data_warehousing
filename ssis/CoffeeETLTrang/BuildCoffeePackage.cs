// Compile against the installed SSIS 16 SDK. Building never executes the package.
using System;
using System.IO;
using System.Security.Cryptography;
using Microsoft.SqlServer.Dts.Runtime;
using Microsoft.SqlServer.Dts.Pipeline.Wrapper;
using DataType=Microsoft.SqlServer.Dts.Runtime.Wrapper.DataType;
using IDTSConnectionManagerFlatFile100=Microsoft.SqlServer.Dts.Runtime.Wrapper.IDTSConnectionManagerFlatFile100;
using IDTSConnectionManagerFlatFileColumn100=Microsoft.SqlServer.Dts.Runtime.Wrapper.IDTSConnectionManagerFlatFileColumn100;
using IDTSName100=Microsoft.SqlServer.Dts.Runtime.Wrapper.IDTSName100;
using Microsoft.SqlServer.Dts.Tasks.ExecuteSQLTask;

public class BuildCoffeePackage {
  static readonly string[] Columns = {"Area Code","Date","Market","Market Size","Product","Product Line","Product Type","State","Type","Budget COGS","Budget Margin","Budget Profit","Budget Sales","COGS","Inventory","Margin","Marketing","Profit","Sales","Total Expenses"};
  static void Bind(ExecuteSQLTask sql, string variable, int ordinal, int datatype, int size) {
    IDTSParameterBinding p=sql.ParameterBindings.Add();
    p.ParameterName=ordinal; p.DtsVariableName="User::"+variable;
    p.ParameterDirection=ParameterDirections.Input; p.DataType=datatype; p.ParameterSize=size;
  }
  static TaskHost SQL(Package pkg, ConnectionManager cm, string name, string command, params string[] vars) {
    TaskHost task=(TaskHost)pkg.Executables.Add("STOCK:SQLTask"); task.Name=name;
    ExecuteSQLTask sql=(ExecuteSQLTask)task.InnerObject;
    sql.Connection=cm.ID; sql.SqlStatementSource=command; sql.BypassPrepare=true;
    for(int i=0;i<vars.Length;i++) Bind(sql,vars[i],i,vars[i]=="SourceCount"?3:130,vars[i]=="SourceCount"?-1:1024);
    return task;
  }
  public static int Main(string[] args) {
    if(args.Length!=2) { Console.Error.WriteLine("BuildCoffeePackage <project-dir> <source-csv>");return 2; }
    string folder=Path.GetFullPath(args[0]), source=Path.GetFullPath(args[1]);
    Directory.CreateDirectory(folder);
    Application app=new Application(); Package pkg=new Package();
    pkg.Name="LoadCoffeeTrang"; pkg.Description="Native Flat File -> Derived BatchID -> OLE DB raw landing; shared validation/upsert contract. Isolated experiment DB only.";
    pkg.ProtectionLevel=DTSProtectionLevel.DontSaveSensitive;
    pkg.CreatorName="Coffee DW team"; pkg.CreatorComputerName="Local development";
    pkg.Variables.Add("SourceFilePath",false,"User",source);
    pkg.Variables.Add("ServerName",false,"User",".");
    pkg.Variables.Add("DatabaseName",false,"User","CoffeeDW_Trang_SSIS_TN03_20261120");
    pkg.Variables.Add("BatchID",false,"User",Guid.NewGuid().ToString());
    string sourceHash;
    using(SHA256 sha=SHA256.Create()) sourceHash=BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(source))).Replace("-","").ToLowerInvariant();
    pkg.Variables.Add("SourceChecksum",false,"User",sourceHash);
    pkg.Variables.Add("SourceFileName",false,"User",Path.GetFileName(source));
    pkg.Variables.Add("SourceCount",false,"User",4248);
    ConnectionManager flat=pkg.Connections.Add("FLATFILE"); flat.Name="CoffeeCSV_UTF8"; flat.ConnectionString=source;
    flat.SetExpression("ConnectionString","@[User::SourceFilePath]");
    IDTSConnectionManagerFlatFile100 f=(IDTSConnectionManagerFlatFile100)flat.InnerObject;
    f.Format="Delimited"; f.Unicode=false; f.CodePage=65001; f.ColumnNamesInFirstDataRow=true;
    f.HeaderRowDelimiter="\r\n"; f.TextQualifier="\"";
    foreach(string name in Columns) {
      IDTSConnectionManagerFlatFileColumn100 c=f.Columns.Add();
      ((IDTSName100)c).Name=name; c.ColumnType="Delimited";
      c.ColumnDelimiter=name==Columns[Columns.Length-1]?"\r\n":",";
      c.DataType=DataType.DT_WSTR; c.MaximumWidth=1024; c.TextQualified=true;
    }
    ConnectionManager db=pkg.Connections.Add("OLEDB"); db.Name="CoffeeDW_Isolated_OLEDB";
    db.ConnectionString="Provider=MSOLEDBSQL;Data Source=.;Initial Catalog=CoffeeDW_Trang_SSIS_TN03_20261120;Integrated Security=SSPI;TrustServerCertificate=True;";
    db.SetExpression("ConnectionString","\"Provider=MSOLEDBSQL;Data Source=\" + @[User::ServerName] + \";Initial Catalog=\" + @[User::DatabaseName] + \";Integrated Security=SSPI;TrustServerCertificate=True;\"");
    TaskHost register=SQL(pkg,db,"EST_01_RegisterBatch",
      "IF DB_NAME() NOT LIKE N'CoffeeDW[_]Trang[_]%' THROW 50201,'Use an isolated CoffeeDW_Trang database',1; DECLARE @b uniqueidentifier=CONVERT(uniqueidentifier,?); DECLARE @file nvarchar(1024)=?; DECLARE @hash char(64)=?; DECLARE @n int=?; IF @hash=REPLICATE('0',64) THROW 50200,'Use Run-CoffeeETL.ps1 to supply actual SHA256 and source count',1; INSERT audit.LoadBatch(BatchID,SourceFile,SourceChecksum,SourceCount) VALUES(@b,@file,@hash,@n);",
      "BatchID","SourceFileName","SourceChecksum","SourceCount");
    TaskHost dataflow=(TaskHost)pkg.Executables.Add("STOCK:PipelineTask"); dataflow.Name="DFT_02_CSV_RawLanding"; dataflow.DelayValidation=true;
    MainPipe pipe=(MainPipe)dataflow.InnerObject; pipe.EngineThreads=2;
    IDTSComponentMetaData100 src=pipe.ComponentMetaDataCollection.New(); src.Name="FFS_CoffeeCSV_20_Text_Columns";
    src.ComponentClassID="DTSAdapter.FlatFileSource.8";
    CManagedComponentWrapper sw=src.Instantiate(); sw.ProvideComponentProperties(); src.Name="FFS_CoffeeCSV_20_Text_Columns";
    src.RuntimeConnectionCollection[0].ConnectionManager=DtsConvert.GetExtendedInterface(flat);
    src.RuntimeConnectionCollection[0].ConnectionManagerID=flat.ID;
    sw.AcquireConnections(null); sw.ReinitializeMetaData(); sw.ReleaseConnections();
    IDTSComponentMetaData100 derive=pipe.ComponentMetaDataCollection.New(); derive.Name="DC_AddBatchID";
    derive.ComponentClassID="DTSTransform.DerivedColumn.8";
    CManagedComponentWrapper dw=derive.Instantiate(); dw.ProvideComponentProperties(); derive.Name="DC_AddBatchID";
    IDTSPath100 p1=pipe.PathCollection.New(); p1.AttachPathAndPropagateNotifications(src.OutputCollection[0],derive.InputCollection[0]);
    // This synchronous transform adds a variable-only expression. Existing
    // columns flow through automatically; selecting them as expression inputs
    // would generate 20 unused-input warnings.
    IDTSOutputColumn100 batch=dw.InsertOutputColumnAt(derive.OutputCollection[0].ID,0,"BatchID","Current immutable batch identifier");
    dw.SetOutputColumnDataTypeProperties(derive.OutputCollection[0].ID,batch.ID,DataType.DT_WSTR,36,0,0,0);
    dw.SetOutputColumnProperty(derive.OutputCollection[0].ID,batch.ID,"Expression","(DT_WSTR,36)@[User::BatchID]");
    dw.SetOutputColumnProperty(derive.OutputCollection[0].ID,batch.ID,"FriendlyExpression","(DT_WSTR,36)@[User::BatchID]");
    IDTSComponentMetaData100 dest=pipe.ComponentMetaDataCollection.New(); dest.Name="OLEDB_Raw_CoffeeCsvLanding";
    dest.ComponentClassID="DTSAdapter.OLEDBDestination.8";
    CManagedComponentWrapper ow=dest.Instantiate(); ow.ProvideComponentProperties(); dest.Name="OLEDB_Raw_CoffeeCsvLanding";
    dest.RuntimeConnectionCollection[0].ConnectionManager=DtsConvert.GetExtendedInterface(db);
    dest.RuntimeConnectionCollection[0].ConnectionManagerID=db.ID;
    ow.SetComponentProperty("AccessMode",0); // row-by-row preserves one-source arrival order
    ow.SetComponentProperty("OpenRowset","[stg].[CoffeeCsvLanding]");
    dest.ValidateExternalMetadata=false; // DDL is staged separately; root applies it before execution.
    IDTSPath100 p2=pipe.PathCollection.New(); p2.AttachPathAndPropagateNotifications(derive.OutputCollection[0],dest.InputCollection[0]);
    IDTSInput100 input=dest.InputCollection[0]; IDTSVirtualInput100 virtualInput=input.GetVirtualInput();
    foreach(IDTSVirtualInputColumn100 c in virtualInput.VirtualInputColumnCollection) {
      IDTSInputColumn100 ic=ow.SetUsageType(input.ID,virtualInput,c.LineageID,DTSUsageType.UT_READONLY);
      IDTSExternalMetadataColumn100 ext=input.ExternalMetadataColumnCollection.New(); ext.Name=c.Name;
      ext.DataType=c.DataType; ext.Length=c.Length; ext.Precision=c.Precision; ext.Scale=c.Scale; ext.CodePage=c.CodePage;
      ow.MapInputColumn(input.ID,ic.ID,ext.ID);
    }
    TaskHost validate=SQL(pkg,db,"EST_03_ValidateAndStage", "DECLARE @b uniqueidentifier=CONVERT(uniqueidentifier,?); EXEC stg.usp_ValidateCoffeeLanding @BatchID=@b;","BatchID");
    TaskHost load=SQL(pkg,db,"EST_04_TransactionalStarLoad", "DECLARE @b uniqueidentifier=CONVERT(uniqueidentifier,?); EXEC dw.usp_LoadCoffee @BatchID=@b;","BatchID");
    pkg.PrecedenceConstraints.Add(register,dataflow); pkg.PrecedenceConstraints.Add(dataflow,validate); pkg.PrecedenceConstraints.Add(validate,load);
    DtsEventHandler onError=(DtsEventHandler)pkg.EventHandlers.Add("OnError");
    TaskHost fail=(TaskHost)onError.Executables.Add("STOCK:SQLTask"); fail.Name="EST_OnError_MarkFailedBatch";
    ExecuteSQLTask ft=(ExecuteSQLTask)fail.InnerObject; ft.Connection=db.ID; ft.BypassPrepare=true;
    ft.SqlStatementSource="DECLARE @b uniqueidentifier=TRY_CONVERT(uniqueidentifier,?); UPDATE audit.LoadBatch SET Status='FAILED',FinishedAt=SYSUTCDATETIME() WHERE BatchID=@b AND Status='STAGED';";
    Bind(ft,"BatchID",0,130,1024);
    app.SaveToXml(Path.Combine(folder,"LoadCoffeeTrang.dtsx"),pkg,null);
    Package scd=new Package(); scd.Name="SCD_TN04_Trang";
    scd.Description="Native SSIS control-flow SCD1/2/3 synthetic P01/A01; independent of blocked CSV DataFlow.";
    scd.CreatorName="Coffee DW team"; scd.CreatorComputerName="Local development"; scd.ProtectionLevel=DTSProtectionLevel.DontSaveSensitive;
    scd.Variables.Add("ServerName",false,"User",".");
    scd.Variables.Add("DatabaseName",false,"User","CoffeeDW_Trang_SSIS_TN03_20261120");
    scd.Variables.Add("RunID",false,"User",Guid.NewGuid().ToString());
    ConnectionManager scdDb=scd.Connections.Add("OLEDB"); scdDb.Name="CoffeeDW_Isolated_OLEDB";
    scdDb.ConnectionString=db.ConnectionString;
    scdDb.SetExpression("ConnectionString",db.GetExpression("ConnectionString"));
    SQL(scd,scdDb,"EST_TN04_SCD_Assertions",File.ReadAllText(Path.Combine(folder,"02_scd_synthetic.sql")),"RunID");
    using(Project project=Project.CreateProject()) {
      project.Name="CoffeeETLTrang"; project.Description=pkg.Description;
      project.CreatorName="Coffee DW team"; project.CreatorComputerName="Local development";
      project.TargetServerVersion=DTSTargetServerVersion.SQLServer2022;
      project.ProtectionLevel=DTSProtectionLevel.DontSaveSensitive;
      project.PackageItems.Add(pkg,"LoadCoffeeTrang.dtsx");
      project.PackageItems.Add(scd,"SCD_TN04_Trang.dtsx");
      project.SaveTo(Path.Combine(folder,"CoffeeETLTrang.ispac"));
    }
    Console.WriteLine("Built native SSIS16 package and ispac; package was NOT executed.");
    foreach(IDTSComponentMetaData100 c in pipe.ComponentMetaDataCollection) Console.WriteLine(c.Name+" | "+c.ComponentClassID);
    return 0;
  }
}
