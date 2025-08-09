from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import random
import json
import csv  # Добавляем модуль csv
import threading  # Добавляем модуль threading
import webbrowser  # Добавляем модуль webbrowser

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this!

NUM_QUESTIONS = 5
DATABASE_PATH = 'questions_with_topics.db'
PASSING_PERCENTAGE = 80 # Добавляем порог прохождения теста
RESULTS_FILE = 'results.csv'  # Добавляем имя файла для сохранения результатов

def get_questions_from_db(count, topic):
    """
    Получает вопросы из базы данных и возвращает их в виде списка.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Учитываем topic в запросе
    cursor.execute("SELECT id FROM questions WHERE topic = ?", (topic,))
    all_ids = [row[0] for row in cursor.fetchall()]

    # Проверяем, что количество запрашиваемых вопросов не превышает доступное
    if count > len(all_ids):
        count = len(all_ids)
        print(f"Предупреждение: Доступно только {count} вопросов по теме '{topic}'. Будет задано {count} вопросов.")

    random.shuffle(all_ids) # Перемешиваем список всех ID
    random_question_ids = random.sample(all_ids, count) # Берем случайные id из перемешанного списка

    conn.close()
    return random_question_ids  # Возвращаем список id

def get_question_data(question_id):
    """
    Извлекает данные вопроса из базы данных по его ID.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT question, options, correct_answers FROM questions WHERE id = ?", (question_id,))
    question_data = cursor.fetchone()
    conn.close()

    if question_data:
        question, options_json, correct_answers_json = question_data
        options = json.loads(options_json)
        correct_answers = json.loads(correct_answers_json) #ИСПРАВЛЕНО: десериализуем поле correct_answers
        return {
            'question': question,
            'options': options,
            'correct_answers': correct_answers,
            'id': question_id
        }
    else:
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        fio = request.form['fio']
        test_type = request.form.get('test_type') # Получаем тип теста

        if test_type == 'linux':
            topic = 'Linux'
        elif test_type == 'network':
            topic = 'Сети'
        else:
            # Обработка ошибки - если тип теста не выбран
            return render_template('index.html', error_message="Пожалуйста, выберите тип теста.")

        # Используем get_questions_from_db для получения списка id
        question_ids = get_questions_from_db(NUM_QUESTIONS, topic)

        # Сохраняем список id вопросов в сессию
        session['fio'] = fio  # Сохраняем ФИО в сессию
        session['question_ids'] = question_ids # Сохраняем список id вопросов
        session['test_name'] = topic # Сохраняем имя теста
        session['correct_count'] = 0 #  Начальное кол-во правильных ответов
        session['incorrect_count'] = 0 #  Начальное кол-во неправильных ответов
        session['incorrect_questions'] = [] # Индексы неправильных вопросов
        session['user_answers'] = {} #  Ответы пользователя
        return redirect(url_for('test', question_index=0))  # Перенаправляем на страницу теста, передаем начальный индекс

    return render_template('index.html')  # Форма для ввода ФИО

@app.route('/test/<int:question_index>', methods=['GET', 'POST'])
def test(question_index):
    if 'question_ids' not in session or 'fio' not in session:
        return redirect(url_for('index')) # Перенаправляем обратно, если нет вопросов или ФИО

    question_ids = session['question_ids']
    fio = session['fio']
    test_name = session['test_name']
    correct_count = session.get('correct_count', 0)
    incorrect_count = session.get('incorrect_count', 0)
    incorrect_questions = session.get('incorrect_questions', [])
    user_answers = session.get('user_answers', {})


    if question_index >= len(question_ids):
        # Тест завершен
        return redirect(url_for('result')) #ИСПРАВЛЕНО: перенаправление на новый маршрут

    question_id = question_ids[question_index]
    question_data = get_question_data(question_id)

    if not question_data:
        return "Ошибка: Вопрос не найден"

    if request.method == 'POST':
        user_answer = request.form.get('answer') # Получаем ответ пользователя
        correct_answers = question_data['correct_answers'] #Правильные ответы

        if user_answer in correct_answers: #  Проверка с правильными ответами из базы
            correct_count += 1
            session['correct_count'] = correct_count

        else:
            incorrect_count += 1
            incorrect_questions.append(question_index)  # Сохраняем индекс вопроса
            #user_answers[question_index] = user_answer #  Сохраняем ответ пользователя
            session['incorrect_count'] = incorrect_count
            session['incorrect_questions'] = incorrect_questions
            #session['user_answers'] = user_answers



        next_question_index = question_index + 1
        return redirect(url_for('test', question_index=next_question_index))

    return render_template('test.html',
                           fio=fio,
                           question=question_data['question'], # ИСПРАВЛЕНО: Отображаем только один вопрос
                           options=question_data['options'],# ИСПРАВЛЕНО: Передаем варианты ответов
                           question_index=question_index + 1, # ИСПРАВЛЕНО: Номер текущего вопроса
                           total_questions=len(question_ids), # ИСПРАВЛЕНО: Всего вопросов
                           test_name=test_name
                           )

@app.route('/result')
def result():
    if 'question_ids' not in session or 'fio' not in session:
        return redirect(url_for('index'))

    correct_count = session.get('correct_count', 0)
    incorrect_count = session.get('incorrect_count', 0)
    incorrect_questions = session.get('incorrect_questions', [])
    fio = session['fio']
    test_name = session['test_name']
    question_ids = session['question_ids']
    user_answers = session.get('user_answers', {})

    # Формируем список вопросов с информацией об ответах пользователя
    results_list = []
    for question_index in range(len(question_ids)):
        question_id = question_ids[question_index]
        question_data = get_question_data(question_id)
        user_answer = user_answers.get(question_index, None) # Получаем ответ пользователя
        results_list.append({
            'question': question_data['question'],
            'correct_answers': question_data['correct_answers'],
            'user_answer': user_answer,
            'is_correct': user_answer in question_data['correct_answers'] if user_answer else False # Сравнение ответа с правильным
        })

    percentage_correct = (correct_count / len(question_ids)) * 100 #  ИСПРАВЛЕНО: расчет процента правильных ответов

    # ИСПРАВЛЕНО: проверяем процент правильных ответов с пороговым значением
    if percentage_correct >= PASSING_PERCENTAGE:
        result_message = f"Тест пройден успешно! У вас {percentage_correct:.2f}% верных ответов."
        result_status = "Успешно"
    else:
        result_message = f"Тест не пройден. У вас {percentage_correct:.2f}% верных ответов."
        result_status = "Неуспешно"

    # Сохраняем результаты в CSV
    try:
        with open(RESULTS_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # проверка заголовка, и что файл пуст. Это предотвращает повторную запись заголовка при каждом запуске теста.
            if file.tell() == 0: #Если файл пуст, записываем заголовок.
                writer.writerow(['ФИО', 'Тема тестирования', 'Правильных ответов', 'Статус', 'Номер Вопроса','Текст вопроса', 'Ответы пользователя', 'Правильные ответы'])

            # Записываем основную информацию о результате
            writer.writerow([fio, test_name, correct_count, result_status, "", "", "", ""]) #пустые строки для инфы об ошибках

            # Записываем информацию о каждой ошибке
            for question_index in incorrect_questions:
                question_id = question_ids[question_index] # Получаем ID вопроса по индексу
                question_data = get_question_data(question_id) # Получаем данные вопроса по ID

                if question_data:
                    user_answer = user_answers.get(question_index, "")  # Получаем ответ пользователя
                    writer.writerow(["", "", "", "",question_index + 1, question_data['question'], user_answer, ", ".join(question_data['correct_answers'])])
                else:
                    print(f"Ошибка: Вопрос с index {question_index} не найден.")

        print(f"Результаты успешно записаны в файл: {RESULTS_FILE}")  # Добавлено
        file_message = f"Результаты успешно записаны в файл: {RESULTS_FILE}"
    except Exception as e:
        print(f"Ошибка при записи в файл: {e}")
        file_message = f"Ошибка при записи в файл: {e}"

    session.clear()  # Очистка сессии после показа результатов

    return render_template('results.html',
                           fio=fio,
                           correct_count=correct_count,
                           incorrect_count=incorrect_count,
                           results=results_list,
                           test_name=test_name,
                           result_message=result_message, # ИСПРАВЛЕНО: передаем сообщение о результате
                           result_status=result_status,  # ИСПРАВЛЕНО: передаем статус результата
                           file_message=file_message # ИСПРАВЛЕНО: передаем сообщение о записи в файл
                           )

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

# Запуск приложения
if __name__ == '__main__':
    threading.Timer(1, open_browser).start()
    app.run(debug=True)
 # режим debug Автоматически перезагружает приложение при изменении кода.
 # Предоставляет отладчик, который позволяет пошагово выполнять код и анализировать значения переменных.
