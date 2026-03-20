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
    # Очистка: оставляем цифры, точку и минус
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    prices = {}
    
    # 1. ЗАГРУЗКА ПРАЙСОВ
    try:
        # Чай
        path_tea = os.path.join(DATA_FOLDER, TEA_FILE)
        df_tea = pd.read_excel(path_tea, sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        
        t_name = 'Чай черный ароматизированный'
        # Берем цену из колонки '80' или 'Предоплата'
        t_price = '80' if '80' in df_tea.columns else 'Предоплата'
        
        if t_name in df_tea.columns:
            for _, r in df_tea.dropna(subset=[t_name]).iterrows():
                prices[str(r[t_name]).lower().strip()] = clean_num(r.get(t_price))

        # Кофе
        path_cof = os.path.join(DATA_FOLDER, COFFEE_FILE)
        df_cof = pd.read_excel(path_cof, sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        if 'Кофе Ароматизированный' in df_cof.columns:
            for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
                prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. ЗАГРУЗКА OZON (Упрощенный метод)
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        
        # Читаем CSV без сложных аргументов, чтобы избежать ошибок версий
        # Используем cp1251 (стандарт Excel в РФ)
        df = pd.read_csv(path, sep=';', skiprows=1, encoding='cp1251')
        
        # Очищаем названия колонок от лишних пробелов
        df.columns = [str(c).strip() for c in df.columns]

        # Проверяем наличие ключевых колонок
        target_name = 'Название товара'
        target_payout = 'Сумма итого, руб.'
        target_sale = 'Цена продавца'
        target_qty = 'Количество'

        if target_name not in df.columns:
            st.error(f"Колонка '{target_name}' не найдена. Доступны: {list(df.columns)}")
            return None

        # Группировка данных по товару
        summary = df.groupby(target_name).agg({
            target_payout: 'sum',
            target_sale: 'max',
            target_qty: 'sum'
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row[target_name])
            if 'nan' in name.lower() or not name or 'итого' in name.lower():
                continue
            
            # Чистим данные внутри сгруппированных строк
            payout = clean_num(row[target_payout])
            sale_price = clean_num(row[target_sale])
            qty = clean_num(row[target_qty])

            # Поиск закупки
            cost_1kg = None
            name_lower = name.lower()
            for p_name, p_val in prices.items():
                if p_name in name_lower:
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                # Проверка на 500 гр
                is_half = any(m in name_lower for m in ['0.5', '500г', '500 гр'])
                # Считаем налог с цены продажи, а закупку с кол-ва
                # В отчете по начислениям количество для услуг может быть 1, 
                # поэтому берем максимум, чтобы не множить себестоимость на логистику
                actual_qty = clean_num(df[df[target_name] == name][target_qty].max())
                
                unit_cost = (cost_1kg / 2 if is_half else cost_1kg) * actual_qty
                tax = (sale_price * actual_qty) * 0.06
                
                results.append({
                    'Товар': name,
                    'Кол-во': actual_qty,
                    'Выплата Ozon': payout,
                    'Закупка': unit_cost,
                    'Налог 6%': tax,
                    'Прибыль': payout - unit_cost - tax
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка Ozon: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L: Ozon")
res = load_data()

if res is not None and not res.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход (после комиссий)", f"{res['Выплата Ozon'].sum():,.2f} ₽")
    c2.metric("Налог УСН (с продаж)", f"{res['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{res['Прибыль'].sum():,.2f} ₽")
    
    st.dataframe(res.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Ожидание данных...")
