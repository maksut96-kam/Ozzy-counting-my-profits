import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    # Очистка строки: убираем всё, кроме цифр, точек и минусов
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    # Оставляем только символы, которые могут быть числом
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def get_col(df, keys):
    for c in df.columns:
        if any(k.lower() in str(c).lower().strip() for k in keys):
            return c
    return None

def load_ozon_csv(path):
    """Пытается прочитать CSV Озона, перебирая кодировки и игнорируя ошибки символов"""
    encodings = ['utf-8', 'cp1251', 'windows-1251', 'latin1']
    for enc in encodings:
        try:
            # errors='replace' заменит непонятные символы на знак вопроса, вместо того чтобы вылетать
            df = pd.read_csv(path, sep=';', skiprows=1, encoding=enc, errors='replace')
            if 'Название товара' in str(df.columns) or 'ID начисления' in str(df.columns):
                return df
        except:
            continue
    return None

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        for s in range(0, 10):
            df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=s)
            c_n = get_col(df_tea, ['Наименование', 'Товар'])
            c_p = get_col(df_tea, ['Предоплата', 'Цена'])
            if c_n and c_p:
                for _, r in df_tea.dropna(subset=[c_n]).iterrows():
                    prices[str(r[c_n]).lower().strip()] = clean_num(r[c_p])
                break
        
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        for s in range(0, 10):
            df_cof = pd.read_excel(path_cof, sheet_name='Кофе', skiprows=s)
            c_n = get_col(df_cof, ['Кофе Ароматизированный', 'Наименование'])
            c_p = get_col(df_cof, ['Прайс 2026', 'Цена'])
            if c_n and c_p:
                for _, r in df_cof.dropna(subset=[c_n]).iterrows():
                    prices[str(r[c_n]).lower().strip()] = clean_num(r[c_p])
                break
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON
    try:
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        df_ozon = load_ozon_csv(path_ozon)
        
        if df_ozon is None:
            st.error("Не удалось прочитать CSV Озон. Попробуйте пересохранить его как Excel.")
            return None

        df_ozon.columns = [c.strip() for c in df_ozon.columns]
        
        o_name = get_col(df_ozon, ['Название товара'])
        o_payout = get_col(df_ozon, ['Сумма итого'])
        o_sale = get_col(df_ozon, ['Цена продавца'])
        o_qty = get_col(df_ozon, ['Количество'])

        # Группировка транзакций
        summary = df_ozon.groupby(o_name).agg({
            o_payout: 'sum',
            o_sale: 'max',
            o_qty: 'sum' # Тут лучше 'sum' для общего кол-ва транзакций
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row[o_name])
            if 'nan' in name.lower() or not name or 'итого' in name.lower(): continue
            
            payout = row[o_payout]
            # Налог считаем только с положительных начислений (продаж)
            # Чтобы не платить налог с возвратов
            sale_price = clean_num(row[o_sale])
            quantity = clean_num(row[o_qty])

            # Поиск закупки
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                # Себестоимость считаем только на положительное кол-во проданного товара
                real_qty = max(0, quantity) 
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * real_qty
                
                tax = (sale_price * real_qty) * 0.06
                profit = payout - unit_cost - tax
                
                results.append({
                    'Товар': name,
                    'Кол-во': real_qty,
                    'Выплата Ozon': payout,
                    'Закупка': unit_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })

        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в отчете Озон: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L по транзакциям")
data = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего от Ozon", f"{data['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог (с продаж)", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")

    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Файлы анализируются. Если это длится долго, проверьте ошибки выше.")
