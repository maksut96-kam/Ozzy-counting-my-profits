import streamlit as st
import pandas as pd
import os

DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="P&L Analytics", layout="wide")

def clean_num(value):
    try:
        if pd.isna(value): return 0.0
        return float(value)
    except: return 0.0

def load_data():
    try:
        # 1. Загрузка прайсов
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_coffee = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        
        prices = {}
        for _, r in df_tea.dropna(subset=['Наименование']).iterrows():
            prices[str(r['Наименование']).lower().strip()] = clean_num(r.get('Предоплата'))
        for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный']).iterrows():
            prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))

        # 2. Загрузка Ozon с поиском колонок
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        df_sales = pd.read_excel(path_ozon)
        
        # Перебираем варианты, пока не найдем колонку с товаром
        for s in range(0, 15):
            df_tmp = pd.read_excel(path_ozon, skiprows=s)
            cols = [str(c).strip() for c in df_tmp.columns]
            if 'Название товара' in cols:
                df_sales = df_tmp
                df_sales.columns = cols # Чистим заголовки от пробелов
                break

        results = []
        # Ключевые колонки (проверяем разные варианты названий)
        col_payout = 'Итого к начислению'
        col_sale = 'Цена реализации'
        
        for _, row in df_sales.iterrows():
            name = str(row.get('Название товара', ''))
            if not name or name == 'nan' or 'итого' in name.lower(): continue

            payout = clean_num(row.get(col_payout, 0))
            sale_price = clean_num(row.get(col_sale, 0))
            
            # Поиск закупки
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg is not None:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                final_cost = cost_1kg / 2 if is_half else cost_1kg
                tax = sale_price * 0.06
                profit = payout - final_cost - tax
                
                results.append({
                    'Товар': name,
                    'Выплата Озон': payout,
                    'Себестоимость': final_cost,
                    'Налог 6%': tax,
                    'Чистая прибыль': profit
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return None

# --- ВЫВОД ---
st.title("📊 Итоговая аналитика прибыли")
res = load_data()

if res is not None and not res.empty:
    # ИТОГОВАЯ СТРОКА
    total_row = pd.DataFrame([{
        'Товар': '💰 ИТОГО',
        'Выплата Озон': res['Выплата Озон'].sum(),
        'Себестоимость': res['Себестоимость'].sum(),
        'Налог 6%': res['Налог 6%'].sum(),
        'Чистая прибыль': res['Чистая прибыль'].sum()
    }])

    # Метрики
    c1, c2, c3 = st.columns(3)
    c1.metric("Выплата Ozon (Всего)", f"{res['Выплата Озон'].sum():,.2f} ₽")
    c2.metric("Налоги (Всего)", f"{res['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{res['Чистая прибыль'].sum():,.2f} ₽", 
              delta=f"{res['Чистая прибыль'].sum():,.2f} ₽")

    # Склеиваем основную таблицу и итог
    full_table = pd.concat([res, total_row], ignore_index=True)
    
    st.write("### Детальный расчет")
    st.dataframe(full_table.style.highlight_max(axis=0, subset=['Чистая прибыль'], color='#e6ffed')
                                .highlight_min(axis=0, subset=['Чистая прибыль'], color='#ffebec'), 
                 use_container_width=True)
else:
    st.warning("Проверьте названия колонок в файле Озона. Ожидаются: 'Название товара', 'Итого к начислению', 'Цена реализации'")
