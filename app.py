import streamlit as st
import pandas as pd
import os

DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Stable", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    s = str(value).strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        # Чай (ищем колонку Наименование вручную)
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        
        # Если "Наименование" не найдено, выведем список всех колонок для отладки
        if 'Наименование' not in df_tea.columns:
            st.error(f"В прайсе чая нет колонки 'Наименование'. Доступны: {list(df_tea.columns)}")
        else:
            for _, r in df_tea.dropna(subset=['Наименование']).iterrows():
                prices[str(r['Наименование']).lower().strip()] = clean_num(r.get('Предоплата'))
        
        # Кофе
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (совместимый метод)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        # Убираем errors='replace', используем стандартный движок и кодировку cp1251
        try:
            df = pd.read_csv(path, sep=';', skiprows=1, encoding='cp1251')
        except:
            df = pd.read_csv(path, sep=';', skiprows=1, encoding='utf-8')
            
        df.columns = [str(c).strip() for c in df.columns]

        if 'Название товара' not in df.columns:
            st.error(f"В отчете Озон не найдена колонка 'Название товара'. Вижу только: {list(df.columns)}")
            return None, None

        # Группировка
        summary = df.groupby('Название товара').agg({
            'Сумма итого, руб.': 'sum', # В новых версиях можно просто sum
            'Цена продавца': 'max',
            'Количество': 'sum'
        }).reset_index()

        results = []
        not_found = []

        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if 'nan' in name.lower() or not name or 'итого' in name.lower(): continue
            
            payout = clean_num(row['Сумма итого, руб.'])
            sale_price = clean_num(row['Цена продавца'])
            qty = clean_num(row['Количество'])

            cost_1kg = None
            name_lower = name.lower()
            
            # Умный поиск: ищем название из прайса внутри названия Озона
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 гр'])
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * max(0, qty)
                tax = (sale_price * max(0, qty)) * 0.06
                results.append({
                    'Товар': name,
                    'Выплата': payout,
                    'Закупка': unit_cost,
                    'Налог': tax,
                    'Прибыль': payout - unit_cost - tax
                })
            else:
                not_found.append({'Товар из Ozon': name, 'Сумма': payout})

        return pd.DataFrame(results), pd.DataFrame(not_found)
    except Exception as e:
        st.error(f"Ошибка Ozon: {e}")
        return None, None

st.title("📊 Итоговый P&L")
data, missing = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{data['Выплата'].sum():,.2f} ₽")
    c2.metric("Налог 6%", f"{data['Налог'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)

if missing is not None and not missing.empty:
    with st.expander("⚠️ Товары без цены закупки"):
        st.table(missing)
