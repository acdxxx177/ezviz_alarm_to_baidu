README
===========================
该插件用于HOMEASSISTANT，采用了萤石的HTTP接口和百度人脸识别V3接口，通过轮询萤石的警告列表中的人体感应消息，来获取图像，然后把图像通过百度人脸识别接口进行人脸识别

***
#### 安装步骤：
1. 下载[ezviz_alarm_to_baidu](./config/custom_components)目录放到HOMEASSISTANT的config/custom_components目录下
1. 申请[萤石开发平台网站](https://open.ys7.com/)和[百度开发者网站](https://cloud.baidu.com/product/face/search) 的账户并创建应用拿到key，完善以下内容，并创建百度人脸库，然后在人脸库中添加人脸
``` YAML {.line-numbers}
sensor:
  - platform: ezviz_alarm_to_baidu
    ezviz:
      appKey: xxxxxxx  #萤石开放平台的apikey
      appSecret: xxxxxxx  #萤石开放平台的appSecret
      devices:
        - 设备序列号1
        - 设备序列号2
        #以此类推，可以添加多个，序列号可以在机身标签或软件内找到
    baidu:
      clientid: XXXXXX  #百度开发者的client_id
      clientSecret: xxxxxxxxx   #百度开发者的clientSecret
      facesgroup: group1,group2 #对应百度人脸库用户组id，用逗号分隔，上限10个
    scan_interval: 60  #间隔轮询的时间（单位秒），好像萤石的免费版有次数限制，每天1万次
```
3. 把上面完善的内容加入config目录里的configuration.yml文件里
3. 重启HOMEASSISTANT

#### 在自动化获取信息方法：
插件在检测到人脸后，会在改变状态为True
如果检测到人脸，会在userInfo中显示json
格式为
``` javascript
{
  "用户组1":["用户1","用户2"],
  "用户组2":["用户3"],
  "no_user":[3]//值为list，值为识别到人脸，但是未添加到人脸库人的数量
  //.....
}
```
根据识别图片中人物数量显示用户组和用户名数量,用户组为人脸库的用户组id，用户为人脸库的用户id（百度好像不能在网页端进行userinfo的信息输入）
如果检测到多人，只有一部分在人脸库中，会显示"no_user"，里面是人员的数量,如果检测到都不在人脸库中，者无信息
在自动化和脚本中可以用语句{{ state_attr('sensor.--实体id--', 'userInfo') }}拿到
拿到后可以循环TTS或其他用途了,具体可以参考[这里](https://bbs.hassbian.com/forum.php?mod=viewthread&tid=6495)。

#### 一个省请求数量的方法
可以在自动化中增加规则，什么时候开启检测，示例比如每天早上8点开启检测，晚上10点关闭检测：
``` YAML
#[automations.yaml]

#关闭萤石获取数据
- alias: 'disabled_change_ezviz_update_shown'
  trigger:
    platform: time
    #在每天晚上22点
    at: '22:00:00'
  action:
    service: binary_sensor.change_ezviz_is_update
    data:
      status: False

#开启萤石获取数据
- alias: 'enabled _change_ezviz_update_shown'
  trigger:
    platform: time
    #在每天早上8点
    at: '8:00:00'
  action:
    service: binary_sensor.change_ezviz_is_update
    data:
      status: True
```
只有给binary_sensor.change_ezviz_is_update服务发送{"status":True}就开启，False关闭


#### 界面预览：
![界面图](/assets/界面图.png)

参考的地方
===
- https://developers.home-assistant.io/docs/en/entity_binary_sensor.html
- https://ai.baidu.com/ai-doc/FACE/Gk37c1uzc
- https://open.ys7.com/doc/zh/book/index/device_alarm.html
- https://bbs.hassbian.com/forum.php?mod=viewthread&tid=2504