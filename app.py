import streamlit as st
import pandas as pd
import os

DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    s = str(value).strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        # Чай - используем ваше название колонки 'Чай черный ароматизированный'
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        
        # Ключевая колонка из вашего сообщения
        tea_col = 'Чай черный ароматизированный'
        price_col = '80' # Судя по вашему списку, цена может быть здесь
        
        if tea_col in df_tea.columns:
            for _, r in df_tea.dropna(subset=[tea_col]).iterrows():
                # Если колонки '80' нет, попробуем 'Предоплата'
                p_val = r.get(price_col) if price_col in df_tea.columns else r.get('Предоплата')
                prices[str(r[tea_col]).lower().strip()] = clean_num(p_val)
        
        # Кофе
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (Форсируем Windows-1251)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Читаем строго в cp1251, так как utf-8 выдает ошибку
        df = pd.read_csv(path, sep=';', skiprows=1, encoding='cp1251')
        df.columns = [str(c).strip() for c in df.columns]

        # Группировка транзакций по товару
        summary = df.groupby('Название товара').agg({
            'Сумма итого, руб.': 'sum',
            'Цена продавца': 'max',
            'Количество': 'sum'
        }).reset_index()

        results = []
        not_found = []

        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if 'nan' in name.lower() or not name or 'итого' in name.lower(): continue
            
            payout = clean_num(row['Сумма итого, руб.'])
            sale_price = clean_num(row['Цена продавца'])
            qty = clean_num(row['Количество'])

            cost_1kg = None
            name_lower = name.lower()
            
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 гр'])
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * max(0, qty)
                tax = (sale_price * max(0, qty)) * 0.06
                results.append({
                    'Товар': name,
                    'Кол-во': qty,
                    'Выплата': payout,
                    'Закупка': unit_cost,
                    'Налог': tax,
                    'Прибыль': payout - unit_cost - tax
                })
            else:
                not_found.append({'Товар из Ozon': name, 'Сумма': payout})

        return pd.DataFrame(results), pd.DataFrame(not_found)
    except Exception as e:
        st.error(f"Ошибка Ozon: {e}")
        return None, None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L Анализ")
data, missing = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Выплата от Ozon", f"{data['Выплата'].sum():,.2f} ₽")
    c2.metric("Налог УСН", f"{data['Налог'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)

if missing is not None and not missing.empty:
    with st.expander("⚠️ Товары, для которых не найдена цена закупки"):
        st.table(missing)
