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
    # Очистка строки от валюты, пробелов и замена запятой на точку
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def get_col(df, keys):
    """Ищет колонку по списку ключевых слов"""
    for c in df.columns:
        if any(k.lower() in str(c).lower().strip() for k in keys):
            return c
    return None

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ (Чай и Кофе)
    try:
        # Чай
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        # Пробуем разные skiprows, пока не найдем колонку "Наименование"
        for s in range(0, 10):
            df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=s)
            c_n = get_col(df_tea, ['Наименование', 'Товар'])
            c_p = get_col(df_tea, ['Предоплата', 'Цена'])
            if c_n and c_p:
                for _, r in df_tea.dropna(subset=[c_n]).iterrows():
                    prices[str(r[c_n]).lower().strip()] = clean_num(r[c_p])
                break
        
        # Кофе
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

    # 2. ЗАГРУЗКА OZON CSV (Исправление кодировки)
    try:
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Пробуем разные кодировки (Ozon часто шлет в windows-1251)
        try:
            df_ozon = pd.read_csv(path_ozon, sep=';', skiprows=1, encoding='utf-8')
        except:
            df_ozon = pd.read_csv(path_ozon, sep=';', skiprows=1, encoding='cp1251')
        
        df_ozon.columns = [c.strip() for c in df_ozon.columns]
        
        # Ключевые колонки
        o_name = get_col(df_ozon, ['Название товара'])
        o_payout = get_col(df_ozon, ['Сумма итого'])
        o_sale = get_col(df_ozon, ['Цена продавца'])
        o_qty = get_col(df_ozon, ['Количество'])

        if not all([o_name, o_payout, o_sale]):
            st.error("Не найдены нужные колонки в CSV. Проверьте заголовки.")
            return None

        # Группируем транзакции по товару
        summary = df_ozon.groupby(o_name).agg({
            o_payout: 'sum',
            o_sale: 'max',
            o_qty: 'max'
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row[o_name])
            if 'nan' in name.lower() or not name: continue
            
            payout = clean_num(row[o_payout])
            sale_price = clean_num(row[o_sale])
            quantity = clean_num(row[o_qty])

            # Поиск себестоимости
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * quantity
                tax = (sale_price * quantity) * 0.06
                profit = payout - unit_cost - tax
                
                results.append({
                    'Товар': name,
                    'Кол-во': quantity,
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
    total_net = data['Прибыль'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего от Ozon (чистыми)", f"{data['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог (с продаж)", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{total_net:,.2f} ₽")

    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Файлы анализируются...")
