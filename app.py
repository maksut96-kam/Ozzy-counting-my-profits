import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
# ВНИМАНИЕ: Проверь, чтобы имя файла в папке data совпадало с этим:
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    # Удаляем символ рубля, пробелы и меняем запятую на точку
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        t_name = 'Чай черный ароматизированный'
        t_price = '80' if '80' in df_tea.columns else 'Предоплата'
        
        for _, r in df_tea.dropna(subset=[t_name]).iterrows():
            prices[str(r[t_name]).lower().strip()] = clean_num(r.get(t_price))

        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА НОВОГО ОТЧЕТА OZON
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Читаем новый файл (он в utf-8 и без лишних строк сверху)
        df = pd.read_csv(path, sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]

        # Группировка всех транзакций по названию
        summary = df.groupby('Название товара').agg({
            'Сумма итого, руб.': lambda x: sum(clean_num(i) for i in x),
            'Цена продавца': lambda x: max(clean_num(i) for i in x),
            'Количество': lambda x: max(clean_num(i) for i in x)
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if 'nan' in name.lower() or not name: continue
            
            payout = row['Сумма итого, руб.']
            sale_price = row['Цена продавца']
            qty = row['Количество']

            # Сопоставление с закупкой
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
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в отчете Ozon: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L (Обновленный файл)")
res = load_data()

if res is not None and not res.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Выплата от Ozon", f"{res['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог (с продаж)", f"{res['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{res['Прибыль'].sum():,.2f} ₽")
    
    st.dataframe(res.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Проверьте, что новый файл лежит в папке 'data' под именем: " + OZON_REPORT)
