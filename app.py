import streamlit as st
import pandas as pd
import os

# --- 1. НАСТРОЙКИ ПУТЕЙ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="Tea&Coffee Analytics", layout="wide")
st.title("📊 Аналитика прибыли: Чай и Кофе 2026")

def load_data():
    try:
        # Формируем пути
        tea_p = os.path.join(DATA_FOLDER, TEA_FILE)
        cof_p = os.path.join(DATA_FOLDER, COFFEE_FILE)
        ozon_p = os.path.join(DATA_FOLDER, OZON_REPORT)

        # 1. Загружаем прайс ЧАЙ (заголовки на 3-й строке)
        df_tea = pd.read_excel(tea_p, sheet_name='Чай', skiprows=2)
        # 2. Загружаем прайс КОФЕ (заголовки на 2-й строке)
        df_coffee = pd.read_excel(cof_p, sheet_name='Кофе', skiprows=1)
        
        # Собираем базу цен закупок
        prices = {}
        
        # Обработка Чая (Наименование + Предоплата)
        if 'Наименование' in df_tea.columns:
            for _, r in df_tea.dropna(subset=['Наименование', 'Предоплата']).iterrows():
                name_clean = str(r['Наименование']).lower().strip()
                prices[name_clean] = r['Предоплата']
        
        # Обработка Кофе (Кофе Ароматизированный + Прайс 2026)
        if 'Кофе Ароматизированный' in df_coffee.columns:
            for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный', 'Прайс 2026']).iterrows():
                name_clean = str(r['Кофе Ароматизированный']).lower().strip()
                prices[name_clean] = r['Прайс 2026']

        # 3. Загружаем отчет Озона
        df_sales = pd.read_excel(ozon_p)
        
        # Поиск заголовков в отчете Озона (если есть пустые строки сверху)
        if 'Название товара' not in df_sales.columns:
            for s in range(1, 15):
                df_tmp = pd.read_excel(ozon_p, skiprows=s)
                if 'Название товара' in df_tmp.columns:
                    df_sales = df_tmp
                    break

        results = []
        for _, row in df_sales.iterrows():
            full_name = str(row['Название товара'])
            payout = row.get('Итого к начислению', 0)
            sale_price = row.get('Цена реализации', 0)
            
            if payout == 0 and sale_price == 0: continue
            
            # Ищем товар в нашей базе цен
            cost_1kg = None
            for p_name, p_val in prices.items():
                if p_name in full_name.lower():
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                # Логика веса: 0.5кг или 500г
                is_half = any(mark in full_name.lower() for mark in ['0.5', '500г', '500 г'])
                unit_cost = cost_1kg / 2 if is_half else cost_1kg
                
                # Налог 6% от выручки
                tax = sale_price * 0.06
                profit = payout - unit_cost - tax
                
                results.append({
                    'Товар': full_name,
                    'Выплата Ozon': payout,
                    'Себестоимость': unit_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Ошибка при чтении файлов: {e}")
        return None

# --- ИНТЕРФЕЙС ---
data = load_data()

if data is not None and not data.empty:
    total_profit = data['Прибыль'].sum()
    total_payout = data['Выплата Ozon'].sum()
    
    c1, c2 = st.columns(2)
    c1.metric("Итого чистая прибыль", f"{total_profit:,.2f} ₽")
    c2.metric("Всего получено от Ozon", f"{total_payout:,.2f} ₽")
    
    st.divider()
    st.subheader("Детализация продаж")
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Данные загружаются... Убедитесь, что все файлы в папке data.")
