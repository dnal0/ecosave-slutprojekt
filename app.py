from flask import Flask, render_template_string, request, redirect, session, url_for
import pandas as pd
from datetime import datetime, timedelta
import requests
import calendar
from sklearn.linear_model import LinearRegression
import numpy as np
import os

# Importera från db_helper
from db_helper import query_db, add_usage

"""
EcoSave SE - Slutprojekt

VIKTIGT FÖR INLÄMNING:
- SECRET_KEY hämtas från miljövariabel (os.environ) om den finns.
- Annars används ett fallback-värde (endast för utveckling).
- Inloggningslösenordet är hårdkodat för demoändamål.
- I ett riktigt projekt skulle både secret_key och lösenord ligga i en .env-fil.
"""

app = Flask(__name__)

# Secret key - bör inte vara hårdkodad i produktion
app.secret_key = os.environ.get('SECRET_KEY', 'ecosave_secret_key_2026_change_me_please')

# ────────────────────────────────────────────────
#  STANDARDVÄRDEN
# ────────────────────────────────────────────────


APPLIANCES = [
    {"name": "Diskmaskin (normalprogram)", "kwh": 0.9},
    {"name": "Tvättmaskin (40–60°C)", "kwh": 0.8},
    {"name": "Elbilsladdning hemma (ca 30–40 km)", "kwh": 10.0},
    {"name": "Ugn (normal bakning/cykel)", "kwh": 1.5},
]

# ────────────────────────────────────────────────
#  HJÄLPFUNKTIONER FÖR SETTINGS
# ────────────────────────────────────────────────

def get_setting(key, default=None):
    row = query_db("SELECT value FROM settings WHERE `key` = %s", (key,), fetch_one=True)
    return row['value'] if row else default

def set_setting(key, value):
    query_db("""
        INSERT INTO settings (`key`, value) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE value = %s
    """, (key, str(value), str(value)), commit=True)

# ────────────────────────────────────────────────
#  HTML-MALLAR
# ────────────────────────────────────────────────

HTML_LOGIN = """
<div class="container mt-5">
    <h2 class="text-center text-success">EcoSave SE</h2>
    <p class="text-center text-muted">Logga in för att se dina elinsikter</p>
    <form method="post" class="mt-4">
        <div class="mb-3">
            <label for="password" class="form-label">Lösenord</label>
            <input type="password" name="password" id="password" class="form-control">
        </div>
        <button type="submit" class="btn btn-success w-100">Logga in</button>
    </form>
</div>
"""

HTML_HOME = """
<!DOCTYPE html>
<html lang="sv" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>EcoSave SE</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
    <style>
        body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 2rem; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); transition: transform 0.2s; }
        .card:hover { transform: translateY(-4px); }
        .header { text-align: center; margin-bottom: 3rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="display-4 fw-bold text-success"><i class="bi bi-lightning-charge-fill me-2"></i>EcoSave SE</h1>
            <p class="lead text-muted">Din smarta elkompis – följ och spara på elen</p>
        </div>
        {% if message %}<div class="alert alert-success text-center">{{ message }}</div>{% endif %}
        
        <div class="row justify-content-center">
            <div class="col-lg-6">
                <div class="card p-4 mb-4">
                    <h5 class="text-center mb-4"><i class="bi bi-upload me-2"></i>Ladda upp historisk data (CSV)</h5>
                    <form method="post" enctype="multipart/form-data">
                        <input type="file" name="energy_csv" class="form-control mb-3" accept=".csv">
                        <button type="submit" class="btn btn-success w-100">Ladda upp CSV</button>
                    </form>
                    <p class="text-muted small mt-3 text-center">Tips: Ladda ner timdata från din elnätsleverantör</p>
                </div>
            </div>
        </div>
        
        <div class="row justify-content-center mb-5">
            <div class="col-lg-8">
                <a href="/budget" class="btn btn-lg btn-primary w-100">
                    <i class="bi bi-wallet2 me-2"></i>Hantera månadsbudget & daglig inmatning
                </a>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="/summary" class="btn btn-lg btn-primary me-3"><i class="bi bi-graph-up me-2"></i>Se sammanfattning</a>
            <a href="/prices" class="btn btn-lg btn-info me-3"><i class="bi bi-clock-history me-2"></i>Elpriser & bästa tider</a>
            <a href="/transactions" class="btn btn-lg btn-outline-light me-3"><i class="bi bi-list-ul me-2"></i>Transaktioner</a>
            <a href="/reset" class="btn btn-lg btn-outline-danger"><i class="bi bi-trash me-2"></i>Radera all data</a>
            <a href="/logout" class="btn btn-lg btn-outline-secondary ms-3"><i class="bi bi-box-arrow-right me-2"></i>Logga ut</a>
        </div>
    </div>
</body>
</html>
"""

HTML_BUDGET = """
<!DOCTYPE html>
<html lang="sv" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>Månadsbudget & daglig inmatning – EcoSave SE</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
    <style>
        body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 2rem; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
        .progress { height: 20px; border-radius: 10px; }
        .progress-bar { transition: width 0.6s ease; }
    </style>
</head>
<body>
    <div class="container">
        <div class="text-center mb-5">
            <h1 class="text-info"><i class="bi bi-wallet2 me-2"></i>Månadsbudget & daglig inmatning</h1>
            <p class="lead text-muted">Här hanterar du din budget och lägger till daglig förbrukning</p>
        </div>

        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="card p-4 mb-5">
                    <h5 class="text-center mb-4">Sätt eller ändra månadsbudget</h5>
                    <form method="post" class="row g-3 align-items-center justify-content-center">
                        <div class="col-auto">
                            <label for="budget" class="col-form-label fw-bold">Mål denna månad (kr):</label>
                        </div>
                        <div class="col-auto">
                            <input type="number" name="budget" id="budget" class="form-control" value="{{ current_budget or 0 }}" min="0" step="100" placeholder="t.ex. 5000">
                        </div>
                        <div class="col-auto">
                            <button type="submit" name="action" value="save_budget" class="btn btn-success">Spara budget</button>
                        </div>
                    </form>
                </div>

                {% if budget_used > 0 or current_budget > 0 %}
                <div class="card p-4 mb-5">
                    <h5 class="text-center mb-4">Din budget just nu</h5>
                    <div class="d-flex justify-content-between mb-1">
                        <span>Använt hittills: <strong>{{ budget_used|round(0) }} kr</strong></span>
                        <span>Mål: <strong>{{ current_budget|round(0) }} kr</strong></span>
                    </div>
                    <div class="progress mb-3">
                        <div class="progress-bar {{ 'bg-success' if budget_percent <= 70 else 'bg-warning' if budget_percent <= 90 else 'bg-danger' }}" 
                             role="progressbar" style="width: {{ budget_capped_percent }}%;" aria-valuenow="{{ budget_percent }}" aria-valuemin="0" aria-valuemax="100">
                             {{ budget_percent|round(0) }}%
                        </div>
                    </div>
                    <p class="text-center fw-bold {{ budget_status_class }}">
                        Prognos: ca {{ budget_forecast|round(0) }} kr denna månad
                    </p>
                    <p class="text-center {{ budget_status_class }} small">
                        {{ budget_status_text }}
                    </p>
                    <p class="text-center small mt-3">
                        <a href="/prices" class="text-info">Kolla billiga timmar</a> för att spara mer!
                    </p>
                </div>
                {% endif %}

                <div class="card p-4">
                    <h5 class="text-center mb-4">Lägg till dagens elförbrukning</h5>
                    <form method="post" class="row g-3 align-items-center justify-content-center">
                        <div class="col-auto">
                            <input type="date" name="entry_date" class="form-control" value="{{ today }}" required>
                        </div>
                        <div class="col-auto">
                            <input type="number" name="entry_kwh" class="form-control" placeholder="kWh idag" min="0" step="0.1" required>
                        </div>
                        <div class="col-auto">
                            <input type="number" name="entry_price" class="form-control" placeholder="Pris SEK/kWh (valfritt)" step="0.01">
                        </div>
                        <div class="col-auto">
                            <button type="submit" name="action" value="add_entry" class="btn btn-primary">Lägg till</button>
                        </div>
                    </form>
                    <p class="text-muted small mt-3 text-center">Ange dagens förbrukning från elmätaren eller Tibber-appen. Tar 10 sekunder.</p>
                </div>
            </div>
        </div>

        <div class="text-center mt-5">
            <a href="/" class="btn btn-lg btn-outline-light"><i class="bi bi-arrow-left me-2"></i>Tillbaka till startsidan</a>
        </div>
    </div>
</body>
</html>
"""

HTML_RESET_CONFIRM = """
<div class="container mt-5 text-center">
    <h2 class="text-danger">Radera all data?</h2>
    <p class="lead">Detta raderar alla dina elförbrukningsrader permanent. Kan inte ångras.</p>
    <a href="/reset?confirm=yes" class="btn btn-danger btn-lg me-4">Ja, radera allt</a>
    <a href="/" class="btn btn-secondary btn-lg">Nej, behåll min data</a>
</div>
"""

HTML_PRICES = """
<!DOCTYPE html>
<html lang="sv" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>Elpriser & bästa tider – EcoSave SE</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 2rem; font-family: system-ui, -apple-system, sans-serif; }
        .card { background: #161b22; border: none; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); overflow: hidden; }
        .header { text-align: center; margin-bottom: 2.5rem; }
        .savings-card { 
            border-radius: 16px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.3); 
            transition: transform 0.2s, box-shadow 0.2s; 
        }
        .savings-card:hover { 
            transform: translateY(-6px); 
            box-shadow: 0 12px 40px rgba(40,167,69,0.3); 
        }
        #priceChartContainer { height: 340px; background: #0d1117; border-radius: 16px; padding: 1.2rem; box-shadow: inset 0 2px 12px rgba(0,0,0,0.6); }
        .best-hour-card { 
            height: 100%; 
            background: linear-gradient(135deg, rgba(40,167,69,0.18), rgba(40,167,69,0.06)); 
            border-radius: 16px; 
            padding: 2rem; 
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            text-align: center; 
            border: 1px solid rgba(40,167,69,0.35); 
            box-shadow: 0 4px 20px rgba(40,167,69,0.15); 
        }
        .best-hour-title { font-size: 1.5rem; margin-bottom: 1.2rem; color: #28a745; font-weight: 600; }
        .best-hour-time { font-size: 2.5rem; font-weight: 700; margin: 0.6rem 0; color: #e6edf3; }
        .best-hour-price { font-size: 1.8rem; color: #28a745; font-weight: 600; margin-bottom: 1rem; }
        .row.g-4 { --bs-gutter-x: 1.5rem; --bs-gutter-y: 1.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="text-info fw-bold"><i class="bi bi-clock-history me-2"></i>Elpriser & bästa tider</h1>
            <p class="lead text-muted">Timvisa elpriser (spot) – se när det är billigast att använda el</p>
        </div>

        <div class="card p-4 mb-5">
            <form method="get" class="row g-3 justify-content-center align-items-center mb-4">
                <div class="col-auto">
                    <label for="area" class="col-form-label fw-bold">Ditt område/län:</label>
                </div>
                <div class="col-auto">
                    <select name="area" id="area" class="form-select form-select-lg" onchange="this.form.submit()">
                        {% for opt in regions %}
                        <option value="{{ opt.code }}" {% if opt.code == area %}selected{% endif %}>{{ opt.name }}</option>
                        {% endfor %}
                    </select>
                </div>
            </form>

            {% if error %}
            <div class="alert alert-warning text-center">{{ error }}</div>
            {% else %}
            <p class="text-center text-muted mb-4">Timvisa elpriser för {{ date }} • Uppdaterat {{ updated }}</p>

            <div class="row g-4 align-items-stretch">
                <div class="col-lg-7 d-flex flex-column">
                    <div id="priceChartContainer" class="flex-grow-1">
                        <canvas id="priceChart"></canvas>
                    </div>
                </div>

                <div class="col-lg-5 d-flex flex-column">
                    {% if advice %}
                    <div class="best-hour-card flex-grow-1">
                        {{ advice | safe }}
                    </div>
                    {% else %}
                    <div class="alert alert-secondary text-center p-5 flex-grow-1 d-flex align-items-center justify-content-center">
                        Inga priser tillgängliga för detta område just nu.
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="row g-4 mt-5">
                {% for app in appliances %}
                <div class="col-md-6 col-lg-3">
                    <div class="card text-center bg-dark border-success savings-card h-100">
                        <div class="card-body d-flex flex-column justify-content-center">
                            <h6 class="mb-3 fw-semibold">{{ app.name }}</h6>
                            <p class="small text-muted mb-2">{{ app.kwh }} kWh per gång</p>
                            <p class="mb-1">Billigast: <strong>{{ app.cheapest_cost|round(1) }} kr</strong></p>
                            <p class="mb-1">Dyrast: <strong>{{ app.expensive_cost|round(1) }} kr</strong></p>
                            <p class="text-success fw-bold fs-5 mt-2">Spara: {{ app.savings|round(1) }} kr 💰</p>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if total_savings > 0 %}
            <div class="alert alert-info mt-5 text-center p-4 fw-bold fs-5">
                <i class="bi bi-lightning-charge-fill me-2"></i>Totalt sparande om du flyttar allt till billigaste timmarna (uppskattat konsumentpris): <span class="text-success">{{ total_savings|round(1) }} kr</span>!
            </div>
            {% endif %}

            <p class="text-muted small mt-4 text-center">
                Timvisa spotpriser från Nord Pool (day-ahead). Uppskattat konsumentpris inkluderar typiskt påslag, energiskatt och moms – nätavgift tillkommer separat och varierar per område.
            </p>
            {% endif %}
        </div>

        <div class="text-center mt-5">
            <a href="/" class="btn btn-lg btn-outline-light"><i class="bi bi-arrow-left me-2"></i>Tillbaka till startsidan</a>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('priceChart').getContext('2d');
        const hours = [{% for p in all_hours %}'{{ p.hour }}:00',{% endfor %}];
        const prices = [{% for p in all_hours %}{{ p.price_sek }},{% endfor %}];

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: hours,
                datasets: [{
                    label: 'Pris kr/kWh',
                    data: prices,
                    backgroundColor: prices.map(p => {
                        if (p < 0) return 'rgba(0, 123, 255, 0.9)';
                        if (p < 0.6) return 'rgba(40, 167, 69, 0.9)';
                        if (p < 1.2) return 'rgba(253, 126, 20, 0.9)';
                        return 'rgba(220, 53, 69, 0.9)';
                    }),
                    borderColor: prices.map(p => p < 0 ? '#0d6efd' : p < 0.6 ? '#28a745' : p < 1.2 ? '#fd7e14' : '#dc3545'),
                    borderWidth: 1,
                    borderRadius: 12,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'kr/kWh', color: '#e6edf3', font: { size: 14, weight: 'bold' } },
                        grid: { color: '#30363d' },
                        ticks: { color: '#e6edf3', font: { size: 12 } }
                    },
                    x: {
                        title: { display: true, text: 'Timme', color: '#e6edf3', font: { size: 14, weight: 'bold' } },
                        grid: { display: false },
                        ticks: { color: '#e6edf3', font: { size: 12 }, maxRotation: 45, minRotation: 45 }
                    }
                },
                animation: { duration: 1400, easing: 'easeOutQuart' }
            }
        });
    </script>
</body>
</html>
"""

# ────────────────────────────────────────────────
#  ROUTER
# ────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get('password') == 'your_password_here':
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template_string(HTML_LOGIN + '<div class="alert alert-danger mt-3 text-center">Fel lösenord. Försök igen.</div>')
    return render_template_string(HTML_LOGIN)

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route("/", methods=["GET", "POST"])
def home():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    message = ""
    if request.method == "POST":
        if 'energy_csv' in request.files and request.files['energy_csv'].filename != '':
            file = request.files['energy_csv']
            try:
                df = pd.read_csv(file)
                df.columns = [col.strip().lower() for col in df.columns]

                user = query_db("SELECT AnvandarID FROM Anvandare WHERE Epost = %s", ('demo@elev.se',), fetch_one=True)
                if not user:
                    message = "Demo-användare hittades inte."
                else:
                    inserted = 0
                    for _, row in df.iterrows():
                        timestamp = str(row.get('timestamp', datetime.now().isoformat()))
                        kwh = float(row.get('kwh', 0))
                        price_sek = float(row.get('price_sek', 0))
                        notes = str(row.get('notes', 'CSV import'))
                        
                        add_usage(user['AnvandarID'], kwh, price_sek, notes)
                        inserted += 1
                    message = f"Importerade {inserted} nya rader."
            except Exception as e:
                message = f"Fel vid uppladdning: {str(e)}"
    
    return render_template_string(HTML_HOME, message=message)

@app.route("/budget", methods=["GET", "POST"])
def budget():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    message = ""
    today = datetime.now().strftime('%Y-%m-%d')
    
    user = query_db("SELECT AnvandarID FROM Anvandare WHERE Epost = %s", ('demo@elev.se',), fetch_one=True)
    if not user:
        return "Demo-användare hittades inte.", 500
    
    anvandar_id = user['AnvandarID']
    
    if request.method == "POST":
        action = request.form.get('action')
        
        if action == 'save_budget':
            try:
                budget = float(request.form['budget'])
                if budget > 0:
                    set_setting('monthly_budget', budget)
                    set_setting('budget_start_date', datetime.now().strftime('%Y-%m-01'))
                    message = f"Månadsbudget uppdaterad till {budget} kr!"
                    print(f"DEBUG: Budget sparad: {budget} kr")  # Debug
                else:
                    message = "Budget måste vara högre än 0 kr."
            except Exception as e:
                message = f"Ogiltigt värde för budget: {str(e)}"
                print(f"DEBUG budget error: {str(e)}")
        
        elif action == 'add_entry':
            try:
                entry_date = request.form['entry_date']
                entry_kwh = float(request.form.get('entry_kwh', 0))
                entry_price = float(request.form.get('entry_price', 0)) if request.form.get('entry_price') else 0.0
                notes = "Daglig inmatning"
                
                add_usage(
                    anvandar_id=anvandar_id,
                    kwh=entry_kwh,
                    price_sek=entry_price,
                    notes=notes,
                    forbrukningsdatum=entry_date
                )
                message = f"Daglig förbrukning för {entry_date} tillagd ({entry_kwh} kWh)!"
                print(f"DEBUG: Tillagd förbrukning {entry_kwh} kWh den {entry_date}")  # Debug
            except Exception as e:
                message = f"Fel vid inmatning: {str(e)}"
                print(f"DEBUG entry error: {str(e)}")
    
    current_budget_str = get_setting('monthly_budget')
    current_budget = float(current_budget_str) if current_budget_str else 0.0
    budget_used = 0.0
    budget_percent = 0.0
    budget_capped_percent = 0.0
    budget_forecast = 0.0
    budget_status_class = 'text-success'
    budget_status_text = 'Lägg till minst 1 dag för prognos'
    
    if current_budget > 0:
        today_dt = datetime.now()
        month_start = datetime.strptime(today_dt.strftime('%Y-%m-01'), '%Y-%m-%d')
        days_in_month = calendar.monthrange(today_dt.year, today_dt.month)[1]
        
        rows = query_db("""
            SELECT kWh, PriceSEK FROM Forbrukning 
            WHERE AnvandarID = %s 
            AND Forbrukningsdatum >= %s 
            AND Forbrukningsdatum < %s
        """, (anvandar_id, month_start.strftime('%Y-%m-%d'), (today_dt + timedelta(days=1)).strftime('%Y-%m-%d')))
        
        df = pd.DataFrame(rows)
        
        if not df.empty:
            df['kWh'] = pd.to_numeric(df['kWh'], errors='coerce').fillna(0).astype(float)
            df['PriceSEK'] = pd.to_numeric(df['PriceSEK'], errors='coerce').fillna(0).astype(float)
            
            used_cost = float((df['kWh'] * df['PriceSEK']).sum())
            budget_used = used_cost
            num_entered_days = len(df)
            
            if num_entered_days > 0:
                daily_avg = used_cost / num_entered_days
                budget_forecast = daily_avg * days_in_month
                
                budget_percent = (used_cost / current_budget) * 100 if current_budget > 0 else 0
                budget_capped_percent = min(budget_percent, 100)
                
                if budget_forecast <= current_budget:
                    budget_status_class = 'text-success'
                    budget_status_text = f'Du är på väg att spara {(current_budget - budget_forecast):.0f} kr!'
                else:
                    budget_status_class = 'text-danger'
                    budget_status_text = f'Risk att överskrida med {(budget_forecast - current_budget):.0f} kr – kolla billiga timmar!'
    
    return render_template_string(HTML_BUDGET,
        message=message,
        current_budget=current_budget,
        budget_used=budget_used,
        budget_percent=budget_percent,
        budget_capped_percent=budget_capped_percent,
        budget_forecast=budget_forecast,
        budget_status_class=budget_status_class,
        budget_status_text=budget_status_text,
        today=today
    )

@app.route("/summary")
def summary():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    user = query_db("SELECT AnvandarID FROM Anvandare WHERE Epost = %s", ('demo@elev.se',), fetch_one=True)
    if not user:
        return "Demo-användare hittades inte.", 500
    
    rows = query_db("SELECT * FROM Forbrukning WHERE AnvandarID = %s ORDER BY Timestamp ASC", (user['AnvandarID'],))
    df = pd.DataFrame(rows)
    
    if df.empty:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="sv" data-bs-theme="dark">
        <head>
            <meta charset="UTF-8">
            <title>EcoSave SE - Sammanfattning</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
            <style>
                body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 2rem; }
                .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
            </style>
        </head>
        <body>
            <div class="container mt-5 text-center">
                <h2 class="text-warning"><i class="bi bi-exclamation-triangle-fill me-2"></i>Ingen data ännu</h2>
                <p class="lead text-muted">Ladda upp eller lägg till daglig förbrukning för att börja.</p>
                <a href="/" class="btn btn-lg btn-primary mt-3"><i class="bi bi-arrow-left me-2"></i>Tillbaka</a>
            </div>
        </body>
        </html>
        """)
    
    total_kwh = float(df['kWh'].sum() or 0)
    total_cost = float((df['kWh'] * df['PriceSEK']).sum() or 0)
    avg_price = float(df['PriceSEK'].mean() or 0)
    num_entries = len(df)
    
    forecast_html = ""
    if len(df) >= 3:
        df['timestamp_dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp_dt'])
        
        if not df.empty:
            df['days'] = (df['timestamp_dt'] - df['timestamp_dt'].min()).dt.days
            
            X = df['days'].values.reshape(-1, 1)
            y = df['kWh'].values
            
            model = LinearRegression()
            model.fit(X, y)
            
            future_days = np.array([max(df['days']) + i for i in range(1, 8)]).reshape(-1, 1)
            predicted_kwh = model.predict(future_days)
            predicted_cost = predicted_kwh * avg_price
            
            total_forecast_kwh = predicted_kwh.sum()
            total_forecast_cost = predicted_cost.sum()
            
            forecast_html = f"""
            <div class="card bg-dark border-warning mt-5 shadow mx-auto" style="max-width: 800px;">
                <div class="card-header bg-warning text-dark text-center">
                    <h5><i class="bi bi-crystal me-2"></i>Prognos för de kommande 7 dagarna</h5>
                </div>
                <div class="card-body text-center">
                    <div class="row g-4">
                        <div class="col-md-6">
                            <h6>Beräknad förbrukning</h6>
                            <div class="metric-value text-warning fs-4 fw-bold">{total_forecast_kwh:.1f} kWh</div>
                        </div>
                        <div class="col-md-6">
                            <h6>Beräknad kostnad</h6>
                            <div class="metric-value text-warning fs-4 fw-bold">{total_forecast_cost:.0f} kr</div>
                        </div>
                    </div>
                    <p class="text-muted small mt-3">Baserat på trend. Verklig kostnad kan variera.</p>
                </div>
            </div>
            """
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="sv" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <title>EcoSave SE - Sammanfattning</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
        <style>
            body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 3rem 1rem; }
            .card { background: #161b22; border: 1px solid #30363d; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); transition: transform 0.2s; overflow: hidden; }
            .card:hover { transform: translateY(-6px); }
            .metric-value { font-size: 2.8rem; font-weight: 700; line-height: 1.1; }
            .header { text-align: center; margin-bottom: 4rem; }
            .icon-lg { font-size: 3.5rem; margin-bottom: 1rem; }
            .section-title { font-weight: 600; margin-bottom: 2rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="display-4 fw-bold text-success"><i class="bi bi-speedometer2 me-2 icon-lg"></i>Din elsammanfattning</h1>
                <p class="lead text-muted">Här ser du din totala förbrukning, kostnad och prognos</p>
            </div>

            <div class="row g-4 justify-content-center">
                <div class="col-md-4 col-lg-3">
                    <div class="card text-center p-4">
                        <i class="bi bi-lightning-charge-fill text-success icon-lg"></i>
                        <h5 class="text-success section-title">Total förbrukning</h5>
                        <div class="metric-value text-success">{{ total_kwh|round(1) }}</div>
                        <p class="text-muted mt-2 fs-5">kWh</p>
                    </div>
                </div>
                <div class="col-md-4 col-lg-3">
                    <div class="card text-center p-4">
                        <i class="bi bi-currency-exchange text-info icon-lg"></i>
                        <h5 class="text-info section-title">Total kostnad</h5>
                        <div class="metric-value text-info">{{ total_cost|round(0) }}</div>
                        <p class="text-muted mt-2 fs-5">kr</p>
                    </div>
                </div>
                <div class="col-md-4 col-lg-3">
                    <div class="card text-center p-4">
                        <i class="bi bi-graph-up-arrow text-primary icon-lg"></i>
                        <h5 class="text-primary section-title">Genomsnittspris</h5>
                        <div class="metric-value text-primary">{{ avg_price|round(2) }}</div>
                        <p class="text-muted mt-2 fs-5">kr/kWh</p>
                    </div>
                </div>
            </div>

            <div class="text-center mt-5 text-muted small">
                Baserat på {{ num_entries }} poster • Senast uppdaterat {{ now }}
            </div>

            {{ forecast_html | safe }}

            <div class="text-center mt-5">
                <a href="/" class="btn btn-lg btn-outline-light"><i class="bi bi-arrow-left me-2"></i>Tillbaka till startsidan</a>
            </div>
        </div>
    </body>
    </html>
    """,
    total_kwh=total_kwh,
    total_cost=total_cost,
    avg_price=avg_price,
    num_entries=num_entries,
    now=datetime.now().strftime('%Y-%m-%d %H:%M'),
    forecast_html=forecast_html
    )

@app.route("/prices")
def prices():
    selected = request.args.get('area', 'SE3')
    if selected not in ['SE1', 'SE2', 'SE3', 'SE4']:
        selected = 'SE3'

    region_options = [
        {'code': 'SE1', 'name': 'Norrbotten & Västerbotten (Luleå, Umeå m.fl.)'},
        {'code': 'SE2', 'name': 'Västernorrland, Jämtland, Gävleborg (Sundsvall, Östersund m.fl.)'},
        {'code': 'SE3', 'name': 'Stockholm, Uppsala, Göteborg, Mälardalen m.fl.'},
        {'code': 'SE4', 'name': 'Skåne, Blekinge, Kronoberg (Malmö, Helsingborg m.fl.)'},
    ]

    energiskatt_exkl_moms = 0.36
    typiskt_paslag = 0.06
    moms_faktor = 1.25

    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        url = f"https://mgrey.se/espot?format=json&date={tomorrow}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200 or not resp.json().get(selected):
            url = f"https://mgrey.se/espot?format=json&date={today}"
            resp = requests.get(url, timeout=10)

        resp.raise_for_status()
        data = resp.json()

        date_str = data.get('date', 'Idag / imorgon')
        updated = datetime.now().strftime('%Y-%m-%d %H:%M')

        prices_list = data.get(selected, [])
        if not prices_list:
            raise ValueError("Inga priser hittades")

        processed = []
        for e in prices_list:
            hour = int(e.get('hour', 0))
            price_ore = float(e.get('price_sek', 0))
            price_sek = price_ore / 100.0
            processed.append({'hour': hour, 'price_sek': round(price_sek, 4)})

        all_hours = sorted(processed, key=lambda x: x['hour'])
        processed_sorted = sorted(processed, key=lambda x: x['price_sek'])
        cheapest = processed_sorted[:8] if processed_sorted else []
        most_expensive = processed_sorted[-1] if processed_sorted else {'price_sek': 0}

        appliance_savings = []
        total_savings = 0.0
        if cheapest:
            for app in APPLIANCES:
                cheap_cost_spot = app['kwh'] * cheapest[0]['price_sek']
                expensive_cost_spot = app['kwh'] * most_expensive['price_sek']

                cheap_consumer = (cheapest[0]['price_sek'] + typiskt_paslag + energiskatt_exkl_moms) * moms_faktor
                expensive_consumer = (most_expensive['price_sek'] + typiskt_paslag + energiskatt_exkl_moms) * moms_faktor

                cheap_cost = app['kwh'] * cheap_consumer
                expensive_cost = app['kwh'] * expensive_consumer
                savings = expensive_cost - cheap_cost
                total_savings += savings

                appliance_savings.append({
                    'name': app['name'],
                    'kwh': app['kwh'],
                    'cheapest_cost': cheap_cost,
                    'expensive_cost': expensive_cost,
                    'savings': savings
                })

            best_hour = cheapest[0]['hour']
            best_price = cheapest[0]['price_sek']
            best_consumer_price = (cheapest[0]['price_sek'] + typiskt_paslag + energiskatt_exkl_moms) * moms_faktor
            advice = f"""
            <h4 class="best-hour-title mb-3"><i class="bi bi-star-fill me-2"></i>Bästa timmen för alla apparater</h4>
            <p class="best-hour-time">{best_hour:02d}:00 – {best_hour + 1:02d}:00</p>
            <p class="best-hour-price mb-3">{best_price:.2f} kr/kWh (spot)</p>
            <p class="best-hour-price mb-3 text-success fw-bold">{best_consumer_price:.2f} kr/kWh uppskattat totalpris</p>
            <p class="mb-0">Perfekt för diskmaskin, tvättmaskin, elbilsladdning och ugn – spara mest just då!</p>
            """
        else:
            advice = "Inga priser tillgängliga just nu."

        return render_template_string(HTML_PRICES,
            regions=region_options,
            area=selected,
            date=date_str,
            updated=updated,
            advice=advice,
            appliances=appliance_savings,
            total_savings=total_savings,
            all_hours=all_hours,
            error=None
        )

    except Exception as e:
        return render_template_string(HTML_PRICES,
            regions=region_options,
            area=selected,
            error=f"Kunde inte hämta priser just nu: {str(e)}.<br>Priser för imorgon visas normalt efter kl. 13:00 – kolla tillbaka då!",
            date="–",
            updated=datetime.now().strftime('%Y-%m-%d %H:%M'),
            advice="Inga priser tillgängliga just nu.",
            appliances=[],
            total_savings=0,
            all_hours=[]
        )

@app.route("/transactions")
def transactions():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    user = query_db("SELECT AnvandarID FROM Anvandare WHERE Epost = %s", ('demo@elev.se',), fetch_one=True)
    if not user:
        return "Demo-användare hittades inte.", 500
    
    rows = query_db("""
        SELECT 
            ForbrukningID,
            Forbrukningsdatum,
            kWh,
            PriceSEK,
            Notes,
            Timestamp AS Inmatad
        FROM Forbrukning 
        WHERE AnvandarID = %s 
        ORDER BY COALESCE(Forbrukningsdatum, Timestamp) DESC, Timestamp DESC
    """, (user['AnvandarID'],))
    
    if not rows:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="sv" data-bs-theme="dark">
        <head>
            <meta charset="UTF-8">
            <title>EcoSave SE - Transaktioner</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
            <style>
                body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 3rem 1rem; }
            </style>
        </head>
        <body>
            <div class="container text-center mt-5">
                <h2 class="text-warning"><i class="bi bi-list-ul me-2"></i>Inga transaktioner ännu</h2>
                <p class="lead text-muted">Du har inte lagt till någon förbrukning.</p>
                <a href="/" class="btn btn-lg btn-primary mt-3"><i class="bi bi-arrow-left me-2"></i>Tillbaka till startsidan</a>
            </div>
        </body>
        </html>
        """)
    
    df = pd.DataFrame(rows)
    
    df = df[['Forbrukningsdatum', 'kWh', 'PriceSEK', 'Notes', 'Inmatad']]
    df = df.rename(columns={
        'Forbrukningsdatum': 'Förbrukningsdatum',
        'kWh': 'kWh',
        'PriceSEK': 'Pris SEK/kWh',
        'Notes': 'Notering',
        'Inmatad': 'Inmatad tid'
    })
    
    df['Förbrukningsdatum'] = pd.to_datetime(df['Förbrukningsdatum'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['Inmatad tid'] = pd.to_datetime(df['Inmatad tid']).dt.strftime('%Y-%m-%d %H:%M')
    
    table_html = df.to_html(
        classes='table table-dark table-striped table-hover table-bordered rounded shadow-sm text-center',
        index=False,
        escape=False,
        justify='center'
    )
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="sv" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <title>EcoSave SE - Transaktioner</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
        <style>
            body { background: linear-gradient(135deg, #0d1117, #161b22); color: #e6edf3; min-height: 100vh; padding: 3rem 1rem; }
            .card { background: #161b22; border: 1px solid #30363d; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); overflow: hidden; }
            .header { text-align: center; margin-bottom: 3rem; }
            .table { border-radius: 12px; overflow: hidden; }
            .table th, .table td { 
                text-align: center !important; 
                vertical-align: middle; 
                padding: 1rem; 
            }
            tr:hover { background-color: #1f2937 !important; }
            .icon-lg { font-size: 3rem; margin-bottom: 1rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="display-4 fw-bold text-info"><i class="bi bi-list-ul icon-lg"></i>Transaktioner</h1>
                <p class="lead text-muted">Alla dina registrerade elförbrukningar</p>
            </div>

            <div class="card p-4">
                <h5 class="text-center mb-4 text-light">Totalt {{ num_rows }} poster</h5>
                <div class="table-responsive">
                    {{ table_html | safe }}
                </div>
                <p class="text-center text-muted small mt-4">
                    Senast uppdaterat: {{ now }}
                </p>
            </div>

            <div class="text-center mt-5">
                <a href="/" class="btn btn-lg btn-outline-light"><i class="bi bi-arrow-left me-2"></i>Tillbaka till startsidan</a>
            </div>
        </div>
    </body>
    </html>
    """,
    table_html=table_html,
    num_rows=len(df),
    now=datetime.now().strftime('%Y-%m-%d %H:%M')
    )

@app.route("/reset")
def reset():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.args.get('confirm') == 'yes':
        user = query_db("SELECT AnvandarID FROM Anvandare WHERE Epost = %s", ('demo@elev.se',), fetch_one=True)
        if user:
            query_db("DELETE FROM Forbrukning WHERE AnvandarID = %s", (user['AnvandarID'],), commit=True)
            query_db("DELETE FROM Manadsbudget WHERE AnvandarID = %s", (user['AnvandarID'],), commit=True)
            query_db(
                "DELETE FROM settings WHERE `key` LIKE %s OR `key` LIKE %s",
                ('%monthly_budget%', '%budget_start_date%'),
                commit=True
            )
        return redirect(url_for('home'))
    
    return render_template_string(HTML_RESET_CONFIRM)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
