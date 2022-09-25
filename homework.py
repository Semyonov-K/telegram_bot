import logging
import telegram
import requests
import sys
import os
import time

from dotenv import load_dotenv
from http import HTTPStatus
from json import JSONDecodeError
from settings import HOMEWORK_STATUSES

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений в телегу."""
    logger.info('Начинаем отправку сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно доставлено')
    except Exception:
        message = 'Сбой при отправке сообщения'
        logger.error(message)


def get_api_answer(current_timestamp):
    """Обращение к API и получение ответа."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logger.info('Обращаемся к API')
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception:
        raise requests.ConnectionError()
    if homework_statuses.status_code != HTTPStatus.OK:
        raise requests.ConnectionError(homework_statuses.status_code)
    try:
        return homework_statuses.json()
    except JSONDecodeError:
        logger.error('Сервер вернул невалидный json')


def check_response(response):
    """Проверка корректности ответа API."""
    try:
        homeworks_list = response.get('homeworks')[0]
    except KeyError as error:
        message = f'Ошибка доступа по ключу homeworks: {error}'
        logger.error(message)
    if homeworks_list is None:
        message = 'В ответе API нет словаря'
        logger.error(message)
    if not isinstance(homeworks_list, list):
        message = 'В ответе API представлены не списком'
        logger.error(message)
    if homeworks_list:
        homeworks_status = homeworks_list[0].get('status')
        if homeworks_status not in HOMEWORK_STATUSES:
            message = 'Неизвестный статус домашней работы'
            logger.error(message)
    return homeworks_list


def parse_status(homework):
    """Получение статуса конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    except KeyError as error:
        message = f'Неверное значение ключа {error}'
        logger.error(message)
    if homework_status not in HOMEWORK_STATUSES:
        message = ('Статус работы не распознан')
        logger.error(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка, что все токены получены."""
    if not PRACTICUM_TOKEN:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'PRACTICUM_TOKEN'")
        logger.critical(message)
        return False
    if not TELEGRAM_TOKEN:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'TELEGRAM_TOKEN'")
        logger.critical(message)
        return False
    if not TELEGRAM_CHAT_ID:
        message = ("Отсутствует обязательная переменная окружения: "
                   "'TELEGRAM_CHAT_ID'")
        logger.critical(message)
        return False
    else:
        message = 'Все обязательные переменные окружения найдены'
        logger.info(message)
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует одна или несколько переменных окружения')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    status = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                new_status = parse_status(homeworks[0])
                if new_status[0]['status'] != status:
                    logger.info('Старт условия')
                    send_message(bot, message)
                
            current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
