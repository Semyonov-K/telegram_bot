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
    """Проверяет ответ от эндпоинта на корректность."""
    if not isinstance(response, dict):
        raise TypeError(f'{sys._getframe().f_code.co_name}. '
                        f'Response не является словарем. '
                        f'Получен тип {type(response)}')
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError(f'{sys._getframe().f_code.co_name}. '
                        f'homeworks не является списком. '
                        f'Полуен тип {type(response)}')
    else:
        homeworks = response.get('homeworks')[0]
        if not homeworks:
            raise TypeError(f'{sys._getframe().f_code.co_name}. '
                                f'Не передан параметр homework')
        else:
            return homeworks


def parse_status(homework):
    """Получение статуса конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
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
