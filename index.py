import imghdr
from sanic import Sanic
from sanic.response import text
from wechatpy import parse_message
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException, InvalidAppIdException
from wechatpy.replies import create_reply
from wechatpy.utils import check_signature
from wechatpy.replies import ArticlesReply
import redis
import time
import requests
import os
import sqlite3

app = Sanic("memo-wx")


# 公众号的appid
appid = ""
if len(appid) == 0:
  appid = os.environ.get('appid')

# 公众号的令牌(Token)
token = ""
if len(token) == 0:
  token = os.environ.get('token')

# 公众号的消息加解密密钥
encoding_aes_key = ""
if len(encoding_aes_key) == 0:
  encoding_aes_key = os.environ.get('encoding_aes_key')

# 公众号的开发者密码(AppSecret)
AppSecret = ""
if len(AppSecret) == 0:
  AppSecret = os.environ.get('AppSecret')

# redis 地址
redisHost = ""
if len(redisHost) == 0:
  redisHost = os.environ.get('redisHost')

# redis端口
redisPort = 0
if redisPort == 0:
  redisPort = int(os.environ.get('redisPort'))

# redis密码
redisPassword = ""
if len(redisPassword) == 0:
  redisPassword = os.environ.get('redisPassword')

myselfUserId = os.environ.get('myselfUserId')
if myselfUserId is None:
  r = redis.Redis(host=redisHost, port=redisPort, db=0, password=redisPassword)

# 用户token确认是否可以使用
allowToken = os.environ.get('allowToken')
if allowToken is None:
  allowToken = "zdyh2023"
crypto = WeChatCrypto(token, encoding_aes_key, appid)

@app.get("/memo-wx")
def memoWXGET(request):
  print(request.args)
  signature = request.args.get("signature")
  echostr = request.args.get("echostr")
  timestamp = request.args.get("timestamp")
  nonce = request.args.get("nonce")
  try:
    check_signature(token, signature, timestamp, nonce)
    return text(echostr)
  except InvalidSignatureException:
    return text("hello")

@app.post("/memo-wx")
def memoWXPOST(request):
  signature = request.args.get("signature")
  msg_signature = request.args.get("msg_signature")
  timestamp = request.args.get("timestamp")
  nonce = request.args.get("nonce")

  from_xml = request.body.decode("UTF-8")
  try:
    check_signature(token, signature, timestamp, nonce)
    try:
      decrypted_xml = crypto.decrypt_message(
        from_xml,
        msg_signature,
        timestamp,
        nonce
      )
    except (InvalidAppIdException, InvalidSignatureException):
      pass
    msg = parse_message(decrypted_xml)
    # print(msg.content)
    userId = msg.source

    if(findExistUser(userId) is None):
      if msg.type == "text":
        content = msg.content
        if content.startswith("token[") and content.endswith("]"):
          userToken = content[6:-1]
          if userToken == allowToken:
            r.set("allow_{}".format(userId), userId)
            return text(ceeateReply('Token 已设置', msg, nonce, timestamp))
          else:
            return text(ceeateReply("当前只有指定用户才可使用此功能1", msg, nonce, timestamp))
        else:
          return text(ceeateReply("输入 token[你的token] 进行配置", msg, nonce, timestamp))
      else:
        return text(ceeateReply("当前只有指定用户才可使用此功能", msg, nonce, timestamp))
    if (findExistMag(msg.id) is not None):
      return text("")
    r.set("msgId_{}".format(msg.id), msg.id)
    r.expire("msgId_{}".format(msg.id), 30)
    if msg.type == "text":
      content = msg.content

      if content == "id":
        return text(ceeateReply(userId, msg, nonce, timestamp))
      if content == "del":
        clearUserSetting(userId)
        return text(ceeateReply("已删除", msg, nonce, timestamp))
      if content == "help":
        help_text = ''' del  --  删除token绑定 \n id    --  我的id \n start  -- 开始打卡 \n cal   -- 退出打卡 \n end   -- 结束打卡并记录'''
        return text(ceeateReply(help_text, msg, nonce, timestamp))
      try:
        return mutilpleMsg(content, "", "", msg, userId, nonce, timestamp)
      except BaseException as e:
        return text(ceeateReply(str(e), msg, nonce, timestamp))
    elif msg.type == "image":

      photo = getFileDown(msg.image, userId)
      try:
        return mutilpleMsg("", photo, "", msg, userId, nonce, timestamp)
      except BaseException as e:
        return text(ceeateReply(str(e), msg, nonce, timestamp))
    elif msg.type == "location":
      location = {}
      location["location_x"] = msg.location_x
      location["location_y"] = msg.location_y
      location["label"] = msg.label
      try:
        return mutilpleMsg("", "", location, msg, userId, nonce, timestamp)
      except BaseException as e:
        return text(ceeateReply(str(e), msg, nonce, timestamp))
    else:
      return text(ceeateReply('不支持此类型的数据', msg, nonce, timestamp))
  except InvalidSignatureException:
    return text("hello")


@app.post("/memo-tg")
def memoTGPOST(request):
  return ()



def mutilpleMsg(content, photo, location, msg, userId, nonce, timestamp):
  if(findExistUserMsg(userId) is not None):
    if content == "start" or content == "Start":
      return text(ceeateReply('已开始记录打卡', msg, nonce, timestamp))
    elif content == "end" or content == "End":
      return saveMark(userId, msg, nonce, timestamp)
    elif content == "cal":
      clearUserMsg(userId)
      return text(ceeateReply('已取消', msg, nonce, timestamp))
    elif content == "show":
      value = getUserMsgAll(userId)
      return text(ceeateReply(str(value), msg, nonce, timestamp))
    else:
      if content != "":
        r.lpush("msgContent_{}".format(userId), content)
        contents = ""
        for line in r.lrange("msgContent_{}".format(userId),0,-1):
          contents = contents + "\n" + line.decode("UTF-8")
        return text(ceeateReply('已记录：{}'.format(contents), msg, nonce, timestamp))
      elif photo != "":
        r.lpush("msgPhoto_{}".format(userId), photo)
        photos = ""
        for line in r.lrange("msgPhoto_{}".format(userId),0,-1):
          photos = photos + "\n" + line.decode("UTF-8")
        return text(ceeateReply('已记录：{}'.format(photos), msg, nonce, timestamp))
      elif location != "":
        r.set("msgLocation_x_{}".format(userId), location["location_x"])
        r.set("msgLocation_y_{}".format(userId), location["location_y"])
        r.set("msgLabel_{}".format(userId), location["label"])
        location_x, location_y, label = findUserLocation(userId)
        location_info = "位置：" + "\n ------ \n" + location_x + "\n ------ \n" + location_y + "\n ------ \n" + label
        return text(ceeateReply(location_info, msg, nonce, timestamp))
      else:
        return text(ceeateReply('不支持此类型的数据', msg, nonce, timestamp))
  else:
    if content == "start":
      r.set("startMsg_{}".format(userId), userId)
      return text(ceeateReply('开始记录打卡，可以发送文字、图片、位置', msg, nonce, timestamp))
    else:
      return text(ceeateReply('输入 start 进行打卡, end 结束, cal 取消', msg, nonce, timestamp))


def saveMark(userId, msg, nonce, timestamp):
  con = ConnectSqlite()

  sql = "INSERT INTO marks (location_x, location_y, label, image, mark_text, user_wx_id, create_time) VALUES (?, ?, ?, ?, ?, ?, ?);"
  value = getUserMsgAll(userId)
  print(value)
  if(con.insert_table_many(sql,value)):
    clearUserMsg(userId)
    con.close_con()
    return text(ceeateReply('打卡成功', msg, nonce, timestamp))
  else:
    clearUserMsg(userId)
    con.close_con()
    return text(ceeateReply('打卡失败', msg, nonce, timestamp))


def getUserMsgAll(userId):
  location_x, location_y, label = findUserLocation(userId)
  if(r.lrange("msgPhoto_{}".format(userId),0,-1) is not None):
    photos = ""
    for line in r.lrange("msgPhoto_{}".format(userId),0,-1):
      photos = photos + line.decode("UTF-8") + ","
  if(r.lrange("msgContent_{}".format(userId),0,-1) is not None):
    contents = ""
    for line in r.lrange("msgContent_{}".format(userId),0,-1):
      contents = contents  + line.decode("UTF-8") + "\n"
  return [(location_x, location_y, label, str(photos), str(contents), userId, int(time.time()))]

def getFileDown(filePath, userId):

  Img_ROOT_DIR = '/data/ass/'
  savePath=str(userId) + '/' 
  if not os.path.exists(Img_ROOT_DIR + savePath):
    os.makedirs(Img_ROOT_DIR +savePath)
  

  response = requests.request("GET", filePath)
  photoContent = response.content
  suffixName = imghdr.what(None, photoContent)

  fileName=str(int(time.time()))+'.'+ suffixName

  with open(Img_ROOT_DIR + savePath + fileName,'wb') as f:
    f.write(photoContent)
  return savePath + fileName

# 创建回复到微信的消息
def ceeateReply(replyContent, msg, nonce, timestamp):
  reply = create_reply(replyContent, message=msg)
  xml = reply.render()
  encrypted_xml = crypto.encrypt_message(xml, nonce, timestamp)
  r.delete("msgId_{}".format(msg.id), msg.id)
  return encrypted_xml


def ceeateArcReply(replyContent, msg, nonce, timestamp):
  reply = ArticlesReply(articles=replyContent, message=msg)
  xml = reply.render()
  encrypted_xml = crypto.encrypt_message(xml, nonce, timestamp)
  r.delete("msgId_{}".format(msg.id), msg.id)
  return encrypted_xml

def clearUserMsg(userId):
  r.delete("startMsg_{}".format(userId))
  r.delete("msgContent_{}".format(userId))
  r.delete("msgPhoto_{}".format(userId))
  r.delete("msgLocation_x_{}".format(userId))
  r.delete("msgLocation_y_{}".format(userId))
  r.delete("msgLabel_{}".format(userId))

def clearUserSetting(userId):
  r.delete("allow_{}".format(userId))

# 从redis获得保存的消息id，用于排重
def findExistMag(msgId):
  return r.get("msgId_{}".format(msgId))

# 从redis获取当前userId是否注册，判断是否可以使用服务
def findExistUser(userId):
  return r.get("allow_{}".format(userId))

# 从redis获取当前userId是否存在会话
def findExistUserMsg(userId):
  return r.get("startMsg_{}".format(userId))


def findUserLocation(userId):
  if(r.get("msgLocation_x_{}".format(userId)) is not None):
    location_x = r.get("msgLocation_x_{}".format(userId)).decode("UTF-8")
    location_y = r.get("msgLocation_y_{}".format(userId)).decode("UTF-8")
    label = r.get("msgLabel_{}".format(userId)).decode("UTF-8")
    return location_x, location_y, label
  else:
    return None, None, None

 
class ConnectSqlite:
 
  def __init__(self):
    """
    初始化连接--使用完记得关闭连接
    :param dbName: 连接库名字，注意，以'.db'结尾
    """
    
    Db_ROOT_DIR = '/data/db/'
    if not os.path.exists(Db_ROOT_DIR):
      os.makedirs(Db_ROOT_DIR)
    dbName=Db_ROOT_DIR + "mark.db"
    self._conn = sqlite3.connect(dbName)
    self._cur = self._conn.cursor()
    self._time_now = "[" + str(time.time()) + "]"
    self.create_tabel()
 
  def close_con(self):
    """
    关闭连接对象--主动调用
    :return:
    """
    self._cur.close()
    self._conn.close()
 
  def create_tabel(self):
    """
    创建表初始化
    :param sql: 建表语句
    :return: True is ok
    """
    try:
      sql_marks = '''CREATE TABLE IF NOT EXISTS marks 
      (
      id    INTEGER   PRIMARY KEY   AUTOINCREMENT,
      location_x  TEXT,
      location_y  TEXT,
      label   TEXT,
      image   TEXT,
      mark_text   TEXT,
      user_wx_id   TEXT NOT NULL,
      create_time INTEGER
      );'''
      self._cur.execute(sql_marks)
      self._conn.commit()
      return True
    except Exception as e:
      print(self._time_now, "[CREATE TABLE ERROR]", e)
      return False
 
  def drop_table(self, table_name):
    """
    删除表
    :param table_name: 表名
    :return:
    """
    try:
      self._cur.execute('DROP TABLE {0}'.format(table_name))
      self._conn.commit()
      return True
    except Exception as e:
      print(self._time_now, "[DROP TABLE ERROR]", e)
      return False
 
  def delete_table(self, sql):
    """
    删除表记录
    :param sql:
    :return: True or False
    """
    try:
      if 'DELETE' in sql.upper():
        self._cur.execute(sql)
        self._conn.commit()
        return True
      else:
        print(self._time_now, "[EXECUTE SQL IS NOT DELETE]")
        return False
    except Exception as e:
      print(self._time_now, "[DELETE TABLE ERROR]", e)
      return False
  
  def fetchall_table(self, sql, limit_flag=True):
    """
    查询所有数据
    :param sql:
    :param limit_flag: 查询条数选择，False 查询一条，True 全部查询
    :return:
    """
    try:
      self._cur.execute(sql)
      war_msg = self._time_now + ' The [{}] is empty or equal None!'.format(sql)
      if limit_flag is True:
        r = self._cur.fetchall()
        return r if len(r) > 0 else war_msg
      elif limit_flag is False:
        r = self._cur.fetchone()
        return r if len(r) > 0 else war_msg
    except Exception as e:
      print(self._time_now, "[SELECT TABLE ERROR]", e)
 
  def insert_update_table(self, sql):
    """
    插入/更新表记录
    :param sql:
    :return:
    """
    try:
      self._cur.execute(sql)
      self._conn.commit()
      return True
    except Exception as e:
      print(self._time_now, "[INSERT/UPDATE TABLE ERROR]", e)
      return False
 
  def insert_table_many(self, sql, value):
    """
    插入多条记录
    :param sql:
    :param value: list:[(),()]
    :return:
    """
    try:
      self._cur.executemany(sql, value)
      self._conn.commit()
      return True
    except Exception as e:
      print(self._time_now, "[INSERT MANY TABLE ERROR]", e)
      return False
 

if __name__ == '__main__':
  app.run(host="0.0.0.0", port=9000, debug=False)
