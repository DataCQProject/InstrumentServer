from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QTreeWidget, QTreeWidgetItem)
from Insrument.instrument_manager import InstrumentManager
from GUI.quantity_frames import *
import logging


class InstrumentManagerGUI(QWidget):
    def __init__(self, instrument_manager: InstrumentManager, logger: logging.Logger):
        super(InstrumentManagerGUI, self).__init__()

        self._im = instrument_manager
        self.logger = logger
        self.quantity_frames = list()
        self.section_frames = dict()
        self.section_tree_weight = 1
        self.section_data_weight = 3

        self.scroll_layout = QVBoxLayout()

        # add all quantities to layouts dependent on section and group name
        self._build_quanitity_sections()
        # add sections to layout
        for section_name, section in self.section_frames.items():
            section.setHidden(True)
            self.scroll_layout.addWidget(section)

        self.scroll_layout.addStretch(1)
        self.scroll_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # this widget is needed for the QScrollArea
        widget = QWidget()
        widget.setLayout(self.scroll_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(widget)
        self.scroll_area.setWidgetResizable(True)

        self._build_section_tree()

        main_layout = QHBoxLayout()
        main_layout.addWidget(self.section_tree, self.section_tree_weight)
        main_layout.addWidget(self.scroll_area, self.section_data_weight)
        self.setLayout(main_layout)

        self.setWindowTitle(f"{self._im.name} Manager")
        self.show()
        self.resize(800, 600)

    def _build_quanitity_sections(self):
        """Loops through all quantities and adds them to the correct groups and lookup list.
        Groups are then assigned to sections. Groups/sections can be found in instrument driver"""
        sections = dict()

        for quantity in self._im.quantity_names:
            quantity_info = self._im.get_quantity_info(quantity)

            frame = quantity_frame_factory(quantity_info, self._im.set_value,
                                           self._im.get_value, self.logger, self.handle_quant_value_change)
            frame.setFixedHeight(40)

            # store all frames in a lookup list
            # This is used to hide quantities if their visibility is tied to another quantity value
            self.quantity_frames.append(frame)

            # get section name, default to Uncategorized
            section_name = quantity_info['section']
            if not section_name:
                section_name = 'Uncategorized'
            # get group name, default to Uncategorized
            group_name = quantity_info['groupname']
            if not group_name:
                group_name = 'Uncategorized'

            # create new section
            if section_name not in sections:
                sections[section_name] = dict()

            # add new frame to existing group
            if group_name in sections[section_name]:
                sections[section_name][group_name].append(frame)
            # create new group
            else:
                sections[section_name][group_name] = list()
                sections[section_name][group_name].append(frame)

        # construct frames for each section
        for section_name, section in sections.items():
            section_frame = QtW.QFrame()
            section_layout = QtW.QVBoxLayout()

            # construct groupboxes for each group
            for group_name in sections[section_name]:
                quantities = section[group_name]
                section_layout.addWidget(QuantityGroupBox(group_name, quantities))

            # set section layout and add to lookup dictionary
            section_frame.setLayout(section_layout)
            self.section_frames[section_name] = section_frame

    def _build_section_tree(self):
        self.section_tree = QTreeWidget()
        self.section_tree.setHeaderLabels(["Sections"])

        for section_name in self.section_frames:
            item = QTreeWidgetItem()
            item.setText(0, section_name)
            self.section_tree.addTopLevelItem(item)

        self.section_tree.itemSelectionChanged.connect(self._handle_section_change)
        self.section_tree.setCurrentItem(self.section_tree.topLevelItem(0))

        return self.section_tree

    def _handle_section_change(self):
        selected_section_name = self.section_tree.currentItem().text(0)

        for section_name, section in self.section_frames.items():
            if section_name == selected_section_name:
                section.setHidden(False)
            else:
                section.setHidden(True)

    def handle_quant_value_change(self, state_quant_name, state_value):
        """Called by QuantityFrame when the quantity's value is changed.
        Sets visibility of other quantities depending on new value"""
        for quantity_frame in self.quantity_frames:
            # Not dependent on the quantity that changed
            if quantity_frame.state_quant != state_quant_name:
                continue

            # the list is populated with quantity.state_values in user form
            if state_value in (self._im.convert_return_value(state_quant_name, v) for v in quantity_frame.state_values):
                quantity_frame.setHidden(False)
                self.logger.debug(f"{quantity_frame.name} is now visible.")
            else:
                quantity_frame.setHidden(True)
                self.logger.debug(f"{quantity_frame.name} is now hidden.")
