from flask import Flask, render_template, request, redirect, url_for, session
import random
import csv
import sqlite3
import json
import webbrowser
import threading

def open_browser():
       webbrowser.open('http://127.0.0.1:5000')
       
ck_test = Flask(__name__)
ck_test.secret_key = 'your_secret_key#$' # Уникальное значение, используемое для шифрования данных сессии.

# Конфигурация тестирования
NUM_QUESTIONS = 10
PASSING_PERCENTAGE = 80
RESULTS_FILE = 'C://Хлам//учеба DE//Работа и задачи//ДС//Тесты ДС//Скрипт для тестирования//test_results.csv'  # Имя файла для сохранения результатов

# База вопросов и ответов. Функция рандомного взятия вопров согласно теме тестирования.
DATABASE_PATH = "C:\Хлам\учеба DE\Работа и задачи\ДС\Тесты ДС\Скрипт для тестирования\questions_with_topics.db"

def get_questions_by_topic(topic, num_questions=NUM_QUESTIONS):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    query = """
        SELECT question, options, correct_answers
        FROM questions
        WHERE topic = ?
        ORDER BY RANDOM()
        LIMIT ?
    """
    cursor.execute(query, (topic, num_questions))
    questions = cursor.fetchall()
    conn.close()

    result = []
    for question_text, options_json, correct_answers_json in questions:
        options = json.loads(options_json)
        correct_answers = json.loads(correct_answers_json)
        result.append({
            'question': question_text,
            'options': options,
            'correct_answers': correct_answers
        })
    return result


# Маршруты Flask

@ck_test.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        fio = request.form['fio']
        test_type = request.form.get('test_type') # Получаем тип теста

        if test_type == 'linux':
            selected_questions = get_questions_by_topic('Linux', NUM_QUESTIONS)
            test_name = "Linux"
        elif test_type == 'network':
            selected_questions = get_questions_by_topic('Сети', NUM_QUESTIONS)
            test_name = "сетям"
        else:
            # Обработка ошибки - если тип теста не выбран
            return render_template('index.html', error_message="Пожалуйста, выберите тип теста.")

# Сериализация списка вопросов в JSON перед сохранением
        session['fio'] = fio  # Сохраняем ФИО в сессию
        session['selected_questions'] = json.dumps(selected_questions)  # Сохраняем сериализованный список вопросов
        session['test_name'] = test_name
        return redirect(url_for('test'))  # Перенаправляем на страницу теста

    return render_template('index.html')  # Форма для ввода ФИО


@ck_test.route('/test', methods=['GET'])  # Изменили с POST на GET, т.к. перенаправляем с POST
def test():
    if 'selected_questions' not in session or 'fio' not in session:
        return redirect(url_for('index')) # Перенаправляем обратно, если нет вопросов или ФИО

    fio = session['fio']
    selected_questions_json = session['selected_questions']  
    #десериализация списка вопросов
    selected_questions = json.loads(selected_questions_json)
    test_name = session['test_name']

    # Теперь используем enumerate в шаблоне для нумерации вопросов
    return render_template('test.html', fio=fio, questions=selected_questions, enumerate=enumerate, test_name=test_name)


@ck_test.route('/result', methods=['POST'])
def result():
    if 'selected_questions' not in session or 'fio' not in session:
        return redirect(url_for('index'))

    fio = session['fio']
    selected_questions_json = session['selected_questions']
    selected_questions = json.loads(selected_questions_json)  # десериализация перед использованием
    test_name = session['test_name']
    correct_answers_count = 0
    incorrect_answers = []  # Список для хранения информации о неправильных ответах
    test_name = session['test_name']

    # Получаем ответы пользователя и проверяем их
    for question_index in range(NUM_QUESTIONS):
        question_id = f"question_{question_index}"
        user_answers = request.form.getlist(question_id)  # Получаем все выбранные варианты ответов
        question_text = request.form.get(f"question_text_{question_index}")  # Получаем текст вопроса из формы!

        # Находим правильный ответ в списке вопросов.
        selected_question = next((q for q in selected_questions if q["question"] == question_text), None) # Ищем вопрос по тексту!

        if selected_question:
            # Сравниваем ответы пользователя с правильными ответами
            if set(user_answers) == set(selected_question['correct_answers']):
                correct_answers_count += 1
            else:
                incorrect_answers.append({
                    'question': question_text,  # Текст вопроса берем из запроса
                    'user_answers': user_answers,
                    'correct_answers': selected_question['correct_answers'],
                    'question_number': question_index + 1  # нумерация с 1
                })
        else:
            print(f"Ошибка: Вопрос '{question_text}' не найден в списке вопросов.") # Обработка ошибки, если вопрос не найден (маловероятно, но хорошо иметь)

    percentage_correct = (correct_answers_count / NUM_QUESTIONS) * 100

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
            writer.writerow([fio, test_name, correct_answers_count, result_status, "", "", "", ""]) #пустые строки для инфы об ошибках

            # Записываем информацию о каждой ошибке
            for error in incorrect_answers:
                writer.writerow(["", "", "", error['question_number'], error['question'], ", ".join(error['user_answers']), ", ".join(error['correct_answers'])])

        print(f"Результаты успешно записаны в файл: {RESULTS_FILE}")  # Добавлено
    except Exception as e:
        print(f"Ошибка при записи в файл: {e}")
        result_message += "\nНе удалось сохранить результаты в файл." # сообщаем об ошибке

    return render_template('result.html', fio=fio, result_message=result_message, incorrect_answers=incorrect_answers)

# Запуск приложения
if __name__ == '__main__':
    threading.Timer(1, open_browser).start()
    ck_test.run(debug=True)
 # режим debug Автоматически перезагружает приложение при изменении кода. 
 # Предоставляет отладчик, который позволяет пошагово выполнять код и анализировать значения переменных.
