import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.xlsx'

st.set_page_config(page_title="P&L Ultimate Fix", layout="wide")

def clean_num(value):
    try:
        if pd.isna(value) or str(value).strip().lower() == 'нет': return 0.0
        # Убираем пробелы и валюту, если они есть в строке
        s = str(value).replace('₽', '').replace(' ', '').replace(',', '.')
        return float(s)
    except: return 0.0

def get_col_by_keyword(df, keywords):
    for col in df.columns:
        col_s = str(col).lower().strip()
        if any(k.lower() in col_s for k in keywords):
            return col
    return None

def load_ozon_universal(path):
    """Пытается найти таблицу с данными Озона на любом листе и любой строке"""
    try:
        xl = pd.ExcelFile(path)
        for sheet in xl.sheet_names:
            # Пробуем разную глубину пропуска строк
            for s in range(0, 30):
                df = pd.read_excel(path, sheet_name=sheet, skiprows=s)
                if len(df.columns) < 3: continue
                
                df.columns = [str(c).strip() for c in df.columns]
                
                # Ключевой признак отчета Озона - наличие названия товара и денег
                has_name = get_col_by_keyword(df, ['Название товара', 'Наименование товара'])
                has_money = get_col_by_keyword(df, ['Итого к начислению', 'К начислению'])
                
                if has_name and has_money:
                    return df, sheet
        return None, None
    except: return None, None

def load_data():
    try:
        prices = {}
        # 1. ЧАЙ (Загрузка как раньше, но с проверкой)
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        c_n = get_col_by_keyword(df_tea, ['Наименование'])
        c_p = get_col_by_keyword(df_tea, ['Предоплата'])
        if c_n and c_p:
            for _, r in df_tea.dropna(subset=[c_n]).iterrows():
                prices[str(r[c_n]).lower().strip()] = clean_num(r[c_p])

        # 2. КОФЕ
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_cof = pd.read_excel(path_cof, sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        c_n = get_col_by_keyword(df_cof, ['Кофе Ароматизированный'])
        c_p = get_col_by_keyword(df_cof, ['Прайс 2026'])
        if c_n and c_p:
            for _, r in df_cof.dropna(subset=[c_n]).iterrows():
                prices[str(r[c_n]).lower().strip()] = clean_num(r[c_p])

        # 3. OZON (Универсальный поиск)
        df_sales, sheet_found = load_ozon_universal(os.path.join(DATA_FOLDER, OZON_REPORT))

        if df_sales is None:
            st.error("❌ Не удалось найти таблицу в файле Озон. Проверьте, что в файле есть колонки 'Название товара' и 'Итого к начислению'.")
            return None

        o_name = get_col_by_keyword(df_sales, ['Название товара', 'Наименование товара'])
        o_payout = get_col_by_keyword(df_sales, ['Итого к начислению', 'К начислению'])
        o_sale = get_col_by_keyword(df_sales, ['Цена реализации', 'Цена продажи'])

        results = []
        for _, row in df_sales.iterrows():
            name = str(row.get(o_name, ''))
            if not name or name == 'nan' or 'итого' in name.lower(): continue

            payout = clean_num(row.get(o_payout, 0))
            sale_price = clean_num(row.get(o_sale, 0))
            
            # Сопоставление
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg is not None:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
                unit_cost = cost_1kg / 2 if is_half else cost_1kg
                tax = sale_price * 0.06
                profit = payout - unit_cost - tax
                
                results.append({
                    'Товар': name,
                    'Выплата Озон': payout,
                    'Закупка': unit_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 P&L Аналитика: Tea & Coffee")
res = load_data()

if res is not None and not res.empty:
    st.success(f"Найдено совпадений: {len(res)}")
    
    # Метрики
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{res['Выплата Озон'].sum():,.2f} ₽")
    c2.metric("Налоги", f"{res['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{res['Прибыль'].sum():,.2f} ₽")

    # Итоги в таблицу
    totals = pd.DataFrame([{'Товар': '💰 ИТОГО', 'Выплата Озон': res['Выплата Озон'].sum(), 
                            'Закупка': res['Закупка'].sum(), 'Налог 6%': res['Налог 6%'].sum(), 
                            'Прибыль': res['Прибыль'].sum()}])
    st.dataframe(pd.concat([res, totals], ignore_index=True), use_container_width=True)
else:
    st.info("Ожидание данных...")
