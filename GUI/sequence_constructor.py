from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

import logging
from Instrument.quantity_manager import QuantityManager

from typing import Callable

class SequenceConstructor(QDialog):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__()

        self.quantity = quantity
        self._name = quantity.instrument_name
        self._quantity_name = quantity.name
        self._quantity_data_type = quantity.data_type
        self._unit = ''
        self._low_lim = quantity.low_lim
        self._high_lim = quantity.high_lim
        if self.quantity.unit:
            self._unit = self.quantity.unit

        self.logger = logger

        """
        Quantities can be set to two different types of values
        Single point value - quantity is set at a constant value through out the experiment
        Start stop values - quantity is varied from start to stop values through a list of points determined by one of two attributes
                        step value -> divide [start, stop] into a list of points with 'step value' difference between each point
                        number of points -> divide [start, stop] into a list of 'number of points' points
        """

        """value_flag: True if single point is selected. False if start and stop values are given."""
        self._value_flag = True
        """step_flag: Applies if value_flag is false (a range is provided). True if step size is provided. False if number of steps is provided."""
        self._step_flag = False
        
        self._level = 1 # default level is set to 1
        self._single_point_value = None
        self._start_value = None
        self._stop_value = None
        self._fixed_step = None
        self._fixed_number_of_steps = 1

        # self._interpolation = "Linear"
        # Currently Experiment Runner only creates linear list of points for a range (np.linspace(start, stop, points))
        # This can be expanded to Logarithmic interlopation as well (np.logspace(start, stop, points))

        self.setWindowTitle("Step setup")
        self.lab_experiment_icon = QIcon("../Icons/labExperiment.png")
        self.setWindowIcon(self.lab_experiment_icon)

        # Set basic layout
        self.layout = QVBoxLayout()
        self.group_box = QGroupBox("Step range")
        self.group_box_layout = QHBoxLayout() 
        self.group_box.setLayout(self.group_box_layout)

        self.left_section_layout = QVBoxLayout()
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.right_section_layout = QVBoxLayout()
        self.group_box_layout.addLayout(self.left_section_layout)
        self.group_box_layout.addWidget(separator)
        self.group_box_layout.addLayout(self.right_section_layout)

        # Left section
        self.value_buttons_group = QButtonGroup()
        self.single_point_button = QRadioButton('Single point')
        self.value_buttons_group.addButton(self.single_point_button)        
        self.single_point_form_layout = QFormLayout()
        
        self.start_stop_button = QRadioButton('Start - Stop')
        self.value_buttons_group.addButton(self.start_stop_button)                
        self.start_stop_form_layout = QFormLayout() 

        self.left_section_layout.addWidget(self.single_point_button)
        self.left_section_layout.addLayout(self.single_point_form_layout)
        self.left_section_layout.addWidget(self.start_stop_button)
        self.left_section_layout.addLayout(self.start_stop_form_layout)

        # Right section
        self.step_buttons_group = QButtonGroup()
        self.fixed_step_button = QRadioButton('Fixed step')
        self.step_buttons_group.addButton(self.fixed_step_button)        
        self.fixed_step_form_layout = QFormLayout()        
        
        self.steps_number_button = QRadioButton('Fixed # of steps')
        self.step_buttons_group.addButton(self.steps_number_button)              
        self.steps_number_form_layout = QFormLayout()

        self.right_section_layout.addWidget(self.fixed_step_button)
        self.right_section_layout.addLayout(self.fixed_step_form_layout)
        self.right_section_layout.addWidget(self.steps_number_button)
        self.right_section_layout.addLayout(self.steps_number_form_layout)

        # Radio button connections
        self.single_point_button.toggled.connect(self.handle_value_checkboxes_toggle)
        self.start_stop_button.toggled.connect(self.handle_value_checkboxes_toggle)
        """single point and start stop radio buttons are grouped together as value checkboxes"""
        self.fixed_step_button.toggled.connect(self.handle_step_checkboxes_toggle)
        self.steps_number_button.toggled.connect(self.handle_step_checkboxes_toggle)        
        """fixed step and steps number radio buttons are grouped togetehr as step checkboxes""" 

        # Add level selector
        level_label = QLabel("Level:")
        self.level_spin_box = QSpinBox()
        self.level_spin_box.setMinimum(1)
        self.level_spin_box.setSingleStep(1)
        self.level_spin_box.setValue(1)
        level_form_layout = QFormLayout()
        level_form_layout.addRow(level_label, self.level_spin_box)        
        
        # Add button box
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_data)
        self.button_box.rejected.connect(self.reject)
        
        # Bottom section with level and buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addLayout(level_form_layout)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.button_box)        

        self.layout.addWidget(self.group_box)
        self.layout.addLayout(bottom_layout)
        self.setLayout(self.layout)

    @property
    def instrument_name(self):
        return self._name
    
    @property
    def quantity_name(self):
        return self._quantity_name
    
    @property
    def unit(self):
        return self._unit
    
    @property
    def data_type(self):
        return self._quantity_data_type
    
    @property
    def level(self):
        return self._level
       
    @property
    def value_flag(self):
        return self._value_flag
        
    @property
    def single_point_value(self):
        return self._single_point_value    

    @property
    def start_value(self):
        return self._start_value
    
    @property
    def stop_value(self):
        return self._stop_value
    
    @property
    def number_of_points(self):
        if self.value_flag:
            return 1
        return self._fixed_number_of_steps    

    def get_value(self):
        try:
            value = self.quantity.get_value()
            self.handle_incoming_value(value)
        except Exception as e:
            self.logger.error(f"Error querying '{self.quantity.name}': {e}")
            QMessageBox.critical(self, f"Error querying '{self.quantity.name}'", str(e))

    def set_value(self):
        try:
            self.quantity.set_value(self.value)
            self.on_value_change(self.quantity.name, self.value)
        except Exception as e:
            self.logger.error(f"Error setting '{self.quantity.name}': {e}")
            QMessageBox.critical(self, f"Error setting '{self.quantity.name}'", str(e))

    def set_default_value(self):
        try:
            self.quantity.set_default_value()
        except Exception as e:
            self.logger.error(f"Error setting '{self.quantity.name}': {e}")
            QMessageBox.critical(self, f"Error setting '{self.quantity.name}'", str(e))
        self.get_value()

    def handle_incoming_value(self, value):
        """Handles any value returned by instrument to be properly displayed. Should be implemented by child class"""
        raise NotImplementedError()

    def handle_value_checkboxes_toggle(self):
        """Handles toggling between single point and start - stop options. Should be implemented by child class"""
        raise NotImplementedError()
    
    def handle_step_checkboxes_toggle(self):
        """Handles toggling between step size and number of steps options -- enabled by start - stop option. Should be implemented by child class"""
        raise NotImplementedError()
    
    def save_data(self):
        """Saves the sequence data"""
        raise NotImplementedError()
    
####################################################################
# Children Classes for different quantity data types
####################################################################    
class BooleanConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)
        # self.group_box_layout

        # combo_items = ["0: Off", "1: On"]
        combo_items = ["False", "True"]

        self.single_point_label = QLabel("Value:")
        self.single_point_combo_box = QComboBox()
        self.single_point_combo_box.addItems(combo_items)
        if self._single_point_value:
            self.single_point_combo_box.setCurrentText(self._single_point_value)
        self.single_point_form_layout.addRow(self.single_point_label, self.single_point_combo_box)

        self.start_label = QLabel("Start:")
        self.start_combo_box = QComboBox()
        self.start_combo_box.addItems(combo_items)

        self.stop_label = QLabel("Stop:")
        self.stop_combo_box = QComboBox()
        self.stop_combo_box.addItems(combo_items)

        self.start_stop_form_layout.addRow(self.start_label, self.start_combo_box)
        self.start_stop_form_layout.addRow(self.stop_label, self.stop_combo_box)

        self.fixed_step_label = QLabel("Step:")
        self.fixed_step_spin_box = QDoubleSpinBox()
        self.fixed_step_spin_box.setMinimum(0)
        self.fixed_step_spin_box.setMaximum(float('inf'))
        self.fixed_step_spin_box.setValue(0)
        self.fixed_step_form_layout.addRow(self.fixed_step_label, self.fixed_step_spin_box)

        self.steps_number_label = QLabel("# of points:")
        self.steps_number_spin_box = QSpinBox()
        self.steps_number_spin_box.setMinimum(0)
        self.steps_number_spin_box.setSingleStep(1)
        self.steps_number_spin_box.setValue(2)
        self.steps_number_form_layout.addRow(self.steps_number_label, self.steps_number_spin_box)
        

    def handle_value_checkboxes_toggle(self):
        """Individually disable corresponding widgets when value checkboxes are toggled"""
        if self.single_point_button.isChecked():
            self.single_point_label.setEnabled(True)
            self.single_point_combo_box.setEnabled(True)

            self.start_label.setEnabled(False)
            self.start_combo_box.setEnabled(False)
            self.stop_label.setEnabled(False)
            self.stop_combo_box.setEnabled(False)

            self.fixed_step_button.setEnabled(False)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_button.setEnabled(False)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)
        else:
            self.single_point_label.setEnabled(False)
            self.single_point_combo_box.setEnabled(False)
            self.start_label.setEnabled(True)
            self.start_combo_box.setEnabled(True)
            self.stop_label.setEnabled(True)
            self.stop_combo_box.setEnabled(True)
            self.fixed_step_button.setEnabled(True)
            self.steps_number_button.setEnabled(True)
            self.handle_step_checkboxes_toggle()

    def handle_step_checkboxes_toggle(self):
        """Individually disable corresponding widgets when step checkboxes are toggled"""
        self.start_stop_button.setChecked(True)
        if self.fixed_step_button.isChecked():
            self.fixed_step_label.setEnabled(True)
            self.fixed_step_spin_box.setEnabled(True)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)          
        else:
            self.steps_number_button.setChecked(True)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_label.setEnabled(True)
            self.steps_number_spin_box.setEnabled(True)    
        
    def save_data(self):
        """Saves the sequence data"""
        if self.value_buttons_group.checkedButton() is None:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("No data")
            msg_box.setWindowIcon(self.lab_experiment_icon)
            msg_box.setText("Please provide data to build a sequence with this quantity.")
            msg_box.exec()
            self.reject()
            return

        self._level = self.level_spin_box.value()
        self._value_flag = self.single_point_button.isChecked()
        self._step_flag = self.fixed_step_button.isChecked()
        
        self._single_point_value = self.single_point_combo_box.currentText()
        self._start_value = self.start_combo_box.currentText()
        self._stop_value = self.stop_combo_box.currentText()
        self._fixed_step = self.fixed_step_spin_box.value()
        self._fixed_number_of_steps = self.steps_number_spin_box.value()
        # self._interpolation = "Linear"
        
        # Save user's data
        self.accept()

class ButtonConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


class ComboConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)

        combo_items = self.quantity.combo_cmd.keys()

        self.single_point_label = QLabel("Value:")
        self.single_point_combo_box = QComboBox()
        self.single_point_combo_box.addItems(combo_items)
        if self._single_point_value:
            self.single_point_combo_box.setCurrentText(self._single_point_value)
        self.single_point_form_layout.addRow(self.single_point_label, self.single_point_combo_box)

        self.start_label = QLabel("Start:")
        self.start_combo_box = QComboBox()
        self.start_combo_box.addItems(combo_items)

        self.stop_label = QLabel("Stop:")
        self.stop_combo_box = QComboBox()
        self.stop_combo_box.addItems(combo_items)

        self.start_stop_form_layout.addRow(self.start_label, self.start_combo_box)
        self.start_stop_form_layout.addRow(self.stop_label, self.stop_combo_box)

        self.fixed_step_label = QLabel("Step:")
        self.fixed_step_spin_box = QDoubleSpinBox()
        self.fixed_step_spin_box.setMinimum(0)
        self.fixed_step_spin_box.setMaximum(float('inf'))
        self.fixed_step_spin_box.setValue(0)
        self.fixed_step_form_layout.addRow(self.fixed_step_label, self.fixed_step_spin_box)

        self.steps_number_label = QLabel("# of points:")
        self.steps_number_spin_box = QSpinBox()
        self.steps_number_spin_box.setMinimum(0)
        self.steps_number_spin_box.setSingleStep(1)
        self.steps_number_spin_box.setValue(2)
        self.steps_number_form_layout.addRow(self.steps_number_label, self.steps_number_spin_box)
        

    def handle_value_checkboxes_toggle(self):
        """Individually disable corresponding widgets when value checkboxes are toggled"""
        if self.single_point_button.isChecked():
            self.single_point_label.setEnabled(True)
            self.single_point_combo_box.setEnabled(True)

            self.start_label.setEnabled(False)
            self.start_combo_box.setEnabled(False)
            self.stop_label.setEnabled(False)
            self.stop_combo_box.setEnabled(False)

            self.fixed_step_button.setEnabled(False)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_button.setEnabled(False)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)
        else:
            self.single_point_label.setEnabled(False)
            self.single_point_combo_box.setEnabled(False)
            self.start_label.setEnabled(True)
            self.start_combo_box.setEnabled(True)
            self.stop_label.setEnabled(True)
            self.stop_combo_box.setEnabled(True)
            self.fixed_step_button.setEnabled(True)
            self.steps_number_button.setEnabled(True)
            self.handle_step_checkboxes_toggle()

    def handle_step_checkboxes_toggle(self):
        """Individually disable corresponding widgets when step checkboxes are toggled"""
        self.start_stop_button.setChecked(True)
        if self.fixed_step_button.isChecked():
            self.fixed_step_label.setEnabled(True)
            self.fixed_step_spin_box.setEnabled(True)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)          
        else:
            self.steps_number_button.setChecked(True)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_label.setEnabled(True)
            self.steps_number_spin_box.setEnabled(True)    
        
    def save_data(self):
        """Saves the sequence data"""
        if self.value_buttons_group.checkedButton() is None:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("No data")
            msg_box.setWindowIcon(self.lab_experiment_icon)
            msg_box.setText("Please provide data to build a sequence with this quantity.")
            msg_box.exec()
            self.reject()
            return

        self._level = self.level_spin_box.value()
        self._value_flag = self.single_point_button.isChecked()
        self._step_flag = self.fixed_step_button.isChecked()
        
        self._single_point_value = self.single_point_combo_box.currentText()
        self._start_value = self.start_combo_box.currentText()
        self._stop_value = self.stop_combo_box.currentText()
        self._fixed_step = self.fixed_step_spin_box.value()
        self._fixed_number_of_steps = self.steps_number_spin_box.value()
        # self._interpolation = "Linear"
        
        # Save user's data
        self.accept()


class ComplexConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


class DoubleConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)

        self.single_point_label = QLabel("Value:")
        self.single_point_spin_box = QDoubleSpinBox()
        self.single_point_spin_box.setMinimum(self._low_lim)
        self.single_point_spin_box.setMaximum(self._high_lim)

        if self._single_point_value:
            self.single_point_spin_box.setValue(self._single_point_value)
        if self._unit:
            self.single_point_spin_box.setSuffix(self._unit)
        self.single_point_form_layout.addRow(self.single_point_label, self.single_point_spin_box)

        self.start_label = QLabel("Start:")
        self.start_spin_box = QDoubleSpinBox()
        self.start_spin_box.setMinimum(self._low_lim)
        self.start_spin_box.setMaximum(self._high_lim)
        if self._unit:
            self.start_spin_box.setSuffix(self._unit)
        
        self.stop_label = QLabel("Stop:")
        self.stop_spin_box = QDoubleSpinBox()
        self.stop_spin_box.setMinimum(self._low_lim)
        self.stop_spin_box.setMaximum(self._high_lim)
        if self._unit:
            self.stop_spin_box.setSuffix(self._unit)

        self.start_stop_form_layout.addRow(self.start_label, self.start_spin_box)
        self.start_stop_form_layout.addRow(self.stop_label, self.stop_spin_box)

        self.fixed_step_label = QLabel("Step:")
        self.fixed_step_spin_box = QDoubleSpinBox()
        self.fixed_step_spin_box.setMinimum(0)
        self.fixed_step_spin_box.setMaximum(float('inf'))
        self.fixed_step_spin_box.setValue(0)
        if self._unit:
            self.fixed_step_spin_box.setSuffix(self._unit)
        self.fixed_step_form_layout.addRow(self.fixed_step_label, self.fixed_step_spin_box)

        self.steps_number_label = QLabel("# of points:")
        self.steps_number_spin_box = QSpinBox()
        self.steps_number_spin_box.setMinimum(2)
        self.steps_number_spin_box.setSingleStep(1)
        self.steps_number_spin_box.setValue(2)
        self.steps_number_form_layout.addRow(self.steps_number_label, self.steps_number_spin_box)

        self.fixed_step_spin_box.valueChanged.connect(self.fixed_step_changed)
        self.steps_number_spin_box.valueChanged.connect(self.steps_number_changed)

    def fixed_step_changed(self):
        """Executes when fixed step value is changed. Calculates and sets number of steps for this new fixed step value"""
        if self.fixed_step_spin_box.value() != 0.0:
            new_number_of_points = (self.stop_spin_box.value() - self.start_spin_box.value()) / self.fixed_step_spin_box.value()
            new_number_of_points = round(new_number_of_points)
            self.steps_number_spin_box.setValue(new_number_of_points + 1)
            if new_number_of_points != 0:
                new_fixed_step = (self.stop_spin_box.value() - self.start_spin_box.value()) / float(new_number_of_points)
                self.fixed_step_spin_box.setValue(new_fixed_step)
        else:
            self.steps_number_spin_box.setValue(0)

    def steps_number_changed(self):
        """Executes when number of steps is changed. Calculates and sets fixed step value for this new number of points"""
        if self.steps_number_spin_box.value() >= 2:
            new_fixed_step = (self.stop_spin_box.value() - self.start_spin_box.value()) / float(self.steps_number_spin_box.value() - 1)
            self.fixed_step_spin_box.setValue(new_fixed_step)
        else:
            self.fixed_step_spin_box.setValue(0.0)

    def handle_value_checkboxes_toggle(self):
        """Individually disable corresponding widgets when value checkboxes are toggled"""
        if self.single_point_button.isChecked():
            self.single_point_label.setEnabled(True)
            self.single_point_spin_box.setEnabled(True)

            self.start_label.setEnabled(False)
            self.start_spin_box.setEnabled(False)
            self.stop_label.setEnabled(False)
            self.stop_spin_box.setEnabled(False)

            self.fixed_step_button.setEnabled(False)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_button.setEnabled(False)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)
        else:
            self.single_point_label.setEnabled(False)
            self.single_point_spin_box.setEnabled(False)
            self.start_label.setEnabled(True)
            self.start_spin_box.setEnabled(True)
            self.stop_label.setEnabled(True)
            self.stop_spin_box.setEnabled(True)
            self.fixed_step_button.setEnabled(True)
            self.steps_number_button.setEnabled(True)
            self.handle_step_checkboxes_toggle()

    def handle_step_checkboxes_toggle(self):
        """Individually disable corresponding widgets when step checkboxes are toggled"""
        self.start_stop_button.setChecked(True)
        if self.fixed_step_button.isChecked():
            self.fixed_step_label.setEnabled(True)
            self.fixed_step_spin_box.setEnabled(True)
            self.steps_number_label.setEnabled(False)
            self.steps_number_spin_box.setEnabled(False)          
        else:
            self.steps_number_button.setChecked(True)
            self.fixed_step_label.setEnabled(False)
            self.fixed_step_spin_box.setEnabled(False)
            self.steps_number_label.setEnabled(True)
            self.steps_number_spin_box.setEnabled(True)    
        
    def save_data(self):
        """Saves the sequence data"""
        if self.value_buttons_group.checkedButton() is None:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("No data")
            msg_box.setWindowIcon(self.lab_experiment_icon)
            msg_box.setText("Please provide data to build a sequence with this quantity.")
            msg_box.exec()
            self.reject()
            return

        self._level = self.level_spin_box.value()
        self._value_flag = self.single_point_button.isChecked()
        self._step_flag = self.fixed_step_button.isChecked()
        
        self._single_point_value = self.single_point_spin_box.value()
        self._start_value = self.start_spin_box.value()
        self._stop_value = self.stop_spin_box.value()
        self._fixed_step = self.fixed_step_spin_box.value()
        self._fixed_number_of_steps = self.steps_number_spin_box.value()
        # self._interpolation = "Linear"
        
        # Save user's data
        self.accept()

class PathConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


class StringConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


class VectorConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


class VectorComplexConstructor(SequenceConstructor):
    def __init__(self, quantity: QuantityManager, logger: logging.Logger):
        super().__init__(quantity, logger)


def sequence_constructor_factory(quantity: QuantityManager, logger: logging.Logger):
    """
    Creates a sequence constructor object for quantities of each data type
    """    
    match quantity.data_type.upper():
        case 'BOOLEAN':
            return BooleanConstructor(quantity, logger)
        case 'BUTTON':
            return ButtonConstructor(quantity, logger)
        case 'COMBO':
            return ComboConstructor(quantity, logger)
        case 'COMPLEX':
            return ComplexConstructor(quantity, logger)
        case 'DOUBLE':
            return DoubleConstructor(quantity, logger)
        case 'PATH':
            return PathConstructor(quantity, logger)
        case 'STRING':
            return StringConstructor(quantity, logger)
        case 'VECTOR':
            return VectorConstructor(quantity, logger)
        case 'VECTOR_COMPLEX':
            return VectorComplexConstructor(quantity, logger)

