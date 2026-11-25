-- Local SSAS processing dependency. No server role or database-wide role is granted.
-- Applies only to the four star-schema source tables in the isolated demo database.
USE [master];
IF SUSER_ID(N'NT Service\MSOLAP$TRANGTRETRAU') IS NULL
    CREATE LOGIN [NT Service\MSOLAP$TRANGTRETRAU] FROM WINDOWS;
GO
USE [CoffeeDW_Trang_20261119];
IF DB_NAME() <> N'CoffeeDW_Trang_20261119' THROW 51000, 'Unexpected database', 1;
IF USER_ID(N'NT Service\MSOLAP$TRANGTRETRAU') IS NULL
    CREATE USER [NT Service\MSOLAP$TRANGTRETRAU] FOR LOGIN [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::[dw].[DimDate] TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::[dw].[DimLocation] TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::[dw].[DimProduct] TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::[dw].[FactSalesPerformance] TO [NT Service\MSOLAP$TRANGTRETRAU];
SELECT DB_NAME() AS DatabaseName, p.name AS PrincipalName,
       dp.state_desc, dp.permission_name, SCHEMA_NAME(o.schema_id) AS SchemaName, o.name AS ObjectName
FROM sys.database_permissions dp
JOIN sys.database_principals p ON p.principal_id=dp.grantee_principal_id
LEFT JOIN sys.objects o ON o.object_id=dp.major_id
WHERE p.name=N'NT Service\MSOLAP$TRANGTRETRAU';
