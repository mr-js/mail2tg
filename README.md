# mail2tg
 Get all your mail in Telegram

 ### Demo
 
 ![mail2tg](/images/mail2tg.png)

 ### Setup

Set and check your credentials via ```keyring``` (terminal command line):

 ```bash
# YOUR_IMAP_SERVER
# Example: imap.mail.ru
 keyring set mail2tg ML_SERVER
 # YOUR_IMAP_USER
 # Example: mr-js@bk.ru
 keyring set mail2tg ML_USER
 # YOUR_IMAP_PASSWORD
 # Example: .........
 keyring set mail2tg ML_PASSWORD
 # YOUR_TELEGRAM_AUTH_TOKEN
 # Example: .........
 keyring set mail2tg TG_TOKEN
 # YOUR_TELEGRAM_CHAT_ID
 # Example: .........
 keyring set mail2tg TG_CHAT

 # CHECK
 keyring get mail2tg ML_SERVER
 keyring get mail2tg ML_USER
 keyring get mail2tg ML_PASSWORD
 keyring get mail2tg TG_TOKEN
 keyring get mail2tg TG_CHAT
 ```
 > [!NOTE]
 > Keyring allows you not to store passwords in an open and unprotected form together with the application, but to use a system service instead (i.e. passwords are securely stored in a protected environment at the OS level of your PC).

 ### Advanced setup and debugging

 Also you can set ```Demo``` to ```True``` in ```mail2tg.cfg``` to check delivery of telegram messages by sending a ```DEMO_MSG``` instead of waiting for a new one in the mail:

 ```ini
DEBUG = True
DEMO = False
DEMO_MSG = """
<div>
    <b>Bold text</b>, <i>Italic text</i>, <u>Underlined text</u>, <s>Strikethrough text</s>, 
    <code>monospace text</code>, <a href=“https://example.com”>link</a>,
    <h1>Heading</h1>, <p>Text paragraph with <span>invalid tag</span></p>,
    <a href=“mailto:email@mail.com”>email@mail.com</a><br>
    <p>One more paragraph</p>
</div>
"""

CHECK_INTERVAL = 60
TG_MSG_MAX = 4096
 ```

 > ```CHECK_INTERVAL``` -- mailbox check interval in seconds, MSG_MAX -- maximum message size in TG (not recommended to change)

  ## Usage

  Just run ```mail2tg.py```
   
 > [!WARNING]
 > Before using it, you must send any message in Telegram to the bot in the specified chat ```TG_CHAT```.

  ## Remarks

  The console will display ```checked``` each time a successful check is performed, and ```sended``` when a new email is detected and sent. Mail attachments are also handled and attached to messages on Telegram.
  > [!NOTE]
  > If the mail volume exceeds the TG message limit ```MSG_MAX```, it will be split and sent in multiple TG messages