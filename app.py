import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    if isinstance(value, (int, float)): return float(value)
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    # 1. Загрузка прайсов (без изменений)
    try:
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        t_name, t_price = 'Чай черный ароматизированный', '80'
        for _, r in df_tea.dropna(subset=[t_name]).iterrows():
            prices[str(r[t_name]).lower().strip()] = clean_num(r.get(t_price))
            
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
            prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. Обработка Ozon по логике ID Начисления
    try:
        df = pd.read_csv(os.path.join(DATA_FOLDER, OZON_REPORT), sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Чистим данные
        df['Сумма итого, руб.'] = df['Сумма итого, руб.'].apply(clean_num)
        df['Цена продавца'] = df['Цена продавца'].apply(clean_num)
        df['Количество'] = df['Количество'].apply(clean_num)

        # ШАГ 1: Группируем по уникальному ID Начисления
        # Это схлопывает все строки одного заказа в одну сущность
        order_grouped = df.groupby('ID начисления').agg({
            'Название товара': 'first',
            'Сумма итого, руб.': 'sum', # Это ЧИСТЫЙ остаток от Озона (Доходы - Логистика - Комиссия)
            'Цена продавца': 'max',     # Грязная цена продажи для налога
            'Количество': 'max'         # Реальное кол-во штук в этом заказе
        }).reset_index()

        # ШАГ 2: Собираем итоги по Товару
        results = []
        for product in order_grouped['Название товара'].unique():
            if pd.isna(product) or 'итого' in str(product).lower(): continue
            
            p_data = order_grouped[order_grouped['Название товара'] == product]
            
            total_qty = p_data['Количество'].sum()
            total_ozon_payout = p_data['Сумма итого, руб.'].sum()
            # Оборот для налога: суммируем (Цена * Кол-во) по каждому ID заказа
            total_turnover = (p_data['Цена продавца'] * p_data['Количество']).sum()

            # Ищем цену закупки
            cost_1kg = 0.0
            p_lower = str(product).lower()
            for name, val in prices.items():
                if name in p_lower:
                    cost_1kg = val
                    break
            
            if cost_1kg > 0:
                is_half = any(m in p_lower for m in ['500 гр', '500г', '0.5'])
                total_purchase = (cost_1kg / 2 if is_half else cost_1kg) * total_qty
                tax = total_turnover * 0.06
                profit = total_ozon_payout - total_purchase - tax
                
                results.append({
                    'Товар': product,
                    'Штук продано': int(total_qty),
                    'Выплата Ozon (чист)': total_ozon_payout,
                    'Закупка (всего)': total_purchase,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })

        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в расчетах: {e}")
        return None

# --- ВЫВОД ---
st.title("📊 Финальный P&L (Учет каждого заказа)")
data = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{data['Выплата Ozon (чист)'].sum():,.2f} ₽")
    c2.metric("Себестоимость", f"{data['Закупка (всего)'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Данные не найдены.")
