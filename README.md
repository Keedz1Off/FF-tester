# FF Tester — инструкция для пользователей

## 1. Скачать проект

### Вариант A: через ZIP
На GitHub нажмите:

Code → Download ZIP

Распакуйте архив и откройте папку проекта.

### Вариант B: через Git
```bash
git clone https://github.com/Keedz1Off/ff-tester.git
cd ff-tester
2. Установить Python

Если Python не установлен, скачайте и установите его с официального сайта.

Во время установки обязательно включите:
Add Python to PATH

3. Установить зависимости

Откройте терминал в папке проекта и выполните:

pip install -r requirements.txt
4. Запустить backend

В терминале выполните:

python server.py

Если всё нормально, появится что-то вроде:

Running on http://127.0.0.1:5000
5. Запустить frontend

Откройте второе окно терминала в этой же папке и выполните:

python -m http.server 8000

После этого откройте в браузере:

http://localhost:8000
6. Как пользоваться
В поле "Адрес" укажите:
http://127.0.0.1:5000
Выберите нужный path
Настройте:
Users
Spawn
Time
Нажмите RUN
Следите за графиками и метриками
7. Важно

Не открывайте index.html напрямую через file://

То есть так делать НЕ надо:

file:///...

Иначе сайт может показать ошибку:

Failed to fetch
8. Примеры настроек
Лёгкий тест
Users: 50
Spawn: 5
Time: 30
Средний тест
Users: 200
Spawn: 10
Time: 60
Сильный тест
Users: 700
Spawn: 20
Time: 90
9. Частые ошибки
Failed to fetch

Причина:
frontend открыт неправильно или backend не запущен

Решение:

запустить python server.py
запустить python -m http.server 8000
открыть http://localhost:8000
ModuleNotFoundError

Причина:
не установлены зависимости

Решение:

pip install -r requirements.txt
locust not found

Причина:
Locust не установлен

Решение:

pip install locust
10. Проверка backend

Если хотите проверить, что backend реально работает, откройте:

http://127.0.0.1:5000/health

Если всё нормально, вы увидите JSON-ответ.

11. Как устроено
server.py — backend на Flask
index.html — интерфейс
locustfile.py — сценарий нагрузки
Locust — выполняет нагрузочное тестирование
12. Коротко

Запуск в двух командах:

python server.py

и во втором окне:

python -m http.server 8000

Потом открыть:

http://localhost:8000
