import imaplib
import email
import telebot
from email.header import decode_header
import chardet
import time
import configparser

config = configparser.ConfigParser()
config.read('mail2tg\mail2tg.cfg')

TG_AUTH_TOKEN = config['TG']['AUTH_TOKEN']
TG_CHAT_ID = config['TG']['CHAT_ID']
IMAP_SERVER = config['IMAP']['SERVER']
IMAP_USER = config['IMAP']['USER']
IMAP_PASSWORD = config['IMAP']['PASSWORD']
CHECK_INTERVAL = config.getint('SETTINGS', 'CHECK_INTERVAL')
TG_MSG_MAX = config.getint('SETTINGS', 'MSG_MAX')

tg_bot = telebot.TeleBot(TG_AUTH_TOKEN)

def mime2text(encoded_text):
    decoded_words = []
    for encoded_word, charset in decode_header(encoded_text):
        if charset is None:
            decoded_words.append(encoded_word)
        else:
            decoded_word = encoded_word.decode(charset)
            decoded_words.append(decoded_word)
    return " ".join(decoded_words)

def part2data(part):
    payload = part.get_payload(decode=True)
    detected_encoding = chardet.detect(payload)['encoding']
    if detected_encoding:
        return payload.decode(detected_encoding, errors='replace')
    else:
        return payload.decode('utf-8', errors='replace')
    
def email2msg(mail, email_id):
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
                    content += part2data(part)
    return from_, subject, content

def split_message(content, limit):
    return [content[i:i + limit] for i in range(0, len(content), limit)]

def msg2tg(from_, subject, content):
    tg_pre = f'From: {from_}\nSubject: {subject}\n\n'
    tg_msg_limit = TG_MSG_MAX - len(tg_pre)
    if len(content) > tg_msg_limit:
        content_parts = split_message(content, tg_msg_limit)
        for part in content_parts:
            tg_bot.send_message(TG_CHAT_ID, f'{tg_pre}{part}')
            tg_pre = ''
    else:
        tg_msg = f'{tg_pre}{content}'
        tg_bot.send_message(TG_CHAT_ID, tg_msg)

def mail2tg():
    while True:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select('inbox')
        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()
        for email_id in email_ids:
            from_, subject, content = email2msg(mail, email_id)
            msg2tg(from_, subject, content)
            print('sended')
            time.sleep(1)
        mail.logout()
        print('checked')
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    mail2tg()
