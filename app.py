import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final Logic", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    if isinstance(value, (int, float)): return float(value)
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    # 1. Загрузка цен закупки
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

    # 2. Обработка Ozon по уникальным ID начислений
    try:
        df = pd.read_csv(os.path.join(DATA_FOLDER, OZON_REPORT), sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Чистим числа сразу
        df['Сумма итого, руб.'] = df['Сумма итого, руб.'].apply(clean_num)
        df['Цена продавца'] = df['Цена продавца'].apply(clean_num)
        df['Количество'] = df['Количество'].apply(clean_num)

        # ШАГ 1: Схлопываем транзакции по ID начисления
        # Это дает нам финансовый результат по каждой отдельной продаже
        order_summary = df.groupby('ID начисления').agg({
            'Название товара': 'first',
            'Сумма итого, руб.': 'sum', # Суммируем доходы и расходы по заказу
            'Цена продавца': 'max',     # Грязная цена для налога
            'Количество': 'max'         # Кол-во штук в этом заказе
        }).reset_index()

        # ШАГ 2: Собираем итоговую таблицу по товарам
        final_table = []
        unique_products = order_summary['Название товара'].unique()

        for product in unique_products:
            if pd.isna(product) or 'итого' in str(product).lower(): continue
            
            product_orders = order_summary[order_summary['Название товара'] == product]
            
            total_qty = product_orders['Количество'].sum()
            total_payout = product_orders['Сумма итого, руб.'].sum()
            # Оборот для налога (Цена * Кол-во по каждому заказу)
            total_turnover = (product_orders['Цена продавца'] * product_orders['Количество']).sum()

            # Ищем себестоимость
            cost_1kg = 0.0
            for p_name, p_val in prices.items():
                if p_name in str(product).lower():
                    cost_1kg = p_val
                    break
            
            if cost_1kg > 0:
                is_half = any(m in str(product).lower() for m in ['500 гр', '500г', '0.5'])
                total_purchase_cost = (cost_1kg / 2 if is_half else cost_1kg) * total_qty
                tax = total_turnover * 0.06
                profit = total_payout - total_purchase_cost - tax
                
                final_table.append({
                    'Товар': product,
                    'Продано (шт)': int(total_qty),
                    'От Ozon (Чистыми)': total_payout,
                    'Закупка (Всего)': total_purchase_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(final_table)
    except Exception as e:
        st.error(f"Ошибка в расчетах: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L Анализ (по Заказам)")
data = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{data['От Ozon (Чистыми)'].sum():,.2f} ₽")
    c2.metric("Себестоимость", f"{data['Закупка (Всего)'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    
    # Добавляем маржинальность
    data['Маржа %'] = (data['Прибыль'] / data['От Ozon (Чистыми)'] * 100)
    
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.warning("Данные не найдены. Проверьте файл в папке data.")
