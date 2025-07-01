#!/bin/bash

# Отримуємо поточну дату і час у форматі YYYY-MM-DD_HH-MM-SS
current_datetime=$(date +%Y-%m-%d_%H-%M-%S)

# Запускаємо Python-програму і перенаправляємо вивід у файл
python3 F_BB01.py > tests/output_${current_datetime}.txt