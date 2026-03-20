import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final Fix", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ (Чай и Кофе)
    try:
        # Чай
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        
        # Используем ваше название колонки 'Чай черный ароматизированный'
        tea_name_col = 'Чай черный ароматизированный'
        tea_price_col = '80' if '80' in df_tea.columns else 'Предоплата'
        
        if tea_name_col in df_tea.columns:
            for _, r in df_tea.dropna(subset=[tea_name_col]).iterrows():
                prices[str(r[tea_name_col]).lower().strip()] = clean_num(r.get(tea_price_col))

        # Кофе
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (CSV в кодировке IBM866)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        
        # Читаем в кодировке ibm866, чтобы победить "краказябры"
        df = pd.read_csv(path, sep=';', skiprows=1, encoding='ibm866')
        df.columns = [str(c).strip() for c in df.columns]

        # Названия колонок из вашего лога (авто-детект)
        col_name = 'Ќ\xa0§ў\xa0\xadЁҐ в®ў\xa0а' # Название товара
        col_payout = '‘г¬¬\xa0 Ёв®Ј®, агЎ.' # Сумма итого
        col_sale = '–Ґ\xad\xa0 Їа®¤\xa0ўж' # Цена продавца
        col_qty = 'Љ®«ЁзҐбвў®' # Количество

        # Группируем все строки по товару
        summary = df.groupby(col_name).agg({
            col_payout: lambda x: sum(clean_num(i) for i in x),
            col_sale: lambda x: max(clean_num(i) for i in x),
            col_qty: lambda x: sum(clean_num(i) for i in x if clean_num(i) > 0)
        }).reset_index()

        results = []
        not_found = []

        for _, row in summary.iterrows():
            name = str(row[col_name])
            # Условие пропуска пустых строк или итогов
            if 'nan' in name.lower() or not name or 'Ёв®Ј®' in name: continue
            
            payout = row[col_payout]
            sale_price = row[col_sale]
            qty = row[col_qty]

            # Поиск в прайсах (по частичному совпадению)
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 гр'])
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * qty
                tax = (sale_price * qty) * 0.06
                
                results.append({
                    'Товар': name,
                    'Кол-во': qty,
                    'Выплата Ozon': payout,
                    'Закупка': unit_cost,
                    'Налог 6%': tax,
                    'Прибыль': payout - unit_cost - tax
                })
            else:
                not_found.append({'Товар из Ozon': name, 'Сумма': payout})

        return pd.DataFrame(results), pd.DataFrame(not_found)
    except Exception as e:
        st.error(f"Ошибка Ozon: {e}")
        return None, None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговая аналитика прибыли")
data, missing = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{data['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог (6%)", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")

    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)

if missing is not None and not missing.empty:
    with st.expander("⚠️ Товары, не найденные в прайсах"):
        st.write("Для этих товаров из Ozon не удалось найти цену закупки:")
        st.table(missing)
