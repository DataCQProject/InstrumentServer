from PyQt6 import QtCore, QtWidgets as QtW
from PyQt6.QtGui import QFont
from typing import Callable


class QuantityFrame(QtW.QFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__()

        self.quantity_info = quantity_info
        self.set_value_method = set_value_method
        self.get_value_method = get_value_method
        self.label_weight = 1
        self.value_weight = 2

        self.layout = QtW.QHBoxLayout()

        self.label = QtW.QLabel()
        self.label.setText(quantity_info['label'])
        font = QFont()
        font.setBold(True)
        self.label.setFont(font)
        self.label.setMaximumHeight(25)
        self.layout.addWidget(self.label, self.label_weight)

        # TODO: Permission
        match self.quantity_info['permission'].upper():
            case 'NONE':
                pass
            case 'READ':
                pass
            case 'WRITE':
                pass
            # Both
            case _:
                pass

    @property
    def value(self):
        """Returns current value of the quantity by the given QWidget. Should be implemented by child class"""
        raise NotImplementedError()

    @property
    def state_quant(self):
        """Returns quantity that controls self's visibility"""
        return self.quantity_info['state_quant']

    @property
    def state_values(self):
        """Returns state values associated with state_quant for when self is visible"""
        return self.quantity_info['state_values']

    def set_value(self):
        self.set_value_method(self.quantity_info['name'], self.value)

    def get_value(self):
        try:
            value = self.get_value_method(self.quantity_info['name'])
            self.handle_incoming_value(value)
        except Exception as e:
            print(e)
            QtW.QMessageBox.critical(self, 'Error', str(e))

    def handle_incoming_value(self, value):
        """Handles any value returned by instrument to be properly displayed. Should be implemented by child class"""
        raise NotImplementedError()


class BooleanFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)

        # Create butto group and connect to method
        self.button_group = QtW.QButtonGroup()
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(self.set_value)

        # add radio buttons to group
        self.true_radio_button = QtW.QRadioButton("True")
        self.button_group.addButton(self.true_radio_button)
        self.true_radio_button.setToolTip(self.quantity_info['tool_tip'])
        self.false_radio_button = QtW.QRadioButton("False")
        self.button_group.addButton(self.false_radio_button)
        self.false_radio_button.setToolTip(self.quantity_info['tool_tip'])

        # create local layout and widget to
        h_layout = QtW.QHBoxLayout()
        h_layout.addWidget(self.true_radio_button)
        h_layout.addWidget(self.false_radio_button)

        widget = QtW.QWidget()
        widget.setLayout(h_layout)
        widget.setFixedHeight(40)

        widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        self.layout.addWidget(widget, self.value_weight)
        self.setLayout(self.layout)

        # set quantity value to last known value in DB or default value
        if self.quantity_info['latest_value']:
            self.handle_incoming_value(bool(self.quantity_info['latest_value']))
        else:
            self.handle_incoming_value(bool(self.quantity_info['def_value']))

    @QuantityFrame.value.getter
    def value(self):
        return self.true_radio_button.isChecked()
    
    def handle_incoming_value(self, value):
        self.true_radio_button.setChecked(value)
        self.false_radio_button.setChecked(not value)


class ButtonFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)


class ComboFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable,
                 on_value_change: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)
        self.on_value_change = on_value_change

        self.combo_box = QtW.QComboBox()
        self.combo_box.addItems(self.quantity_info['combos'])
        self.combo_box.setToolTip(self.quantity_info['tool_tip'])

        self.layout.addWidget(self.combo_box, self.value_weight)

        self.setLayout(self.layout)

    @QuantityFrame.value.getter
    def value(self):
        return self.combo_box.currentText()

    def set_value(self):
        """Overrides and calls QuantityGroup set_value. Afterwards, it calls the handler method that was passed through
        at instantiation"""
        super().set_value()
        self.on_value_change(self.quantity_info['name'], self.value)

    def handle_incoming_value(self, value):
        self.combo_box.setCurrentText(value)


class ComplexFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)


class DoubleFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)

        self.spin_box = QtW.QDoubleSpinBox()

        # Set min/max. Floats can handle '+-INF'
        low = float(quantity_info["low_lim"])
        high = float(quantity_info["high_lim"])
        self.spin_box.setMinimum(low)
        self.spin_box.setMaximum(high)
        self.spin_box.setSuffix(f" {self.quantity_info['unit']}")
        self.spin_box.setToolTip(self.quantity_info['tool_tip'])

        self.layout.addWidget(self.spin_box, self.value_weight)

        self.setLayout(self.layout)

        # set quantity value to default value
        self.handle_incoming_value(float(self.quantity_info['def_value']))

    @QuantityFrame.value.getter
    def value(self):
        return self.spin_box.value()
    
    def handle_incoming_value(self, value):
        self.spin_box.setValue(float(value))
        

class PathFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)


class StringFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)


class VectorFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)
        self.setLayout(self.layout)


class VectorComplexFrame(QuantityFrame):
    def __init__(self, quantity_info: dict, set_value_method: Callable, get_value_method: Callable):
        super().__init__(quantity_info, set_value_method, get_value_method)


def quantity_frame_factory(quantity_info: dict, set_value_method: Callable, get_value_method: Callable,
                           on_value_change: Callable = None):
    match quantity_info['data_type'].upper():
        case 'BOOLEAN':
            return BooleanFrame(quantity_info, set_value_method, get_value_method)
        case 'BUTTON':
            return ButtonFrame(quantity_info, set_value_method, get_value_method)
        case 'COMBO':
            return ComboFrame(quantity_info, set_value_method, get_value_method, on_value_change)
        case 'COMPLEX':
            return ComplexFrame(quantity_info, set_value_method, get_value_method)
        case 'DOUBLE':
            return DoubleFrame(quantity_info, set_value_method, get_value_method)
        case 'PATH':
            return PathFrame(quantity_info, set_value_method, get_value_method)
        case 'STRING':
            return StringFrame(quantity_info, set_value_method, get_value_method)
        case 'VECTOR':
            return VectorFrame(quantity_info, set_value_method, get_value_method)
        case 'VECTOR_COMPLEX':
            return VectorComplexFrame(quantity_info, set_value_method, get_value_method)


class QuantityGroupBox(QtW.QGroupBox):
    def __init__(self, group_name: str, frames: list[QuantityFrame]):
        super().__init__()

        self.layout = QtW.QVBoxLayout()

        self.label = QtW.QLabel()
        self.label.setText(group_name)
        font = QFont()
        font.setBold(True)
        self.label.setFont(font)
        self.label.setMaximumHeight(25)
        self.layout.addWidget(self.label)

        for frame in frames:
            self.layout.addWidget(frame)

        self.setLayout(self.layout)