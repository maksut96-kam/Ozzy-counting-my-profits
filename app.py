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
    # Очистка: оставляем только цифры, точки и минус
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        # Чай - используем ваше название колонки 'Чай черный ароматизированный'
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        
        name_col_tea = 'Чай черный ароматизированный'
        # Пытаемся взять цену из '80' или 'Предоплата'
        price_col_tea = '80' if '80' in df_tea.columns else 'Предоплата'
        
        if name_col_tea in df_tea.columns:
            for _, r in df_tea.dropna(subset=[name_col_tea]).iterrows():
                prices[str(r[name_col_tea]).lower().strip()] = clean_num(r.get(price_col_tea))

        # Кофе
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (С защитой от битых символов)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        
        # Читаем файл, принудительно заменяя нечитаемые символы на "?"
        # Это лечит ошибку 'charmap' decode
        with open(path, 'r', encoding='cp1251', errors='replace') as f:
            df = pd.read_csv(f, sep=';', skiprows=1)
            
        df.columns = [str(c).strip() for c in df.columns]

        if 'Название товара' not in df.columns:
            st.error(f"Колонки не найдены. Доступны: {list(df.columns)}")
            return None, None

        # Группировка транзакций
        summary = df.groupby('Название товара').agg({
            'Сумма итого, руб.': lambda x: sum(clean_num(i) for i in x),
            'Цена продавца': lambda x: max(clean_num(i) for i in x),
            'Количество': lambda x: sum(clean_num(i) for i in x if clean_num(i) > 0)
        }).reset_index()

        results = []
        not_found = []

        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if 'nan' in name.lower() or not name or 'итого' in name.lower(): continue
            
            payout = row['Сумма итого, руб.']
            sale_price = row['Цена продавца']
            qty = row['Количество']

            # Поиск закупки (ищем короткое название из прайса в длинном названии Озона)
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
                not_found.append({'Товар из Ozon': name, 'Выплата': payout})

        return pd.DataFrame(results), pd.DataFrame(not_found)
    except Exception as e:
        st.error(f"Ошибка в отчете Ozon: {e}")
        return None, None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L: Анализ прибыли")
data, missing = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего от Ozon (Net)", f"{data['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог УСН (с продаж)", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")

    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)

if missing is not None and not missing.empty:
    with st.expander("⚠️ Товары без сопоставления цен"):
        st.write("Эти товары найдены в Ozon, но не найдены в прайсах:")
        st.table(missing)
