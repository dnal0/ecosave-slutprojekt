# EcoSave SE

En enkel men funktionell webbapp för att hålla koll på elförbrukning hemma.  
Appen är byggd som skolprojekt och hjälper till att:

- Ladda upp historisk eldata via CSV
- Mata in dagens förbrukning manuellt
- Sätta och följa en månadsbudget med prognos och varning
- Se timvisa spotpriser från Nord Pool (SE1–SE4) med rekommendationer
- Få en enkel prognos för kommande dagar (med linjär regression)
- Visa alla registrerade förbrukningar

Appen är helt på svenska och körs lokalt på Ubuntu med Flask + MySQL.

## Teknologi
- **Backend**: Flask (Python)
- **Databas**: MySQL 8
- **Frontend**: Bootstrap 5 + Chart.js
- **Extra**: pandas, scikit-learn (för prognos), pymysql, requests
- **ER-diagram**: Finns i mappen `docs/` (eller se bilden du genererade i dbdiagram.io)

## Hur man kör projektet lokalt

Klona repot eller ladda ner det.  
Skapa och aktivera en virtuell miljö:

```bash
python3 -m venv venv
source venv/bin/activate
```

Installera beroenden:

```bash
pip install flask pandas pymysql scikit-learn requests
```

Starta MySQL och kör filerna i denna ordning:
- `setup.sql` (skapar databas, tabeller, trigger och stored procedure)
- `priviliges.sql` (skapar användaren `ecosave_user`)

Starta sedan appen:

```bash
python app.py
```

Öppna webbläsaren och gå till `http://din-ip:5002`  
(exempel: http://192.168.133.205:5002 – byt ut mot din egen IP-adress).

**Inloggning**  
Lösenord: `your_password_here`  

## Projektstruktur
```
ecosave-se/
├── app.py              # Huvudfil – alla routes och HTML-mallar
├── db_helper.py        # Alla databasfunktioner
├── setup.sql           # Skapar tabeller, data, trigger och procedure
├── priviliges.sql      # Skapar MySQL-användaren med rätt rättigheter
├── README.md
└── docs/
    └── er-diagram.png  
```

## ER-diagram

ER-diagrammet finns här:
[`docs/er-diagram.png`](docs/er-diagram.png)


## Framtida förbättringar (Todo)
- Riktig användarinloggning med flera konton
- Direktkoppling till Tibber eller elnätsleverantörens API
- Bättre mobilanpassning
- Möjlighet att exportera data som PDF/CSV
- Dark/Light mode toggle

Gjort som hobby- och skolprojekt våren 2026.
Feedback och pull requests är välkomna!
