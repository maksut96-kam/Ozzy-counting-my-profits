import streamlit as st
import pandas as pd
import os

# --- НАСТРОЙКИ ---
DATA_FOLDER = 'data' 
TEA_FILE = 'Прайс ЧАЙ 2026.xlsx'
COFFEE_FILE = 'Прайс закуп КОФЕ 2026.xls'
OZON_REPORT = 'Озон Отчет Начисления 01.01.2026-20.03.2026.csv'

st.set_page_config(page_title="Ozon P&L Logic Fix", layout="wide")

def clean_num(value):
    if pd.isna(value): return 0.0
    s = str(value).replace('₽', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    cleaned = "".join([c for c in s if c.isdigit() or c in '.-'])
    try: return float(cleaned)
    except: return 0.0

def load_data():
    # 1. Загрузка цен (оставляем без изменений, это работало)
    prices = {}
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

    # 2. Обработка Ozon по сложной логике
    try:
        df = pd.read_csv(os.path.join(DATA_FOLDER, OZON_REPORT), sep=';', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Очищаем суммы сразу во всем файле
        df['Чистая_Сумма'] = df['Сумма итого, руб.'].apply(clean_num)
        
        # Группируем по Названию товара
        # Сумма итого теперь — это РЕАЛЬНЫЙ чистый приход (Доходы минус Расходы Ozon)
        summary = df.groupby('Название товара').agg({
            'Чистая_Сумма': 'sum',      # Сумма всех транзакций (профит от Озона)
            'Цена продавца': 'max',      # Цена для расчета налога
            'Количество': 'max'          # Реальное кол-во (не сумма строк!)
        }).reset_index()

        results = []
        for _, row in summary.iterrows():
            name = str(row['Название товара'])
            if not name or 'итого' in name.lower(): continue
            
            payout_ozon = row['Чистая_Сумма']  # Сколько Озон реально перечислит за этот товар
            sale_price = row['Цена продавца']
            qty = row['Количество']

            # Ищем закупку
            cost_1kg = None
            for p_name, p_val in prices.items():
                if p_name in name.lower():
                    cost_1kg = p_val
                    break
            
            if cost_1kg:
                is_half = any(m in name.lower() for m in ['500 гр', '500г', '0.5'])
                total_cost = (cost_1kg / 2 if is_half else cost_1kg) * qty
                
                # Налог 6% берется с Грязной цены (Цена продавца * Кол-во)
                tax = (sale_price * qty) * 0.06
                
                # Итоговая прибыль: Чистый приход Озона - Себестоимость - Налог
                profit = payout_ozon - total_cost - tax
                
                results.append({
                    'Товар': name,
                    'Продано': qty,
                    'От Ozon (Чистыми)': payout_ozon,
                    'Себестоимость': total_cost,
                    'Налог 6%': tax,
                    'Прибыль': profit
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка в анализе файла: {e}")
        return None

# --- ВЫВОД ---
st.title("📊 Глубокий P&L Анализ (По транзакциям)")
data = load_data()

if data is not None and not data.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Чистый приход Ozon", f"{data['От Ozon (Чистыми)'].sum():,.2f} ₽")
    c2.metric("Общая себестоимость", f"{data['Себестоимость'].sum():,.2f} ₽")
    c3.metric("ИТОГО ПРИБЫЛЬ", f"{data['Прибыль'].sum():,.2f} ₽")
    
    # Добавим расчет маржи в %
    data['Маржа %'] = (data['Прибыль'] / data['От Ozon (Чистыми)']) * 100
    
    st.dataframe(data.sort_values('Прибыль', ascending=False), use_container_width=True)
else:
    st.warning("Не удалось собрать данные. Проверьте структуру файла.")
