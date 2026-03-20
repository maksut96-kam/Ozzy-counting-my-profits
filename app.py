import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="P&L Analytics Final", layout="wide")

def clean_num(value):
    try:
        if pd.isna(value): return 0.0
        return float(value)
    except: return 0.0

def find_sheet_data(path, sheet, target_col):
    """Ищет, на какой строке находится нужная колонка, и возвращает чистый DataFrame"""
    for s in range(0, 10):
        try:
            df = pd.read_excel(path, sheet_name=sheet, skiprows=s)
            df.columns = [str(c).strip() for c in df.columns]
            if any(target_col.lower() in str(c).lower() for c in df.columns):
                return df
        except: continue
    return None

def load_data():
    try:
        prices = {}
        
        # 1. Загрузка ЧАЯ
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = find_sheet_data(path_tea, 'Чай', 'Наименование')
        if df_tea is not None:
            # Находим реальное имя колонки (с учетом регистра/пробелов)
            name_col = [c for c in df_tea.columns if 'наименование' in c.lower()][0]
            price_col = [c for c in df_tea.columns if 'предоплата' in c.lower()][0]
            for _, r in df_tea.dropna(subset=[name_col]).iterrows():
                prices[str(r[name_col]).lower().strip()] = clean_num(r.get(price_col))

        # 2. Загрузка КОФЕ
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_cof = find_sheet_data(path_cof, 'Кофе', 'Кофе Ароматизированный')
        if df_cof is not None:
            name_col = [c for c in df_cof.columns if 'кофе ароматизированный' in c.lower()][0]
            price_col = [c for c in df_cof.columns if 'прайс 2026' in c.lower()][0]
            for _, r in df_cof.dropna(subset=[name_col]).iterrows():
                prices[str(r[name_col]).lower().strip()] = clean_num(r.get(price_col))

        # 3. Загрузка OZON
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        df_sales = find_sheet_data(path_ozon, 0, 'Название товара') # берем первый лист

        if df_sales is None:
            st.error("Не удалось найти колонку 'Название товара' в отчете Ozon")
            return None

        results = []
        # Определяем имена колонок Ozon
        ozon_name_col = [c for c in df_sales.columns if 'название товара' in c.lower()][0]
        ozon_payout_col = [c for c in df_sales.columns if 'итого к начислению' in c.lower()][0]
        ozon_sale_col = [c for c in df_sales.columns if 'цена реализации' in c.lower()][0]

        for _, row in df_sales.iterrows():
            name = str(row.get(ozon_name_col, ''))
            if not name or name == 'nan' or 'итого' in name.lower(): continue

            payout = clean_num(row.get(ozon_payout_col, 0))
            sale_price = clean_num(row.get(ozon_sale_col, 0))
            
            # Поиск соответствия
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
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Критическая ошибка: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговая аналитика прибыли")
res = load_data()

if res is not None and not res.empty:
    # Общие итоги для метрик
    total_p = res['Выплата Озон'].sum()
    total_t = res['Налог 6%'].sum()
    total_net = res['Прибыль'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{total_p:,.2f} ₽")
    c2.metric("Налоги", f"{total_t:,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{total_net:,.2f} ₽")

    # Итоговая строка для таблицы
    totals = pd.DataFrame([{'Товар': '💰 ИТОГО', 'Выплата Озон': total_p, 'Себестоимость': res['Себестоимость'].sum(), 'Налог 6%': total_t, 'Прибыль': total_net}])
    final_tab = pd.concat([res, totals], ignore_index=True)

    st.dataframe(final_tab, use_container_width=True)
else:
    st.warning("Данные не найдены. Проверьте названия листов и колонок в файлах.")
