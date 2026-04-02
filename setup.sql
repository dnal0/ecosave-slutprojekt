-- =============================================
-- EcoSave SE
-- =============================================

USE ecosave_db;

-- ========== TABELLER ==========

-- Tabell 1: Anvandare
-- Grundtabell för alla användare. Här sparas vem som äger förbrukningsdatan.
-- CHECK på Omrade säkerställer att bara giltiga elområden kan väljas (integritet).
CREATE TABLE IF NOT EXISTS Anvandare (
  AnvandarID INT PRIMARY KEY AUTO_INCREMENT,          -- Unik ID för varje användare
  Namn VARCHAR(100) NOT NULL,                         -- Namn (obligatoriskt)
  Epost VARCHAR(100) NOT NULL UNIQUE,                 -- E-post som unik identifierare
  LosenordHash VARCHAR(255) NOT NULL,                 -- Hashat lösenord (säkerhet)
  Registreringsdatum DATE DEFAULT (CURDATE()),        -- Automatiskt dagens datum
  Omrade CHAR(3) DEFAULT 'SE3',                       -- Elområde (t.ex. SE3 = Stockholm)
  CONSTRAINT chk_omrade CHECK (Omrade IN ('SE1','SE2','SE3','SE4'))  -- Endast giltiga områden
);

-- Tabell 2: Apparater
-- Lista över vanliga hushållsapparater med deras ungefärliga elförbrukning.
-- CHECK > 0 hindrar orealistiska värden.
CREATE TABLE IF NOT EXISTS Apparater (
  ApparatID INT PRIMARY KEY AUTO_INCREMENT,
  Namn VARCHAR(100) NOT NULL,
  TypiskKWh DECIMAL(6,2) NOT NULL CHECK (TypiskKWh > 0)  -- Måste vara positiv förbrukning
);

-- Tabell 3: Forbrukning (huvudtabell – här sparas ALLA mätningar)
-- Kopplar användare och apparat till varje förbrukningspost.
-- FOREIGN KEY med CASCADE/SET NULL skyddar dataintegriteten.
CREATE TABLE IF NOT EXISTS Forbrukning (
  ForbrukningID INT PRIMARY KEY AUTO_INCREMENT,
  AnvandarID INT NOT NULL,                            -- Vem gjorde förbrukningen?
  ApparatID INT NULL,                                 -- Vilken apparat? (kan vara NULL)
  Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,       -- När raden skapades i systemet
  Forbrukningsdatum DATE NULL,                        -- Vilken dag förbrukningen gällde (manuell)
  kWh DECIMAL(8,2) NOT NULL CHECK (kWh >= 0),         -- Förbrukning i kWh (kan inte vara negativ)
  PriceSEK DECIMAL(7,3) NOT NULL,                     -- Pris per kWh den dagen
  Notes TEXT,                                         -- Extra info (t.ex. "Diskmaskin kväll")
  FOREIGN KEY (AnvandarID) REFERENCES Anvandare(AnvandarID) ON DELETE CASCADE,
  FOREIGN KEY (ApparatID) REFERENCES Apparater(ApparatID) ON DELETE SET NULL
);

-- Tabell 4: settings
-- Enkel tabell för nyckel-värde-inställningar (t.ex. månadsbudget).
-- PRIMARY KEY på `key` gör uppslagning supersnabbt.
CREATE TABLE IF NOT EXISTS settings (
  `key` VARCHAR(50) PRIMARY KEY,                      -- Namn på inställningen (t.ex. monthly_budget)
  value TEXT NOT NULL                                 -- Värdet (t.ex. "1800")
);

-- Tabell 5: Logg
-- Visar hur trigger fungerar i praktiken.
-- Varje ny förbrukning loggas hit automatiskt.
CREATE TABLE IF NOT EXISTS Logg (
  LoggID INT PRIMARY KEY AUTO_INCREMENT,
  Meddelande TEXT NOT NULL,
  Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabell 6: Manadsbudget
-- Budget per månad och användare.
-- UNIQUE KEY hindrar dubbla budgetar samma månad.
CREATE TABLE IF NOT EXISTS Manadsbudget (
  BudgetID INT PRIMARY KEY AUTO_INCREMENT,
  AnvandarID INT NOT NULL,
  Manad DATE NOT NULL,                                -- Vilken månad budgeten gäller
  MalBelopp DECIMAL(10,2) NOT NULL CHECK (MalBelopp > 0),
  UNIQUE KEY unique_month (AnvandarID, Manad),        -- En budget per månad och användare
  FOREIGN KEY (AnvandarID) REFERENCES Anvandare(AnvandarID) ON DELETE CASCADE
);

-- ========== TESTDATA / DEMO-DATA ==========
-- INSERT IGNORE gör att vi inte får fel om data redan finns.

INSERT IGNORE INTO Apparater (Namn, TypiskKWh) VALUES
('Diskmaskin (normalprogram)', 0.9),
('Tvättmaskin (40-60°C)', 0.8),
('Elbilsladdning hemma (ca 30-40 km)', 10.0),
('Ugn (normal bakning/cykel)', 1.5);

INSERT IGNORE INTO Anvandare (Namn, Epost, LosenordHash, Omrade)
VALUES ('Demo Student', 'demo@elev.se', 'demo123', 'SE3');

-- ========== INDEX för bättre prestanda ==========
-- Index på kolumner vi ofta söker/sorterar på → mycket snabbare rapporter.

CREATE INDEX idx_forbrukning_timestamp ON Forbrukning(Timestamp);
CREATE INDEX idx_forbrukning_anvandarid ON Forbrukning(AnvandarID);

-- ========== TRIGGER ==========
-- Varje gång en ny rad läggs i Forbrukning → loggas det automatiskt i Logg-tabellen.
DELIMITER //
DROP TRIGGER IF EXISTS log_new_usage //
CREATE TRIGGER log_new_usage 
AFTER INSERT ON Forbrukning 
FOR EACH ROW
BEGIN
    INSERT INTO Logg (Meddelande) 
    VALUES (CONCAT('Ny förbrukning registrerad: ', NEW.kWh, ' kWh för användare ', NEW.AnvandarID));
END//
DELIMITER ;

-- ========== STORED PROCEDURE ==========
-- Beräknar sammanfattning för en månad och jämför med budget.
-- Använder LEFT JOIN för att inkludera månader utan budget.
DELIMITER //
DROP PROCEDURE IF EXISTS GetMonthlySummary //
CREATE PROCEDURE GetMonthlySummary(IN pAnvandarID INT, IN pYearMonth DATE)
BEGIN
    SELECT 
        SUM(f.kWh) as TotalKWh,
        ROUND(SUM(f.kWh * f.PriceSEK), 2) as TotalKostnad,
        ROUND(AVG(f.PriceSEK), 3) as SnittPris,
        b.MalBelopp,
        CASE 
            WHEN SUM(f.kWh * f.PriceSEK) > b.MalBelopp THEN 'Överskrider budget!'
            ELSE 'Inom budget – bra jobbat!'
        END as Status
    FROM Forbrukning f
    LEFT JOIN Manadsbudget b 
        ON f.AnvandarID = b.AnvandarID 
        AND DATE_FORMAT(f.Timestamp, '%Y-%m') = DATE_FORMAT(b.Manad, '%Y-%m')
    WHERE f.AnvandarID = pAnvandarID 
      AND DATE_FORMAT(f.Timestamp, '%Y-%m') = DATE_FORMAT(pYearMonth, '%Y-%m')
    GROUP BY b.MalBelopp;
END//
DELIMITER ;
