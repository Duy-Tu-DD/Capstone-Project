import sys
import socket
from datetime import datetime
import threading
import time
from tracemalloc import reset_peak
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import egm_pb2 as egm
from lxml import etree
import cv2
import mediapipe as mp
from PyQt5.QtCore import pyqtSignal, QThread, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton,QMessageBox, QHBoxLayout, QSlider, QGroupBox, 
    QGridLayout, QComboBox, QCompleter, QStyle, QTextEdit,QTabWidget)
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtCore import Qt,QTimer,pyqtSignal
from collections import deque
import numpy as np
import pyqtgraph as pg
from ws4py.client.threadedclient import WebSocketClient
import xml.etree.ElementTree as ET
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== Global Variables ====================
Pos = [500.0, 0.0, 600.0] 
Euler = [0.0, 0.0, 0.0]
num = 0
lock = threading.Lock()

# ==================== EGM Handler ===================
class ReceiveThread(QThread):
    update_feedback = pyqtSignal(float, float, float,float, float, float)
    update_egm_state = pyqtSignal(str)

    def __init__(self, sock):
        super().__init__()
        self.sock = sock
        self.running = True

    def run(self):
        global num  
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
                msg = egm.EgmRobot()
                msg.ParseFromString(data)
                num = msg.header.seqno + 1
                self.update_feedback.emit(msg.feedBack.cartesian.pos.x,
                                          msg.feedBack.cartesian.pos.y,
                                          msg.feedBack.cartesian.pos.z,
                                          msg.feedBack.cartesian.euler.x,
                                          msg.feedBack.cartesian.euler.y,
                                          msg.feedBack.cartesian.euler.z)   
                self.update_egm_state.emit(egm.EgmMCIState.MCIStateType.Name(msg.mciState.state))
            except Exception as e:
                print("EGM receive error:", e)
                time.sleep(0.01)

def CreateSensorMessage(seq_num, pos, euler):
    egmSensor = egm.EgmSensor()
    egmSensor.header.seqno = seq_num
    egmSensor.header.mtype = egm.EgmHeader.MessageType.MSGTYPE_CORRECTION
    pose = egmSensor.planned.cartesian
    pose.pos.x, pose.pos.y, pose.pos.z = pos
    pose.euler.x, pose.euler.y, pose.euler.z = euler
    return egmSensor

class SendThread(QThread):
    def __init__(self, sock, addr):
        super().__init__()
        self.sock = sock
        self.addr = addr
        self.running = True

    def run(self):
        global num, Pos, Euler
        while self.running:
            with lock:
                pos = Pos.copy()
                euler = Euler.copy()
            msg = CreateSensorMessage(num, pos, euler)
            self.sock.sendto(msg.SerializeToString(), self.addr)
            num += 1
            time.sleep(0.004)

# ==================== RWS Handler ====================
class RwsWebSocketClient(WebSocketClient):
    def __init__(self, url, headers, parent=None):
        super().__init__(url, protocols=['rws_subscription'], headers=headers)
        self.parent = parent
    def opened(self):
        print("RWS WebSocket connection established")
    def closed(self, code, reason=None):
        print(f"RWS WebSocket closed: {code} - {reason}")
    def received_message(self, message):
        if message.is_text:
            try:
                self.parent.process_rws_event(message.data.decode('utf-8'))
            except Exception as e:
                print(f"Error processing message: {e}")

class RwsClient:
    def __init__(self, ip, port=443, username="Admin", password="robotics"):
        self.session = requests.Session()
        self.ip = ip
        self.port = port
        self.base_url = f"https://{ip}:{port}/rw/"
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Accept": "application/xhtml+xml;v=2.0"}
        self.post_headers = {
            "Content-Type": "application/x-www-form-urlencoded;v=2.0",
            "Accept": "application/xhtml+xml;v=2.0"
        }   
        self.reg_url = f"https://{ip}:{port}/users/register/local"
        self.identity_url = f"https://{ip}:{port}/ctrl/identity"
        self.subscription_url = f"https://{ip}:{port}/subscription"
        self.ws_client = None
        self.subscription_thread = None
        self.running = False
    
    def register_user_local(self):
        try:
            url = self.reg_url
            data = {    
                "username": "abc",
                "application": "RobotStudio",
                "location" : "Labbr",
                "local-key" : "123456"
            }
            r = self.session.post(url, data=data,
                              headers=self.post_headers,
                              auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    
    def get_identity(self):
        try:
            response = self.session.get(
                self.identity_url,
                headers=self.headers,
                auth=self.auth,
                verify=False
            )
        
            if response.status_code != 200:
                return {"error": f"HTTP Error: {response.status_code}"}

            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        
            name = root.xpath(
                './/xhtml:li[@class="ctrl-identity-info"]/xhtml:span[@class="ctrl-name"]/text()',
                namespaces=ns
            )
            ctrl_type = root.xpath(
                './/xhtml:li[@class="ctrl-identity-info"]/xhtml:span[@class="ctrl-type"]/text()',
                namespaces=ns
            )

            return {
                "name": name[0].strip() if name else "N/A",
                "type": ctrl_type[0].strip() if ctrl_type else "N/A"
            }

        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

    def set_opmode(self, mode):
        try:
            r = self.session.post(self.base_url + "panel/opmode", 
                                  data={"opmode": mode},
                                  headers=self.post_headers,
                                  auth=self.auth, verify=False)
        
            return r.status_code
        except Exception as e:
            return str(e)
    
    def opmode_ack(self):
        try:
            r = self.session.post(self.base_url + "/panel/opmode/acknowledge", 
                                  data={"opmode": "auto"}, 
                                  headers=self.post_headers,
                                  auth=self.auth, verify=False)
        
            return r.status_code
        except Exception as e:
            return str(e)

    def get_opmde(self):
        try:
            response = self.session.get(
                self.base_url + "/panel/opmode",
                headers=self.headers,
                auth=self.auth,
                verify=False,
                timeout=2
            )
            if response.status_code != 200:
                return f"HTTP Error: {response.status_code}"
            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            state = root.xpath(
                './/xhtml:li[@class="pnl-opmode"]/xhtml:span[@class="opmode"]/text()',
                namespaces=ns
            )
            return state[0].strip().lower() if state else "unknown"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def set_ctrl_state(self, state):
        try:
            r = self.session.post(self.base_url + "panel/ctrl-state",
                                  data={"ctrl-state": state},
                                  headers=self.post_headers,
                                  auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    
    def get_ctrl_state(self):
        try:
            response = self.session.get(
                self.base_url + "panel/ctrl-state",
                headers=self.headers,
                auth=self.auth,
                verify=False,
                timeout=2
            )
            if response.status_code != 200:
                return f"HTTP Error: {response.status_code}"
            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            state = root.xpath(
                './/xhtml:li[@class="pnl-ctrlstate"]/xhtml:span[@class="ctrlstate"]/text()',
                namespaces=ns
            )
            return state[0].strip().lower() if state else "unknown"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def start_rapid(self):
        try:
            url = self.base_url + "rapid/execution/start"
            data = {
                "regain": "continue",
                "execmode": "continue",
                "cycle": "forever",
                "condition": "none",
                "stopatbp": "disabled",
                "alltaskbytsp": "false"
            }
            r = self.session.post(url, data=data,
                              headers=self.post_headers,
                              auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    
    def stop_rapid(self):
        try:
            url = self.base_url + "rapid/execution/stop?mastership=implicit"
            data = {
                "stopmode": "stop",
                "usetsp": "true"
            }
            r = self.session.post(url, data=data,
                              headers=self.post_headers,
                              auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    
    def reset_rapid(self):
        try:
            url = self.base_url + "rapid/execution/resetpp?mastership=implicit"
            data = {             
            }
            r = self.session.post(url, data=data,
                              headers=self.post_headers,
                              auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    
    def get_rapid_state(self):
        try:
            response = self.session.get(
                self.base_url + "/rapid/execution",
                headers=self.headers,
                auth=self.auth,
                verify=False,
                timeout=2
            )
            if response.status_code != 200:
                return f"HTTP Error: {response.status_code}"
            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            state = root.xpath(
                './/xhtml:li[@class="rap-execution"]/xhtml:span[@class="ctrlexecstate"]/text()',
                namespaces=ns
            )
            return state[0].strip().lower() if state else "unknown"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def set_IO(self, lvalue):
        try:
            r = self.session.post(self.base_url + "/iosystem/signals/EtherNetIP/ABB_Scalable_IO1/ABB_Scalable_IO1_0_DO2/set-value", 
                            data={"lvalue": lvalue}, 
                            headers=self.post_headers, auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    def get_IO_state(self):
        try:
            response = self.session.get(
                self.base_url + "/iosystem/signals/EtherNetIP/ABB_Scalable_IO1/ABB_Scalable_IO1_0_DO2",
                headers=self.headers,
                auth=self.auth,
                verify=False,
                timeout=2   
            )
            if response.status_code != 200:
                return f"HTTP Error: {response.status_code}"
            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            state = root.xpath(
                './/xhtml:li[@class="ios-signal-li"]/xhtml:span[@class="lvalue"]/text()',
                namespaces=ns
            )
            return state[0].strip().lower() if state else "unknown"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def set_speed(self, ratio):
        try:
            r = self.session.post(self.base_url + "panel/speedratio?mastership=implicit", 
                            data={"speed-ratio": str(ratio)}, 
                            headers=self.post_headers, auth=self.auth, verify=False)
            return r.status_code
        except Exception as e:
            return str(e)
    def get_speed(self):
        try:
            response = self.session.get(
                self.base_url + "panel/speedratio",
                headers=self.headers,
                auth=self.auth,
                verify=False,
                timeout=2
            )
            if response.status_code != 200:
                return f"HTTP Error: {response.status_code}"
            root = etree.fromstring(response.content)
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            speed_1 = root.xpath(
                './/xhtml:li[@class="pnl-speedratio"]/xhtml:span[@class="speedratio"]/text()',
                namespaces=ns
            )
            return int(speed_1[0].strip().lower()) if speed_1 else "unknown"
        except Exception as e:
            return f"Error: {str(e)}"

    def subscribe(self, parent):
        try:
            payload = {
                'resources': ['1','2','3'],
                '1': '/rw/panel/speedratio',
                '1-p': '1',
                '2': '/rw/panel/ctrl-state',
                '2-p': '1',
                '3': '/rw/panel/opmode',
                '3-p': '1'
            }
            
            resp = self.session.post(self.subscription_url, 
                                    auth=self.auth, 
                                    headers=self.post_headers, 
                                    data=payload, 
                                    verify=False)
            
            if resp.status_code == 201:
                location = resp.headers['Location']
                
                cookies = []
                for cookie in self.session.cookies:
                    cookies.append(f"{cookie.name}={cookie.value}")
                cookie_str = "; ".join(cookies)
              
                auth_header = HTTPBasicAuth(self.auth.username, self.auth.password)
                auth_value = auth_header(self.session).headers['Authorization']
                
                headers = [
                    ('Cookie', cookie_str),
                    ('Authorization', auth_value)  
                ]
                ws_url = location.replace('https://', 'wss://')
                
                self.ws_client = RwsWebSocketClient(ws_url, headers, parent)
                self.subscription_thread = threading.Thread(target=self.ws_client.connect)
                self.subscription_thread.daemon = True
                self.subscription_thread.start()
                return True
            else:
                print(f"Failed to subscribe: {resp.status_code}")
                return False
        except Exception as e:
            print(f"Subscription error: {e}")
            return False

#================================CAMERA Hanlder===================================
class HandDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1)
        self.mp_draw = mp.solutions.drawing_utils

    def find_hands(self, frame):
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)
        hand_landmarks = []

        if results.multi_hand_landmarks:
            for hand_landmark in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame, hand_landmark, self.mp_hands.HAND_CONNECTIONS)

                h, w, _ = frame.shape
                landmarks = []
                for id, lm in enumerate(hand_landmark.landmark):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    landmarks.append([id, cx, cy])
                if landmarks:
                    hand_landmarks.append(landmarks)

        return frame, hand_landmarks

    def count_fingers(self, landmarks):
        if not landmarks:
            return -1

        finger_indices = [4, 8, 12, 16, 20]
        count = 0

        if landmarks[finger_indices[0]][1] < landmarks[finger_indices[0] - 1][1]:
            count += 1

        for idx in finger_indices[1:]:
            if landmarks[idx][2] < landmarks[idx - 2][2]:
                count += 1

        return count

def is_hand_in_area(x, y, w, h, landmarks):
    if not landmarks:
        return False
    for hand in landmarks:
        for _, lx, ly in hand:
            if x < lx < x + w and y < ly < y + h:
                return True
    return False

def draw_button(frame, x, y, w, h, text, color=None, font_scale=0.5, thickness=1, bg_color=(200, 200, 200)):
    if color is None:
        color = (0, 0, 0) 
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, 1) 
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    tx = x + (w - tw) // 2
    ty = y + (h + th) // 2
    cv2.putText(frame, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

class CameraThread(QThread):
    frame_processed = pyqtSignal(QImage, list)
    button_pressed = pyqtSignal(str)
    gripper_changed = pyqtSignal(bool)
    reset_xyz_requested = pyqtSignal()
    reset_rxyz_requested = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.detector = HandDetector()
        self.running = False
        self.process_hands = False
        self.camera_index = 0
        self.states = {
            'hand_mode': False,
            'current_mode': None,
            'gripper': False,
            'xyz': {'X': 500, 'Y': 0, 'Z': 600},
            'rxyz': {'RX': 180, 'RY': 0, 'RZ': 180},
            'xyz_timers': {'X+': 0, 'X-': 0, 'Y+': 0, 'Y-': 0, 'Z+': 0, 'Z-': 0},
            'rxyz_timers': {'RX+': 0, 'RX-': 0, 'RY+': 0, 'RY-': 0, 'RZ+': 0, 'RZ-': 0},
            'mode_timers': {}}

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        while self.running:
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame")
                continue

            frame = cv2.flip(frame, 1)

            if self.process_hands:
                frame, landmarks = self.detector.find_hands(frame)
                self.process_controls(frame, landmarks)
            else:
                landmarks = []

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
            self.frame_processed.emit(qt_image, landmarks)
    
        cap.release()
        print("Camera thread stopped")

    def process_controls(self, frame, landmarks):
        current_time = time.time()
        # Gripper Control Mode
        if self.states['hand_mode']:
            
            draw_button(frame, 20, 100, 120, 40, "Position Mode", (255,0,255))
            if is_hand_in_area(20, 100, 120, 40, landmarks):
                 if 'position' not in self.states['mode_timers']:
                    self.states['mode_timers']['position'] = current_time
                 elif current_time - self.states['mode_timers']['position'] >= 1.0:
                    self.states['hand_mode'] = False
                    self.states['current_mode'] = 'xyz'
                    del self.states['mode_timers']['position']  
            else:
                if 'position' in self.states['mode_timers']:
                    del self.states['mode_timers']['position'] 
            
            draw_button(frame, 150, 100, 120, 40, "Rotation Mode", (255, 0, 0))
            if is_hand_in_area(150, 100, 120, 40, landmarks):
                 if 'rotation' not in self.states['mode_timers']:
                    self.states['mode_timers']['rotation'] = current_time
                 elif current_time - self.states['mode_timers']['rotation'] >= 1.0:
                    self.states['hand_mode'] = False
                    self.states['current_mode'] = 'rxyz'
                    del self.states['mode_timers']['rotation']
            else:
                if 'rotation' in self.states['mode_timers']:
                    del self.states['mode_timers']['rotation'] 
            
            area_x, area_y = 350, 50
            area_w, area_h = 250, 250
            cv2.rectangle(frame, (area_x, area_y), (area_x + area_w, area_y + area_h), (0, 255, 0), 2)
            
            if is_hand_in_area(area_x, area_y, area_w, area_h, landmarks):
                fingers = self.detector.count_fingers(landmarks[0] if landmarks else [])                
                if fingers in [0, 5]:
                    new_state = (fingers == 0)

                    if new_state != self.states['gripper']:
                        if 'gripper_hold' not in self.states['mode_timers']:
                            self.states['mode_timers']['gripper_hold'] = current_time
                        elif current_time - self.states['mode_timers']['gripper_hold'] >= 1.0: 
                            self.states['gripper'] = new_state
                            self.gripper_changed.emit(new_state)
                            del self.states['mode_timers']['gripper_hold']
                    else:
                        if 'gripper_hold' in self.states['mode_timers']:
                            del self.states['mode_timers']['gripper_hold']
                else:
                    if 'gripper_hold' in self.states['mode_timers']:
                        del self.states['mode_timers']['gripper_hold']
            else:
                
                if 'gripper_hold' in self.states['mode_timers']:
                    del self.states['mode_timers']['gripper_hold'] 

            cv2.putText(frame, f"Gripper: {'ON' if self.states['gripper'] else 'OFF'}",
                        (area_x + 10, area_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
        # XYZ Position Control Mode
        elif self.states['current_mode'] == 'xyz':
            xyz_labels = ['-X', '+X', '-Y', '+Y', '-Z', '+Z']
            
            draw_button(frame, 10, 200, 120, 40, "Hand Mode", (0,255,255))
            if is_hand_in_area(10, 200, 120, 40, landmarks):
                if 'hand_xyz' not in self.states['mode_timers']:
                    self.states['mode_timers']['hand_xyz'] = current_time
                elif current_time - self.states['mode_timers']['hand_xyz'] >= 1.0:
                    self.states['hand_mode'] = True
                    del self.states['mode_timers']['hand_xyz']
            else:
                if 'hand_xyz' in self.states['mode_timers']:
                    del self.states['mode_timers']['hand_xyz'] 
            
            draw_button(frame, 10, 250, 120, 40, "Rotation Mode", (255, 0, 0))
            if is_hand_in_area(10, 250, 120, 40, landmarks):
                if 'rotation_xyz' not in self.states['mode_timers']:
                    self.states['mode_timers']['rotation_xyz'] = current_time
                elif current_time - self.states['mode_timers']['rotation_xyz'] >= 1.0:
                    self.states['current_mode'] = 'rxyz'
                    del self.states['mode_timers']['rotation_xyz']
            else:
                if 'rotation_xyz' in self.states['mode_timers']:
                    del self.states['mode_timers']['rotation_xyz']
            
            for i, label in enumerate(xyz_labels):
                btn_x = 220 + i * 70
                draw_button(frame, btn_x, 30, 60, 40, label, (255,0,255))
                axis = label[1]
                delta = -2 if label[0] == '-' else 2
                key = f'{axis}{label[0]}'
                current_time = time.time()
                if is_hand_in_area(btn_x, 30, 60, 40, landmarks):
                    last_time = self.states['xyz_timers'][key]
                    if last_time == 0 or current_time - last_time > 0.15:
                        self.states['xyz'][axis] += delta
                        self.states['xyz_timers'][key] = current_time
                        self.button_pressed.emit(label)
                else:
                    self.states['xyz_timers'][key] = 0

            draw_button(frame, 150, 30, 60, 40, "Reset", (0, 0, 255))
            if is_hand_in_area(150, 30, 60, 40, landmarks):
                if 'reset_timer' not in self.states['mode_timers']:
                    self.states['mode_timers']['reset_timer'] = current_time
                elif current_time - self.states['mode_timers']['reset_timer'] >= 1.0:
                    self.states['xyz'] = {'X': 500, 'Y': 0, 'Z': 600}
                    self.reset_xyz_requested.emit()
                    del self.states['mode_timers']['reset_timer']
            else:
                if 'reset_timer' in self.states['mode_timers']:
                    del self.states['mode_timers']['reset_timer']
            
            cv2.putText(frame, f"POSITION MODE",(10,20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,255), 2)
        # RXYZ Rotation Control Mode
        elif self.states['current_mode'] == 'rxyz':
            rxyz_labels = ['-RX', '+RX', '-RY', '+RY', '-RZ', '+RZ']

            draw_button(frame,10, 200, 120, 40, "Hand Mode", (0,255,255))
            if is_hand_in_area(10, 200, 120, 40, landmarks):
                if 'hand_rxyz' not in self.states['mode_timers']:
                    self.states['mode_timers']['hand_rxyz'] = current_time
                elif current_time - self.states['mode_timers']['hand_rxyz'] >= 1.0:
                    self.states['hand_mode'] = True
                    del self.states['mode_timers']['hand_rxyz']
            else:
                if 'hand_rxyz' in self.states['mode_timers']:
                    del self.states['mode_timers']['hand_rxyz'] 

            draw_button(frame, 10, 250, 120, 40, "Position Mode", (255,0,255)) 
            if is_hand_in_area(10, 250, 120, 40, landmarks):
                if 'position_rxyz' not in self.states['mode_timers']:
                    self.states['mode_timers']['position_rxyz'] = current_time
                elif current_time - self.states['mode_timers']['position_rxyz'] >= 1.0:
                    self.states['current_mode'] = 'xyz'
                    del self.states['mode_timers']['position_rxyz']
            else:
                if 'position_rxyz' in self.states['mode_timers']:
                    del self.states['mode_timers']['position_rxyz']
                    
            for i, label in enumerate(rxyz_labels):
                    btn_x = 220 + i * 70
                    draw_button(frame, btn_x, 30, 60, 40, label, (255, 0, 0))
                    axis = label[1:] 
                    delta = -0.5 if label[0] == '-' else 0.5
                    current_time = time.time()
                    if is_hand_in_area(btn_x, 30, 60, 40, landmarks):
                        last_time = self.states['rxyz_timers'].get(axis, 0)
                        if last_time == 0 or current_time - last_time > 0.2:  
                            self.states['rxyz'][axis] += delta
                            self.states['rxyz_timers'][axis] = current_time
                            self.button_pressed.emit(label)
                    else:
                        self.states['rxyz_timers'][axis] = 0

            draw_button(frame, 150, 30, 60, 40, "Reset", (0, 0, 255))
            if is_hand_in_area(150, 30, 60, 40, landmarks):
                if 'reset_timer' not in self.states['mode_timers']:
                    self.states['mode_timers']['reset_timer'] = current_time
                elif current_time - self.states['mode_timers']['reset_timer'] >= 1.0:
                    self.states['rxyz'] = {'RX': 180, 'RY': 0, 'RZ': 180}
                    self.reset_rxyz_requested.emit()
                    del self.states['mode_timers']['reset_timer']
            else:
                if 'reset_timer' in self.states['mode_timers']:
                    del self.states['mode_timers']['reset_timer']

            cv2.putText(frame, f"ROTATION MODE",(10,20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
#====================HOLDBUTTON Hanlder============================
class HoldButton(QPushButton):
    pressed = pyqtSignal()
    released = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._handle_repeat)
        self._initial_delay = 300 
        self._repeat_interval = 100 

    def mousePressEvent(self, event):
        self.pressed.emit()
        self._timer.start(self._initial_delay)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.released.emit()
        self._timer.stop()
        super().mouseReleaseEvent(event)

    def _handle_repeat(self):
        self._timer.setInterval(self._repeat_interval)
        self.clicked.emit()

# ==================== GUI ====================
class MainWindow(QWidget):
    speed_changed = pyqtSignal(int)
    opmode_changed = pyqtSignal(str)
    motor_state_changed = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.rws_connected = False
        self.robot_socket = None
        self.initial_pose_received = False
        self.setWindowTitle("CRB15000 Robot Control")
        self.setWindowIcon(QIcon("C:/Users/2002d/Desktop/20TDHCLC1_105200358-QUACHTHIENDUC_105200391-DODANGDUYTU_105200386-NGUYENHUUNAMTHANH/Project_Robot/PythonApplication1/icon.png"))
       
        self.setStyleSheet("""
            QWidget {
                font-family: Segoe UI;
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                color: #555555;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 3px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: #ddd;
                height: 5px;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #409EFF,
                    stop:1 #409EFF
                );
                border: 1px;
                height: 5px;
                border-radius: 2px;
            }

            QSlider::add-page:horizontal {
                background: #ccc;
                border: none;
                height: 5px;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #409EFF;
                width: 14px;             
                margin: -5px 0;           
                border-radius: 6px;
            }

            QSlider::handle:horizontal:hover {
                background: #66baff;
                border: 1px solid #0077cc;
            }
        """)

        #
        self.speed_changed.connect(self.update_speed_ui)
        self.opmode_changed.connect(self.update_opmode_ui)
        self.motor_state_changed.connect(self.update_motor_ui)
        
        
        # ===== Main Layout =====
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)

        

        # ===== Control Layout =====
        main_control_layout = QHBoxLayout()
        main_control_layout.setContentsMargins(0, 0, 0, 0)
        main_control_layout.setSpacing(10)

            # +++++++ Left Panel (EGM) +++++++
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        egm_group = self.create_egm_group()
        left_layout.addWidget(egm_group)
        main_control_layout.addWidget(left_panel, 2)

            # +++++++ Center Panel (CAMERA) +++++++
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        cam_group = self.init_camera_ui()
        center_layout.addWidget(cam_group)
        main_control_layout.addWidget(center_panel, 2)

            # +++++++ Right Panel (RWS) +++++++
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        rws_group = self.create_rws_group()
        right_layout.addWidget(rws_group)
        main_control_layout.addWidget(right_panel, 2)

        # ===== System Log =====
        main_log_layout = QHBoxLayout()
        main_log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(110)
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setIcon(QIcon("D:/2024-2025 KI_2/PythonApplication1/PythonApplication1/trash.png"))
        self.btn_clear_log.clicked.connect(self.clear_log)
        main_log_layout.addWidget(self.log_output, 9)
        main_log_layout.addWidget(self.btn_clear_log, 1)

        #==========================================
        main_layout.addLayout(main_control_layout)
        main_layout.addLayout(main_log_layout)
        self.setLayout(main_layout)

        
        # Khoi tao cameraThread
        self.camera_thread = CameraThread()
        self.camera_thread.frame_processed.connect(self.update_camera_preview)
        self.camera_thread.button_pressed.connect(self.handle_camera_button)
        self.camera_thread.gripper_changed.connect(self.handle_gripper_change)
        self.camera_thread.reset_xyz_requested.connect(self.reset_xyz_position)
        self.camera_thread.reset_rxyz_requested.connect(self.reset_rxyz_rotation)
        # Thread and connection variables
        self.recv_thread = None
        self.send_thread = None
        self.connected = False
        self.addr = None
        self.rws = RwsClient("127.0.0.1")
         
#********Camera Group*************
    def init_camera_ui(self):
        camera_group = QGroupBox("Camera Control")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setContentsMargins(5, 15, 5, 15)
        camera_layout.setSpacing(10)
        
        #Camera Selection
        select_group = QGroupBox()
        select_layout = QHBoxLayout(select_group)
        select_layout.setContentsMargins(10, 10, 10, 10)
        select_layout.addWidget(QLabel("Select Camera:"))
        self.camera_combo = QComboBox()
        self.camera_combo.addItem("Camera 0", 0)
        self.camera_combo.addItem("Camera 1", 1)
        select_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(select_group)

        #Camera Stream
        stream_group = QGroupBox()
        stream_layout = QVBoxLayout(stream_group)
        stream_layout.setContentsMargins(0, 5, 0, 5)
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(750, 550)
        self.camera_label.setAlignment(Qt.AlignCenter)
        stream_layout.addWidget(self.camera_label)
        camera_layout.addWidget(stream_group)
        #Camera Controls
        control_group = QGroupBox()
        control_layout = QGridLayout(control_group)
        #control_layout.setContentsMargins(10, 15, 10, 15)
        self.btn_camera = QPushButton("Start Camera")
        self.btn_camera.clicked.connect(self.toggle_camera)
        self.btn_hand_tracking = QPushButton("Enable Hand Tracking")
        self.btn_hand_tracking.clicked.connect(self.toggle_hand_tracking)
        self.btn_hand_control = QPushButton("Hand Control Mode")
        self.btn_hand_control.clicked.connect(self.toggle_hand_control)
        control_layout.addWidget(self.btn_camera,0,0)
        control_layout.addWidget(self.btn_hand_tracking,0,1)
        control_layout.addWidget(self.btn_hand_control,0,2)
        control_group.setLayout(control_layout)
        camera_layout.addWidget(control_group)

        return camera_group
 
#********Egm Group*************       
    def create_egm_group(self):
        egm_group = QGroupBox("EGM Control")
        egm_layout = QVBoxLayout()
        egm_layout.setContentsMargins(12, 15, 12, 15)
        egm_layout.setSpacing(10)

        # Egm Connect 
        connect_group = QGroupBox()
        conn_layout = QGridLayout()
        self.egm_ip = QLineEdit("192.168.125.10")
        ip_suggest = [
        "192.168.125.10",
        "127.0.0.1"]
        completer = QCompleter(ip_suggest)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.egm_ip.setCompleter(completer)
        self.egm_port = QLineEdit("6510")
        self.btn_connect = QPushButton("Start EGM")
        self.btn_connect.clicked.connect(self.toggle_egm)
        self.btn_connect.setStyleSheet("background-color: #d7e9f9;")
        self.lbl_egm_state = QLabel("EGM State: Unknown")
        conn_layout.addWidget(QLabel("Robot IP:"), 0, 0)
        conn_layout.addWidget(self.egm_ip, 0, 1)
        conn_layout.addWidget(QLabel("Port:"), 1, 0)
        conn_layout.addWidget(self.egm_port, 1, 1)
        conn_layout.addWidget(self.btn_connect, 2, 0, 1, 2)
        conn_layout.addWidget(self.lbl_egm_state,3,0,1,2)
        connect_group.setLayout(conn_layout)
        egm_layout.addWidget(connect_group)
        
        # Position controls
        pos_group = QGroupBox("Position (mm)")
        pos_layout = QVBoxLayout()
        pos_layout.setContentsMargins(10, 20, 10, 10)
        pos_layout.setSpacing(10)
        self.lbl_feedback1 = QLabel("Current Pos: X=0.00 Y=0.00 Z=0.00")
        pos_layout.addWidget(self.lbl_feedback1)
        # X axis controls
        x_layout = QHBoxLayout()
        self.btn_x_minus = HoldButton("-X")
        self.btn_x_minus.pressed.connect(lambda: self.start_adjust(0, -1))
        self.btn_x_minus.released.connect(self.stop_adjust)
        self.lbl_x = QLabel("0.0")
        x_layout.addWidget(self.btn_x_minus)
        x_layout.addWidget(QLabel("X:"))
        x_layout.addWidget(self.lbl_x)
        self.btn_x_plus = HoldButton("+X")
        self.btn_x_plus.pressed.connect(lambda: self.start_adjust(0, 1))
        self.btn_x_plus.released.connect(self.stop_adjust)
        x_layout.addWidget(self.btn_x_plus)
        pos_layout.addLayout(x_layout)

        # Y axis controls
        y_layout = QHBoxLayout()
        self.btn_y_minus = HoldButton("-Y")
        self.btn_y_minus.pressed.connect(lambda: self.start_adjust(1, -1))
        self.btn_y_minus.released.connect(self.stop_adjust)
        self.lbl_y = QLabel("0.0")
        y_layout.addWidget(self.btn_y_minus)
        y_layout.addWidget(QLabel("Y:"))
        y_layout.addWidget(self.lbl_y)
        self.btn_y_plus = HoldButton("+Y")
        self.btn_y_plus.pressed.connect(lambda: self.start_adjust(1, 1))
        self.btn_y_plus.released.connect(self.stop_adjust)
        y_layout.addWidget(self.btn_y_plus)
        pos_layout.addLayout(y_layout)

        # Z axis controls
        z_layout = QHBoxLayout()
        self.btn_z_minus = HoldButton("-Z")
        self.btn_z_minus.pressed.connect(lambda: self.start_adjust(2, -1))
        self.btn_z_minus.released.connect(self.stop_adjust)
        self.lbl_z = QLabel("0.0")
        z_layout.addWidget(self.btn_z_minus)
        z_layout.addWidget(QLabel("Z:"))
        z_layout.addWidget(self.lbl_z)
        self.btn_z_plus = HoldButton("+Z")
        self.btn_z_plus.pressed.connect(lambda: self.start_adjust(2, 1))
        self.btn_z_plus.released.connect(self.stop_adjust)
        z_layout.addWidget(self.btn_z_plus)
        pos_layout.addLayout(z_layout)
        pos_group.setLayout(pos_layout)

        # Rotation controls
        rot_group = QGroupBox("Rotation (degree)")
        rot_layout = QVBoxLayout()
        rot_layout.setContentsMargins(10, 20, 10, 10)
        rot_layout.setSpacing(10)
        self.lbl_feedback2 = QLabel("Current Rot: RX=0.00 RY=0.00 RZ=0.00")
        rot_layout.addWidget(self.lbl_feedback2)
         
        # RX axis controls
        rx_layout = QHBoxLayout()
        self.btn_rx_minus = HoldButton("-RX")
        self.btn_rx_minus.pressed.connect(lambda: self.start_rotate(0, -1))
        self.btn_rx_minus.released.connect(self.stop_rotate)
        self.lbl_rx = QLabel("0.0")
        rx_layout.addWidget(self.btn_rx_minus)
        rx_layout.addWidget(QLabel("RX:"))
        rx_layout.addWidget(self.lbl_rx)
        self.btn_rx_plus = HoldButton("+RX")
        self.btn_rx_plus.pressed.connect(lambda: self.start_rotate(0, 1))
        self.btn_rx_plus.released.connect(self.stop_rotate)
        rx_layout.addWidget(self.btn_rx_plus)
        rot_layout.addLayout(rx_layout)

        # RY axis controls
        ry_layout = QHBoxLayout()
        self.btn_ry_minus = HoldButton("-RY")
        self.btn_ry_minus.pressed.connect(lambda: self.start_rotate(1, -1))
        self.btn_ry_minus.released.connect(self.stop_rotate)
        self.lbl_ry = QLabel("0.0")
        ry_layout.addWidget(self.btn_ry_minus)
        ry_layout.addWidget(QLabel("RY:"))
        ry_layout.addWidget(self.lbl_ry)
        self.btn_ry_plus = HoldButton("+RY")
        self.btn_ry_plus.pressed.connect(lambda: self.start_rotate(1, 1))
        self.btn_ry_plus.released.connect(self.stop_rotate)
        ry_layout.addWidget(self.btn_ry_plus)
        rot_layout.addLayout(ry_layout)

        # RZ axis controls
        rz_layout = QHBoxLayout()
        self.btn_rz_minus = HoldButton("-RZ")
        self.btn_rz_minus.pressed.connect(lambda: self.start_rotate(2, -1))
        self.btn_rz_minus.released.connect(self.stop_rotate)
        self.lbl_rz = QLabel("0.0")
        rz_layout.addWidget(self.btn_rz_minus)
        rz_layout.addWidget(QLabel("RZ:"))
        rz_layout.addWidget(self.lbl_rz)
        self.btn_rz_plus = HoldButton("+RZ")
        self.btn_rz_plus.pressed.connect(lambda: self.start_rotate(2, 1))
        self.btn_rz_plus.released.connect(self.stop_rotate)
        rz_layout.addWidget(self.btn_rz_plus)
        rot_layout.addLayout(rz_layout)
        rot_group.setLayout(rot_layout)

        egm_layout.addWidget(pos_group)
        egm_layout.addWidget(rot_group)      
        egm_group.setLayout(egm_layout)
        
        return egm_group
#********Robot Web Services Group*************
    def create_rws_group(self):
        rws_group = QGroupBox("RWS Control")
        rws_layout = QVBoxLayout()
        rws_layout.setContentsMargins(10, 15, 10,10)
        rws_layout.setSpacing(10)
        
        # RWS Connect
        connect_group = QGroupBox()
        connect_layout = QGridLayout()
        connect_layout.setContentsMargins(10, 10, 10, 10)
        connect_layout.setVerticalSpacing(10)
        connect_layout.setHorizontalSpacing(20)
        self.rws_ip = QLineEdit("192.168.125.1")
        ip_suggestions = [
        "192.168.125.1",
        "127.0.0.1"]
        completer = QCompleter(ip_suggestions)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.rws_ip.setCompleter(completer)
        self.rws_port = QLineEdit("443")
        self.rws_user = QLineEdit("Admin")
        user_suggestions = [
        "Admin",
        "Default User"]
        completer = QCompleter(user_suggestions)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.rws_user.setCompleter(completer)
        self.rws_pass = QLineEdit("robotics")
        self.rws_pass.setEchoMode(QLineEdit.Password)
        self.btn_rws_connect = QPushButton("Connect RWS")
        self.btn_rws_connect.setStyleSheet("background-color: #d7e9f9;")
    
        connect_layout.addWidget(QLabel("IP:"), 0, 0)
        connect_layout.addWidget(self.rws_ip, 0, 1)
        connect_layout.addWidget(QLabel("Port:"), 1, 0)
        connect_layout.addWidget(self.rws_port, 1, 1)
        connect_layout.addWidget(QLabel("Username:"), 2, 0)
        connect_layout.addWidget(self.rws_user, 2, 1)
        connect_layout.addWidget(QLabel("Password:"), 3, 0)
        connect_layout.addWidget(self.rws_pass, 3, 1)
        connect_layout.addWidget(self.btn_rws_connect, 4, 0, 1, 2)
        connect_group.setLayout(connect_layout)
        self.btn_rws_connect.clicked.connect(self.toggle_rws_connection)
        rws_layout.addWidget(connect_group)
        
        # Identity section
        iden_group = QGroupBox("Controller Information")
        iden_layout = QVBoxLayout()
        iden_layout.setContentsMargins(10, 20, 10, 10)
        iden_layout.setSpacing(10)
        
        identity_layout = QHBoxLayout()
        self.lbl_identity = QLabel("Controller Infor: Unknown")
        self.lbl_identity.setWordWrap(True)
        identity_layout.addWidget(self.lbl_identity, 1)
        iden_layout.addLayout(identity_layout)
        iden_group.setLayout(iden_layout)
        rws_layout.addWidget(iden_group)
        
        #Gripper Control 
        IO_layout = QVBoxLayout()
        IO_button_layout = QHBoxLayout()
        self.lbl_IO_status = QLabel("Gripper Status:Unknown")
        self.btn_on_io = QPushButton("ON Gripper")
        self.btn_on_io.setStyleSheet("background-color: #d4edda;")
        self.btn_on_io.clicked.connect(self.ON_IO)
        self.btn_off_io = QPushButton("OFF Gripper")
        self.btn_off_io.setStyleSheet("background-color: #f8d7da;")
        self.btn_off_io.clicked.connect(self.OFF_IO)
        IO_button_layout.addWidget(self.btn_on_io)
        IO_button_layout.addWidget(self.btn_off_io)
        IO_layout.addWidget(self.lbl_IO_status)
        IO_layout.addLayout(IO_button_layout)    
        rws_layout.addLayout(IO_layout)
        
        #Operation Mode Control
        Mode_layout = QVBoxLayout()
        Mode_button_layout = QHBoxLayout()
        self.lbl_opmode = QLabel("Operation Mode: Unknown")
        self.btn_mode_Auto = QPushButton("AUTO")
        self.btn_mode_Auto.setStyleSheet("background-color: #d4edda;")
        self.btn_mode_Auto.clicked.connect(self.mode_auto)
        self.btn_mode_Man = QPushButton("MANUAL")
        self.btn_mode_Man.setStyleSheet("background-color: #f8d7da;")
        self.btn_mode_Man.clicked.connect(self.mode_man)
        Mode_layout.addWidget(self.lbl_opmode)
        Mode_button_layout.addWidget(self.btn_mode_Auto)
        Mode_button_layout.addWidget(self.btn_mode_Man)
        Mode_layout.addLayout(Mode_button_layout)
        rws_layout.addLayout(Mode_layout)
        
        # Motor controls
        motor_layout = QVBoxLayout()
        motor_button_layout = QHBoxLayout()
        self.lbl_motor_status = QLabel("Motor Status: Unknown")
        self.btn_motor_on = QPushButton("Motor ON")
        self.btn_motor_on.setStyleSheet("background-color: #d4edda;")
        self.btn_motor_on.clicked.connect(self.motor_on)
        self.btn_motor_off = QPushButton("Motor OFF")
        self.btn_motor_off.setStyleSheet("background-color: #f8d7da;")
        self.btn_motor_off.clicked.connect(self.motor_off)
        motor_layout.addWidget(self.lbl_motor_status)
        motor_button_layout.addWidget(self.btn_motor_on)
        motor_button_layout.addWidget(self.btn_motor_off)
        motor_layout.addLayout(motor_button_layout)
        rws_layout.addLayout(motor_layout)

        # RAPID controls
        rapid_layout = QVBoxLayout()
        rapid_button_layout = QHBoxLayout()
        self.lbl_rapid_status = QLabel("Rapid Status: Unknown")
        self.btn_start_rapid = QPushButton("  Run")
        self.btn_start_rapid.setIcon(QIcon("C:/Users/2002d/Desktop/20TDHCLC1_105200358-QUACHTHIENDUC_105200391-DODANGDUYTU_105200386-NGUYENHUUNAMTHANH/Project_Robot/PythonApplication1/play.png"))
        self.btn_start_rapid.setStyleSheet("background-color: #d4edda;")
        self.btn_start_rapid.clicked.connect(self.start_rapid)
        self.btn_start_rapid.clicked.connect(self.update_rapid_status)
        self.btn_stop_rapid = QPushButton("  Stop")
        self.btn_stop_rapid.setIcon(QIcon("C:/Users/2002d/Desktop/20TDHCLC1_105200358-QUACHTHIENDUC_105200391-DODANGDUYTU_105200386-NGUYENHUUNAMTHANH/Project_Robot/PythonApplication1/stop.png"))
        self.btn_stop_rapid.setStyleSheet("background-color: #f8d7da;")
        self.btn_stop_rapid.clicked.connect(self.stop_rapid)
        self.btn_stop_rapid.clicked.connect(self.update_rapid_status)
        self.btn_reset_rapid = QPushButton("Reset PP")
        self.btn_reset_rapid.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_reset_rapid.setIcon(QIcon("C:/Users/2002d/Desktop/20TDHCLC1_105200358-QUACHTHIENDUC_105200391-DODANGDUYTU_105200386-NGUYENHUUNAMTHANH/Project_Robot/PythonApplication1/reset.png"))
        self.btn_reset_rapid.setStyleSheet("background-color: #FFFFCC;")
        self.btn_reset_rapid.clicked.connect(self.reset_rapid)
        rapid_layout.addWidget(self.lbl_rapid_status)
        rapid_button_layout.addWidget(self.btn_start_rapid)
        rapid_button_layout.addWidget(self.btn_stop_rapid)
        rapid_button_layout.addWidget(self.btn_reset_rapid)
        rapid_layout.addLayout(rapid_button_layout)
        rws_layout.addLayout(rapid_layout)

        # Speed control
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("Speed Ratio:"))
        slider_layout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self.set_speed)
        self.lbl_speed = QLabel("100%")
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.lbl_speed)
        speed_layout.addLayout(slider_layout)
        rws_layout.addLayout(speed_layout)
        rws_group.setLayout(rws_layout)
        
        return rws_group
       
    # ==================== EGM Functions ====================
    def toggle_egm(self):
        if not self.connected:
            try:
                # Validate inputs
                computer_ip = self.egm_ip.text()
                robot_port = int(self.egm_port.text())

                # Create new socket
                self.robot_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.robot_socket.bind((computer_ip, robot_port))
                
                print(f"Waiting for EGM connection on {computer_ip}:{robot_port}...")
                data, addr = self.robot_socket.recvfrom(2048)
                print(f"Connected to robot at {addr}")

                self.addr = addr
                self.recv_thread = ReceiveThread(self.robot_socket)
                self.recv_thread.update_feedback.connect(self.update_feedback)
                self.recv_thread.update_egm_state.connect(self.update_egm_state)
                self.recv_thread.start()
                self.send_thread = SendThread(self.robot_socket, self.addr)
                self.send_thread.start()
                self.connected = True
                self.btn_connect.setText("Stop EGM")
                QMessageBox.information(self, "Success", "EGM Started!")
                self.add_log("EGM Started!")
                self.initial_pose_received = False
                
            except ValueError as ve:
                QMessageBox.critical(self, "Input Error", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", str(e))
                if self.robot_socket:
                    self.robot_socket.close()
        else:
            if self.recv_thread: 
                self.recv_thread.running = False
                self.recv_thread.wait()
            if self.send_thread: 
                self.send_thread.running = False
                self.send_thread.wait()
            if self.robot_socket:
                self.robot_socket.close()
            self.connected = False
            self.btn_connect.setText("Start EGM")
            QMessageBox.information(self, "Info", "EGM Stopped!")
            self.add_log("EGM Stopped!")
            self.lbl_egm_state.setText("EGM State: Disconnected")

    def start_adjust(self, axis, direction):
        self.adjust_timer = QTimer()
        self.adjust_timer.timeout.connect(lambda: self.adjust_position(axis, direction))
        self.adjust_timer.start(100) 
        self.adjust_position(axis, direction)

    def stop_adjust(self):
        if hasattr(self, 'adjust_timer'):
            self.adjust_timer.stop()
            del self.adjust_timer

    def adjust_position(self, axis, direction):
        global Pos, lock
        step = 2 * direction
        with lock:
            Pos[axis] += step
            self.camera_thread.states['xyz'][['X','Y','Z'][axis]] = Pos[axis]
            if axis == 0:
                self.lbl_x.setText(f"{Pos[axis]:.1f}")
            elif axis == 1:
                self.lbl_y.setText(f"{Pos[axis]:.1f}")
            elif axis == 2:
                self.lbl_z.setText(f"{Pos[axis]:.1f}")

    def update_feedback(self, x, y, z, rx, ry, rz):
        global Pos, Euler, lock
        if not self.initial_pose_received:
            with lock:
                Pos = [x, y, z]
                Euler = [rx,ry,rz]
        self.lbl_x.setText(f"{x:.1f}")
        self.lbl_y.setText(f"{y:.1f}")
        self.lbl_z.setText(f"{z:.1f}")
        self.lbl_rx.setText(f"{Euler[0]:.1f}")
        self.lbl_ry.setText(f"{Euler[1]:.1f}")
        self.lbl_rz.setText(f"{Euler[2]:.1f}")
            
        self.initial_pose_received = True
        self.lbl_feedback1.setText(
            f"POS: X={x:.2f} Y={y:.2f} Z={z:.2f} "
        )
        self.lbl_feedback2.setText(
            f"RX={rx:.2f} RY={ry:.2f} RZ={rz:.2f}"
        )

    def start_rotate(self, axis, direction):
        self.rotate_timer = QTimer()
        self.rotate_timer.timeout.connect(lambda: self.adjust_rotation(axis, direction))
        self.rotate_timer.start(100)
        self.adjust_rotation(axis, direction)

    def stop_rotate(self):
        if hasattr(self, 'rotate_timer'):
            self.rotate_timer.stop()
            del self.rotate_timer

    def adjust_rotation(self, axis, direction):
        global Euler, lock
        step = 0.5 * direction  
        with lock:
            Euler[axis] += step
            if Euler[axis] > 180:
                Euler[axis] -= 360
            elif Euler[axis] < -180:
                Euler[axis] += 360  
            self.camera_thread.states['rxyz'][['RX','RY','RZ'][axis]] = Euler[axis] 
            if axis == 0:
                self.lbl_rx.setText(f"{Euler[axis]:.1f}")
            elif axis == 1:
                self.lbl_ry.setText(f"{Euler[axis]:.1f}")
            elif axis == 2:
                self.lbl_rz.setText(f"{Euler[axis]:.1f}")

    def update_egm_state(self, state):
        self.lbl_egm_state.setText(f"EGM State: {state}")
    
    def reset_xyz_position(self):
        global Pos, lock
        reset_values = [500.0, 0.0, 600.0]

        with lock:
            Pos = reset_values.copy()
            self.camera_thread.states['xyz'] = {'X': 500, 'Y': 0, 'Z': 600}
        self.lbl_x.setText(f"{reset_values[0]:.1f}")
        self.lbl_y.setText(f"{reset_values[1]:.1f}")
        self.lbl_z.setText(f"{reset_values[2]:.1f}")

    def reset_rxyz_rotation(self):
        global Euler, lock
        reset_rxyz_values = [180.0, 0.0, 180.0]

        with lock:
            Euler = reset_rxyz_values.copy()
            self.camera_thread.states['rxyz'] = {'RX': 180, 'RY': 0, 'RZ': 180}
        self.lbl_rx.setText(f"{reset_rxyz_values[0]:.1f}")
        self.lbl_ry.setText(f"{reset_rxyz_values[1]:.1f}")
        self.lbl_rz.setText(f"{reset_rxyz_values[2]:.1f}")
        
# ==================== RWS Functions ====================
    def toggle_rws_connection(self):
        if not self.rws_connected:
            try:
                self.rws = RwsClient(
                    self.rws_ip.text(),
                    port=int(self.rws_port.text()),
                    username=self.rws_user.text(),
                    password=self.rws_pass.text()
                )
                # Test connection
                identity = self.rws.get_identity()
                if "error" in identity:
                    raise Exception(identity["error"])
                
                self.rws_connected = True
                self.btn_rws_connect.setText("Disconnect RWS")
                
                QMessageBox.information(self, "Success", "Connected to RWS!")
                self.add_log("Connected to RWS!")
                print("Connected to RWS!")
                self.update_motor_status()
                self.update_rapid_status()
                self.update_opmode()
                self.update_IO_status()
                self.show_identity()
                self.rws.register_user_local()
                self.update_speed()
                
                # Start subscription for real-time updates
                if self.rws.subscribe(self):
                    print("Subscribed to RWS events")
                else:
                    QMessageBox.warning(self, "Warning", "Failed to subscribe to events")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")
                print("Connection failed!")
        else:
            # Close WebSocket connection
            if self.rws and self.rws.ws_client:
                self.rws.ws_client.close()
                if self.rws.subscription_thread:
                    self.rws.subscription_thread.join(timeout=1.0)
            
            self.rws = None
            self.rws_connected = False
            print("Disconnected to RWS!")
            self.add_log("Disconnected to RWS!")
            self.btn_rws_connect.setText("Connect RWS")
            self.btn_rws_connect.setStyleSheet("")
            self.lbl_motor_status.setText("Motor Status: Disconnected")
            self.lbl_rapid_status.setText("Rapid Status: Disconnected")
            self.lbl_IO_status.setText("Gripper Status: Disconnected")
            self.lbl_opmode.setText("Operation Mode: Disconnected")

    def process_rws_event(self, event_xml):
        namespace = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        try:
            root = ET.fromstring(event_xml)
            
            # Process speed ratio
            speed_elem = root.find(".//xhtml:li[@class='pnl-speedratio-ev']/xhtml:span", namespace)
            if speed_elem is not None and speed_elem.text:
                speed_str = speed_elem.text.strip()
                speed = int(speed_str)
                self.speed_changed.emit(speed)
            
            # Process opmode
            opmode_elem = root.find(".//xhtml:li[@class='pnl-opmode-ev']/xhtml:span", namespace)
            if opmode_elem is not None and opmode_elem.text:
                mode = opmode_elem.text.lower()
                self.opmode_changed.emit(mode)
            
            # Process motor state
            ctrl_elem = root.find(".//xhtml:li[@class='pnl-ctrlstate-ev']/xhtml:span", namespace)
            if ctrl_elem is not None and ctrl_elem.text:
                state = ctrl_elem.text.lower()
                if 'on' in state:
                    self.motor_state_changed.emit(True)
                elif 'off' in state:
                    self.motor_state_changed.emit(False)
                    
        except Exception as e:
            print(f"Error processing RWS event: {e}")

    def update_speed_ui(self, speed):
        self.slider.setValue(speed)
        self.lbl_speed.setText(f"{speed}%")

    def update_opmode_ui(self, mode):
        if "auto" in mode:
            self.lbl_opmode.setText("Operation Mode: AUTO")
            self.lbl_opmode.setStyleSheet("color: green; font-weight: bold;")
        elif "man" in mode:
            self.lbl_opmode.setText("Operation Mode: MANUAL")
            self.lbl_opmode.setStyleSheet("color: red; font-weight: bold;")

    def update_motor_ui(self, state):
        if state:
            self.lbl_motor_status.setText("Motor Status: ON")
            self.lbl_motor_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_motor_status.setText("Motor Status: OFF")
            self.lbl_motor_status.setStyleSheet("color: red; font-weight: bold;")
    
    def mode_auto(self):
        if self.rws_connected:
            code = self.rws.set_opmode("auto")
            if code == 202:
                QMessageBox.information(self, "Succesfully","Change Mode Success!")
                self.add_log("Auto mode selected!")
                self.rws.opmode_ack()
            else:
                QMessageBox.critical(self, "Error", f"Failed to changes mode: {code}")

    def mode_man(self):
        if self.rws_connected:
            code = self.rws.set_opmode("man")
            if code == 202:
                QMessageBox.information(self, "Succesfully","Change Mode Success!")
                self.add_log("Manual mode selected!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to changes mode: {code}")

    def motor_on(self):
        if self.rws_connected:
            code = self.rws.set_ctrl_state("motoron")
            if code == 204:
                self.update_motor_status()
                self.add_log("Motor On state!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to start motors: {code}")

    def motor_off(self):
        if self.rws_connected:
            code = self.rws.set_ctrl_state("motoroff")
            if code == 204:
                self.update_motor_status()
                self.add_log("Motor Off state!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to stop motors: {code}")

    
    def set_speed(self, value):
        self.lbl_speed.setText(f"{value}%")
        if self.rws_connected:
            code = self.rws.set_speed(value)
            self.add_log("Speed Adjusted!")
            if code != 204:
                print("Error updating preview:")
    
    def update_speed(self):
        if self.rws_connected:
            speed_1 = self.rws.get_speed()
            self.slider.setValue(speed_1)
            self.lbl_speed.setText(f"{speed_1}%")

    def ON_IO(self,lvalue):
        if self.rws_connected:
            code = self.rws.set_IO("1")
            if code == 204:
                self.rws.set_IO(lvalue)
                self.add_log("Gripper ON!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to changes IO values: {code}")

    def OFF_IO(self,lvalue):
        if self.rws_connected:
            code = self.rws.set_IO("0")
            if code == 204:
                self.rws.set_IO(lvalue)
                self.add_log("Gripper OFF!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to changes IO values: {code}")

    def show_identity(self):
        if self.rws_connected:
            identity_info = self.rws.get_identity()
            if "error" in identity_info:
                self.lbl_identity.setText(f"Error: {identity_info['error']}")
                return
            display_text = f"Name: {identity_info['name']}\nType: {identity_info['type']}"
            self.lbl_identity.setText(display_text)

    def start_rapid(self):
        if self.rws_connected:
            code = self.rws.start_rapid()
            if code == 204:
                QMessageBox.information(self, "Success", "RAPID started!")
                self.add_log("RAPID program started!")
                
            else:
                QMessageBox.critical(self, "Error", f"Failed to start RAPID: {code}")

    def stop_rapid(self):
        if self.rws_connected:
            code = self.rws.stop_rapid()
            if code == 204:
                QMessageBox.information(self, "Success", "RAPID stopped!")
                self.add_log("RAPID program stopped!")
                
            else:
                QMessageBox.critical(self, "Error", f"Failed to stop RAPID: {code}")

    def reset_rapid(self):
        if self.rws_connected:
            code = self.rws.reset_rapid()
            if code == 204:
                QMessageBox.information(self, "Success", "RAPID reseted!")
                self.add_log("RAPID program has been reset!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to reset PP: {code}")


    def update_rapid_status(self):
        if self.rws_connected:
            state = self.rws.get_rapid_state()
            if "running" in state:
                self.lbl_rapid_status.setText("Rapid Status: Running")
                self.lbl_rapid_status.setStyleSheet("color: green; font-weight: bold;")
            elif "stopped" in state:
                self.lbl_rapid_status.setText("Rapid Status: Stopped")
                self.lbl_rapid_status.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.lbl_rapid_status.setText(f"Rapid Status: {state}")
                self.lbl_rapid_status.setStyleSheet("color: orange; font-weight: bold;")

    def update_motor_status(self):
        if self.rws_connected:
            state = self.rws.get_ctrl_state()
            if "motoron" in state:
                self.lbl_motor_status.setText("Motor Status: ON")
                self.lbl_motor_status.setStyleSheet("color: green; font-weight: bold;")
            elif "motoroff" in state:
                self.lbl_motor_status.setText("Motor Status: OFF")
                self.lbl_motor_status.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.lbl_motor_status.setText(f"Motor Status: {state}")
                self.lbl_motor_status.setStyleSheet("color: orange; font-weight: bold;")

    def update_opmode(self):
        if self.rws_connected:
            state = self.rws.get_opmde()
            if "auto" in state:
                self.lbl_opmode.setText("Operation Mode: AUTO")
                self.lbl_opmode.setStyleSheet("color: green; font-weight: bold;")
            elif "manr" in state:
                self.lbl_opmode.setText("Operation Mode: MANUAL")
                self.lbl_opmode.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.lbl_opmode.setText(f"Operation Mode: {state}")
                self.lbl_opmode.setStyleSheet("color: orange; font-weight: bold;")
    
    def update_IO_status(self):
        if self.rws_connected:
            state = self.rws.get_IO_state()
            if "1" in state:
                self.lbl_IO_status.setText("Gripper Status: ON")
                self.add_log("Gipper ON!")
                self.lbl_IO_status.setStyleSheet("color: green; font-weight: bold;")
            elif "0" in state:
                self.lbl_IO_status.setText("Gripper: OFF")
                self.add_log("Gripper OFF!")
                self.lbl_IO_status.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.lbl_IO_status.setText(f"Gripper Status: {state}")
                self.lbl_IO_status.setStyleSheet("color: orange; font-weight: bold;")

#==================Camera Function=================
    def toggle_camera(self):
        if self.camera_thread.isRunning():
            self.camera_thread.running = False
            self.camera_thread.quit()  
            self.btn_camera.setText("Start Camera")
            self.add_log("Stopped Camera!")
            self.camera_label.clear()
        else:
            camera_index = self.camera_combo.currentData()
            self.camera_thread.camera_index = camera_index
            self.camera_thread.running = True
            self.camera_thread.start()  
            self.btn_camera.setText("Stop Camera")
            self.add_log("Started Camera!")
    
    def toggle_hand_tracking(self):
        self.camera_thread.process_hands = not self.camera_thread.process_hands
        self.btn_hand_tracking.setText(
            "Disable Hand Tracking" if self.camera_thread.process_hands 
            else "Enable Hand Tracking"
        )

    def update_camera_preview(self, image, landmarks):
        try:
            pixmap = QPixmap.fromImage(image)
            if not pixmap.isNull():
                self.camera_label.setPixmap(
                    pixmap.scaled(self.camera_label.width(), 
                                 self.camera_label.height(),
                                 Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation)
                )
        except Exception as e:
            print("Error updating preview:", e)

    def handle_camera_button(self, command):
        if command[1] in ['X', 'Y', 'Z']:
            axis_map = {'X': 0, 'Y': 1, 'Z': 2}
            direction = 3 if '+' in command else -3
            axis = axis_map[command[1]]
            self.adjust_position(axis, direction)
        
        elif command.startswith(('+R', '-R')):
            axis_map = {'RX': 0, 'RY': 1, 'RZ': 2}
            rotation_axis = command[1:]
            direction = 0.2 if command[0] == '+' else -0.2
        
            if rotation_axis in axis_map:
                axis = axis_map[rotation_axis]
                self.adjust_rotation(axis, direction)

    def handle_gripper_change(self, state):
        if self.rws_connected:
            lvalue = "1" if state else "0"
            code = self.rws.set_IO(lvalue)
            if code == 204:
                self.update_IO_status()
            else:
                self.add_log("Failed to update gripper via camera: {code}")

    def toggle_hand_control(self):
        self.camera_thread.states['hand_mode'] = not self.camera_thread.states['hand_mode']
        self.add_log("Started Hand Mode!")

#========================System Log================================
    def add_log(self, message, level="INFO", source="ABB CRB1500"):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        log_line = f"{now} - {source} - {level} - {message}"
        self.log_output.append(log_line)
    def clear_log(self):
        self.log_output.clear()
        self.add_log("[INFO] Log cleared by user.")
#=============================================================
    def closeEvent(self, event):
        if self.recv_thread: 
            self.recv_thread.running = False
            self.recv_thread.wait()
        if self.send_thread: 
            self.send_thread.running = False
            self.send_thread.wait()
        if self.robot_socket:
            self.robot_socket.close()
        if self.camera_thread.isRunning():
            self.camera_thread.running = False
            self.camera_thread.wait()
        if self.rws_connected and self.rws and self.rws.ws_client:
            self.rws.ws_client.close()
            if self.rws.subscription_thread:
                self.rws.subscription_thread.join(timeout=1.0)
        if hasattr(self, 'chart_timer'):
            self.chart_timer.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1500, 750)
    win.show()
    sys.exit(app.exec_())