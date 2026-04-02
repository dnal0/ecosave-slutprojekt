-- =============================================
-- PRIVILEGES.SQL
-- 
-- Denna fil sätter upp rättigheter för app-användaren 'ecosave_user'.
-- =============================================

USE ecosave_db;

-- Ta bort användaren om den redan finns (för att nollställa)
-- DROP USER IF EXISTS är säkert – ger inget fel om användaren inte finns.
DROP USER IF EXISTS 'ecosave_user'@'localhost';

-- Skapa användaren med starkt lösenord
CREATE USER 'ecosave_user'@'localhost' IDENTIFIED BY 'EcoSave2026StrongPass!';

-- Ge grundläggande åtkomst till databasen
-- USAGE krävs för att användaren ska kunna logga in alls (utan rättigheter).
GRANT USAGE ON ecosave_db.* TO 'ecosave_user'@'localhost';

-- Ge rättigheter till tabeller appen använder
-- SELECT = läsa, INSERT = skapa nytt, UPDATE = ändra, DELETE = ta bort
--
-- Forbrukning: Appen lägger till, visar och ibland raderar förbrukning
GRANT SELECT, INSERT, UPDATE, DELETE ON ecosave_db.Forbrukning TO 'ecosave_user'@'localhost';

-- Manadsbudget: Spara och hämta månadsbudget
GRANT SELECT, INSERT, UPDATE, DELETE ON ecosave_db.Manadsbudget TO 'ecosave_user'@'localhost';

-- settings: Spara och hämta enkla inställningar (t.ex. budget)
GRANT SELECT, INSERT, UPDATE, DELETE ON ecosave_db.settings TO 'ecosave_user'@'localhost';

-- Logg: Appen skriver bara hit via trigger
GRANT SELECT, INSERT ON ecosave_db.Logg TO 'ecosave_user'@'localhost';

-- Apparater: Bara läsa (lista apparater)
GRANT SELECT ON ecosave_db.Apparater TO 'ecosave_user'@'localhost';

-- Anvandare: Bara läsa (hämta användar-ID för demo)
GRANT SELECT ON ecosave_db.Anvandare TO 'ecosave_user'@'localhost';

-- Steg 5: Ge rätt att köra stored procedure
-- EXECUTE krävs för att anropa CALL GetMonthlySummary
GRANT EXECUTE ON PROCEDURE ecosave_db.GetMonthlySummary TO 'ecosave_user'@'localhost';

-- Steg 6: Uppdatera rättigheterna (alltid viktigt efter GRANT)
FLUSH PRIVILEGES;

-- Bekräftelse – visas när scriptet körs
SELECT 'Alla rättigheter är nu satta – ecosave_user har minimala rättigheter!' AS Status;
