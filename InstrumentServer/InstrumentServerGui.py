import sys
import os
from http import HTTPStatus

import requests
import logging
import threading
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from DB import db
from instrument_connection_service import InstrumentConnectionService, AlreadyConnectedError
from InstrumentDetection.instrument_detection_service import InstrumentDetectionService
from GUI.experimentWindowGui import ExperimentWindowGui
from GUI.instrument_manager_gui import InstrumentManagerGUI
from enum import Enum
from GUI.instrument_settings_gui import InstrumentSettingsGUI
from collections import OrderedDict


class INST_INTERFACE(Enum):
    USB = 'USB'
    GPIB = 'GPIB'
    TCPIP = 'TCPIP'
    SERIAL = 'SERIAL'
    ASRL = 'ASRL'
    COM = 'COM'


###################################################################################
# InstrumentServerWindow
###################################################################################
class InstrumentServerWindow(QMainWindow):

    def __init__(self, flask_app, logger: logging.Logger, dev_mode=False):

        self.my_logger = logger
        self.get_logger().info('Initializing Instrument Server GUI...')
        self.dev_mode = dev_mode

        # key: instrument cute name, value: instrument type - VISA or NONE_VISA
        self.instrument_type = {}

        super(InstrumentServerWindow, self).__init__()

        self.currently_selected_instrument = None

        # The parent flask application
        self.flask_app = flask_app

        # The "top most" layout is vertical box layout (top -> bottom)
        self.main_layout = QVBoxLayout()

        # This is the outermost widget
        self.main_widget = QWidget()

        parent_dir = os.getcwd()
        self.my_logger.debug(f'InstrumentServerWindow current working directory: {parent_dir}')

        # Split path using OS specific separator
        list_of_str = parent_dir.split(os.sep)

        # Create Dict that preserves order of list_of_str
        ordered_dict = OrderedDict.fromkeys(list_of_str)

        # Concern the dict keys back to list
        set_with_order = list(ordered_dict.keys())

        # Add OS separator for driver (usually C)
        set_with_order[0] = set_with_order[0] + os.sep

        # Construct a valid parent dir path
        parent_dir = os.path.join(*set_with_order)

        # Set Icons directory
        self.icons_dir = os.path.join(parent_dir, "Icons")
        self.my_logger.info(f'Icons directory: {self.icons_dir}')

        server_icon = QIcon(os.path.join(self.icons_dir, "servers.png"))
        self.green_icon = QIcon(os.path.join(self.icons_dir, "greenIcon.png"))
        self.red_icon = QIcon(os.path.join(self.icons_dir, "redIcon.png"))
        self.settings_icon = QIcon(os.path.join(self.icons_dir, "gear.png"))
        self.remove_icon = QIcon(os.path.join(self.icons_dir, "delete.png"))
        self.add_icon = QIcon(os.path.join(self.icons_dir, "add.png"))
        self.create_experiment_icon = QIcon(os.path.join(self.icons_dir, "edit.png"))
        self.connect_icon = QIcon(os.path.join(self.icons_dir, "connection.png"))
        self.connect_all_icon = QIcon(os.path.join(self.icons_dir, "connection_multiple.png"))
        self.close_icon = QIcon(os.path.join(self.icons_dir, "unlink.png"))
        self.close_all_icon = QIcon(os.path.join(self.icons_dir, "disconnect_all.png"))

        self.setWindowIcon(server_icon)
        self.setWindowTitle("Instrument Server")

        self.construct_menu()

        self.construct_instrument_table_header()

        # Since we need multiple columns, we cannot use QListWidget. Instead, we can use QTreeWidget
        # since it support columns.
        self.instrument_tree = QTreeWidget(self)
        self.instrument_tree.setHeaderLabels(['Instrument Model', 'Unique Name', 'Address'])

        # Allow only one selection at a time -> SingleSelection
        self.instrument_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.instrument_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.instrument_tree.itemSelectionChanged.connect(self.instrument_selected_changed)
        self.main_layout.addWidget(self.instrument_tree)

        self.instrument_tree.itemDoubleClicked.connect(self.show_quantity_manager_gui)

        self.construct_bottom_buttons()
        self.construct_instrument_server_status()

        # Set the layout for main widget
        self.main_widget.setLayout(self.main_layout)

        # Set the central widget
        self.setCentralWidget(self.main_widget)

        # Instrument Connection Service
        self._ics = InstrumentConnectionService(self.my_logger)

        # Instrument Detection Service
        self._ids = InstrumentDetectionService(self.my_logger)

        self.get_known_instruments()

        # Setup Experiment Windows GUI
        self.experiment_window_gui = ExperimentWindowGui(self, self._ics, self.my_logger)

        # Delegates instrument server status check to a separate thread
        is_running_th = threading.Thread(target=self.check_instrument_status, daemon=True)
        is_running_th.start()

        self.my_logger.info('Done initializing Instrument Server GUI')

    def get_logger(self):
        """Get the application logger"""
        return self.my_logger

    def construct_menu(self):
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.exit_gui)

        menu = self.menuBar()
        menu.addSeparator()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(exit_action)

        edit_menu = menu.addMenu("&Edit")

        tools_menu = menu.addMenu("&Tools")
        detect_visa_resources_action = QAction("&Detect VISA Resources...", self)
        detect_visa_resources_action.triggered.connect(self.detect_visa_resources_action)
        tools_menu.addAction(detect_visa_resources_action)

        help_menu = menu.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.about_action)
        help_menu.addAction(about_action)

    def construct_instrument_table_header(self):
        table_header = QWidget()
        table_header_layout = QHBoxLayout()

        instrument_status_lbl = QLabel("Laboratory Instruments:")
        table_header_layout.addWidget(instrument_status_lbl)
        table_header_layout.setAlignment(instrument_status_lbl, Qt.AlignmentFlag.AlignLeft)

        connect_btn = QPushButton("Connect")
        connect_btn.setIcon(self.connect_icon)
        connect_btn.clicked.connect(self.connect_btn_clicked)
        table_header_layout.addWidget(connect_btn)

        connect_all_btn = QPushButton("Connect All")
        connect_all_btn.setIcon(self.connect_all_icon)
        connect_all_btn.clicked.connect(self.connect_all_btn_clicked)
        table_header_layout.addWidget(connect_all_btn)

        close_btn = QPushButton("Close")
        close_btn.setIcon(self.close_icon)
        close_btn.clicked.connect(self.close_btn_clicked)
        table_header_layout.addWidget(close_btn)

        close_all_btn = QPushButton("Close All")
        close_all_btn.setIcon(self.close_all_icon)
        close_all_btn.clicked.connect(self.close_all_btn_clicked)
        table_header_layout.addWidget(close_all_btn)

        table_header.setLayout(table_header_layout)
        self.main_layout.addWidget(table_header)

    def construct_bottom_buttons(self):
        bottom_button_group_widget = QWidget()
        bottom_button_layout = QHBoxLayout()

        add_btn = QPushButton("Add")
        add_btn.setIcon(self.add_icon)
        add_btn.clicked.connect(self.add_btn_clicked)
        bottom_button_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setIcon(self.remove_icon)
        remove_btn.clicked.connect(self.remove_btn_clicked)
        bottom_button_layout.addWidget(remove_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setIcon(self.settings_icon)
        settings_btn.clicked.connect(self.settings_btn_clicked)
        bottom_button_layout.addWidget(settings_btn)

        close_btn = QPushButton("Exit")
        close_btn.clicked.connect(self.exit_gui)
        bottom_button_layout.addWidget(close_btn)

        bottom_button_group_widget.setLayout(bottom_button_layout)
        self.main_layout.addWidget(bottom_button_group_widget)

    def construct_instrument_server_status(self):
        status_widget = QWidget()
        status_layout = QHBoxLayout()

        create_experiment_btn = QPushButton("Create Experiment")
        create_experiment_btn.setIcon(self.create_experiment_icon)
        create_experiment_btn.clicked.connect(self.create_experiment_clicked)
        status_layout.setAlignment(create_experiment_btn, Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(create_experiment_btn)

        self.instrument_server_status_lbl = QLabel("Instrument Server Is Running")
        self.instrument_server_status_lbl.setStyleSheet("font-weight: bold")
        status_layout.addWidget(self.instrument_server_status_lbl)
        status_layout.setAlignment(self.instrument_server_status_lbl, Qt.AlignmentFlag.AlignRight)

        status_widget.setLayout(status_layout)
        self.main_layout.addWidget(status_widget)

    def set_instrument_server_running_lbl(self):
        self.instrument_server_status_lbl.setText("Instrument Server Is Running")

    def set_instrument_server_not_responding_lbl(self):
        self.instrument_server_status_lbl.setText("Instrument Server Not Responding")

    # Defines exit behavior
    def exit_gui(self):
        self.get_logger().debug('Exit was clicked')
        self.close()

    # Defines about behavior
    def about_action(self):
        msgBox = QMessageBox(self)
        msg = 'Instrument Server\nCSCI 5040 & CSCI 5050 Class Project\nVersion: 0.02'

        msgBox.setWindowTitle("About Instrument Server")
        msgBox.setText(msg)
        msgBox.exec()

    def detect_visa_resources_action(self):
        msgBox = QMessageBox(self)
        msg = f'Detected the following VISA resources:\n\n{self._ids.detect_visa_resources()}\n'
        msgBox.setWindowTitle("VISA Resource Detection")
        msgBox.setText(msg)
        msgBox.exec()

    def instrument_selected_changed(self):
        # THere should only be one selected item
        selected_instrument = self.instrument_tree.selectedItems()

        if len(selected_instrument) > 0:
            log_instrument = 'Currently selected instrument: {} {}'.format(selected_instrument[0].text(0),
                                                                           selected_instrument[0].text(1))

            self.get_logger().info(log_instrument)
            self.currently_selected_instrument = selected_instrument[0].text(1)

    def settings_btn_clicked(self):
        self.get_logger().info('Settings was clicked')
        if not self.currently_selected_instrument:
            QMessageBox.warning(self, 'Warning', 'No Instrument was selected!')
            return

        settings_gui = InstrumentSettingsGUI(self.flask_app, self, self.my_logger, self.currently_selected_instrument)
        settings_gui.exec()

    def create_experiment_clicked(self):
        self.get_logger().debug('Create Experiment was clicked')
        self.show_experiment_window()

    def add_btn_clicked(self):
        self.get_logger().debug("Add was clicked")
        dlg = AddInstrumentWindow()

        if dlg.exec():
            if not dlg.name_line.text() or not dlg.path_line.text() or not dlg.address_line.text():
                msgBox = QMessageBox(self)
                msg = "Failed to add instrument. Please provide complete details."
                msgBox.setWindowTitle("Add Instrument")
                msgBox.setText(msg)
                msgBox.exec()
                self.get_logger().debug('Missing required fields')

            else:
                details = {"cute_name": dlg.name_line.text().strip(),
                           "interface": dlg.interface_choice.currentText(),
                           "address": dlg.address_line.text().strip(),
                           "baud_rate": dlg.baud_rate_line.text().strip(),
                           "serial": str(dlg.serial_check.isChecked()),
                           "visa": str(dlg.visa_check.isChecked()),
                           "path": dlg.path_line.text()}
                connect_result, msg = self._ics.add_instrument_to_database(details)

                if not connect_result: msg = "Failed. " + msg
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle("Status")
                msgBox.setText(msg)
                msgBox.exec()
                self.get_known_instruments()
        else:
            self.get_logger().debug('User hit cancel')

    def remove_btn_clicked(self):
        self.get_logger().debug('Remove was clicked')

        if not self.check_if_instrument_selected():
            return

        button = QMessageBox.question(self, "Remove Instrument",
                                      "Are you sure you want to remove the instrument '{}'?".format(
                                          self.currently_selected_instrument))

        if button == QMessageBox.StandardButton.Yes:
            msg = self._ics.remove_instrument_from_database(self.currently_selected_instrument)
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle("Status")
            msgBox.setText(msg)
            msgBox.exec()
            self.get_known_instruments()

    def show_experiment_window(self):
        self.experiment_window_gui.show()

    def connect_btn_clicked(self):
        self.get_logger().debug('Connect was clicked')

        if not self.check_if_instrument_selected():
            return

        try:
            if self.instrument_type[self.currently_selected_instrument] == "VISA":
                self._ics.connect_to_visa_instrument(self.currently_selected_instrument)
                current_item = self.instrument_tree.currentItem()
                current_item.setIcon(0, self.green_icon)
            else:
                self._ics.connect_to_none_visa_instrument(self.currently_selected_instrument)
                current_item = self.instrument_tree.currentItem()
                current_item.setIcon(0, self.green_icon)

        except AlreadyConnectedError:
            QMessageBox.information(self, 'Instrument is already connected', 'Instrument is already connected')

        except Exception as e:
            self.get_logger().critical(f'There was a problem connecting to instrument: {e}')
            QMessageBox.critical(self, 'ERROR', f'Could not connect to instrument: {e}')

    def connect_all_btn_clicked(self):
        """Attempts to connect all listed instruments"""
        self.get_logger().debug('Connect All was clicked')

        failed_connections = []

        # iterate through instrument_tree and connect to instrument
        qtiter = QTreeWidgetItemIterator(self.instrument_tree)
        while qtiter.value():
            try:
                current_item = qtiter.value()
                if self.instrument_type[current_item.text(1)] == "VISA":
                    self._ics.connect_to_visa_instrument(current_item.text(1))
                else:
                    self._ics.connect_to_none_visa_instrument(current_item.text(1))
                current_item.setIcon(0, self.green_icon)
            except:
                failed_connections.append(current_item.text(1))
            qtiter += 1

        if len(failed_connections) > 0:
            QMessageBox.critical(self, 'ERROR', f'Could not connect to the following instrument: {failed_connections}.')

    def close_btn_clicked(self):
        """Closes connection to selected instrument"""

        if not self.check_if_instrument_selected():
            return

        self.get_logger().info(f'Closing instrument {self.currently_selected_instrument}')

        try:
            self._ics.disconnect_instrument(self.currently_selected_instrument)

            current_item = self.instrument_tree.currentItem()
            current_item.setIcon(0, self.red_icon)
        except KeyError:
            QMessageBox.information(self, 'Instrument is not currently connected.',
                                    'Instrument is not currently connected.')
        except Exception as e:
            QMessageBox.critical(self, 'Unknown Error', e)

    def check_if_instrument_selected(self):
        if not self.currently_selected_instrument:
            QMessageBox.warning(self, 'Warning', 'No Instrument was selected!')
            return False
        else:
            return True

    def close_all_btn_clicked(self):
        self.get_logger().debug('Close All was clicked')
        self._ics.disconnect_all_instruments()

        qtiter = QTreeWidgetItemIterator(self.instrument_tree)
        while qtiter.value():
            current_item = qtiter.value()
            current_item.setIcon(0, self.red_icon)
            qtiter += 1

    def closeEvent(self, event):
        """Overrides closeEvent so that we throw a Dialogue question whether to exit or not."""
        answer = QMessageBox.question(self, "Instrument Server",
                                      "Are you sure you want to exit? This will close all instruments.")

        if answer != QMessageBox.StandardButton.Yes:
            # Ignore the event that brings down this window
            event.ignore()
            return

        try:
            self._ics.disconnect_all_instruments()
        except Exception as e:
            # Error disconnecting instruments, ask user if they still want to disconnect
            self.get_logger().fatal(f'There was a problem disconnecting all instruments: {e}')

            answer = QMessageBox.question(self, "Disconnect Error", f"{e} Do you still want to exit?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        # Accept shutdown and call endpoint
        event.accept()
        url = r'http://127.0.0.1:5000/shutDown'
        requests.get(url)

    def add_instrument_to_list(self, model: str, cute_name: str, address: str) -> None:
        newItem = QTreeWidgetItem(self.instrument_tree, [model, cute_name, address])

        if self._ics.is_connected(cute_name):
            newItem.setIcon(0, self.green_icon)
        else:
            newItem.setIcon(0, self.red_icon)

    def clear_instrument_list(self):
        """
        Clears the Instrument List 
        """
        self.get_logger().debug('Clearing Instrument List...')
        self.instrument_tree.clear()

    def check_instrument_status(self):
        """Checks the status of Instrument Server every 5 minutes"""

        threading.Timer(300, self.check_instrument_status).start()
        self.get_logger().info("Checking Instrument Server Status...")

        response = HTTPStatus.OK
        try:
            url = r'http://127.0.0.1:5000/serverStatus/isRunning'
            response = requests.get(url)

        except Exception as ex:
            self.get_logger().critical('Could not check if Instrument Server is running!')
            response = HTTPStatus.NOT_FOUND

        if response.status_code == HTTPStatus.OK:
            self.set_instrument_server_running_lbl()
        else:
            self.set_instrument_server_not_responding_lbl()
            self.get_logger().critical("Instrument Server is not responding!")

    def get_known_instruments(self):
        """Get all the known instruments from DB"""
        self.clear_instrument_list()
        connection = None

        with self.flask_app.app_context():
            try:
                connection = db.get_db()

                with connection.cursor() as cursor:
                    all_instruments_query = "SELECT * FROM {};".format("instruments")
                    cursor.execute(all_instruments_query)
                    result = cursor.fetchall()

                    for instrument in result:
                        cute_name = instrument[0]
                        manufacturer = instrument[1]
                        interface = instrument[2]
                        address = instrument[3]
                        serial = instrument[4]
                        visa = instrument[5]

                        if visa:
                            self.instrument_type[cute_name] = "VISA"
                        else:
                            self.instrument_type[cute_name] = "NONE_VISA"

                        # The actual address to be displayed
                        display_address = address

                        if interface == INST_INTERFACE.GPIB.name:
                            display_address = f'{interface}::{address}'

                        # If an IP Address was provided, use it for Address column, otherwise use the Interface
                        self.add_instrument_to_list(manufacturer,
                                                    cute_name,
                                                    display_address)

            except Exception as ex:
                self.get_logger().fatal(f'There was a problem getting all known instruments: {ex}')

            finally:
                # Make sure we always close the connection
                db.close_db(connection)

    # Decorator allows method to know which item was double-clicked, we can ignore column in this case
    @pyqtSlot(QTreeWidgetItem, int)
    def show_quantity_manager_gui(self, item, column):
        cute_name = item.text(1)

        # do nothing if not connected
        if not self._ics.is_connected(cute_name):
            self.connect_btn_clicked()
            return

        try:
            instrument_manager = self._ics.get_instrument_manager(cute_name)
        except Exception as e:
            QMessageBox.critical(self, 'Unknown Error', e)
            return

        self.quantity_manager_gui = InstrumentManagerGUI(instrument_manager, self.my_logger)


###################################################################################
# AddInstrumentWindow
###################################################################################
class AddInstrumentWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add New Instrument")
        self.is_baud_rate_visible = False

        # * Indicates a required field

        # Box 1 for driver file input
        self.file_message = QLabel("File path: *")
        self.path_line = QLineEdit()
        self.filebutton = QPushButton("Select File")
        self.filebutton.clicked.connect(self.getFilePath)

        file_input_hbox = QHBoxLayout()
        file_input_hbox.addWidget(self.path_line)
        file_input_hbox.addWidget(self.filebutton)

        file_input_vbox = QVBoxLayout()
        file_input_vbox.addWidget(self.file_message)
        file_input_vbox.addLayout(file_input_hbox)

        self.file_group_box = QGroupBox("Instrument Driver")
        self.file_group_box.setLayout(file_input_vbox)
        self.file_group_box.setFixedHeight(90)

        # Box 2 for communication input
        self.name_line = QLineEdit()
        self.interface_choice = QComboBox()
        self.interface_choice.addItems(["TCPIP", "USB", "GPIB"])
        self.address_line = QLineEdit()
        self.baud_rate_line = QLineEdit()

        self.comm_form_layout = QFormLayout()
        self.comm_form_layout.insertRow(0, QLabel("Unique Name: *"), self.name_line)
        self.comm_form_layout.insertRow(1, QLabel("Interface: *"), self.interface_choice)
        self.comm_form_layout.insertRow(2, QLabel("Address: *"), self.address_line)

        # Only visible if the "Serial" checkbox is checked
        self.comm_form_layout.insertRow(3, QLabel("Baud Rate:"), self.baud_rate_line)
        self.hide_baud_rate()

        self.serial_check = QCheckBox("Serial")
        self.serial_check.clicked.connect(self.serial_checkbox_clicked)
        self.visa_check = QCheckBox("VISA instrument")

        comm_input_hbox = QHBoxLayout()
        comm_input_hbox.addWidget(self.serial_check)
        comm_input_hbox.addWidget(self.visa_check)

        comm_input_vbox = QVBoxLayout()
        comm_input_vbox.addLayout(self.comm_form_layout)
        comm_input_vbox.addLayout(comm_input_hbox)

        self.comm_group_box = QGroupBox("Communication")
        self.comm_group_box.setLayout(comm_input_vbox)

        # Box 3 for Ok and Cancel inputs
        question_buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.button_box = QDialogButtonBox(question_buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.file_group_box)
        self.layout.addWidget(self.comm_group_box)
        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)
        self.setFixedWidth(400)
        self.setFixedHeight(320)

    def getFilePath(self):
        file_filter = 'Configuration File (*.ini);; Python File (*.py)'
        initial_filter = 'Configuration File (*.ini)'
        fileName = QFileDialog.getOpenFileName(parent=self, caption="Select File", directory="C:\\", filter=file_filter,
                                               initialFilter=initial_filter)
        self.path_line.setText(fileName[0])

    def show_baud_rate(self):
        self.is_baud_rate_visible = True
        self.comm_form_layout.setRowVisible(3, True)

    def hide_baud_rate(self):
        self.is_baud_rate_visible = False
        self.comm_form_layout.setRowVisible(3, False)

    def serial_checkbox_clicked(self):
        if self.is_baud_rate_visible:
            self.hide_baud_rate()
        else:
            self.show_baud_rate()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWin = InstrumentServerWindow()
    availableGeometry = mainWin.screen().availableGeometry()
    mainWin.resize(800, 600)
    mainWin.show()
    app.exec()
