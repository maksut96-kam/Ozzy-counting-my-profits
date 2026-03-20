import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    # Очистка от валюты и мусора
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ (как раньше, это работало)
    try:
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        # Используем ваше подтвержденное название колонки
        t_name = 'Чай черный ароматизированный'
        t_price = '80' if '80' in df_tea.columns else 'Предоплата'
        if t_name in df_tea.columns:
            for _, r in df_tea.dropna(subset=[t_name]).iterrows():
                prices[str(r[t_name]).lower().strip()] = clean_num(r.get(t_price))

        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (Метод по индексам столбцов)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Читаем как есть, игнорируя ошибки кодировки заголовков
        df = pd.read_csv(path, sep=';', skiprows=1, encoding='cp1251', errors='replace')
        
        # ПРИНУДИТЕЛЬНОЕ ПЕРЕИМЕНОВАНИЕ ПО НОМЕРАМ (ИНДЕКСАМ)
        # В вашем файле: 6-Название, 7-Кол-во, 8-Цена продавца, 15-Сумма итого
        new_cols = list(df.columns)
        new_cols[6] = 'REAL_NAME'
        new_cols[7] = 'REAL_QTY'
        new_cols[8] = 'REAL_SALE'
        new_cols[15] = 'REAL_PAYOUT'
        df.columns = new_cols

        # Группировка
        summary = df.groupby('REAL_NAME').agg({
            'REAL_PAYOUT': lambda x: sum(clean_num(i) for i in x),
            'REAL_SALE': lambda x: max(clean_num(i) for i in x),
            'REAL_QTY': lambda x: sum(clean_num(i) for i in x if clean_num(i) > 0)
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row['REAL_NAME'])
            if 'nan' in name.lower() or not name: continue
            
            payout = row['REAL_PAYOUT']
            sale_price = row['REAL_SALE']
            qty = row['REAL_QTY']

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
                    'Выплата': payout,
                    'Закупка': unit_cost,
                    'Налог': tax,
                    'Прибыль': payout - unit_cost - tax
                })
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка Ozon: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Финансовый результат: Ozon P&L")
res = load_data()

if res is not None and not res.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Выплата Ozon", f"{res['Выплата'].sum():,.2f} ₽")
    c2.metric("Налог УСН", f"{res['Налог'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{res['Прибыль'].sum():,.2f} ₽")
    st.dataframe(res.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Данные не найдены. Проверьте файлы в папке data.")
