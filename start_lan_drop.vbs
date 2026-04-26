Set ws = CreateObject("Wscript.Shell")

' --- 自动化配置区 ---
' 1. 填你 lan_drop.py 所在的真实文件夹路径
workDir = "D:\Project\Tools\localSend" 

' 2. 脚本文件名
scriptName = "lan_drop.py"
' ------------------

ws.CurrentDirectory = workDir

' 这里的 0 代表完全隐藏黑框，True 代表等待执行（这里用 False 即可）
ws.Run "python " & scriptName, 0, False