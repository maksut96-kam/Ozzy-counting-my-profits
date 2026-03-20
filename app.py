import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="Analytics Fix", layout="wide")
st.title("📊 P&L Аналитика: Проверка данных")

def load_data():
    try:
        # 1. Загрузка чая (Заголовки на 3-й строке, индекс 2)
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=2)
        
        # 2. Загрузка кофе (Заголовки на 2-й строке, индекс 1)
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_coffee = pd.read_excel(path_cof, sheet_name='Кофе', skiprows=1)
        
        # Создаем словарь цен
        prices = {}
        # Чай: Наименование и Предоплата
        if 'Наименование' in df_tea.columns:
            for _, r in df_tea.dropna(subset=['Наименование']).iterrows():
                val = r.get('Предоплата', 0)
                if pd.notna(val):
                    prices[str(r['Наименование']).lower().strip()] = float(val)

        # Кофе: Кофе Ароматизированный и Прайс 2026
        if 'Кофе Ароматизированный' in df_coffee.columns:
            for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный']).iterrows():
                val = r.get('Прайс 2026', 0)
                if pd.notna(val):
                    prices[str(r['Кофе Ароматизированный']).lower().strip()] = float(val)

        # 3. Загрузка отчета Озон
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Читаем без пропусков сначала
        df_sales = pd.read_excel(path_ozon)
        
        # Умный поиск заголовков Озона
        if 'Название товара' not in df_sales.columns:
            for s in range(1, 15):
                df_tmp = pd.read_excel(path_ozon, skiprows=s)
                if 'Название товара' in df_tmp.columns:
                    df_sales = df_tmp
                    break

        if 'Название товара' not in df_sales.columns:
            st.error("В отчете Озона не найдена колонка 'Название товара'!")
            return None

        results = []
        for _, row in df_sales.iterrows():
            name = str(row['Название товара'])
            payout = row.get('Итого к начислению', 0)
            sale_price = row.get('Цена реализации', 0)
            
            if pd.isna(payout) or (payout == 0 and sale_price == 0): continue

            # Поиск в прайсе
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                final_cost = cost_1kg / 2 if is_half else cost_1kg
                tax = sale_price * 0.06
                profit = payout - final_cost - tax
                
                results.append({
                    'Товар': name,
                    'Выплата Озон': payout,
                    'Закупка': final_cost,
                    'Налог': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Ошибка: {e}")
        return None

# Запуск
res = load_data()

if res is not None and not res.empty:
    st.success(f"Готово! Обработано строк: {len(res)}")
    st.metric("Общая прибыль", f"{res['Прибыль'].sum():,.2f} ₽")
    st.dataframe(res)
else:
    # Если всё равно пусто, выведем отладочную информацию
    st.info("Проверьте, что в папке 'data' лежат файлы именно с такими названиями.")
    if os.path.exists(DATA_FOLDER):
        st.write("Файлы в папке data:", os.listdir(DATA_FOLDER))
