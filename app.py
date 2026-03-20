import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="Tea&Coffee P&L", layout="wide")
st.title("📊 Итоговая аналитика прибыли")

def clean_price(value):
    """Превращает значение в число, если это возможно, иначе возвращает None"""
    try:
        return float(value)
    except:
        return None

def load_data():
    try:
        # 1. Загрузка чая
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=2)
        
        # 2. Загрузка кофе
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_coffee = pd.read_excel(path_cof, sheet_name='Кофе', skiprows=1)
        
        prices = {}
        
        # Обработка Чая
        if 'Наименование' in df_tea.columns:
            for _, r in df_tea.dropna(subset=['Наименование']).iterrows():
                p = clean_price(r.get('Предоплата'))
                if p is not None:
                    prices[str(r['Наименование']).lower().strip()] = p

        # Обработка Кофе
        if 'Кофе Ароматизированный' in df_coffee.columns:
            for _, r in df_coffee.dropna(subset=['Кофе Ароматизированный']).iterrows():
                p = clean_price(r.get('Прайс 2026'))
                if p is not None:
                    prices[str(r['Кофе Ароматизированный']).lower().strip()] = p

        # 3. Загрузка отчета Озон
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        df_sales = pd.read_excel(path_ozon)
        
        # Поиск заголовков в отчете Озон
        if 'Название товара' not in df_sales.columns:
            for s in range(1, 15):
                df_tmp = pd.read_excel(path_ozon, skiprows=s)
                if 'Название товара' in df_tmp.columns:
                    df_sales = df_tmp
                    break

        results = []
        for _, row in df_sales.iterrows():
            name = str(row.get('Название товара', ''))
            payout = clean_price(row.get('Итого к начислению', 0))
            sale_price = clean_price(row.get('Цена реализации', 0))
            
            if not name or payout is None: continue

            # Поиск соответствия в прайсе
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                # Вес: 0.5кг или 500г
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                final_cost = cost_1kg / 2 if is_half else cost_1kg
                
                tax = (sale_price or 0) * 0.06
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
        st.error(f"Ошибка при чтении файлов: {e}")
        return None

# Вывод
res = load_data()

if res is not None and not res.empty:
    st.success(f"Данные успешно сопоставлены! Найдено позиций: {len(res)}")
    
    col1, col2 = st.columns(2)
    col1.metric("Общая прибыль", f"{res['Чистая прибыль'].sum():,.2f} ₽")
    col2.metric("Средняя прибыль на ед.", f"{res['Чистая прибыль'].mean():,.2f} ₽")
    
    st.dataframe(res.sort_values('Чистая прибыль', ascending=False), use_container_width=True)
else:
    st.warning("Не удалось найти совпадения товаров из отчета Озона в ваших прайсах.")
    st.info("Проверьте, что названия товаров на Озоне содержат те же слова, что и в колонках 'Наименование' или 'Кофе Ароматизированный' в ваших прайсах.")
