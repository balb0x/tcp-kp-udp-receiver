import datetime
import os
import socket
import sys
import threading
import netifaces as ni
from PyQt5 import uic, QtGui
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox

from at_messages.error_response import ErrorResponse
from at_messages.input_status_response import InputStatusResponse
from at_messages.name_request import NameRequest
from at_messages.name_response import NameResponse

forbidden_ips = ["127.0.0.1"]
input_true_status = '0'


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


"""
Class: Relay
Description: Used to display a single relay. It represents whether the relay status is on or off
"""


class Relay:
    def __init__(self, form, index, ip):
        # Depending on the index, we configure the relay
        self.name = "Relay " + str(index + 1)
        self.ip = ip
        if index == 0:
            self.group = form.relay_1
        elif index == 1:
            self.group = form.relay_2
        elif index == 2:
            self.group = form.relay_2
        else:
            self.group = form.relay_4
        # Check for the images and link them to the class parameter
        for child in self.group.children():
            if "image_1" in child.objectName():
                self.input_1 = child
            if "image_2" in child.objectName():
                self.input_2 = child

        self.state_1 = -1
        self.state_2 = -1
        self.ok_image = resource_path('resources/ok.png')
        self.error_image = resource_path('resources/error.png')

    def update_inputs(self, message):
        if type(message) is InputStatusResponse:
            # If we receive an InputStatusResponse, we update the state of the relay inputs
            message_input_1_status = message.input_states[0] == input_true_status
            message_input_2_status = message.input_states[1] == input_true_status
            if self.state_1 != message_input_1_status:
                self.state_1 = message_input_1_status
                self.input_1.clear()
                pia = QPixmap(self.ok_image if message_input_1_status else self.error_image)
                pia = pia.scaledToWidth(90)
                self.input_1.setPixmap(pia)

            if self.state_2 != message_input_2_status:
                self.state_2 = message_input_2_status
                self.input_2.clear()
                pia = QPixmap(self.ok_image if message_input_2_status else self.error_image)
                pia = pia.scaledToWidth(90)
                self.input_2.setPixmap(pia)
        elif type(message) is NameResponse:
            # If we receive an NameResponse, we update the relay name
            self.group.setTitle(self.name + " - " + message.name)

    def clear(self):
        self.input_1.clear()
        self.input_2.clear()
        self.group.setTitle(self.name)


"""
Class: UDPServer
Description: This class starts an UDP server on the selected port. 
The main loop is backgrounded so we need to take care not to leave 
the loop alive forever
"""


class UDPServer:
    def __init__(self, _ip, _port, _callback):
        self.ip = _ip
        self.port = _port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = (_ip, _port)
        self.callback = _callback

        try:
            self.socket.bind(server_address)
        except Exception as e:
            self.callback(ErrorResponse(str(e)))
        self.working = True

    def parse_message(self, data, address):
        # Incoming message, parse parse and caste it to a known class
        payload = data.decode('utf-8')
        try:
            message = None
            if InputStatusResponse.get_header() in payload:
                message = InputStatusResponse(payload, address)
            elif NameResponse.get_header() in payload:
                message = NameResponse(payload, address)
            if message is not None and self.callback is not None:
                self.callback(message)
        except Exception as e:
            print("Exception while parsing message: ")
            print(e)

    def loop(self):
        # Main server loop, active while self.working
        while self.working:
            try:
                data, address = self.socket.recvfrom(4096)
                self.parse_message(data, address)
            except:
                pass

    def send_request(self, request, address):
        self.socket.sendto(request.payload.encode('utf-8'), address)

    def start(self):
        threading.Thread(target=self.loop).start()

    def stop(self):
        self.working = False
        self.socket.close()


"""
Class: BaseController
Description: This class displays the .ui file designed in QTDesigner. Take cares
of the selected ip to start the server and displays the state of the relays
"""


class BaseController(QWidget):
    update_ui_signal = pyqtSignal(name='update_ui_signal')
    error_ui_signal = pyqtSignal(str, name='error_ui_signal')

    def __init__(self):
        super().__init__()
        file_name = resource_path("resources/main.ui")
        form, window = uic.loadUiType(file_name)
        self.window = window()
        self.form = form()
        self.form.setupUi(self.window)

        # signals are used to execute functions in the main thread, wich
        # are called from a background process
        self.update_ui_signal.connect(self.update_ui)
        self.error_ui_signal.connect(self.show_error)

        self.setGeometry(300, 300, 250, 150)
        self.setWindowTitle('Signal & slot')
        self.status_label = self.form.status_edit
        self.button = self.form.start_button
        self.fill_widgets()
        self.server = None
        self.messages = []
        self.last_messages = []
        self.server_started = False
        self.window.show()
        self.relays = {}
        self.window.setFixedSize(self.window.width(), self.window.height())
        self.window.setWindowIcon(QtGui.QIcon(resource_path("resources/icon.ico")))

    def show_error(self, title):
        # Show an error as a new window
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(title)
        msg.setWindowTitle("Error")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def fill_widgets(self):
        self.form.ip_combo_box.addItems(ips)
        self.button.clicked.connect(self.on_server_button_clicked)

    def update_ui(self):
        # Print the incoming messages to the box area
        self.status_label.setText('\n'.join(self.messages))
        while len(self.last_messages) > 0:
            message = self.last_messages.pop(0)
            if message.ip not in self.relays:
                self.relays[message.ip] = Relay(self.form, len(self.relays), message.ip)
                if self.server is not None:
                    self.server.send_request(NameRequest(), message.address)
            else:
                self.relays[message.ip].update_inputs(message)

    def on_server_button_clicked(self):
        # start/stop the server
        if not self.server_started:
            self.start_server()
        else:
            self.close_server()
        self.update_ui_signal.emit()

        self.button.setText("Start" if not self.server_started else "Stop")

    def add_message(self, message):
        # add message to the box area, format it and send it to the messages buffer
        now = datetime.datetime.now()
        hour = '{:02d}'.format(now.hour)
        minute = '{:02d}'.format(now.minute)
        self.messages.insert(0, hour + ":" + minute + " -> " + message)
        if len(self.messages) >= 10:
            self.messages.pop(len(self.messages) - 1)

    def close_server(self):
        # Stop the server
        self.add_message("Stopping server")
        self.server_started = False
        if self.server is not None:
            self.server.stop()
            self.server = None
        for relay in self.relays:
            self.relays[relay].clear()
        self.relays = {}
        self.last_messages = []

    def start_server(self):
        # Start the server
        self.server_started = True
        self.server = UDPServer(self.form.ip_combo_box.currentText(),
                                int(self.form.port_edit.text()),
                                self.on_message_received)
        self.server.start()
        self.add_message("Starting server")

    def on_message_received(self, message):
        # Received a parsed message
        if type(message) is ErrorResponse:
            # if it is an error, show it
            self.error_ui_signal.emit(message.error)
            try:
                self.close_server()
            except Exception as e:
                print(e)
            return
        # log the message on the box area
        self.last_messages.append(message)
        self.add_message("Received data: " + message.ip + " " + str(message.param))
        if len(self.messages) >= 10:
            self.messages.pop(len(self.messages) - 1)
        #update the relays
        self.update_ui_signal.emit()

# Check the network interfaces and remove the forbidden ones
ips = []
for interface in ni.interfaces():
    data = ni.ifaddresses(interface)
    if ni.AF_INET in data:
        ip = data[ni.AF_INET][0]['addr']
        if ip not in forbidden_ips:
            ips.append(ip)

# Start QTApplication
app = QApplication([])
base_controller = BaseController()
app.exec_()
base_controller.close_server()
