import imaplib
import email
import telebot
from email.header import decode_header
from lxml import html
from lxml.html.clean import Cleaner
import chardet
import re
import asyncio
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from threading import Thread
from secrets import token_hex
import keyring

app = Flask(__name__)
app.secret_key = token_hex(8)

file_handler = RotatingFileHandler('app.log', mode='a', maxBytes=1*1024*1024, backupCount=0, encoding='utf-8', delay=False)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s [%(funcName)s]', '%Y.%m.%d %H:%M:%S'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s [%(funcName)s]', '%Y.%m.%d %H:%M:%S'))
logger = logging.getLogger('my_logger')
app.logger.setLevel(logging.DEBUG) if app.config['DEBUG'] else app.logger.setLevel(logging.WARNING)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app.config.from_pyfile('mail2tg.cfg', silent=False)
app.config['TG_TOKEN'] = keyring.get_password('mail2tg', 'TG_TOKEN')
app.config['TG_CHAT'] = keyring.get_password('mail2tg', 'TG_CHAT')
app.config['ML_SERVER'] = keyring.get_password('mail2tg', 'ML_SERVER')
app.config['ML_USER'] = keyring.get_password('mail2tg', 'ML_USER')
app.config['ML_PASSWORD'] = keyring.get_password('mail2tg', 'ML_PASSWORD')

tg_bot = telebot.TeleBot(app.config['TG_TOKEN'])

def html2tg_html(html_content):
    if len(html_content) == 0:
        return ''
    allow_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'tg-spoiler', 'a', 'code', 'pre']
    allow_attributes = {'a': ['href']}
    cleaner = Cleaner()
    cleaner.allow_tags = allow_tags
    cleaner.allow_attributes = allow_attributes
    cleaner.safe_attrs_only = False
    cleaner.remove_unknown_tags = False
    cleaner.kill_tags = set()
    cleaned_html = cleaner.clean_html(html_content)
    cleaned_html = cleaned_html.replace('<div>', '').replace('</div>', '').strip()
    return cleaned_html

def html2tg_text(html_content):
    if len(html_content) == 0:
        return ''    
    text = re.sub(r'<[^>]*>', '', html_content)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*', '', text, flags=re.DOTALL)
    text = re.sub(r'style="[^"]*"', '', text)
    text = re.sub(r'style=\'[^\']*\'', '', text)
    text = re.sub(r'on\w+="[^"]*"', '', text)
    text = re.sub(r'on\w+=\'[^\']*\'', '', text)
    text = re.sub(r'\b[a-zA-Z_-]+\s*:\s*[^;]+;', '', text)
    text = re.sub(r'\b[a-zA-Z_-]+\s*=\s*\'[^\']*\'', '', text)
    text = re.sub(r'\b[a-zA-Z_-]+\s*=\s*"[^"]*"', '', text)
    text = re.sub(r'@media\s+[^{]+\{[^}]*\}', '', text)
    text = re.sub(r'@keyframes\s+[^{]+\{[^}]*\}', '', text)
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\b(html|webkit-text-size-adjust|none|ms-text-size-adjust|mob_100|important|width|max-width|screen|and|only)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\s\u200b\xa0]+', ' ', text)
    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    cleaned_text = re.sub(r'(?<=[^\.\!\?])\s+(?=[А-ЯЁA-Z])', '\n', cleaned_text)
    return cleaned_text

def mime2text(encoded_text):
    decoded_words = []
    for encoded_word, charset in decode_header(encoded_text):
        if charset is None:
            decoded_words.append(encoded_word)
        else:
            decoded_word = encoded_word.decode(charset)
            decoded_words.append(decoded_word)
    return " ".join(decoded_words)

def msg2tg(from_, subject, content, attachments=[]):
    tg_pre = f'{html2tg_html(from_)}\n<strong>{html2tg_html(subject)}</strong>\n\n'
    tg_blank = '\n\n...'
    tg_msg_limit = app.config['TG_MSG_MAX'] - (len(tg_pre) - len(tg_blank))
    if len(content) > tg_msg_limit:
        content = f'{content[:tg_msg_limit]}{tg_blank}'
    try:
        tg_msg = f'{tg_pre}{html2tg_html(content)}'
        tg_bot.send_message(app.config['TG_CHAT'], tg_msg, parse_mode='HTML')
    except:
        logger.warning(f'{from_} {subject}\n{content}')
        try:
            tg_msg = f'{tg_pre}{html2tg_text(content)}'
        except:
            logger.error(f'{from_} {subject}\n{content}')
            tg_bot.send_message(app.config['TG_CHAT'], tg_msg, parse_mode='HTML')
    if len(attachments):
        try:
            for msg_attach in attachments:
                tg_bot.send_document(chat_id=app.config['TG_CHAT'], document=msg_attach.get('content', ''), visible_file_name=msg_attach.get('filename', ''))
        except:
            logger.warning(f'{from_} {subject}\nATTACHMENT MISSING')

def part2data(part):
    payload = part.get_payload(decode=True)
    detected_encoding = chardet.detect(payload)['encoding']
    if detected_encoding:
        return payload.decode(detected_encoding, errors='replace')
    else:
        return payload.decode('utf-8', errors='replace')

def email2msg(mail, email_id):
    attachments = []
    status, msg_data = mail.fetch(email_id, '(RFC822)')
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else 'utf-8')
            from_, encoding = decode_header(msg['From'])[0]
            if isinstance(from_, bytes):
                from_ = from_.decode(encoding if encoding else 'utf-8')
            content = ''
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition'))
                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    content += part2data(part)
                elif content_type == 'text/html' and 'attachment' not in content_disposition:
                    content += html2tg_text(part2data(part))
                elif 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append({'filename': mime2text(filename), 'content': part.get_payload(decode=True)})
    return from_, subject, content, attachments

async def mail2tg():
    while True:
        mail = imaplib.IMAP4_SSL(app.config['ML_SERVER'])
        mail.login(app.config['ML_USER'], app.config['ML_PASSWORD'])
        mail.select('inbox')
        if app.config['DEMO']:
            from_ = 'from@domain.com'
            subject = 'Subject'
            content = app.config['DEMO_MSG']
            logger.debug('inbox mail checked (demo)')
            msg2tg(from_, subject, content)
        else:
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            logger.debug('inbox mail checked')
            for email_id in email_ids:
                from_, subject, content, attachments = email2msg(mail, email_id)
                msg2tg(from_, subject, content, attachments)
                time.sleep(1)
        mail.logout()
        await asyncio.sleep(app.config['CHECK_INTERVAL'])

@app.route('/')
def index():
    return jsonify({'message': 'Mail checker running in the background'})

def start_flask():
    app.run(debug=True, use_reloader=False)

def start_asyncio():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(mail2tg())

def run():
    try:
        logger.info('Checking Telegram connection...')
        tg_bot.get_me()
        tg_bot.get_chat(app.config['TG_CHAT'])
        logger.info('Telegram connection established')
    except Exception as e:
        logger.critical(f'Telegram connection failed: {e}')
        return

    try:
        if not app.config['DEMO']:
            logger.info('Checking email connection...')
            server = imaplib.IMAP4_SSL(app.config['ML_SERVER'])
            server.login(app.config['ML_USER'], app.config['ML_PASSWORD'])
            server.logout()
            logger.info('Email connection established')
        else:
            logger.info('Email connection (DEMO)')
    except Exception as e:
        logger.critical(f'Email connection failed: {e}')
        return

    logger.info(f'Starting application for user {app.config["ML_USER"]} to chat {app.config["TG_CHAT"]}')

    flask_thread = Thread(target=start_flask)
    flask_thread.start()

    asyncio_thread = Thread(target=start_asyncio)
    asyncio_thread.start()

    logger.info('Application started')

if __name__ == '__main__':
    run()
