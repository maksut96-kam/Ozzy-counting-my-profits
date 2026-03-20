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
        if pd.isna(value) or value == 'нет': return 0.0
        return float(value)
    except: return 0.0

def get_col_by_keyword(df, keywords):
    """Ищет колонку, в названии которой есть хотя бы одно из ключевых слов"""
    for col in df.columns:
        if any(k.lower() in str(col).lower() for k in keywords):
            return col
    return None

def load_sheet_safe(path, sheet_name=0):
    """Пробует загрузить лист, перебирая варианты пропуска строк"""
    for s in range(0, 15):
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, skiprows=s)
            # Убираем пустые колонки и чистим имена
            df.columns = [str(c).strip() for c in df.columns]
            # Если в таблице есть хоть какие-то данные
            if len(df.columns) > 2:
                return df
        except: continue
    return None

def load_data():
    try:
        prices = {}
        
        # 1. ЗАГРУЗКА ЧАЯ
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = load_sheet_safe(path_tea, 'Чай')
        if df_tea is not None:
            c_name = get_col_by_keyword(df_tea, ['Наименование', 'Товар', 'Название'])
            c_price = get_col_by_keyword(df_tea, ['Предоплата', 'Цена', 'Закуп'])
            if c_name and c_price:
                for _, r in df_tea.dropna(subset=[c_name]).iterrows():
                    prices[str(r[c_name]).lower().strip()] = clean_num(r[c_price])

        # 2. ЗАГРУЗКА КОФЕ
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_cof = load_sheet_safe(path_cof, 'Кофе')
        if df_cof is not None:
            c_name = get_col_by_keyword(df_cof, ['Кофе Ароматизированный', 'Наименование', 'Товар'])
            c_price = get_col_by_keyword(df_cof, ['Прайс 2026', 'Цена', 'Закуп'])
            if c_name and c_price:
                for _, r in df_cof.dropna(subset=[c_name]).iterrows():
                    prices[str(r[c_name]).lower().strip()] = clean_num(r[c_price])

        # 3. ЗАГРУЗКА OZON
        path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
        df_sales = load_sheet_safe(path_ozon, 0) # Первый лист

        if df_sales is None: return None

        # Ищем колонки Озона
        o_name = get_col_by_keyword(df_sales, ['Название товара'])
        o_payout = get_col_by_keyword(df_sales, ['Итого к начислению'])
        o_sale = get_col_by_keyword(df_sales, ['Цена реализации'])

        if not all([o_name, o_payout, o_sale]):
            st.error(f"В Озоне не найдены колонки. Нашел: Название={o_name}, Выплата={o_payout}, Продажа={o_sale}")
            return None

        results = []
        for _, row in df_sales.iterrows():
            name = str(row.get(o_name, ''))
            if not name or name == 'nan' or 'итого' in name.lower(): continue

            payout = clean_num(row.get(o_payout, 0))
            sale_price = clean_num(row.get(o_sale, 0))
            
            # Поиск в прайсе
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
        st.error(f"Ошибка в логике: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговая аналитика прибыли")
res = load_data()

if res is not None and not res.empty:
    # Метрики
    total_p = res['Выплата Озон'].sum()
    total_t = res['Налог 6%'].sum()
    total_net = res['Прибыль'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{total_p:,.2f} ₽")
    c2.metric("Налоги", f"{total_t:,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{total_net:,.2f} ₽")

    # Итоговая строка
    totals = pd.DataFrame([{
        'Товар': '💰 ИТОГО', 
        'Выплата Озон': total_p, 
        'Себестоимость': res['Себестоимость'].sum(), 
        'Налог 6%': total_t, 
        'Прибыль': total_net
    }])
    final_tab = pd.concat([res, totals], ignore_index=True)

    st.dataframe(final_tab, use_container_width=True)
else:
    st.warning("Данные не найдены или не сопоставлены. Проверьте файлы в папке /data")
