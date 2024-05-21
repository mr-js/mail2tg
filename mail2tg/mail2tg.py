import imaplib
import email
import telebot
from email.header import decode_header
from lxml import html
from lxml.html.clean import Cleaner

from flask import Flask, jsonify
from secrets import token_hex, choice
from threading import Thread
import asyncio
import time


app = Flask(__name__)
app.secret_key = token_hex(4)
app.config.from_pyfile('mail2tg.cfg', silent=False)
bot = telebot.TeleBot(app.config['TG_AUTH_TOKEN'])


def clean_html_for_telegram(html_content):
    # Допустимые теги для Telegram
    allow_tags = [
        'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 
        'tg-spoiler', 'a', 'code', 'pre'
    ]
    # Допустимые атрибуты
    allow_attributes = {
        'a': ['href']
    }
    
    # Создание объекта Cleaner с необходимыми параметрами
    cleaner = Cleaner()
    cleaner.allow_tags = allow_tags
    cleaner.allow_attributes = allow_attributes
    cleaner.safe_attrs_only = False
    cleaner.remove_unknown_tags = False
    cleaner.kill_tags = set()

    # Очистка HTML
    cleaned_html = cleaner.clean_html(html_content)
    cleaned_html = cleaned_html.replace('<div>', '').replace('</div>', '').strip()
    
    return cleaned_html


def reset_html_for_telegram(html_content):
    return html.fromstring(html_content).text_content()


def send_msg(from_, subject, content):
    tg_pre = f'{clean_html_for_telegram(from_)}\n<strong>{clean_html_for_telegram(subject)}</strong>\n\n'
    tg_blank = '\n\n...'
    tg_msg_limit = app.config['TG_MSG_MAX'] - (len(tg_pre) - len(tg_blank))
    if len(content) > tg_msg_limit:
        content = f'{content[:tg_msg_limit]}{tg_blank}'
    try:
        tg_msg = f'{tg_pre}{clean_html_for_telegram(content)}'
        bot.send_message(app.config['TG_CHAT_ID'], tg_msg, parse_mode='HTML')
    except:
        print(f'WARNING: {from_} {subject}\{content}')
        try:
             tg_msg = f'{tg_pre}{reset_html_for_telegram(content)}'
        except:
            print(f'ERROR: {from_} {subject}\{content}')
            bot.send_message(app.config['TG_CHAT_ID'], tg_msg, parse_mode='HTML')


async def check_email():
    while True:
        mail = imaplib.IMAP4_SSL(app.config['IMAP_SERVER'])
        mail.login(app.config['IMAP_USER'], app.config['IMAP_PASSWORD'])
        mail.select('inbox')
        if app.config['DEMO']:
            from_ = 'from@domain.com'
            subject = 'Subject'
            content = app.config['DEMO_MSG']
            print('checked (demo)')
            send_msg(from_, subject, content)
        else:
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            print('checked')
            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg['Subject'])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else 'utf-8')
                        from_ = msg.get('From')
                        content = 'NO TEXT DATA'
                        
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get('Content-Disposition'))

                                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                                    content = part.get_payload(decode=True).decode()
                                    break
                        else:
                            content = msg.get_payload(decode=True).decode()
                        send_msg(from_, subject, content)
                        time.sleep(1)
        mail.logout()
        await asyncio.sleep(app.config['CHECK_INTERVAL'])


@app.route('/')
def index():
    return jsonify({'message': 'Mail checker running in the background'})


def start_flask():
    app.run(debug=True, use_reloader=False)


def start_asyncio(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_email())


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    flask_thread = Thread(target=start_flask)
    flask_thread.start()

    asyncio_thread = Thread(target=start_asyncio, args=(loop,))
    asyncio_thread.start()