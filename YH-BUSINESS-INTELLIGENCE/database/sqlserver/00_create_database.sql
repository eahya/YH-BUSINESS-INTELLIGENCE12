/* Run with sqlcmd against master. Then reconnect to YH_BusinessIntelligence. */
IF DB_ID(N'YH_BusinessIntelligence') IS NULL
BEGIN
    CREATE DATABASE [YH_BusinessIntelligence];
END;
GO
