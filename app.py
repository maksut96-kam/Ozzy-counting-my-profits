import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет по начислениям_01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Final Recovery", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    # Очистка от мусора: оставляем цифры, точку, запятую и минус
    s = str(value).strip().replace('\xa0', '').replace(' ', '')
    # Заменяем запятую на точку для расчетов
    s = s.replace(',', '.')
    # Убираем все лишние знаки, кроме основных для числа
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def get_col(df, keys):
    for c in df.columns:
        if any(k.lower() in str(c).lower().strip() for k in keys):
            return c
    return None

def load_ozon_csv_ultra(path):
    """Метод 'грубой силы' для чтения CSV с любыми ошибками кодировки"""
    for enc in ['utf-8', 'cp1251', 'windows-1251', 'latin1', 'iso-8859-1']:
        try:
            # Читаем, заменяя нечитаемые символы на знаки вопроса
            df = pd.read_csv(path, sep=';', skiprows=1, encoding=enc, on_bad_lines='skip', engine='python')
            if 'Название товара' in str(df.columns) or 'Сумма итого' in str(df.columns):
                return df
        except:
            continue
    return None

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        # Чай
        p_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = pd.read_excel(p_tea, sheet_name='Чай', skiprows=2)
        c_n_tea = get_col(df_tea, ['Наименование'])
        c_p_tea = get_col(df_tea, ['Предоплата'])
        if c_n_tea and c_p_tea:
            for _, r in df_tea.dropna(subset=[c_n_tea]).iterrows():
                prices[str(r[c_n_tea]).lower().strip()] = clean_num(r[c_p_tea])
        
        # Кофе
        p_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_cof = pd.read_excel(p_cof, sheet_name='Кофе', skiprows=1)
        c_n_cof = get_col(df_cof, ['Кофе Ароматизированный'])
        c_p_cof = get_col(df_cof, ['Прайс 2026'])
        if c_n_cof and c_p_cof:
            for _, r in df_cof.dropna(subset=[c_n_cof]).iterrows():
                prices[str(r[c_n_cof]).lower().strip()] = clean_num(r[c_p_cof])
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА И ОБРАБОТКА OZON
    path_ozon = os.path.join(DATA_FOLDER, OZON_REPORT)
    df_ozon = load_ozon_csv_ultra(path_ozon)
    
    if df_ozon is None:
        return None

    # Очистка имен колонок от пробелов и мусора
    df_ozon.columns = [str(c).strip() for c in df_ozon.columns]
    
    col_name = get_col(df_ozon, ['Название товара'])
    col_payout = get_col(df_ozon, ['Сумма итого'])
    col_sale = get_col(df_ozon, ['Цена продавца'])
    col_qty = get_col(df_ozon, ['Количество'])

    # Группировка всех транзакций по названию товара
    # Это важно, так как на 1 товар в CSV по 4-5 строк (логистика, комиссия и т.д.)
    summary = df_ozon.groupby(col_name).agg({
        col_payout: lambda x: sum(clean_num(i) for i in x),
        col_sale: lambda x: max(clean_num(i) for i in x),
        col_qty: lambda x: max(clean_num(i) for i in x) # Берем макс. кол-во (обычно 1)
    }).reset_index()

    results = []
    for _, row in summary.iterrows():
        name = str(row[col_name])
        if 'nan' in name.lower() or not name or 'итого' in name.lower(): continue
        
        payout = row[col_payout]
        sale_price = row[col_sale]
        qty = row[col_qty]

        # Поиск закупки
        cost_1kg = None
        name_lower = name.lower()
        for p_name, p_val in prices.items():
            if p_name in name_lower:
                cost_1kg = p_val
                break
        
        if cost_1kg:
            is_half = any(m in name_lower for m in ['0.5', '500г', '500 г'])
            unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * qty
            tax = (sale_price * qty) * 0.06
            profit = payout - unit_cost - tax
            
            results.append({
                'Товар': name,
                'Кол-во': qty,
                'Выплата Ozon': payout,
                'Закупка': unit_cost,
                'Налог 6%': tax,
                'Прибыль': profit
            })

    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС ---
st.title("📊 Финансовый результат Ozon (Транзакции)")

data = load_data()

if data is not None and not data.empty:
    # Метрики
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход (после комиссий)", f"{data['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог УСН (6%)", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")

    # Основная таблица
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.warning("⚠️ Не удалось сопоставить данные. Проверьте, что названия товаров в Прайсах и в Ozon совпадают хотя бы частично.")
