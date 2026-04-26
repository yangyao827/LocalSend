import os
import uuid
import json
import socket
import shutil
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

# === 新增下面这段代码：强迫 PyInstaller 把这两个隐藏依赖塞进 exe 里 ===
try:
    import multipart
except ImportError:
    pass

try:
    import python_multipart
except ImportError:
    pass
# ==========================================================

# 临时文件存储目录
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# 持久化存储设备名与IP映射的文件
DAT_FILE = "devices.dat"

def load_devices():
    if os.path.exists(DAT_FILE):
        try:
            with open(DAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_devices(data):
    with open(DAT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

app = FastAPI()

# ---------------------------------------------------------
# 前端 HTML/CSS/JS 代码 (单文件集成)
# ---------------------------------------------------------
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>局域网互传助手</title>
    <style>
        body { margin: 0; padding: 0; background: #f4f7f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; touch-action: manipulation; }
        
        .container { flex: 1; position: relative; overflow: hidden; width: 100%; box-sizing: border-box; }
        
        /* 气泡外壳 */
        .bubble-wrap { position: absolute; transition: all 0.5s cubic-bezier(0.25, 0.8, 0.25, 1); z-index: 5; }

        /* --- 恢复原本鲜艳的渐变底色 --- */
        .bubble { 
            width: 100%; height: 100%; 
            border-radius: 50%; 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); /* 蓝青色 */
            color: white; 
            display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; 
            font-weight: bold; 
            box-shadow: 0 10px 25px rgba(79, 172, 254, 0.4); 
            cursor: pointer; 
            user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; 
            word-break: break-all; padding: 5%; box-sizing: border-box; 
            animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; 
            transition: margin 3s ease-in-out, transform 0.1s; 
            position: relative; 
            overflow: hidden; /* 极其重要：把超出的水切掉，保持圆形 */
        }
        
        /* 自己的气泡：恢复橙黄色 */
        .bubble.self { 
            background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); 
            box-shadow: 0 10px 25px rgba(253, 160, 133, 0.4); 
        }
        .bubble:active { transform: scale(0.9) !important; }
        
        /* --- 纯净的水层：去掉了旋转白框 --- */
        .water {
            position: absolute;
            bottom: 0; left: 0;
            width: 100%;
            height: 0%; /* 初始没水 */
            background: rgba(0, 230, 118, 0.95); /* 鲜艳的绿色，带一丢丢透明度融合底色 */
            transition: height 0.2s linear; /* 平滑上升 */
            z-index: 1; /* 藏在文字下面 */
        }

        /* 确保文字永远在水上面 */
        .bubble-text {
            position: relative;
            z-index: 10; 
        }
        
        @keyframes popIn { from { transform: scale(0); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        
        /* 模态弹窗和吐司样式保持不变 */
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: none; align-items: center; justify-content: center; z-index: 100; backdrop-filter: blur(4px); }
        .modal { background: white; padding: 25px; border-radius: 16px; width: 85%; max-width: 350px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.2); animation: slideUp 0.3s ease; }
        @keyframes slideUp { from { transform: translateY(30px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .modal h3 { margin-top: 0; color: #333; }
        .modal p { color: #555; line-height: 1.5; word-break: break-all; max-height: 200px; overflow-y: auto;} /* 增加内容过长时的滚动支持 */
        
        .btn-group { display: flex; justify-content: space-around; margin-top: 20px; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; color: white; font-weight: bold; flex: 1; margin: 0 5px; transition: opacity 0.2s; }
        .btn:active { opacity: 0.8; }
        .btn-accept { background: #4caf50; }
        .btn-reject { background: #f44336; }
        .btn-primary { background: #667eea; width: 100%; margin: 0; }
        
        input[type="text"], textarea { width: 100%; padding: 12px; margin: 15px 0; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; font-family: inherit; resize: none; font-size: 16px; }
        input[type="text"]:focus, textarea:focus { outline: none; border-color: #667eea; }
        #fileInput { display: none; }
        
        #toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: white; padding: 12px 24px; border-radius: 30px; display: none; z-index: 1000; font-size: 14px; animation: fadeInOut 2.5s forwards; white-space: nowrap; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        @keyframes fadeInOut { 0% { opacity: 0; bottom: 20px; } 15% { opacity: 1; bottom: 40px; } 85% { opacity: 1; bottom: 40px; } 100% { opacity: 0; bottom: 60px; } }
    </style>
</head>
<body>
    <div class="container" id="bubbleContainer"></div>
    <input type="file" id="fileInput" multiple> 
    <div id="toast"></div>

    <div id="loginModal" class="modal-overlay">
        <div class="modal">
            <h3 id="loginModalTitle">加入互传网络</h3>
            <input type="text" id="deviceNameInput" placeholder="请输入当前设备名称" maxlength="15">
            <button class="btn btn-primary" onclick="joinNetwork()">确定</button>
        </div>
    </div>

    <div id="inputModal" class="modal-overlay">
        <div class="modal">
            <h3 id="inputTitle">发送消息</h3>
            <textarea id="inputText" rows="4" placeholder="输入要发送的文本..."></textarea>
            <div class="btn-group">
                <button class="btn btn-reject" onclick="closeModal('inputModal')">取消</button>
                <button class="btn btn-accept" onclick="sendTextMessage()">发送</button>
            </div>
        </div>
    </div>

    <div id="transferModal" class="modal-overlay">
        <div class="modal">
            <h3>接收文件请求</h3>
            <p id="modalMessage"></p>
            <div class="btn-group">
                <button class="btn btn-reject" onclick="rejectFile()">拒绝</button>
                <button class="btn btn-accept" onclick="acceptFile()">接收全部</button>
            </div>
        </div>
    </div>

    <div id="textModal" class="modal-overlay">
        <div class="modal">
            <h3 id="textSender" style="margin-bottom: 15px; font-size: 16px; color: #222;"></h3>
            <div style="position: relative; background: #f0f4f8; padding: 15px; padding-top: 40px; border-radius: 8px; text-align: left; margin-bottom: 15px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);">
                <button onclick="copyMessage()" class="btn" style="position: absolute; top: 8px; right: 8px; width: auto; padding: 5px 12px; font-size: 12px; border-radius: 6px; background: #999999; color: white; margin: 0;">复制</button>
                <div id="textMessage" style="min-height: 40px; word-break: break-all; color: #444; line-height: 1.5; font-size: 15px;"></div>
            </div>
            <button class="btn btn-primary" onclick="closeModal('textModal')">关闭</button>
        </div>
    </div>

    <script>
        // 防缩放代码
        document.addEventListener('touchstart', function(event) { if (event.touches.length > 1) { event.preventDefault(); } }, { passive: false });
        document.addEventListener('gesturestart', function(event) { event.preventDefault(); });
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            let now = (new Date()).getTime();
            if (now - lastTouchEnd <= 300) { event.preventDefault(); }
            lastTouchEnd = now;
        }, { passive: false });

        let ws;
        let myId;
        let myName;
        let pendingTargetId = null;
        let selectedFiles = []; // 改为数组存储多个文件
        let currentRequestSender = null;
        let currentDevices = []; 
        let currentReceivedText = ""; 
        let globalBubbleSize = 90;

        window.onload = () => { connect(); };

        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024, sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function showToast(msg) {
            const toast = document.getElementById("toast");
            toast.textContent = msg;
            toast.style.display = "block";
            toast.style.animation = 'none';
            toast.offsetHeight; 
            toast.style.animation = null; 
            setTimeout(() => { toast.style.display = "none"; }, 2500);
        }

        function closeModal(id) { document.getElementById(id).style.display = "none"; }

        function joinNetwork() {
            const name = document.getElementById("deviceNameInput").value.trim();
            myName = name || "设备_" + Math.floor(Math.random() * 1000);
            closeModal("loginModal");
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "join", name: myName }));
                showToast("设备名称已更新");
            }
        }

        // --- 干净利落的“装水”逻辑 ---
        function updateProgress(deviceId, percent) {
            const waterEl = document.getElementById(`water-${deviceId}`);
            if (waterEl) {
                waterEl.style.height = `${percent}%`;
                // 装满了，延迟一小会抽干，恢复气泡原样
                if (percent >= 100) {
                    setTimeout(() => {
                        waterEl.style.height = "0%"; 
                    }, 1000);
                }
            }
        }

        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {};

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "your_id") {
                    myId = data.id;
                } else if (data.type === "init_ack") {
                    if (data.name) {
                        myName = data.name;
                        ws.send(JSON.stringify({ type: "join", name: myName })); 
                        showToast(`欢迎回来, ${myName}`);
                    } else {
                        document.getElementById("loginModalTitle").innerText = "加入互传网络";
                        document.getElementById("deviceNameInput").value = "";
                        document.getElementById("loginModal").style.display = "flex";
                    }
                } else if (data.type === "devices") {
                    currentDevices = data.list;
                    renderBubbles(currentDevices);
                } else if (data.type === "text_msg") {
                    currentReceivedText = data.text; 
                    document.getElementById("textSender").innerText = `来自：${data.from_name}`;
                    document.getElementById("textMessage").innerHTML = data.text.replace(/\\n/g, '<br>');
                    document.getElementById("textModal").style.display = "flex";
                } else if (data.type === "file_request") {
                    currentRequestSender = data.from_id;
                    
                    // 构造接收多文件的提示信息
                    let fileListHtml = data.file_names.length > 3 
                        ? data.file_names.slice(0, 3).join("<br>") + `<br>...等 ${data.file_count} 个文件`
                        : data.file_names.join("<br>");

                    const msg = `来自 <b>${data.from_name}</b> 分享了 ${data.file_count} 个文件：<br><br><span style="font-size:14px;">${fileListHtml}</span><br><br>总计: ${formatBytes(data.total_size)}<br><br>是否全部接收？`;
                    
                    document.getElementById("modalMessage").innerHTML = msg;
                    document.getElementById("transferModal").style.display = "flex";
                } else if (data.type === "file_response") {
                    if (data.accept) {
                        showToast("对方已同意，正在发送文件...");
                        uploadFile(data.from_id);
                    } else {
                        showToast("对方拒绝了您的文件。");
                        selectedFiles = []; // 清空选中的文件
                    }
                } else if (data.type === "progress") {
                    // 接收方同步更新
                    updateProgress(data.from_id, data.progress);
                } else if (data.type === "file_ready") {
                    if (data.files && data.files.length > 0) {
                        showToast(`开始下载 ${data.files.length} 个文件...`);
                        // 稍微延迟间隔下载，防止浏览器拦截批量弹窗
                        data.files.forEach((fileInfo, index) => {
                            setTimeout(() => {
                                downloadFile(fileInfo.url, fileInfo.file_name);
                            }, index * 300);
                        });
                    }
                }
            };
            ws.onclose = () => { showToast("连接断开，正在尝试重连..."); setTimeout(connect, 2000); };
        }

        function copyMessage() {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(currentReceivedText).then(() => {
                    showToast("✅ 已复制到剪贴板");
                }).catch(() => fallbackCopyTextToClipboard(currentReceivedText));
            } else {
                fallbackCopyTextToClipboard(currentReceivedText);
            }
        }

        function fallbackCopyTextToClipboard(text) {
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.top = "0";
            textArea.style.left = "0";
            textArea.style.position = "fixed";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                const successful = document.execCommand('copy');
                if(successful) showToast("✅ 已复制到剪贴板");
                else showToast("❌ 复制失败，请手动选择复制");
            } catch (err) {
                showToast("❌ 复制失败，请手动选择复制");
            }
            document.body.removeChild(textArea);
        }

        function renderBubbles(devices) {
            const container = document.getElementById("bubbleContainer");
            container.innerHTML = "";
            
            let myDevice = devices.find(d => d.id === myId);
            let others = devices.filter(d => d.id !== myId);

            const minDim = Math.min(container.clientWidth, container.clientHeight);
            globalBubbleSize = Math.max(80, Math.min(minDim * 0.15, 200));
            const radius = Math.max(120, Math.min(minDim * 0.35, minDim / 2 - globalBubbleSize / 2 - 10));

            if (myDevice) createBubbleNode(myDevice, container, true, 0, 0, globalBubbleSize);

            others.forEach((dev, index) => {
                const angle = (index / others.length) * 2 * Math.PI - (Math.PI / 2);
                const x = radius * Math.cos(angle);
                const y = radius * Math.sin(angle);
                createBubbleNode(dev, container, false, x, y, globalBubbleSize);
            });
        }

        function createBubbleNode(dev, container, isSelf, offsetX, offsetY, size) {
            const wrap = document.createElement("div");
            wrap.className = "bubble-wrap";
            wrap.style.width = `${size}px`;
            wrap.style.height = `${size}px`;
            wrap.style.left = `calc(50% - ${size / 2}px + ${offsetX}px)`;
            wrap.style.top = `calc(50% - ${size / 2}px + ${offsetY}px)`;
            wrap.style.zIndex = isSelf ? 10 : 5;

            // 气泡主体
            const bubble = document.createElement("div");
            bubble.className = "bubble" + (isSelf ? " self" : "");

            // 纯净水层
            const water = document.createElement("div");
            water.className = "water";
            water.id = `water-${dev.id}`;
            bubble.appendChild(water);

            // 文字层
            const textSpan = document.createElement("span");
            textSpan.className = "bubble-text";
            const fontSize = Math.max(12, Math.min(size * 0.15, 18));
            textSpan.style.fontSize = `${fontSize}px`;
            const mark = isSelf ? `<br><span style='font-size:${fontSize*0.8}px;opacity:0.8'>(我)</span>` : "";
            textSpan.innerHTML = dev.name + mark;
            bubble.appendChild(textSpan);

            // 初始随机偏移量
            const movementRange = size * 0.2;
            bubble.style.marginTop = `${(Math.random() - 0.5) * movementRange}px`;
            bubble.style.marginLeft = `${(Math.random() - 0.5) * movementRange}px`;

            if (isSelf) {
                setupSelfInteraction(bubble); 
            } else {
                setupBubbleInteraction(bubble, dev.id, dev.name); 
            }

            wrap.appendChild(bubble);
            container.appendChild(wrap);
        }

        window.addEventListener('resize', () => {
            if (currentDevices.length > 0) renderBubbles(currentDevices);
        });

        setInterval(() => {
            document.querySelectorAll('.bubble').forEach(b => {
                const movementRange = globalBubbleSize * 0.4;
                const mt = (Math.random() - 0.5) * movementRange;
                const ml = (Math.random() - 0.5) * movementRange;
                b.style.marginTop = `${mt}px`;
                b.style.marginLeft = `${ml}px`;
            });
        }, 2500); 

        function setupSelfInteraction(element) {
            let pressTimer;
            let isLongPress = false;
            let isTouch = false;

            element.addEventListener('contextmenu', e => e.preventDefault());

            const startPress = (e) => {
                if (e.type === 'touchstart') isTouch = true;
                if (e.type === 'mousedown' && isTouch) return;
                isLongPress = false;
                pressTimer = setTimeout(() => {
                    isLongPress = true;
                    document.getElementById("loginModalTitle").innerText = "修改设备名称";
                    document.getElementById("deviceNameInput").value = myName;
                    document.getElementById("loginModal").style.display = "flex";
                }, 500); 
            };

            const endPress = (e) => {
                if (e.cancelable) e.preventDefault();
                if (e.type === 'touchend' || e.type === 'touchcancel') isTouch = true;
                if (e.type === 'mouseup' && isTouch) return;
                clearTimeout(pressTimer);
            };

            element.addEventListener('mousedown', startPress);
            element.addEventListener('mouseup', endPress);
            element.addEventListener('mouseleave', () => clearTimeout(pressTimer));
            element.addEventListener('touchstart', startPress, {passive: false});
            element.addEventListener('touchend', endPress, {passive: false});
            element.addEventListener('touchcancel', endPress, {passive: false});
        }

        function setupBubbleInteraction(element, targetId, targetName) {
            let pressTimer;
            let isLongPress = false;
            let isTouch = false;

            element.addEventListener('contextmenu', e => e.preventDefault());

            const startPress = (e) => {
                if (e.type === 'touchstart') isTouch = true;
                if (e.type === 'mousedown' && isTouch) return;
                isLongPress = false;
                pressTimer = setTimeout(() => {
                    isLongPress = true;
                    pendingTargetId = targetId;
                    document.getElementById("inputTitle").innerText = `向 [${targetName}] 发送消息`;
                    document.getElementById("inputText").value = "";
                    document.getElementById("inputModal").style.display = "flex";
                }, 500); 
            };

            const endPress = (e) => {
                if (e.cancelable) e.preventDefault();
                if (e.type === 'touchend' || e.type === 'touchcancel') isTouch = true;
                if (e.type === 'mouseup' && isTouch) return;
                clearTimeout(pressTimer);
                if (!isLongPress) {
                    pendingTargetId = targetId;
                    document.getElementById('fileInput').click();
                }
            };

            element.addEventListener('mousedown', startPress);
            element.addEventListener('mouseup', endPress);
            element.addEventListener('mouseleave', () => clearTimeout(pressTimer));
            element.addEventListener('touchstart', startPress, {passive: false});
            element.addEventListener('touchend', endPress, {passive: false});
            element.addEventListener('touchcancel', endPress, {passive: false});
        }

        function sendTextMessage() {
            const text = document.getElementById("inputText").value;
            if (text && text.trim() !== "") {
                ws.send(JSON.stringify({ type: "text_msg", to_id: pendingTargetId, text: text }));
                showToast("消息已发送");
            }
            closeModal("inputModal");
        }

        // 修改：处理多文件选择并发起请求
        document.getElementById('fileInput').addEventListener('change', (e) => {
            if (e.target.files.length > 0 && pendingTargetId) {
                selectedFiles = Array.from(e.target.files);
                
                let totalSize = selectedFiles.reduce((acc, f) => acc + f.size, 0);
                let fileNames = selectedFiles.map(f => f.name);

                ws.send(JSON.stringify({
                    type: "file_request",
                    to_id: pendingTargetId,
                    file_names: fileNames,
                    total_size: totalSize,
                    file_count: selectedFiles.length
                }));
                showToast("已发送请求，等待对方确认...");
            }
            e.target.value = ""; // 重置 input 方便下次选择同名文件
        });

        function acceptFile() {
            closeModal("transferModal");
            showToast("准备接收文件...");
            ws.send(JSON.stringify({ type: "file_response", to_id: currentRequestSender, accept: true }));
        }
        
        function rejectFile() {
            closeModal("transferModal");
            ws.send(JSON.stringify({ type: "file_response", to_id: currentRequestSender, accept: false }));
        }

        function uploadFile(targetId) {
            if (!selectedFiles || selectedFiles.length === 0) return;
            const formData = new FormData();
            
            // 将所有文件附加到 formData 中
            selectedFiles.forEach(file => {
                formData.append("files", file); 
            });
            formData.append("to_id", targetId);

            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload", true);

            xhr.upload.onprogress = function(event) {
                if (event.lengthComputable) {
                    let percent = Math.floor((event.loaded / event.total) * 100);
                    updateProgress(targetId, percent);
                    ws.send(JSON.stringify({ type: "progress", to_id: targetId, progress: percent }));
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    showToast("文件发送成功！");
                    updateProgress(targetId, 100);
                    ws.send(JSON.stringify({ type: "progress", to_id: targetId, progress: 100 }));
                } else {
                    showToast("文件发送失败");
                    updateProgress(targetId, 0); 
                    ws.send(JSON.stringify({ type: "progress", to_id: targetId, progress: 0 }));
                }
                selectedFiles = []; // 上传完毕清理
            };

            xhr.onerror = function() {
                showToast("上传出错");
                updateProgress(targetId, 0);
                ws.send(JSON.stringify({ type: "progress", to_id: targetId, progress: 0 }));
                selectedFiles = [];
            };

            xhr.send(formData);
        }

        function downloadFile(url, fileName) {
            const a = document.createElement("a");
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# WebSocket 连接管理器
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.device_names: dict[str, str] = {}
        self.ip_name_map: dict[str, str] = load_devices()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        client_ip = websocket.client.host
        return client_id, client_ip

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.device_names.pop(client_id, None)

    async def broadcast_devices(self):
        devices = [{"id": cid, "name": name} for cid, name in self.device_names.items()]
        for connection in self.active_connections.values():
            try:
                await connection.send_text(json.dumps({"type": "devices", "list": devices}))
            except Exception:
                pass

    async def send_to(self, target_id: str, message: dict):
        if target_id in self.active_connections:
            try:
                await self.active_connections[target_id].send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

# ---------------------------------------------------------
# 路由设定
# ---------------------------------------------------------
@app.get("/")
async def get_home():
    return HTMLResponse(HTML_CONTENT)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id, client_ip = await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "your_id", "id": client_id}))
        
        known_name = manager.ip_name_map.get(client_ip, "")
        await websocket.send_text(json.dumps({"type": "init_ack", "name": known_name}))

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg["type"] == "join":
                name = msg.get("name", "Unknown")
                manager.device_names[client_id] = name
                manager.ip_name_map[client_ip] = name
                save_devices(manager.ip_name_map)
                
                await manager.broadcast_devices()
                
            elif msg["type"] == "text_msg":
                await manager.send_to(msg.get("to_id"), {
                    "type": "text_msg",
                    "from_name": manager.device_names.get(client_id, "Unknown"),
                    "text": msg.get("text")
                })
                
            elif msg["type"] == "file_request":
                # 修改：同步支持多文件的请求数据传输
                await manager.send_to(msg.get("to_id"), {
                    "type": "file_request",
                    "from_id": client_id,
                    "from_name": manager.device_names.get(client_id, "Unknown"),
                    "file_names": msg.get("file_names", []),
                    "total_size": msg.get("total_size", 0),
                    "file_count": msg.get("file_count", 0)
                })
                
            elif msg["type"] == "file_response":
                await manager.send_to(msg.get("to_id"), {
                    "type": "file_response",
                    "from_id": client_id,
                    "accept": msg.get("accept")
                })
                
            elif msg["type"] == "progress":
                await manager.send_to(msg.get("to_id"), {
                    "type": "progress",
                    "from_id": client_id, 
                    "progress": msg.get("progress")
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast_devices()

# 修改：支持 List[UploadFile] 多文件上传
@app.post("/upload")
async def upload_files(to_id: str = Form(...), files: List[UploadFile] = File(...)):
    file_info_list = []
    
    for file in files:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(TEMP_DIR, file_id)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_info_list.append({
            "url": f"/download/{file_id}/{file.filename}",
            "file_name": file.filename
        })
        
    await manager.send_to(to_id, {
        "type": "file_ready",
        "files": file_info_list # 把多文件的链接列表打包发给接收方
    })
    return {"status": "ok"}

# 修改：加入 BackgroundTasks 阅后即焚（下载完立即删除服务器本地的临时文件）
@app.get("/download/{file_id}/{file_name}")
async def download_file(file_id: str, file_name: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(TEMP_DIR, file_id)
    if os.path.exists(file_path):
        
        # 定义一个删除文件的后台任务
        def remove_temp_file():
            try:
                os.remove(file_path)
            except Exception as e:
                pass
                
        # 挂载到 background_tasks，FastAPI会在文件响应流结束（下载完成）后自动调用它
        background_tasks.add_task(remove_temp_file)
        
        return FileResponse(path=file_path, filename=file_name)
    return {"error": "File not found or already deleted"}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

if __name__ == "__main__":
    ip = get_local_ip()
    print("="*60)
    print(f"🚀 服务已启动！")
    print(f"👉 复制链接在浏览器中打开: http://{ip}:8001")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=8001, use_colors=False)