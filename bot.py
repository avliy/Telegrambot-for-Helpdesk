#!/usr/bin/python3.6
import config
import db
import util
import telebot
from time import strftime, localtime, time
import cherrypy
from random import randint
import re 
from pprint import pprint
from os.path import isfile
from requests import get


# Определение специальных chat_id

ALL = [i['chat_id'] for sub in (config.supports,config.supportgroups,config.controllers) for i in sub]
SUPPORTS = [i['chat_id'] for sub in (config.supports,) for i in sub]
SUPPORTGROUPS = [i['chat_id'] for sub in (config.supportgroups,) for i in sub]
CONTROLLERS = [i['chat_id'] for sub in (config.controllers,) for i in sub]

# Определение специальных сообщений

USR_SPEC = ('/service', '/1')
SUP_SPEC = ('/service',)
ALL_SPEC = USR_SPEC + SUP_SPEC

bot = telebot.TeleBot(config.token)

# Вэбхук-сервер
class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        if 'content-length' in cherrypy.request.headers and \
           'content-type' in cherrypy.request.headers and \
           cherrypy.request.headers['content-type'] == 'application/json':
            length = int(cherrypy.request.headers['content-length'])
            json_string = cherrypy.request.body.read(length).decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return ''
        else:
            raise cherrypy.HTTPError(403)


# ТАЙМЕР ПРОВЕРКИ ВРЕМЕНИ С МОМЕНТА ОТВЕТА СПЕЦИАЛИСТА

util.timer(util.check_user_noreply_interval, config.reply_checking_interval)


# ХЭНДЛЕРЫ СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ

# Хэндлер на первое сообщение
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'email_address')==None and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text'])
def first_message(message):    

    user = db.get_user_namedtuple(message.chat.id)
    if not user:
        regcode = randint(1111,9999)
        new_user = (['first_name', message.chat.first_name],
                    ['last_name', message.chat.last_name],
                    ['chat_id', message.chat.id],
                    ['auth_code', regcode],
                    ['email_address', 'email_address_is_not_defined'],
                    ['message_log', '[ServiceBot] Получено сообщение от нового пользователя'])
        db.create_user(new_user)
        reply = ('Судя по всему, Вы обращаетесь к Сервисному боту впервые.\n'
                 'Давайте познакомимся. Пожалуйста, укажите ваш рабочий адрес электронной почты, чтобы я Вас узнал:'
                )
        bot.reply_to(message, reply)
        db.set_user(message.chat.id, email_is_requested=1)
    db.append_message_to_history(message.chat.id, message.text)

# Хэндлер на сообщения с адресом электронной почты
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'auth_code_is_sent')==(0,) and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text'])
def message_with_email_address(message):

    db.append_message_to_history(message.chat.id, message.text)
    pattern = r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$'
    reg = re.compile(pattern)
    if reg.match(message.text):
        reply = ('На указанный Вами адрес электронной почты направлено сообщение, содержащее код аутентификации. '
                 'Если Вы ввели некорректный адрес электронной почты, введите \'/\', в появившемся всплывающем меню выберите "/service Сервисное меню" и нажмите кнопку "Сменить адрес электронной почты".'
                )
        bot.reply_to(message, reply)
        util.send_authcode(message.text, db.get_user(message.chat.id, 'auth_code')[0])
        db.set_user(message.chat.id, auth_code_is_sent=1)
        email = '\'' + message.text + '\''
        db.set_user(message.chat.id, email_address=email)
    else:
        bot.reply_to(message, 'Это не похоже на адрес электронной почты. Введите Ваш рабочий адрес электронной почты для отправки Вам кода аутентификации')

# Хэндлер на сообщения с кодом аутентификации
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'auth_code_is_sent','is_authenticated')==(1,0) and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text'])
def message_with_auth_code(message):

    user = db.get_user_namedtuple(message.chat.id)
    db.append_message_to_history(message.chat.id, message.text)
    try:
        if int(message.text) == user.auth_code:
            db.set_user(message.chat.id, is_authenticated=1, last_msg_time_from_user=int(time()))
            reply = ('Отлично! Теперь я знаю, кто Вы, и запомню это на будущее. В любое время Вы можете написать сообщение мне с Вашим вопросом, '
                     'и я постараюсь соединить Вас со специалистом, который Вам поможет.\n\nПожалуйста, напишите Ваш вопрос к технической поддержке:'
                    )
            bot.reply_to(message, reply)
            template = config.REPLY['new_user_authenticated'].format(util.print_userinfo(message.chat.id, with_log=False))
            for gr in SUPPORTGROUPS:
                bot.send_message(gr, template)
        else:
            bot.reply_to(message, 'Код аутентификации указан неверно')
    except ValueError:
        bot.reply_to(message, 'Код аутентификации указан неверно')
                


# Хэндлер на первое сообщение новой коммуникации
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'is_authenticated','has_active_communics','current_communic_is_appointed')==(1,0,0) and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text', 'document', 'photo'])
def message_first_message_of_new_communic(message):

    if message.text:
        db.append_message_to_history(message.chat.id, message.text)
    elif message.photo or message.document:
        util.process_content(message)
    db.set_user(message.chat.id, has_active_communics=1, last_msg_time_from_user=int(time()))
    template = config.REPLY['new_communication'].format(util.print_userinfo(message.chat.id, with_log=False))
    user = db.get_user_namedtuple(message.chat.id)
    button2 = [['Перевести на себя коммуникацию с ' + user.first_name + ' ' + user.last_name, 'take_open_communic' + user.chat_id]]
    keyboard = util.get_keyboard(button2)
    for gr in SUPPORTGROUPS:
        if message.text:
            util.send_history(gr, template, reply_markup=keyboard)
        elif message.photo:
            util.send_history(gr, template, reply_markup=keyboard)
            bot.send_message(gr, '[ServiceBot]: Отправленное пользователем фото:')
            bot.send_photo(gr, util.get_file_photo_id(message))           
        elif message.document:
            util.send_history(gr, template, reply_markup=keyboard)
            bot.send_message(gr, '[ServiceBot]: Отправленный пользователем файл:')
            bot.send_document(gr, message.document.file_id)

            
# Хэндлер на второе сообщение в группу после открытия новой коммуникации до перевода коммуникации
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'is_authenticated','has_active_communics','current_communic_is_appointed')==(1,1,0) and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text', 'document', 'photo'])
def message_second_message_of_new_communic_before_communic_appointment(message):

    if message.text:
        db.append_message_to_history(message.chat.id, message.text)
    elif message.photo or message.document:
        util.process_content(message)
    
            
# Хэндлер на сообщения после перевода коммуникации
@bot.message_handler(func=lambda message: db.get_user(message.chat.id,'current_communic_is_appointed')==(1,) and message.chat.id not in ALL and message.text not in ALL_SPEC, content_types=['text', 'document', 'photo'])
def message_after_appointment(message):    
    if message.text:
        db.append_message_to_history(message.chat.id, message.text)
    elif message.photo or message.document:
        util.process_content(message)
    db.set_user(message.chat.id, last_msg_time_from_user=int(time()))
    user = db.get_user_namedtuple(message.chat.id)
    if message.text:
        bot.send_message(user.current_communic_responsible, '[' + user.email_address + '] ' + message.text)
    elif message.photo:
        mark = '[' + user.email_address + '] Фото:'
        if message.caption:
            mark = mark[:-1] + '. Подпись к фото: ' + message.caption
        bot.send_message(user.current_communic_responsible, mark)
        bot.send_photo(user.current_communic_responsible, util.get_file_photo_id(message))           
    elif message.document:
        mark = '[' + user.email_address + '] Файл:'
        if message.caption:
            mark = mark[:-1] + '. Подпись к файлу: ' + message.caption
        bot.send_message(user.current_communic_responsible, mark)
        bot.send_document(user.current_communic_responsible, message.document.file_id)


# Хэндлер на сообщения от пользователя для вывода сервисного меню
@bot.message_handler(func=lambda message: message.chat.id not in ALL and message.text=='/service', content_types=['text'])
def kb_for_users(message):

    keyboard = util.get_keyboard(config.USERS_KEYBOARD)
    bot.send_message(message.chat.id, 'Сервисное меню:', reply_markup=keyboard)


# ХЭНДЛЕРЫ СООБЩЕНИЙ СПЕЦИАЛИСТА

# Хэндлер на сообщения от специалиста
@bot.message_handler(func=lambda message: message.chat.id in SUPPORTS and message.text !='/service', content_types=['text', 'document', 'photo'])
def message_from_support(message):
    
    user_id = db.get_user_chat_id_by_responsible(message.chat.id)
    if user_id != None and message.text != '/service':
        if message.text:
            db.append_message_to_history(user_id, '[' + util.get_support_name_by_chat_id(message.chat.id) + ']: ' + message.text)
        elif message.photo or message.document:
            util.process_content(message)
        db.set_user(user_id, last_msg_time_from_specialist=int(time()))
        if message.text:
            bot.send_message(user_id, message.text)
        elif message.photo:
            mark = util.get_support_name_by_chat_id(message.chat.id) + ' отправил Вам фото:'
            if message.caption:
                mark = mark[:-1] + '. Подпись к фото: ' + message.caption
            bot.send_message(user_id, mark)
            bot.send_photo(user_id, util.get_file_photo_id(message))
        elif message.document:
            mark = util.get_support_name_by_chat_id(message.chat.id) + ' отправил Вам файл:'
            if message.caption:
                mark = mark[:-1] + '. Подпись к файлу: ' + message.caption
            bot.send_message(user_id, mark)
            bot.send_document(user_id, message.document.file_id)        
    elif user_id != None:
        bot.reply_to(message, config.REPLY['incorrect_request'])
    elif user_id == None:
        bot.reply_to(message, config.REPLY['no_active_communics'])


# Хэндлер на сообщения от специалиста для вывода сервисного меню
@bot.message_handler(func=lambda message: message.chat.id in SUPPORTS and message.text=='/service', content_types=['text'])
def kb_for_supports(message):

    keyboard = util.get_keyboard(config.SUPPORTS_KEYBOARD)
    bot.send_message(message.chat.id, '[ServiceBot] Сервисное меню:', reply_markup=keyboard)

   
# ХЭНДЛЕРЫ СООБЩЕНИЙ КОНТРОЛЛЕРА

# Хэндлер отображения первой клавиатуры для контроллера
@bot.message_handler(func=lambda message: message.chat.id in CONTROLLERS, content_types=['text'])
def kb_for_controllers(message):    

    keyboard = util.get_keyboard(config.CONTROLLERS_KEYBOARD)
    bot.send_message(message.chat.id, '[ServiceBot] Сервисное меню:', reply_markup=keyboard)


# ХЭНДЛЕРЫ НАЖАТИЯ КЛАИВАТУРЫ ПОЛЬЗОВАТЕЛЯМИ

# Хэндлер на нажатия клавиатуры 'Сменить адрес электронной почты'
@bot.callback_query_handler(func=lambda call: call.from_user.id not in CONTROLLERS and call.from_user.id not in SUPPORTS and call.data == 'change_email_address')
def callback_change_email_address(call):    

    if call.message:
        if db.get_user(call.from_user.id,'auth_code_is_sent','is_authenticated')==(1,0):
            db.append_message_to_history(call.from_user.id, '[ServiceBot]: Пользователь запросил смену адреса электронной почты')
            db.set_user(call.from_user.id, auth_code_is_sent=0)
            bot.send_message(call.from_user.id, 'Введите адрес электронной почты')
        else:
            bot.send_message(call.from_user.id, 'Cмена адреса электронной почты поддерживается при прохождении процедуры аутентификации')


# ХЭНДЛЕРЫ НАЖАТИЯ КЛАИВАТУРЫ СПЕЦИАЛИСТАМИ и КОНТРОЛЛЕРАМИ

# Хэндлер на нажатия клавиатуры 'Есть ли у меня текущая коммуникация?'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'get_current_communic')
def callback_get_current_communic(call):    

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        current_comm = db.get_user_chat_id_by_responsible(call.from_user.id)
        if current_comm:
            bot.answer_callback_query(call.id, pre + '[ServiceBot] За Вами закреплена коммуникация с пользователем:\n\n' + util.print_userinfo(current_comm), show_alert=True)
        else:
            bot.answer_callback_query(call.id, pre + '[ServiceBot] У Вас нет текущей коммуникации.', show_alert=True)


# Хэндлер на нажатия клавиатуры 'Закрыть текущую коммуникацию'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'close_current_communic')
def callback_close_current_communic(call):

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        util.close_current_communic_by_button(call.id, call.from_user.id, pre)


# Хэндлер на нажатия клавиатуры 'Перевести мою текущую коммуникацию в неназначенные'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'return_current_communic')
def callback_return_current_communic(call):

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        u_chat_id = db.get_user_chat_id_by_responsible(call.from_user.id)
        if u_chat_id:
            u = db.get_user_namedtuple(u_chat_id)
            ui = util.print_userinfo(u_chat_id)
            db.append_message_to_history(u_chat_id, '[ServiceBot]: Специалист ' + util.get_support_name_by_chat_id(call.from_user.id) +
                                                      ' перевел коммуникацию в незакрепленное состояние.')
            db.set_user(u_chat_id, current_communic_is_appointed=0, current_communic_responsible=0, last_msg_time_from_user=int(time()))
            message_to_specialist = 'Вы перевели коммуникацию с пользователем\n\n' + ui + '\nв незакрепленное состояние.'
            message_to_group = '[ServiceBot] Специалист ' + util.get_support_name_by_chat_id(call.from_user.id) +\
                               ' перевел активную коммуникацию с пользователем\n\n' + ui + '\nв незакрепленное состояние.\n\nВы можете перевести на себя коммуникацию, нажав кнопку, следующую за данным сообщением.'
            bot.send_message(call.from_user.id, pre + message_to_specialist)
            button = [['Перевести на себя коммуникацию с ' + u.first_name + ' ' + u.last_name, 'take_open_communic' + u.chat_id]]
            keyboard = util.get_keyboard(button)
            for gr in SUPPORTGROUPS:
                bot.send_message(gr, message_to_group, reply_markup=keyboard)        
        elif u_chat_id == None:
            bot.answer_callback_query(call.id, pre + config.REPLY['no_active_communics'], show_alert=True)
           
            
# Хэндлер на нажатия клавиатуры 'Список неназначенных коммуникаций'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'await_communic')
def callback_await_communic(call):

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        await_communics = db.get_awaiting_communics_namedtuple()
        if await_communics:
            bot.send_message(call.message.chat.id, pre + '[ServiceBot] Список коммуникаций:')
            for c in await_communics:
                text = str(c.id) + '.) ' + 'Username: ' + c.first_name + ' ' + c.last_name + ', ' + 'Email: ' + c.email_address
                button = [['Перевести на себя коммуникацию с ' + c.first_name + ' ' + c.last_name, 'take_open_communic' + c.chat_id]]
                keyboard = util.get_keyboard(button)
                bot.send_message(call.message.chat.id, text, reply_markup=keyboard)
        else:
            bot.answer_callback_query(call.id, pre + '[ServiceBot] Нет ожидающих перевода коммуникаций.', show_alert=True)


# Хэндлер на нажатия клавиатуры 'Список пользователей в базе'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'users')
def callback_users(call):

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        users = db.get_all_users_namedtuple()
        if len(users) != 0:
            reply = str()
            reply += '[ServiceBot] На данный момент в базе существуют следующие пользователи:\n\n'
            for u in users:
                reply += (str(u.id) + '.) ' + 'Username: ' + u.first_name + ' ' + u.last_name + ',\n')
                if u.is_authenticated == 0:
                    reply += 'Пользователь не прошел аутентификацию,\n'
                if u.email_address != 'email_address_is_not_defined':
                    reply += ('Email: ' + u.email_address + ',\n')
                if u.is_authenticated == 1 and u.has_active_communics == 0:
                    reply += ('Активной коммуникации не имеет,\n')
                if u.has_active_communics == 1 and u.current_communic_is_appointed == 0: 
                    reply += ('Активная коммуникация не переведена,\n')
                if u.has_active_communics == 1 and u.current_communic_is_appointed == 1:
                    reply += ('Активная коммуникация переведена на ' + util.get_support_name_by_chat_id(u.current_communic_responsible) + ',\n')
                reply += '\n'    
            reply = reply[:(len(reply)-2)]
            bot.send_message(call.message.chat.id, pre + reply[:-1])
        elif len(users) == 0:
            bot.answer_callback_query(call.id, pre + '[ServiceBot] На данный момент в базе нет пользователей.', show_alert=True)


# Хэндлер на нажатия клавиатуры 'Запрос истории сообщений по пользователям'
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and call.data == 'message_log')
def callback_message_log(call):

    if call.message:
        pre = util.get_prefix_for_servicebutton_reply(call.data)
        users = db.get_all_users_namedtuple()
        buttons = []
        for u in users:
            text = str(u.id) + '.) ' + 'Username: ' + u.first_name + ' ' + u.last_name + ', ' + 'Email: ' + u.email_address
            buttons.append([text, 'user'+str(u.id)])
        keyboard = util.get_keyboard(buttons)    
        bot.send_message(call.message.chat.id, pre + '[ServiceBot] Выберите пользователя:', reply_markup=keyboard)


# Хэндлер на нажатия клавиатуры 'Перевести на себя коммуникацию с '
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and bool(re.match(r'^take_open_communic(\d*)$', call.data)))
def callback_take_open_communic(call):

    if call.message:
        num = re.search(r'^take_open_communic(\d*)$', call.data)
        user_chat_id = num.group(1)
        util.take_open_communic_by_button(call.from_user.id, user_chat_id)


# Хэндлер на нажатия клавиатуры Выбор пользователя для просмотра истории коммуникаций
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and bool(re.match(r'^user(\d*)$', call.data)))
def callback_select_user_for_message_log_request(call):

    if call.message:
        num = re.search(r'^user(\d*)$', call.data)
        _id = num.group(1)
        u = db.get_user_by_id_namedtuple(_id)
        if u.message_log == config.REPLY['communic_closed']: # переписать условие
            keyboard = util.get_keyboard((('Архив сообщений по последней коммуникаций пользователя', 'last_communic_log'+_id), ('Архив сообщений по предыдущим коммуникациям пользователя', 'full_log'+_id)))
            bot.send_message(call.message.chat.id, '[ServiceBot] История сообщений по пользователю ' + u.first_name + ' ' + u.last_name + ', ' + 'Email: ' + u.email_address)
            util.send_history(call.message.chat.id, u.message_log, reply_markup=keyboard)
        else:
            keyboard = util.get_keyboard((('Архив сообщений по предыдущим коммуникациям пользователя', 'full_log'+_id),))
            bot.send_message(call.message.chat.id, '[ServiceBot] История сообщений по активной коммуникации пользователя ' + u.first_name + ' ' + u.last_name + ', ' + 'Email: ' + u.email_address)
            util.send_history(call.message.chat.id, u.message_log, reply_markup=keyboard)


# Хэндлер на нажатия клавиатуры Просмотр истории последней коммуникаций
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and bool(re.match(r'^last_communic_log(\d*)$', call.data)))
def callback_last_communic_log(call):

    if call.message:
        num = re.search(r'^last_communic_log(\d*)$', call.data)
        _id = num.group(1)
        u = db.get_user_by_id_namedtuple(_id)
        f = open(config.archive + str(u.chat_id) + '/' + str(u.chat_id) + r'.txt', 'r')
        st = f.read()
        f.close()
        m = 0
        k = 0
        while m != -1:
            m = st.find(60*'_' + '\n\n' + 'Запись от ', k)
            if m == -1:
                break
            k = m + 1
        bot.send_message(call.message.chat.id, '[ServiceBot] Архив сообщений по последней коммуникации пользователя ' + u.first_name + ' ' + u.last_name + ', ' + 'Email: ' + u.email_address)
        util.send_history(call.message.chat.id, st[k-1:])


# Хэндлер на нажатия клавиатуры Просмотр архива коммуникаций по пользователю
@bot.callback_query_handler(func=lambda call: call.from_user.id in CONTROLLERS or call.from_user.id in SUPPORTS and bool(re.match(r'^full_log(\d*)$', call.data)))
def callback_full_log(call):

    if call.message:
        num = re.search(r'^full_log(\d*)$', call.data)
        _id = num.group(1)
        u = db.get_user_by_id_namedtuple(_id)
        file_log = config.archive + str(u.chat_id) + '/' + str(u.chat_id) + r'.txt'
        if (isfile(file_log) == True):
            f = open(file_log, 'r')
            ar = f.read()
            bot.send_message(call.message.chat.id, '[ServiceBot] Архив сообщений по коммуникациям пользователя ' + u.first_name + ' ' + u.last_name + ', ' + 'Email: ' + u.email_address)
            util.send_history(call.message.chat.id, ar)
            f.close()
        elif (isfile(file_log) == False):
            bot.answer_callback_query(call.id, '[ServiceBot] На данный момент по данному пользователю нет архива коммуникаций.', show_alert=True)
            
# Сброс и установка вэбхука
bot.remove_webhook()
bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                certificate=open(config.WEBHOOK_SSL_CERT, 'r'))


# Обновление конфигурации вэбхук-сервера
cherrypy.config.update({
    'server.socket_host': config.WEBHOOK_LISTEN,
    'server.socket_port': config.WEBHOOK_PORT,
    'server.ssl_module': 'builtin',
    'server.ssl_certificate': config.WEBHOOK_SSL_CERT,
    'server.ssl_private_key': config.WEBHOOK_SSL_PRIV
})


# Запуск вэбхук-сервера
cherrypy.quickstart(WebhookServer(), config.WEBHOOK_URL_PATH, {'/': {}})

