import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Pro", layout="wide")

def clean_num(value):
    """Превращает любую строку с мусором (₽, пробелы, запятые) в чистое число float"""
    if pd.isna(value): return 0.0
    if isinstance(value, (int, float)): return float(value)
    
    # Удаляем символ рубля, неразрывные пробелы и обычные пробелы
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    # Оставляем только цифры, точку и минус
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    
    try:
        return float(cleaned)
    except:
        return 0.0

def load_data():
    prices = {}
    # 1. Загрузка прайсов (без изменений)
    try:
        df_tea = pd.read_excel(os.path.join(DATA_FOLDER, TEA_FILE), sheet_name='Чай', skiprows=2)
        df_tea.columns = [str(c).strip() for c in df_tea.columns]
        t_name, t_price = 'Чай черный ароматизированный', '80'
        for _, r in df_tea.dropna(subset=[t_name]).iterrows():
            prices[str(r[t_name]).lower().strip()] = clean_num(r.get(t_price))
            
        df_cof = pd.read_excel(os.path.join(DATA_FOLDER, COFFEE_FILE), sheet_name='Кофе', skiprows=1)
        df_cof.columns = [str(c).strip() for c in df_cof.columns]
        for _, r in df_cof.dropna(subset=['Кофе Ароматизированный']).iterrows():
            prices[str(r['Кофе Ароматизированный']).lower().strip()] = clean_num(r.get('Прайс 2026'))
    except Exception as e:
        st.error(f"Ошибка в прайсах: {e}")

    # 2. Обработка Ozon
    try:
        path = os.path.join(DATA_FOLDER, OZON_REPORT)
        df = pd.read_csv(path, sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Предварительно очищаем все числовые колонки
        df['Сумма итого, руб.'] = df['Сумма итого, руб.'].apply(clean_num)
        df['Цена продавца'] = df['Цена продавца'].apply(clean_num)
        df['Количество'] = df['Количество'].apply(clean_num)
        
        # Группируем по товару
        # Логика: Сумма итого — это чистый приход от Озона по всем транзакциям (доход - расход)
        # Цена продавца — берем среднее или макс, так как она одинаковая для всех строк одного заказа
        # Количество — берем макс в группе (это и есть реальное кол-во штук в заказе)
        summary = df.groupby('Название товара').agg({
            'Сумма итого, руб.': 'sum',
            'Цена продавца': 'max',
            'Количество': 'max'
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if not name or 'nan' in name.lower() or 'итого' in name.lower():
                continue
            
            payout_ozon = row['Сумма итого, руб.']
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
                is_half = any(m in name_lower for m in ['500 гр', '500г', '0.5'])
                total_cost = (cost_1kg / 2 if is_half else cost_1kg) * qty
                # Налог всегда с ГРЯЗНОЙ цены продажи
                tax = (sale_price * qty) * 0.06
                profit = payout_ozon - total_cost - tax
                
                results.append({
                    'Товар': name,
                    'Кол-во': qty,
                    'Чистый приход Ozon': payout_ozon,
                    'Себестоимость': total_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в анализе Ozon: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Итоговый P&L Анализ")
data = load_data()

if data is not None and not data.empty:
    # Итоговые карточки
    c1, c2, c3 = st.columns(3)
    c1.metric("Приход от Ozon", f"{data['Чистый приход Ozon'].sum():,.2f} ₽")
    c2.metric("Налог УСН", f"{data['Налог 6%'].sum():,.2f} ₽")
    c3.metric("ЧИСТАЯ ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    
    # Расчет ROI (Рентабельность вложений)
    data['ROI %'] = (data['Прибыль'] / data['Себестоимость'] * 100).replace([float('inf'), -float('inf')], 0)
    
    st.subheader("Детализация по товарам")
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.info("Данные загружаются или файлы не найдены.")
