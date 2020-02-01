"""萤石摄像头，人体警告触发"""
import logging
import datetime
import asyncio
# 引入这两个库，用于配置文件格式校验
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

#实体
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice, DEVICE_CLASS_MOTION, DOMAIN

from .Faces_Datas import Faces_Datas

#萤石
APPKEY = "appKey"
APPSECRET = "appSecret"
#百度
CLIENT_ID = "clientid"
CLIENT_SECRET = "clientSecret"
FACE_GROUP = "facesgroup"
#设备序列号
DEVICESID_LIST = "devices"
#消息类型 2-所有，1-已读，0-未读，默认为0（未读状态）
MESSAGESTATUS = 0
#告警类型，默认为-1（全部）10000为人体感应
ALARMTYPE = 10000
#验证数据
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("ezviz"): {
        vol.Required(APPKEY): cv.string,
        vol.Required(APPSECRET): cv.string,
        vol.Required(DEVICESID_LIST): cv.ensure_list
    },
    vol.Required("baidu"): {
        vol.Required(CLIENT_ID): cv.string,
        vol.Required(CLIENT_SECRET): cv.string,
        vol.Required(FACE_GROUP): cv.string
    }
})

SERVICE_CHANGE_EZVIZ_IS_UPDATE_SCHEMA = vol.Schema(
    {vol.Optional("status"): cv.boolean})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    #先打印一个日志,感受我的存在
    _LOGGER.info("萤石人体感应开始加载")
    #获取yml中的参数
    appkey = config.get('ezviz')[APPKEY]
    appSecret = config.get('ezviz')[APPSECRET]
    devices_list = config.get('ezviz')[DEVICESID_LIST]
    client_id = config.get('baidu')[CLIENT_ID]
    client_secret = config.get('baidu')[CLIENT_SECRET]
    face_group = config.get('baidu')[FACE_GROUP]
    #创建获取数据类
    face_data = Faces_Datas(hass, appkey, appSecret, client_id, client_secret,
                            True)
    #获取萤石和百度token
    await face_data.async_get_ezviz_token(datetime.datetime.now())
    await face_data.async_get_baidu_token(datetime.datetime.now())

    #创建实体
    creat_entiy = []
    for device in devices_list:
        creat_entiy.append(
            FaceRecognition(face_data, device, MESSAGESTATUS, ALARMTYPE,
                            face_group))
    async_add_devices(creat_entiy, True)

    async def change_ezviz_is_update(call):
        """更新状态回调"""
        status = call.data.get("status", False)
        face_data._is_update = status
        _LOGGER.debug("更新状态是:%s", status)

    #增加一个服务,开关更新状态
    hass.services.async_register(DOMAIN,
                                 "change_ezviz_is_update",
                                 change_ezviz_is_update,
                                 schema=SERVICE_CHANGE_EZVIZ_IS_UPDATE_SCHEMA)


class FaceRecognition(BinarySensorDevice):
    def __init__(self, face_data, deviceid, messagestatus, alarmtype,
                 grouplist):
        self._face_data = face_data
        self._deviceid = deviceid
        self._messagestatus = messagestatus
        self._alarmtype = alarmtype
        self._grouplist = grouplist
        self._is_on = False
        self._updatetime = None
        self._facenumber = 0
        self._faceinfo = {}

    @property
    def name(self):
        return 'ezviz_' + self._deviceid

    @property
    def is_on(self):
        """是否开启"""
        return self._is_on

    @property
    def registry_name(self):
        """返回实体的friendly_name属性."""
        return 'face_recognition_' + self._deviceid

    @property
    def device_class(self):
        """类型，这里设置运动"""
        return DEVICE_CLASS_MOTION

    @property
    def updatetime(self):
        """更新时间."""
        return self._updatetime

    @property
    def should_poll(self):
        """是否开始更新"""
        return self._face_data.is_update

    @property
    def device_state_attributes(self):
        """设置其它一些属性值."""
        if self.is_on is not None:
            return {"检测到的人数:": self._facenumber, "userInfo": self._faceinfo}

    async def async_update(self):
        """获取萤石消息列表"""
        if self._face_data.ezviz_accessToken is None:
            _LOGGER.error("没有萤石Token.....")
            #休息120秒
            await asyncio.sleep(120)
            if self._face_data.ezviz_accessToken is None:
                await self._face_data.async_get_ezviz_token(
                    datetime.datetime.now())
            return
        ezviz_payload = {
            'accessToken': self._face_data.ezviz_accessToken,
            'deviceSerial': self._deviceid,
            'status': self._messagestatus,
            'alarmType': self._alarmtype
        }
        ezvizmessage = await self._face_data.async_get_ezviz_messageList(
            ezviz_payload)
        if ezvizmessage is not None and self._updatetime != ezvizmessage[
                'alarmTime']:
            self._updatetime = ezvizmessage['alarmTime']
            self._is_on = True
            #获取图片进行人脸搜索
            if self._face_data.baidu_accessToken is None:
                _LOGGER.error("没有百度Token.....")
                #休息120秒
                await asyncio.sleep(120)
                if self._face_data.ezviz_accessToken is None:
                    await self._face_data.async_get_baidu_token(
                        datetime.datetime.now())
                return
            img = await self._face_data.async_fech_imgdata(
                ezvizmessage['imgurl'])
            if img is not None and len(img) > 10:
                baidu_payload = {
                    'image_type': 'BASE64',
                    'group_id_list': self._grouplist,
                    'max_face_num': 5,
                    'image': img
                }
                facesdata = await self._face_data.async_get_baidu_faceinfo(
                    baidu_payload)
                if facesdata is not None:
                    self._facenumber = facesdata['face_num']
                    self.make_baidu_face_json(facesdata['face_list'])
                else:
                    self._facenumber = 0
                    self._faceinfo = None
                    _LOGGER.debug("未检测到人脸")
            else:
                self._facenumber = 0
                self._faceinfo = None
        else:
            self._is_on = False
            self._facenumber = 0
            self._faceinfo = None
            _LOGGER.debug("跳过人脸检测")

    def make_baidu_face_json(self, data):
        """整理百度人脸识别的数据"""
        faces = {}
        for face in data:
            if 'user_list' in face and len(face['user_list']) > 0:
                fobj = face['user_list'][0]
                if fobj['group_id'] not in faces:
                    faces[fobj['group_id']] = []
                faces[fobj['group_id']].append(fobj['user_id'])
            else:
                if 'no_user' not in faces:
                    faces['no_user'] = [0]
                faces['no_user'][0] += 1
        _LOGGER.debug("检测到人脸：%s", faces)
        self._faceinfo = faces