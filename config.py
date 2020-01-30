

# Bot token issued by BotFather

token = ''


# CherryPy server parameters

WEBHOOK_HOST = '' # Outer IP-address 
WEBHOOK_PORT = 8443  # 443, 80, 88 или 8443 
WEBHOOK_LISTEN = ''  # Inner IP-address of bot-server

WEBHOOK_SSL_CERT = ''  # Certificate location 
WEBHOOK_SSL_PRIV = ''  # Private key location

WEBHOOK_URL_BASE = 'https://%s:%s' % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = '/%s/' % (token)


# Database file location

db_file = '' 


# Location of folder with text archives

archive = './archive/'


# Groupmembers definition

supports = (
            {'chat_id':,
             'name':''},
            {'chat_id':,
             'name':''},            
           )


supportgroups = (
                 {'chat_id':,
                  'name':''},
                ) 
            
controllers = ()


# Definitions of common replies

REPLY = {'no_active_communics': '[ServiceBot] У Вас нет текущей коммуникации. Следите за анонсами новых коммуникаций в сервисной группе.',
         'incorrect_request': '[ServiceBot] Запрос не определен.',
         'new_user_authenticated': '[ServiceBot] Новый пользователь успешно прошел аутентификацию: \n\n{0}\nБот ожидает от пользователя открытия коммуникации.',
         'new_communication': 'Данный пользователь инициировал новую коммуникацию: \n\n{0}Вы можете перевести на себя коммуникацию, нажав кнопку, следующую за данным сообщением.',
         'communic_closed': 'Пользователь не имеет активной коммуникации.',
         'sent_content': '[ServiceBot]: {0} отправил {1}{2}. Файл сохранен в папке с архивом под именем {3}'
        }


# Definition of service keyboard for users

USERS_KEYBOARD = (('Сменить адрес электронной почты', 'change_email_address'),
                 )


# Definition of service keyboard for supports

SUPPORTS_KEYBOARD = (('Есть ли у меня текущая коммуникация?', 'get_current_communic'),
                     ('Закрыть текущую коммуникацию', 'close_current_communic'),
                     ('Перевести мою текущую коммуникацию в неназначенные', 'return_current_communic'),
                     ('Список неназначенных коммуникаций', 'await_communic'),
                     ('Список пользователей в базе', 'users'),
                     ('Запрос истории сообщений по пользователям', 'message_log'),
                    )


# Definition of service keyboard for controllers

CONTROLLERS_KEYBOARD = (('Список ожидающих перевода коммуникаций', 'await_communic'),
                        ('Список пользователей в базе', 'users'),
                        ('Запрос истории сообщений по пользователям', 'message_log'),
                       )


# No-reply timeout (seconds) causing communication automatic closing

timeout_noreply = 3600 #3600


# User-reply-status checking interval (sec)

reply_checking_interval = 300 #300


# Bot mailbox parameters

mail_server = '' # FQDN of mailserver

mail_port = 587 # Mailserver port number 

email_address = '' # E-mail address to use for sending mail

email_login = '' # AD account login to login to mailserver

email_password = '' # AD account password to login to mailserver 




 





