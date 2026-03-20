import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon Business Intelligence", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    if isinstance(value, (int, float)): return float(value)
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_prices():
    prices = {}
    try:
        # Чай
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        for _, r in df_tea.dropna(subset=['Чай черный ароматизированный']).iterrows():
            prices[str(r['Чай черный ароматизированный']).lower().strip()] = clean_num(r.get('80'))
        # Кофе
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
            prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка загрузки прайсов: {e}")
    return prices

def analyze_ozon(prices):
    try:
        df = pd.read_csv(os.path.join(DATA_FOLDER, OZON_REPORT), sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Очистка данных
        for col in ['Сумма итого, руб.', 'Цена продавца', 'Количество']:
            df[col] = df[col].apply(clean_num)

        # ШАГ 1: Группировка по ID начисления (один уникальный заказ/событие)
        orders = df.groupby('ID начисления').agg({
            'Название товара': 'first',
            'Сумма итого, руб.': 'sum',
            'Цена продавца': 'max',
            'Количество': 'max'
        }).reset_index()

        # ШАГ 2: Итоговая сборка по названиям товаров
        report = []
        for product in orders['Название товара'].unique():
            if not product or 'итого' in str(product).lower(): continue
            
            p_orders = orders[orders['Название товара'] == product]
            
            total_qty = p_orders['Количество'].sum()
            total_payout = p_orders['Сумма итого, руб.'].sum()
            # Налог с оборота (грязная цена * кол-во)
            total_revenue = (p_orders['Цена продавца'] * p_orders['Количество']).sum()

            # Поиск себестоимости
            cost_base = 0.0
            p_name_lower = str(product).lower()
            for name, val in prices.items():
                if name in p_name_lower:
                    cost_base = val
                    break
            
            if cost_base > 0:
                is_500g = any(m in p_name_lower for m in ['500 гр', '500г', '0.5'])
                unit_purchase = cost_base / 2 if is_500g else cost_base
                total_purchase = unit_purchase * total_qty
                
                tax = total_revenue * 0.06
                profit = total_payout - total_purchase - tax
                
                report.append({
                    'Товар': product,
                    'Продано (шт)': int(total_qty),
                    'Выручка (Грязная)': total_revenue,
                    'Выплата Ozon (Чистая)': total_payout,
                    'Закупка': total_purchase,
                    'Налог (6%)': tax,
                    'Чистая прибыль': profit,
                    'Рентабельность (%)': (profit / total_revenue * 100) if total_revenue > 0 else 0
                })
        
        return pd.DataFrame(report)
    except Exception as e:
        st.error(f"Ошибка обработки Ozon: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("🚀 Панель управления прибылью Ozon")

prices = load_prices()
data = analyze_ozon(prices)

if data is not None and not data.empty:
    # Метрики для предпринимателя
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Общая выручка", f"{data['Выручка (Грязная)'].sum():,.2f} ₽")
    m2.metric("Чистая прибыль", f"{data['Чистая прибыль'].sum():,.2f} ₽", delta_color="normal")
    m3.metric("Удержано Ozon (%)", f"{((1 - data['Выплата Ozon (Чистая)'].sum()/data['Выручка (Грязная)'].sum())*100):.1f}%")
    m4.metric("Средняя рентабельность", f"{(data['Чистая прибыль'].sum()/data['Выручка (Грязная)'].sum()*100):.1f}%")

    st.subheader("Детальный анализ по позициям")
    st.dataframe(data.sort_values('Чистая прибыль', ascending=False), use_container_width=True)
else:
    st.info("Загрузите файлы в папку data для анализа.")
