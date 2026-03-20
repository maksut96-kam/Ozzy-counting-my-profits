import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ПУТЕЙ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="Tea&Coffee Analytics", layout="wide")
st.title("📊 Отчет о прибылях и убытках (P&L) 2026")

def load_data():
    try:
        # Пути к файлам в папке data
        tea_p = os.path.join(DATA_FOLDER, TEA_FILE)
        cof_p = os.path.join(DATA_FOLDER, COFFEE_FILE)
        ozon_p = os.path.join(DATA_FOLDER, OZON_REPORT)

        # 1. Загружаем прайс ЧАЙ (заголовки обычно на 3-й строке)
        df_tea = pd.read_excel(tea_p, sheet_name='Чай', skiprows=2)
        # 2. Загружаем прайс КОФЕ (заголовки обычно на 2-й строке)
        df_coffee = pd.read_excel(cof_p, sheet_name='Кофе', skiprows=1)
        
        # Собираем единый словарь цен за 1 кг
        prices = {}
        
        # Обработка Чая
        if 'Наименование' in df_tea.columns and 'Предоплата' in df_tea.columns:
            for _, r in df_tea.dropna(subset=['Наименование', 'Предоплата']).iterrows():
                prices[str(r['Наименование']).lower().strip()] = r['Предоплата']
        
        # Обработка Кофе
        if 'Кофе Ароматизированный' in df_coffee.columns and 'Прайс 2026' in df_coffee.columns:
            for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный', 'Прайс 2026']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = r['Прайс 2026']

        # 3. Загружаем отчет Озона
        df_sales = pd.read_excel(ozon_p)
        
        # Если Озон вставил пустые строки в начало, ищем заголовок 'Название товара'
        if 'Название товара' not in df_sales.columns:
            for s in range(1, 15):
                df_tmp = pd.read_excel(ozon_p, skiprows=s)
                if 'Название товара' in df_tmp.columns:
                    df_sales = df_tmp
                    break

        results = []
        for _, row in df_sales.iterrows():
            name = str(row['Название товара'])
            # 'Итого к начислению' - это сумма, которую Озон УЖЕ очистил от комиссий и логистики
            payout = row.get('Итого к начислению', 0)
            sale_price = row.get('Цена реализации', 0)
            
            # Если это возврат или пустая строка - пропускаем
            if payout == 0 and sale_price == 0: continue
            
            # Поиск соответствия товара в прайсах
            cost_1kg = None
            for p_name, p_val in prices.items():
                if p_name in name.lower():
                    cost_1kg = p_val
                    break
            
            # Если товар найден в закупке, считаем P&L
            if cost_1kg:
                # ЛОГИКА ВЕСА: делим закупку на 2, если упаковка 0.5кг или 500г
                is_half = any(mark in name.lower() for mark in ['0.5', '500г', '500 г'])
                unit_purchase_cost = cost_1kg / 2 if is_half else cost_1kg
                
                # Налог 6% (УСН) берется от цены, которую заплатил покупатель
                tax = sale_price * 0.06
                
                # ЧИСТАЯ ПРИБЫЛЬ = Выплата - Закупка - Налог
                net_profit = payout - unit_purchase_cost - tax
                
                results.append({
                    'Товар': name,
                    'Цена продажи': sale_price,
                    'Выплата Озон (чистая)': payout,
                    'Себестоимость': unit_purchase_cost,
                    'Налог (6%)': tax,
                    'Прибыль': net_profit
                })
        
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
        return None

# --- ИНТЕРФЕЙС ПРИЛОЖЕНИЯ ---
res_df = load_data()

if res_df is not None and not res_df.empty:
    # Итоговые показатели
    total_profit = res_df['Прибыль'].sum()
    total_payout = res_df['Выплата Озон (чистая)'].sum()
    
    col1, col2 = st.columns(2)
    col1.metric("Чистая прибыль за период", f"{total_profit:,.2f} ₽")
    col2.metric("Сумма начислений от Ozon", f"{total_payout:,.2f} ₽")
    
    st.divider()
    
    # Таблица с подробностями
    st.subheader("Детальный расчет по каждой позиции")
    # Красим прибыль в зеленый/красный
    st.dataframe(res_df.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.warning("Загрузи файлы в папку 'data' на GitHub и проверь названия файлов в коде.")
