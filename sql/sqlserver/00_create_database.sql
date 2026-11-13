-- Run in SSMS with an account allowed to create databases. No existing DB is dropped.
USE master;
GO
IF DB_ID(N'CoffeeDW') IS NULL EXEC(N'CREATE DATABASE CoffeeDW');
GO
USE CoffeeDW;
GO
