import logging
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from GUI.quantity_frames import *
from GUI.sequence_constructor import *
import json
     
class StepSequenceTreeWidget(QTreeWidget):
    def __init__(self, channels_added: dict(), item_valid: Callable, logger: logging.Logger):
        super().__init__()
        self.logger = logger

        # dictionary for added channels in the table
        self.channels_added = channels_added

        # dictionary for quantities of each added channel
        # key: (instrument_name, quantity_name)
        # value: SequenceConstructor object
        self.quantities_added = dict()

        self.setDragEnabled(True) # TODO: Disable manual rearrangement
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
         # Disabling arrows in the Tree Widget
        self.setStyleSheet( "QTreeWidget::branch{border-image: url(none.png);}") # TODO: Remove

        # Tree Widget Items remain expanded, disabling the option to toggle expansion
        self.setItemsExpandable(False) # TODO: Remove

        # Allow only one selection at a time -> SingleSelection
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.item_valid = item_valid

        """
        Column Order:
        [Loop Level, Instrument, Quantity, Number of points, Value/Range]
        """
        self.setHeaderLabels(['Level', 'Instrument', 'Quantity', '# pts.', 'Value/Step range'])
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)        

        self.itemSelectionChanged.connect(self.step_sequence_table_selection_changed)
        self.itemDoubleClicked.connect(self.show_sequence_constructor_gui)

    @property
    def quantities(self):
        return self.quantities_added.keys()

    def check_item_valid(self, instrument_name, quantity_name):
        # Check if the channel already exists
        if (instrument_name, quantity_name) in self.quantities_added.keys():
            return False
        return True

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/json'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/json'):
            byte_data = event.mimeData().data('application/json')
            json_string = str(byte_data, 'utf-8')
            data_dict = json.loads(json_string)
            if self.item_valid(data_dict['instrument_name'], data_dict['quantity_name']):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/json'):
            byte_data = event.mimeData().data('application/json')
            json_string = str(byte_data, 'utf-8')
            data_dict = json.loads(json_string)

            instrument_name = data_dict['instrument_name']
            quantity_name = data_dict['quantity_name']

            # TODO: Remove
            if (instrument_name, quantity_name) in self.quantities_added.keys():
                event.ignore()
                return
            
            quantity = self.channels_added[instrument_name].quantities[quantity_name]
            create_sequence_dialog = sequence_constructor_factory(quantity, self.logger)
            if create_sequence_dialog.exec():
                self.quantities_added[(instrument_name, quantity_name)] = create_sequence_dialog
                self.add_tree_item(create_sequence_dialog)
                self.update_tree()

        else:
            event.ignore()

    def add_tree_item(self, sequence_constructor):
        instrument_name = sequence_constructor.instrument_name
        quantity_name = sequence_constructor.quantity_name
        level = sequence_constructor.level

        if sequence_constructor.value_flag:
            value = sequence_constructor.single_point_value
            points = sequence_constructor.number_of_points
            unit = sequence_constructor.unit
            QTreeWidgetItem(self, [str(level), instrument_name, quantity_name, str(points), str(value) + unit])
        else:
            start = sequence_constructor.start_value
            stop = sequence_constructor.stop_value
            points = sequence_constructor.number_of_points
            unit =  sequence_constructor.unit                
            QTreeWidgetItem(self, [str(level), instrument_name, quantity_name, str(points), str(start) + unit +' - '+ str(stop) + unit])

    def show_sequence_constructor_gui(self, selected_item, column=None):
        instrument_name = selected_item.text(1)
        quantity_name = selected_item.text(2)
        if (instrument_name, quantity_name) in self.quantities_added.keys():
            sequence_constructor = self.quantities_added[(instrument_name, quantity_name)]
            if sequence_constructor.exec():
                level = sequence_constructor.level
                selected_item.setText(0, str(level))

                if sequence_constructor.value_flag:
                    value = sequence_constructor.single_point_value
                    points = sequence_constructor.number_of_points
                    unit =  sequence_constructor.unit
                    selected_item.setText(3, str(points))
                    selected_item.setText(4, str(value) + unit)
                else:
                    start = sequence_constructor.start_value
                    stop = sequence_constructor.stop_value
                    points = sequence_constructor.number_of_points
                    unit =  sequence_constructor.unit
                    selected_item.setText(3, str(points))
                    selected_item.setText(4, str(start)+unit+' - '+str(stop)+unit)
            self.update_tree()
        return

    """ Removes a selected quantitiy sequence from the Step Sequence Table """
    def remove_quantity(self):
        selected_item = self.currentItem()
        if selected_item is not None:     
            instrument_name = selected_item.text(1)
            quantity_name = selected_item.text(2)       
            del self.quantities_added[(instrument_name, quantity_name)]
            self.takeTopLevelItem(self.indexOfTopLevelItem(selected_item))

    """ Removes all quantity sequences related to an instrument from the Step Sequence Table """
    def remove_channel(self, cute_name):
        if cute_name:
            # Traverse the tree in reverse to remove the tree widgets that belong to an instrument
            for index in range(self.topLevelItemCount() - 1, -1, -1):
                tree_item = self.topLevelItem(index)
                ins, qty = tree_item.text(1), tree_item.text(2)
                if (ins, qty) in self.quantities_added.keys() and ins == cute_name:
                    del self.quantities_added[(ins, qty)]
                    self.takeTopLevelItem(index)

    def update_tree(self):
        # Sort the tree items based on level value
        self.sortItems(0, Qt.SortOrder.AscendingOrder)  

    def step_sequence_table_selection_changed(self):
        selected_item = self.currentItem()
        pass

    def validate_sequence(self):
        current_level = None
        current_points = None
        for i in range(self.topLevelItemCount()):
            tree_item = self.topLevelItem(i)
            ins, qty = tree_item.text(1), tree_item.text(2)
            if (ins, qty) in self.quantities_added.keys():
                sc = self.quantities_added[(ins, qty)]
                if sc.level != current_level:
                    current_level = sc.level
                    current_points = sc.number_of_points
                else:
                    if sc.number_of_points != current_points:
                        self.logger.error(f"Number of points for {qty} of {ins} does not does not match the corresponding number of points at its level.")
                        msg_box = QMessageBox()
                        msg_box.setIcon(QMessageBox.Icon.Critical)
                        msg_box.setWindowTitle("Invalid sequence data")
                        lab_experiment_icon = QIcon("../Icons/labExperiment.png")
                        msg_box.setWindowIcon(lab_experiment_icon)
                        msg_box.setText(f"""Number of points for '{qty}' of '{ins}' does not match the corresponding number of points at level {sc.level}.
For single valued quantities, set 'start' and 'stop' to this value and change the number of points.""")
                        msg_box.exec()
                        return False

            else:
                self.logger.error(f"{qty} of {ins} not found in Step Sequence table.")
                return False
            
        return True
    
    def get_step_sequence_quantities(self):
        input_quantities = []
        quantity_sequences = {}
        current_level = None        
        for i in range(self.topLevelItemCount()):
            tree_item = self.topLevelItem(i)
            ins, qty = tree_item.text(1), tree_item.text(2)
            if (ins, qty) in self.quantities_added.keys():
                # sc is the sequence constructor object for the quantity
                sc = self.quantities_added[(ins, qty)]

                level = sc.level
                if current_level != level:
                    input_quantities.append([(ins, qty)]) # create a new level of inputs
                    current_level = level
                else:
                    input_quantities[-1].append((ins, qty)) # append to the previous level of inputs
                              
                data_type =  sc.data_type
                if sc.value_flag:
                    points = 1
                    start = stop = sc.single_point_value
                else:
                    points = sc.number_of_points
                    start = sc.start_value
                    stop = sc.stop_value
                quantity_sequences[(ins, qty)] = {'datapoints': points, 
                                        'start':start, 
                                        'stop':stop, 
                                        'datatype': data_type}

            else:
                self.logger.error(f"{qty} of {ins} not found in Step Sequence table.")
                break
            
        return input_quantities, quantity_sequences

            

            
                