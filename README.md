<img width="1172" height="862" alt="image" src="https://github.com/user-attachments/assets/a6bc21bd-8083-486e-b0c2-aa287fd75c91" />一款基于python实现的局域网内文件互传的小工具，默认端口8001，支持多端设备使用
使用方法:
1、pc端在控制台启动land_drop.py程序，或者编辑好start_lan_drop.vbs这个脚本的路径，直接点击start_lan_drop.vbs启动；
2、pc端在浏览器打开http://localhost:8001/，手机端在浏览器打开http://{电脑ip}:8001，电脑ip可能会变，可以使用{电脑设备名称}.local:8001来访问
首次进入会要求你输入设备名称，随便输入；
3、进入后会有你在线的各个设备
<img width="513" height="272" alt="image" src="https://github.com/user-attachments/assets/ba3b92c1-986e-4408-8581-94d5269707a0" />
点击对应气泡是向该设备发送文件，长按气泡是发送文本；
4、可以把start_lan_drop.vbs脚本加入到系统启动项里，这样电脑开机后会自动启动服务
  1）win+r,输入shell:startup然后回车
![Uploading image.png…]()
把start_lan_drop.vbs拖到到目录里即可。
