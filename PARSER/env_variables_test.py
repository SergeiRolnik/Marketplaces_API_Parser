import os

print('Переменные окружения')
for key, value in os.environ.items():
    print(key, value)
