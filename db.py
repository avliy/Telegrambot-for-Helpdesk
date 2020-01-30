from sqlite3 import connect
import config
from time import strftime, localtime, time
from collections import namedtuple


MODEL = (    
         ('id', 'integer PRIMARY KEY'),
         ('first_name', 'text NOT NULL'),
         ('last_name', 'text'),
         ('chat_id', 'text'),
         ('auth_code', 'integer'),
         ('email_is_requested', 'integer'),
         ('email_address', 'text'),
         ('auth_code_is_sent', 'integer'),
         ('is_authenticated', 'integer'),
         ('current_communic_is_appointed', 'integer'),
         ('current_communic_responsible', 'integer'),
         ('has_active_communics', 'integer'),
         ('message_log', 'text'),
         ('service_mode', 'integer'),         
         ('last_msg_time_from_user', 'integer'),
         ('last_msg_time_from_specialist', 'integer')
        )


def create_connection(db_file):
    
	try:
        conn = connect(db_file)
        return conn
    except Error as e:
        print(e)
    return None


def create_user(new_user):
        
    connection = create_connection(config.db_file)
    # getting new user parameters and combining with default values 
    a = [None] * (len(MODEL)-1)
    l = 0
    for i in MODEL[1:]:
        for j in new_user:
            if i[0] == j[0]:
                a[l] = j[1]
            elif a[l] == None and i[0] != j[0] and i[1] == 'text':
                a[l] = ''
            elif a[l] == None and i[0] != j[0] and i[1] == 'integer':
                a[l] = 0
            else:
                pass
        l += 1
    create_query = 'INSERT INTO users('
    for i in MODEL[1:]:
        create_query += (i[0] + ', ')
    create_query = create_query[:(len(create_query)-2)]    
    create_query += (') VALUES(' + '?,'*(len(MODEL)-2) + '?)')
    cur = connection.cursor()
    cur.execute(create_query, a)
    connection.commit()
    connection.close()
    return cur.lastrowid


def get_user(chat_id, *args):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    param = str()
    if(args):
        for key in args:
            param += (key + ', ')
        param = param[:(len(param)-2)]    
    else:
        param = '*'
    sql = "SELECT {0} FROM users WHERE chat_id={1}"
    sql = sql.format(param, chat_id)
    cur.execute(sql)
    rows = cur.fetchone()
    connection.close()
    return rows 


def get_user_namedtuple(chat_id):

    connection = create_connection(config.db_file)
    connection.row_factory = namedtuple_factory
    cur = connection.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id=:id", {"id": chat_id})
    rows = cur.fetchone()
    connection.close()
    return rows


def get_all_users_namedtuple():

    connection = create_connection(config.db_file)
    connection.row_factory = namedtuple_factory
    cur = connection.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    connection.close()
    return rows
    

def namedtuple_factory(cursor, row):
    
    user = []
    for x in MODEL:
        user.append(x[0])
    nt = namedtuple('nt', user)
    return nt(*row)


def get_user_by_id_namedtuple(user_id):

    connection = create_connection(config.db_file)
    connection.row_factory = namedtuple_factory
    cur = connection.cursor()
    cur.execute("SELECT * FROM users WHERE id=:id", {"id": user_id})
    rows = cur.fetchone()
    connection.close()
    return rows
   
       
def get_chat_id_by_id(user_id):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT chat_id FROM users WHERE id=:id", {"id": user_id})
    rows = cur.fetchone()
    connection.close()
    return rows[0] if rows else rows


def get_message_log_by_id(user_id):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT message_log FROM users WHERE id=:id", {"id": user_id})
    rows = cur.fetchone()
    connection.close()
    return rows[0] if rows else config.REPLY['communic_closed']
    

def get_active_communics():

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT * FROM users WHERE has_active_communics=1")
    rows = cur.fetchone()
    connection.close()
    return rows

def get_awaiting_communics_namedtuple():

    connection = create_connection(config.db_file)
    connection.row_factory = namedtuple_factory
    cur = connection.cursor()
    cur.execute("SELECT * FROM users WHERE has_active_communics=1 AND current_communic_responsible=0")
    rows = cur.fetchall()
    connection.close()
    return rows if rows else None
       

def set_user(chat_id, **kwargs):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    param = str()
    for key in kwargs:
        param += (key + ' = ' + str(kwargs[key]) + ', ')
    param = param[:(len(param)-2)]
    sql = "UPDATE users SET {0} WHERE chat_id = {1}"
    sql = sql.format(param, chat_id)
    cur.execute(sql)
    connection.commit()
    connection.close()


def append_message_to_history(chat_id, msg):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT message_log FROM users WHERE chat_id=:id", {"id": chat_id})
    rows = (cur.fetchone())[0]
    if(rows == config.REPLY['communic_closed']):
        rows = ''
    rows += (strftime("%d.%m.%Y %H:%M:%S", localtime()) + '  ' + msg + '\n')
    cur.execute("UPDATE users SET message_log=:msg WHERE chat_id=:id", {"msg": rows, "id": chat_id})
    connection.commit()
    connection.close()


def get_user_chat_id_by_responsible(resp_id):

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT chat_id FROM users WHERE current_communic_responsible=:id", {"id": resp_id})
    rows = cur.fetchone()
    connection.close()
    return rows[0] if rows else rows


def get_all_users():

    connection = create_connection(config.db_file)
    cur = connection.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    connection.close()
    return rows


