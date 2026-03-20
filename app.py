import streamlit as st
import pandas as pd
import os

# --- 1. НАСТРОЙКИ ПУТЕЙ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
# Твое точное название файла из папки data
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="Tea&Coffee P&L Analytics", layout="wide")
st.title("📊 Фактический P&L отчет за 1 квартал 2026")

def load_data():
    try:
        # Пути к файлам
        tea_p = os.path.join(DATA_FOLDER, TEA_FILE)
        cof_p = os.path.join(DATA_FOLDER, COFFEE_FILE)
        ozon_p = os.path.join(DATA_FOLDER, OZON_REPORT)

        # Читаем прайсы (учитываем структуру твоих Excel)
        # Для чая заголовки на 3-й строке (skiprows=2)
        df_tea = pd.read_excel(tea_p, sheet_name='Чай', skiprows=2)
        # Для кофе заголовки на 2-й строке (skiprows=1)
        df_coffee = pd.read_excel(cof_p, sheet_name='Кофе', skiprows=1)
        
        # Собираем базу цен за 1 кг
        prices = {}
        
        # Обработка чая (используем колонку 'Наименование' и 'Предоплата')
        if 'Наименование' in df_tea.columns and 'Предоплата' in df_tea.columns:
            for _, r in df_tea.dropna(subset=['Наименование', 'Предоплата']).iterrows():
                prices[str(r['Наименование']).lower().strip()] = r['Предоплата']
        
        # Обработка кофе (используем 'Кофе Ароматизированный' и 'Прайс 2026')
        if 'Кофе Ароматизированный' in df_coffee.columns and 'Прайс 2026' in df_coffee.columns:
            for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный', 'Прайс 2026']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = r['Прайс 2026']

        # Читаем отчет Озон
        df_sales = pd.read_excel(ozon_p)
        
        # Если Озон вставил пустые строки сверху, ищем заголовок 'Название товара'
        if 'Название товара' not in df_sales.columns:
            for s in range(1, 12):
                df_tmp = pd.read_excel(ozon_p, skiprows=s)
                if 'Название товара' in df_tmp.columns:
                    df_sales = df_tmp
                    break

        results = []
        for _, row in df_sales.iterrows():
            name = str(row['Название товара'])
            payout = row.get('Итого к начислению', 0) # Сумма, которую Озон УЖЕ выплатил за вычетом комиссий
            sale_price = row.get('Цена реализации', 0) # Цена продажи клиенту

            # Пропускаем пустые строки или нулевые начисления
            if payout == 0 and sale_price == 0: continue

            # Ищем товар в прайсе по вхождению названия
            cost_1kg = None
            for p_name, p_val in prices.items():
                if p_name in name.lower():
                    cost_1kg = p_val
                    break
            
            # Считаем прибыль только если нашли закупку
            if cost_1kg:
                # ЛОГИКА ВЕСА: делим закупку на 2, если упаковка 0.5кг или 500г
                is_half = any(mark in name.lower() for mark in ['0.5', '500г', '500 г'])
                unit_cost = cost_1kg / 2 if is_half else cost_1kg
                
                # Налог 6% от цены продажи клиенту (УСН)
                tax = sale_price * 0.06
                
                # Чистая прибыль = Начисление - Себестоимость - Налог
                net_profit = payout - unit_cost - tax
                
                results.append({
                    'Дата': row.get('Дата начисления', '-'),
                    'Товар': name,
                    'Выплата Озон': payout,
                    'Себестоимость': unit_cost,
                    'Налог (6%)': tax,
                    'Чистая прибыль': net_profit
                })
        
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Произошла ошибка при обработке: {e}")
        return None

# --- ИНТЕРФЕЙС ---
res_df = load_data()

if res_df is not None and not res_df.empty:
    # Итоговые метрики
    total_profit = res_df['Чистая прибыль'].sum()
    total_rev = res_df['Выплата Озон'].sum()
    
    col1, col2 = st.columns(2)
    col1.metric("Итого чистая прибыль", f"{total_profit:,.2f} ₽")
    col2.metric("Всего пришло от Ozon (без комиссий)", f"{total_rev:,.2f} ₽")
    
    st.divider()
    
    # Таблица результатов
    st.subheader("Детализация по каждой позиции")
    st.dataframe(res_df.sort_values('Чистая прибыль', ascending=False), use_container_width=True)
else:
    st.warning("Проверь файлы в папке data. Если отчет не грузится, убедись, что названия колонок в Excel совпадают.")
