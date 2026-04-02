import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    'host': 'localhost',
    'user': 'ecosave_user',
    'password': 'EcoSave2026StrongPass!',
    'database': 'ecosave_db',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def query_db(sql, params=None, fetch_one=False, commit=False):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            
            if commit:
                conn.commit()
                return True
            else:
                if fetch_one:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
    except Exception as e:
        print(f"ERROR i query_db: {str(e)}")
        if commit:
            conn.rollback()
        raise  
    finally:
        conn.close()

def add_usage(anvandar_id, kwh, price_sek, notes='', apparat_id=None, forbrukningsdatum=None):
    sql = """
    INSERT INTO Forbrukning 
    (AnvandarID, ApparatID, kWh, PriceSEK, Notes, Forbrukningsdatum)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (anvandar_id, apparat_id, kwh, price_sek, notes, forbrukningsdatum)
    return query_db(sql, params, commit=True)

def get_monthly_summary(anvandar_id, year_month):
    sql = "CALL GetMonthlySummary(%s, %s)"
    return query_db(sql, (anvandar_id, year_month))
