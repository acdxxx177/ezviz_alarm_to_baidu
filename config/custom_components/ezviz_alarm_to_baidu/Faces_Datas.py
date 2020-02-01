"""
获取数据类

"""
import logging
import datetime
import base64
import json
#HTTP请求库
import asyncio
import aiohttp
import async_timeout
from homeassistant.helpers.aiohttp_client import (async_get_clientsession)
#事件处理
from homeassistant.helpers.event import async_track_point_in_time

_LOGGER = logging.getLogger(__name__)

EZVIZ_BASE_URL = "https://open.ys7.com"


class Faces_Datas(object):
    def __init__(self, hass, ezviz_appkey, ezviz_appSecret, baidu_client_id,
                 baidu_client_secret, is_update):
        self._hass = hass
        self._ezviz_appkey = ezviz_appkey
        self._ezviz_appSecret = ezviz_appSecret
        self._baidu_client_id = baidu_client_id
        self._baidu_client_secret = baidu_client_secret
        self._ezviz_accessToken = None
        self._baidu_accessToken = None
        self._ezviz_token_lock = False  #萤石token锁
        self._baidu_token_lock = False  #百度token锁
        self._is_update = is_update

    @property
    def ezviz_accessToken(self):
        """萤石accessToken"""
        return self._ezviz_accessToken

    @property
    def baidu_accessToken(self):
        """百度accessToken"""
        return self._baidu_accessToken

    @property
    def is_update(self):
        """是否更新"""
        return self._is_update

    @is_update.setter
    def is_update(self, value):
        self._is_update = value

    async def async_get_ezviz_token(self, datetimenow):
        """获取萤石token"""
        #加个同步锁，多设备的时候有时请求两次token
        if self._ezviz_token_lock:
            return
        self._ezviz_token_lock = True
        try:
            getTokenUrl = EZVIZ_BASE_URL + "/api/lapp/token/get"
            payload = {
                'appKey': self._ezviz_appkey,
                'appSecret': self._ezviz_appSecret
            }
            _LOGGER.info("时间:%s正在获取萤石Token....", datetimenow)
            result = await self.fetch_data(getTokenUrl, payload, "萤石Tkoen")
            if result is not None and result["code"] == "200":
                data = result["data"]
                token = data["accessToken"]
                _LOGGER.debug("获取的萤石token为:%s", token)
                self._ezviz_accessToken = token
                expireTime = int(data['expireTime'])
                timeStamp = int(expireTime / 1000)
                dateArray = datetime.datetime.fromtimestamp(timeStamp)
                _LOGGER.debug("萤石token下次更新时间:%s", dateArray)
                #添加一个事件，在指定时间再次获取token
                async_track_point_in_time(hass=self._hass,
                                          action=self.async_get_ezviz_token,
                                          point_in_time=dateArray)
            elif result is not None and result["code"] == "10007":
                _LOGGER.error("获取萤石接口:%s次", result['msg'])
            else:
                _LOGGER.error("获取萤石Token错误:%s", result)
                self._ezviz_accessToken = None
        except Exception:
            raise
        finally:
            self._ezviz_token_lock = False

    async def async_get_ezviz_messageList(self, payload):
        """获取萤石消息列表"""
        message_list_url = EZVIZ_BASE_URL + '/api/lapp/alarm/device/list'
        result = await self.fetch_data(message_list_url, payload, "萤石消息列表")
        if result is not None and result["code"] == "200":
            messageList = result['data']
            if len(messageList) > 0:
                imgurl = messageList[0]['alarmPicUrl']
                alarmTime = int(messageList[0]['alarmTime'])
                timeStamp = int(alarmTime / 1000)
                dateArray = datetime.datetime.fromtimestamp(timeStamp)
                _LOGGER.debug("获取的萤石图像为:%s,时间是：%s", imgurl, dateArray)
                return {'imgurl': imgurl, 'alarmTime': dateArray}
        elif result is not None and result["code"] == "10007":
            _LOGGER.error("获取萤石接口:%s次", result['msg'])
        else:
            _LOGGER.error("获取萤石消息列表错误:%s", result)

    async def async_get_baidu_token(self, datetimenow):
        """获取百度Token"""
        #加个同步锁，多设备的时候有时请求两次token
        if self._baidu_token_lock:
            return
        self._baidu_token_lock = True
        try:
            getTokenUrl = "https://aip.baidubce.com/oauth/2.0/token"
            payload = {
                'grant_type': 'client_credentials',
                'client_id': self._baidu_client_id,
                'client_secret': self._baidu_client_secret
            }
            _LOGGER.info("时间:%s正在获取百度Token....", datetimenow)
            result = await self.fetch_data(getTokenUrl, payload, "百度Tkoen")
            if result is not None and "error" not in result:
                token = result["access_token"]
                _LOGGER.debug("获取的百度token为:%s", token)
                self._baidu_accessToken = token
                expireTime = int(result['expires_in'])
                dateArray = datetime.datetime.now() + datetime.timedelta(
                    seconds=expireTime)
                _LOGGER.debug("百度token下次更新时间:%s", dateArray)
                #添加一个事件，在指定时间再次获取token
                async_track_point_in_time(hass=self._hass,
                                          action=self.async_get_baidu_token,
                                          point_in_time=dateArray)
            else:
                _LOGGER.error("获取百度Token错误:%s", result)
                self._baidu_accessToken = None
        except Exception:
            raise
        finally:
            self._baidu_token_lock = False

    async def async_get_baidu_faceinfo(self, payload):
        """在百度搜索人脸"""
        searchUrl = "https://aip.baidubce.com/rest/2.0/face/v3/multi-search?access_token=%s" % self.baidu_accessToken
        result = await self.fetch_data(
            searchUrl,
            json.dumps(payload),
            "百度人脸搜索",
            headers={'content-type': 'application/json'})
        if 'error_msg' in result and result['error_msg'] == "SUCCESS":
            _LOGGER.debug("人脸识别成功,检测到人员%s人，信息为:%s",
                          result['result']['face_num'],
                          result['result']['face_list'])
            return result['result']
        elif 'error_code' in result and result['error_code'] == 222207:
            _LOGGER.debug("百度人脸搜索未匹配到人脸")
        else:
            _LOGGER.error("百度人脸搜索错误:%s", result)

    async def fetch_data(
        self,
        url,
        payload,
        fetchname="数据",
        headers={'content-type': 'application/x-www-form-urlencoded'}):
        """POST获取数据"""
        _LOGGER.debug("获取%s开始.....", fetchname)
        websession = async_get_clientsession(self._hass)
        try:
            with async_timeout.timeout(15):
                response = await websession.post(url,
                                                 data=payload,
                                                 headers=headers)
                result = await response.json()
                if response.status != 200:
                    raise ValueError("返回码错误:%s" % response.status)
                elif result is None:
                    raise ValueError("未知错误")
                return result
        except asyncio.TimeoutError:
            _LOGGER.error("获取%s超时", fetchname)
        except aiohttp.ClientError as err:
            _LOGGER.error("获取%s错误: %s", fetchname, err)
        except Exception as err:
            _LOGGER.error("获取%s发生未知错误:%s", fetchname, err)

    async def async_fech_imgdata(self, imgurl):
        """获取图像数据"""
        websession = async_get_clientsession(self._hass)
        try:
            with async_timeout.timeout(16):
                response = await websession.get(imgurl)
                imagebyte = await response.read()
                imagebase64 = str(base64.b64encode(imagebyte),
                                  encoding='utf-8')
                return imagebase64
        except asyncio.TimeoutError:
            _LOGGER.error("获取图像超时.......")

        except aiohttp.ClientError as err:
            _LOGGER.error("获取图像错误: %s", err)
        except Exception:
            _LOGGER.error("获取图像未知错误")