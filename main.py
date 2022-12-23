import telebot as telebot
from telebot import types
import copy
import sqlite3
import hashlib
from typing import Optional
from abc import ABC, abstractmethod
from functools import wraps
from datetime import datetime

from loguru import logger

from replaces import model, printers, parsers, network
from replaces.printers import printer

bot = telebot.TeleBot('1331385164:AAG0MC2MxmBh8y-qAO_cqhqorCj_WyQraa8')

DB_PATH = 'replaces_db.db'
SCHEMA = """
CREATE TABLE if not exists cache (key text primary key , value text);
CREATE TABLE if not exists replaces_history (got_timestamp text, content blob, content_hash text);
"""


class Cache:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def set(self, key: str, value: str):
        with self.db:
            self.db.execute('insert into cache values (? , ?);', (key, value))

    def get(self, key: str, default=None):
        res = self.db.execute('select value from cache where key = ?;', (key,)).fetchone()
        if res is None:
            return default

        else:
            return res[0]

    def upsert(self, key: str, value: str):
        with self.db:
            self.db.execute('insert into cache values (?, ?) on conflict do update set value = ?;', (key, value, value))

    def delete(self, key: str):
        with self.db:
            self.db.execute('delete from cache where key = ?;', (key,))


class CacheKeys:
    replaces_url = 'replaces_url'


class ReplacesDB:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def check_hash(self, _hash: str) -> bool:
        """
        Returns True if record with specified hash exists in table replaces_history
        :param _hash: a hash to check
        :return:
        """

        return bool(self.db.execute(
            'select exists(select 1 from replaces_history where content_hash = ?);',
            (_hash,)
        ).fetchone()[0])

    def store_replaces(self, replaces: bytes, _hash: str, timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat(timespec='seconds')  # timestamp in UTC
        with self.db:
            self.db.execute('insert into replaces_history values (?, ?, ?);', (timestamp, replaces, _hash))

    def get_latest_replacements_page(self) -> tuple[bytes, str, str]:  # page, hash, timestamp unix
        return self.db.execute(
            'select content, got_timestamp, content_hash from replaces_history order by got_timestamp desc limit 1;'
        ).fetchone()


class Hook(ABC):
    @abstractmethod
    def update(self, replaces: model.Replaces) -> None:
        """
        This method calls when detected new replaces
        :param replaces: new replaces
        :return:
        """
        ...


class HookGroup(Hook):
    def __init__(self, replaces_db: ReplacesDB, group: int):
        self.replaces_db = replaces_db
        self.group = group

    def update(self, replaces: model.Replaces) -> str:
        if self.is_duplicate(replaces):
            return

        if self.group in replaces.groups:
            logger.debug(f'Found replaces for {self.group} group')

            msg = replaces.header + '\n'
            msg += printers.printer(replaces.groups[self.group])

        else:  # Notify No replacements
            msg = f'{replaces.header}\n{self.group} Замен нет'

        return msg

    def is_duplicate(self, latest_replacements: model.Replaces) -> bool:
        """
        Checks if we have sent same replacements for group today (i.e. replacements for a day have changed but
        replacements for specified group hasn't changed

        :param latest_replacements: Replacements we've got during current check. As we already in this method,
         it is different from replacements we've got during previous check

         TODO: doesn't works properly

        :return: True if replacements for a group are the same
        """

        prev_replacements_page = self.replaces_db.get_latest_replacements_page()
        try:
            prev_replacements = parsers.parse_replaces(prev_replacements_page[0])
            if prev_replacements.header == latest_replacements.header:
                if printer(prev_replacements.groups.get(self.group)) == printer(latest_replacements.groups.get(self.group)):
                    logger.debug(f'Figured out latest replacements is duplicate for {self.group} group')
                    return True

        except Exception:
            logger.opt(exception=True).warning(f"Exception occurred during try to deduplicate")
            return False

        return False


def fallback_value(func: callable, default, force_fallback=False) -> callable:
    class ForceFallbackException(Exception):
        pass

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            if force_fallback:
                raise ForceFallbackException

            return func(*args, **kwargs)

        except Exception:
            logger.opt(exception=True).warning(f'Falling back to value {default!r}')
            return default

    return inner


def main():
    """
    1. Try to get replacements link by url, fallback to cache
    2. Get replaces as str, hash it, compare with replaces_history
    if exists:
        exit()

    Parse it (on fallback do screenshot, store do db)
        run hooks
        store to db
    """
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)

    cache = Cache(db)
    replaces_db = ReplacesDB(db)

    endpoint = fallback_value(network.fetch_replaces_url, cache.get(CacheKeys.replaces_url))()

    if endpoint is None:
        logger.error(f"Couldn't get endpoint")
        exit(1)

    replaces_page: bytes = network.fetch(network.the_session, endpoint)
    replaces_hash = hashlib.sha256(replaces_page).hexdigest()

    cache.upsert(CacheKeys.replaces_url, endpoint)

    if replaces_db.check_hash(replaces_hash):
        # if record exists
        # logger.debug(f'Found record')
        exit(0)

    try:
        parsed_replaces = parsers.parse_replaces(replaces_page)
        print(printer(parsed_replaces))

    except Exception:
        logger.opt(exception=True).error(f'Replaces parsing failed')
        # TODO: fallback to screenshot

    else:
        hooks: list[Hook] = [HookGroup(replaces_db, group=304)]
        for hook in hooks:
            try:
                hook.update(copy.deepcopy(parsed_replaces))

            except Exception:
                logger.opt(exception=True).warning(f'Hook {hook!r} failed')

        # store replaces to db anyway
        replaces_db.store_replaces(replaces_page, replaces_hash)





@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Я на связи👋. Напиши мне что-нибудь. 🤖 /help')

@bot.message_handler(commands=["help"])
def help(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    qu = types.KeyboardButton('привет👋')
    dela = types.KeyboardButton('как дела❓')
    otvet = types.KeyboardButton('норм,ты как?🤗')
    urk = types.KeyboardButton('уроки📕')
    zmn = types.KeyboardButton('замены🏫')


    markup.add(qu,dela,otvet,urk,zmn)
    bot.send_message(message.chat.id, "зачем❓", reply_markup=markup )

@bot.message_handler(content_types=["text"])
def get_user_text(message):
    if message.text == 'привет👋':
        bot.send_message(message.chat.id, "привет👋" )
    elif message.text =="как дела❓":
        bot.send_message(message.chat.id,"норм,ты как?🤗")
    elif message.text == "норм,ты как?🤗":
        bot.send_message(message.chat.id, "понятно😋")
    elif message.text == "замены🏫":
        replaces = get_replaces()
        bot.send_message(message.chat.id, replaces)
    else:
        bot.send_message(message.chat.id,'я тебя не понимаю')
@bot.message_handler(content_types=["sticker"])
def sticker(message):
        bot.send_message(message.chat.id,"классный стикер")

def get_replaces(num: int = 304) -> str:
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)

    cache = Cache(db)
    replaces_db = ReplacesDB(db)

    endpoint = fallback_value(network.fetch_replaces_url, cache.get(CacheKeys.replaces_url))()

    if endpoint is None:
        logger.error(f"Couldn't get endpoint")
        exit(1)

    replaces_page: bytes = network.fetch(network.the_session, endpoint)
    replaces_hash = hashlib.sha256(replaces_page).hexdigest()

    cache.upsert(CacheKeys.replaces_url, endpoint)

    if replaces_db.check_hash(replaces_hash):
        # if record exists
        # logger.debug(f'Found record')
        exit(0)

    try:
        parsed_replaces = parsers.parse_replaces(replaces_page)
        print(printer(parsed_replaces))

    except Exception:
        logger.opt(exception=True).error(f'Replaces parsing failed')
        # TODO: fallback to screenshot

    else:
        hooks: list[Hook] = [HookGroup(replaces_db, group=num)]
        for hook in hooks:
            try:
                return hook.update(copy.deepcopy(parsed_replaces))

            except Exception:
                logger.opt(exception=True).warning(f'Hook {hook!r} failed')

        # store replaces to db anyway
        replaces_db.store_replaces(replaces_page, replaces_hash)
if __name__ == '__main__':
    bot.polling(none_stop=True)