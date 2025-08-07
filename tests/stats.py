import csv
from datetime import datetime
import os
import re

# Назва файлу CSV
CSV_FILE = "trading_data.csv"

# Заголовки для CSV
HEADERS = ["Дата_Час", "Процент", "Фандинг", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер"]

# Перевірка, чи файл CSV уже існує, якщо ні — створити з заголовками
def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)

# Отримання поточної дати та часу у форматі РРРР-ММ-ДД ГГ:ХХ
def get_current_date_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# Обробка введених даних
def process_input(data):
    # Видаляємо зайві пробіли та символ $
    data = re.sub(r'\s*\$\s*', ' ', data)  # Замінюємо $ на пробіл
    # Розбиваємо рядок за пробілами, враховуючи, що значення можуть містити коми
    values = [v.strip() for v in re.split(r'\s+', data.strip()) if v.strip()]
    if len(values) != 8:
        print(f"Помилка: Введено {len(values)} значень. Очікується 8 значень: {values}")
        return None
    return values

# Запис даних у CSV
def write_to_csv(values):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Додаємо поточну дату та час як перший стовпець
        row = [get_current_date_time()] + values
        writer.writerow(row)

def main():
    # Ініціалізація CSV-файлу
    initialize_csv()
    
    print("Введіть дані у форматі: Процент Фандинг Прибиль Доход Комисия Обєм В-сделке Тикер")
    print("Приклад: 2,43% -2,77 $ 0,39 $ 3,37 $ 0,21 $ 137 $ 11с MYXUSDT")
    
    # Запит даних у користувача
    user_input = input("Введіть дані: ")
    
    # Обробка введених даних
    values = process_input(user_input)
    if values:
        # Запис у CSV
        write_to_csv(values)
        print(f"Дані успішно записано до {CSV_FILE}")

if __name__ == "__main__":
    main()