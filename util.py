import config
import telebot
import db
from smtplib import SMTP
from threading import Timer
from time import strftime, localtime, time
from os import mkdir
from os.path import isfile, isdir
from email.utils import formataddr
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from requests import get
from shutil import disk_usage
from platform import system
from socket import gethostname, gethostbyname_ex


SUPPORTS = [i['chat_id'] for sub in (config.supports,) for i in sub]
SUPPORTGROUPS = [i['chat_id'] for sub in (config.supportgroups,) for i in sub]

bot = telebot.TeleBot(config.token)


def send_authcode(addr, regcode):    
    subj = 'Код регистрации в Службе технической поддержки'
    _from =  formataddr((str(Header('Сервисный бот', 'utf-8')), config.email_address))
    to = addr
    body = 'Добрый день!\n\n\nВы получили это письмо, потому что отправили обращение Telegram-боту ' + \
           'службы технической поддержки.\n\nВам следует сообщить боту код аутентификации: ' + str(regcode)
    send_email(_from, to, subj, body)


def send_email(from_field=None, to_field=None, subject_field=None, msg_body=None):    

    server = SMTP(config.mail_server, config.mail_port)
    server.starttls()
    server.login(config.email_login, config.email_password)
    msg = MIMEMultipart()
    msg['From'] = from_field
    msg['To'] = to_field
    msg['Subject'] = subject_field
    body = MIMEText(msg_body, 'plain', 'utf-8')
    msg.attach(body)
    server.sendmail(config.email_address, to_field, msg.as_string())


def print_userinfo(chat_id, with_log=False):

    user = db.get_user_namedtuple(chat_id)
    userinfo = ('Username: ' + user.first_name + ' ' + user.last_name + '\n'
                'Chat_id: ' + user.chat_id + '\n'
                'Email: ' + user.email_address + '\n'
               )
    if(with_log):
        userinfo += 'Message_log:\n' + user.message_log + '\n'
    return userinfo


def get_support_name_by_chat_id(chat_id):

    n = [i['name'] for i in config.supports if i['chat_id'] == chat_id]
    return n[0] if n[0] else None


def get_keyboard(buttons):

    keyboard = telebot.types.InlineKeyboardMarkup()
    for k in buttons:
        callback_button = telebot.types.InlineKeyboardButton(text=k[0], callback_data=k[1])
        keyboard.add(callback_button)
    return keyboard


# Таймер проверки времени с момента ответа специалиста
def timer(func, interval):

    func()
    Timer(interval, timer, (func, interval)).start()


def check_user_noreply_interval():

    communics = db.get_all_users_namedtuple()
    if communics:
        for u in communics:
            if u.last_msg_time_from_user != 0 and u.last_msg_time_from_specialist != 0 and u.current_communic_responsible != 0:
                if u.last_msg_time_from_user < u.last_msg_time_from_specialist and time() - u.last_msg_time_from_specialist > config.timeout_noreply:
                    archive_communic_from_chat_id(u.chat_id, timeout=True)
                    db.set_user(u.chat_id, has_active_communics=0, current_communic_is_appointed=0, current_communic_responsible=0, message_log = '\'' + config.REPLY['communic_closed'] + '\'')
                    bot.send_message(u.current_communic_responsible, 'Коммуникация, закрепленная ранее за Вами, автоматически закрыта по таймауту.')
                    for gr in SUPPORTGROUPS:
                        bot.send_message(gr, 'Коммуникация от пользователя: \n\n' + print_userinfo(u.chat_id, with_log=False) + '\nбыла автоматически закрыта по таймауту.')


def take_open_communic_by_button(support_chat_id, user_chat_id):

    user = db.get_user_namedtuple(user_chat_id)
    specialist_has_communics = (False if db.get_user_chat_id_by_responsible(support_chat_id) == None else True)
    if not specialist_has_communics and user.current_communic_is_appointed == 0 and user.has_active_communics == 1:
        db.append_message_to_history(user_chat_id, '[ServiceBot]: ' + get_support_name_by_chat_id(support_chat_id) + ' перевел на себя коммуникацию')
        db.set_user(user_chat_id, last_msg_time_from_specialist=int(time()))
        reply_to_group = ('{0} взял коммуникацию с пользователем: \n\n' + print_userinfo(user_chat_id, with_log=False))
        reply_to_specialist = ('{0}, Вы перевели на себя коммуникацию с пользователем: \n\n' + print_userinfo(user_chat_id, with_log=True) + '\nСообщения, которые Вы получаете от бота в личном чате, '
                               'перенаправляются Вам в том виде, в каком пользователь направляет их боту.\n\nСообщения, отправляемые Вами боту '
                               'в личном чате, перенаправляются пользователю.\n\nВсе сообщения попадают в историю коммуникации и после закрытия коммуникации архивируются.\n\nВам следует убедиться, что по данной коммуникации '
                               'еще не зарегистрирована заявка в сервисдеске, и зарегистрировать ее самостоятельно.\n\nДля открытия сервисного меню нажмите кнопку "/" и выберите позицию "/service" во всплывающем меню.\n\n'
                               'Для закрытия коммуникации нажмите кнопку "Закрыть текущую коммуникацию" в сервисном меню.'
                              )
        reply_to_user = ('Ваша коммуникация была переведена на специалиста. Имя специалиста: ' + get_support_name_by_chat_id(support_chat_id) + '.\n'
                         'Сообщения, отправляемые Вами боту, перенаправляются специалисту.')
        for gr in SUPPORTGROUPS:
            bot.send_message(gr, reply_to_group.format(get_support_name_by_chat_id(support_chat_id)))
        db.set_user(user_chat_id, current_communic_is_appointed=1)
        send_history(support_chat_id, reply_to_specialist.format(get_support_name_by_chat_id(support_chat_id)))
        db.set_user(user_chat_id, current_communic_responsible=support_chat_id)
        bot.send_message(user_chat_id, reply_to_user)
    elif not specialist_has_communics and user.current_communic_is_appointed == 0 and user.has_active_communics == 0:
        reply_to_specialist_1 = ('{0}, Вы хотели перевести на себя коммуникацию с пользователем {1}. Эта коммуникация уже закрыта. Пользователь не имеет активных коммуникаций.')
        bot.send_message(support_chat_id, reply_to_specialist_1.format(get_support_name_by_chat_id(support_chat_id), user.first_name + user.last_name))
    elif user.current_communic_is_appointed == 1 and user.has_active_communics == 1 and support_chat_id == user.current_communic_responsible:
        reply_to_specialist_2 = ('{0}, Вы хотели перевести на себя коммуникацию с пользователем {1}. Эта коммуникация уже закреплена за Вами. Вы можете общаться с пользователем через личный чат с ботом.')
        bot.send_message(support_chat_id, reply_to_specialist_2.format(get_support_name_by_chat_id(support_chat_id), user.first_name + user.last_name))
    elif user.current_communic_is_appointed == 1 and user.has_active_communics == 1 and support_chat_id != user.current_communic_responsible:
        reply_to_specialist_3 = ('{0}, Вы хотели перевести на себя коммуникацию с пользователем {1}. Эта коммуникация уже закреплена за другим специалистом.')
        bot.send_message(support_chat_id, reply_to_specialist_3.format(get_support_name_by_chat_id(support_chat_id), user.first_name + user.last_name))    
    elif specialist_has_communics:
        reply_to_specialist_4 = ('{0}, Вы хотели перевести на себя коммуникацию с пользователем {1}. У Вас есть текущая коммуникация. Для перевода на Вас новой коммуникации следует сначала закрыть текущую.')
        bot.send_message(support_chat_id, reply_to_specialist_4.format(get_support_name_by_chat_id(support_chat_id), user.first_name + user.last_name))
    else:
        bot.send_message(support_chat_id, config.REPLY['incorrect_request'])


def close_current_communic_by_button(id_, support_chat_id, prefix):

    user_chat_id = db.get_user_chat_id_by_responsible(support_chat_id)
    u = db.get_user_namedtuple(user_chat_id)
    if user_chat_id != None:
        archive_communic_from_chat_id(user_chat_id)
        db.set_user(user_chat_id, current_communic_is_appointed=0, current_communic_responsible=0, has_active_communics=0, message_log='\'' + config.REPLY['communic_closed'] + '\'')
        reply_to_group = (('Специалист {0} закрыл коммуникацию с пользователем: \n\n' + print_userinfo(user_chat_id, with_log=False)).format(get_support_name_by_chat_id(support_chat_id)))
        reply_to_specialist = ('[ServiceBot] Вы закрыли коммуникацию с пользователем: \n\n' + print_userinfo(user_chat_id, with_log=False))
        bot.send_message(support_chat_id, prefix + reply_to_specialist)
        for gr in SUPPORTGROUPS:
            bot.send_message(gr, reply_to_group)
    elif user_chat_id == None:
        bot.answer_callback_query(id_, prefix + config.REPLY['no_active_communics'], show_alert=True)
        

def archive_communic_from_chat_id(chat_id, timeout=False):

    if chat_id != None:
        u = db.get_user_namedtuple(chat_id)
        if timeout:
            db.append_message_to_history(chat_id, '[ServiceBot]: Коммуникация была автоматически закрыта по таймауту')
        else:
            db.append_message_to_history(chat_id, '[ServiceBot]: ' + get_support_name_by_chat_id(u.current_communic_responsible) + ' закрыл коммуникацию')
        dir_log = config.archive + str(chat_id)
        file_log = config.archive + str(chat_id) + '/' + str(chat_id) + r'.txt'
        if(isdir(dir_log) == False):
            mkdir(dir_log)            
        if(isfile(file_log) == False):
            f = open(file_log, 'w+')
            f.write(50*'#' + '\n\n' + 'Архив сообщений по пользователю' + '\n\n' + print_userinfo(chat_id) + '\n' + 50*'#' + '\n\n')
            f.close()
        f = open(file_log, 'a')
        f.write(60*'_' + '\n\n' + 'Запись от ' + strftime('%d.%m.%Y %H:%M:%S', localtime()) + ' (локальное время сервера)' + '\n' + 60*'_')

        # workaround for emoji logging
        res = ''
        for s in db.get_message_log_by_id(u.id):
            if (ord(s) > 0xfff):
                k = '[U+{:X}]'.format(ord(s))
                res += k
            else:
                res += s
        f.write('\n\n' + str(res) + '\n' + 60*'_' + '\n\n')
        f.close()


def get_prefix_for_servicebutton_reply(string):

    q = [k[0] for k in config.SUPPORTS_KEYBOARD or config.CONTROLLERS_KEYBOARD if k[1] == string]
    return 'Q: ' + q[0] + '\n\n' if q[0] else None


def process_content(message):

    dir_log = config.archive + str(message.chat.id)
    if(isdir(dir_log) == False):
            mkdir(dir_log) 
    if message.photo:
        content = get_file_photo_id(message)
        filename_suff = content[-10:] + '.jpg'
        a = 'фото'
        b = '. Подпись к фото: ' + message.caption if message.caption else ''
    elif message.document:
        content = message.document.file_id
        filename_suff = message.document.file_name
        a = 'файл ' + message.document.file_name
        b = '. Подпись к файлу: ' + message.caption if message.caption else ''
    if message.chat.id in SUPPORTS:
        h = db.get_user_chat_id_by_responsible(message.chat.id)
        c = 'Специалист'
    else:
        h = message.chat.id
        c = 'Пользователь'
    filename = dir_log + '/' + strftime('%Y%m%d_%H%M%S', localtime()) + '__' + filename_suff
    db.append_message_to_history(h, config.REPLY['sent_content'].format(c, a, b, filename))
    download_content(content, filename)
    

def download_content(cont, filename):

    if system() == 'Linux':
        du = disk_usage('/')
    elif system() == 'Windows':
        du = disk_usage('C:')
    free_space_rate = du.free / du.total * 100
    if free_space_rate <= 10:
        for gr in SUPPORTGROUPS:
            bot.send_message(gr, '[WARNING] Free disk space on bot-server ' + gethostname() + ' is less than 10%\n\nBot-server info (hostname, aliaslist, ipaddrlist):\n\n' + \
                                  str(gethostbyname_ex(gethostname())) + '\n\nThis message was generated at file saving procedure.')
        send_warning('support@depit.ru')
    file_info = bot.get_file(cont)
    file = get('https://api.telegram.org/file/bot{0}/{1}'.format(config.token, file_info.file_path))
    new_file = open(filename, 'wb')
    new_file.write(file.content)
    new_file.close()


def send_warning(addr):

    subj = '[WARNING] Free disk space on bot-server ' + gethostname() + ' is less than 10%'
    _from =  formataddr((str(Header('Сервисный бот', 'utf-8')), config.email_address))
    to = addr
    body = '[WARNING] Free disk space on bot-server ' + gethostname() + ' is less than 10%\n\nBot-server info (hostname, aliaslist, ipaddrlist):\n\n' + \
            str(gethostbyname_ex(gethostname())) + '\n\nThis message was generated at file saving procedure.'
    send_email(_from, to, subj, body)
    

def get_file_photo_id(message):

    if message.photo:
        it = [i.file_size for i in message.photo]
        return message.photo[it.index(max(it))].file_id


# workaround for Telegram maximum message size
def break_history(h):
    s = 4096
    if len(h) > s:
        hist_list = []
        n = len(h) // s
        for i in range(1, n+1):
            hist_list.append(h[s*(i-1):s*i])
        hist_list.append(h[s*n:])
        print('hist_list', hist_list)
        return hist_list
    else:
        print('h', h)
        return h     


def send_history(chat_id, h, **kwargs):

    if len(h) > 4096:
        k = 1
        while len(h) > k*4096:
            z = h[4096*(k-1):4096*k]
            bot.send_message(chat_id, z)
            k += 1
        if 'reply_markup' in kwargs:
            bot.send_message(chat_id, h[4096*(k-1):], reply_markup=kwargs['reply_markup'])
        else:
            bot.send_message(chat_id, h[4096*(k-1):])
    else:
        if 'reply_markup' in kwargs:
            bot.send_message(chat_id, h, reply_markup=kwargs['reply_markup'])
        else:
            bot.send_message(chat_id, h)




            
