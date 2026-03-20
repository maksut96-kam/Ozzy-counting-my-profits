import streamlit as st
import pandas as pd
import os

DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv' # Теперь CSV

st.set_page_config(page_title="Ozon P&L Pro", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    s = str(value).replace('₽', '').replace(' ', '').replace('\xa0', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def load_data():
    # 1. Загрузка цен (оставляем как было, это работало)
    prices = {}
    try:
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        for _, r in df_tea.dropna(subset=['Наименование']).iterrows():
            prices[str(r['Наименование']).lower().strip()] = clean_num(r.get('Предоплата'))
        
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
            prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. Загрузка и обработка CSV Озона
    try:
        # Читаем CSV с учетом точки с запятой
        df_ozon = pd.read_csv(os.path.join(DATA_FOLDER, OZON_REPORT), sep=';', skiprows=1)
        df_ozon.columns = [c.strip() for c in df_ozon.columns]

        # Группируем данные по товару, чтобы собрать все комиссии и логистику в одну сумму
        # Суммируем "Сумма итого, руб." - это наш чистый приход
        # Максимум "Цена продавца" - это база для налога
        # Сумма "Количество" - сколько штук продано
        summary = df_ozon.groupby('Название товара').agg({
            'Сумма итого, руб.': 'sum',
            'Цена продавца': 'max',
            'Количество': 'max' 
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if 'nan' in name.lower() or not name: continue
            
            payout = row['Сумма итого, руб.']
            sale_price = row['Цена продавца']
            quantity = row['Количество']

            # Ищем себестоимость в прайсах
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
                    'Выплата (Net)': payout,
                    'Закупка (Total)': unit_cost,
                    'Налог 6%': tax,
                    'Чистая прибыль': profit
                })

        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в отчете Озон: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Точный P&L: Анализ транзакций Ozon")
data = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Итого к выплате", f"{data['Выплата (Net)'].sum():,.2f} ₽")
    c2.metric("Налог УСН", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Чистая прибыль'].sum():,.2f} ₽")

    st.dataframe(data.sort_values('Чистая прибыль', ascending=False), use_container_width=True)
else:
    st.info("Данные обрабатываются...")
