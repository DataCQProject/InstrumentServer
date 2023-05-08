import os
import sys
from time import sleep
import logging

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt
from pymeasure.display.Qt import QtWidgets
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
from datetime import datetime

from itertools import product
import numpy as np

"""
Implementation of Experiment Runner is inspired by PyMeasure's tutorial on ManagedWindow 
ref: https://pymeasure.readthedocs.io/en/latest/tutorial/graphical.html#using-the-managedwindow

MainExperimentProcedure extends PyMeasure's Procedure class and implements experiment according to
Experiment GUI's experiment DTO by creating dynamic loops. This is achieved using python's itertools package.
"""

###################################################################################
# StringParameter
###################################################################################
# Extend the implementation of procedure class using PyMeasure's Parameter rather than using local objects for attributes
# This is an example of defining a StringParameter class extending the Parameter class
# Default classes are already defined in PyMeasure for Integer and Float
class StringParameter(Parameter):
    """ :class:`Parameter` sub-class that uses the string type to store the value.

    :var value: The string value of the parameter
    :param name: The parameter name
    :param default: The default string value
    :param ui_class: A Qt class to use for the UI of this parameter
    """

    @property
    def value(self):
        if self.is_set():
            return self._value
        else:
            return ''

    @value.setter
    def value(self, value):
        self._value = str(value)


###################################################################################
# MainExperimentProcedure
###################################################################################
class MainExperimentProcedure(Procedure):   
    input = [] # 2D list with (int, qty) to be changed at different levels
    output = [] # list with (ins, qty) to measure
    sequence = {} # Dictionary with key -> (ins, qty), value -> sequence details dict: start, stop, number_of_points, data_type
    quantities = {} # Dictionary with key -> (ins, qty), value -> QuantitiyManager object

    # Dynamically added column names
    input_data_names = {}
    output_data_names = {}

    delay_time = 0 # delay time between each command

    def set_parameters(self, DTO, logger):
        """Sets values to all the above attributes using DTO from the Experiment GUI"""
        self.set_logger(logger)
        self.input = DTO.input_quantities
        self.sequence = DTO.quantity_sequences
        self.output = DTO.output_quantities
        self.quantities = DTO.quantitiy_managers

        self.delay_time = DTO.delay_time

        for level in self.input:
            for instrument_name, quantity_name in level:
                input_name = "Input - " + str(instrument_name) + " - " + str(quantity_name)
                self.input_data_names[(instrument_name, quantity_name)] = input_name
        for instrument_name, quantity_name in self.output:
            output_name = "Output - " + str(instrument_name) + " - " + str(quantity_name)
            self.output_data_names[instrument_name, quantity_name] = output_name
    
    def set_logger(self, logger: logging.Logger):
        """Sets logger"""
        self.logger = logger

    def startup(self):
        """Start up method"""
        self.logger.info('startup() was called')
        
    def generate_sequence(self, seq: dict):
        """Generates an array of values for [start, stop] range with given number of points"""
        if seq['datatype'].upper() == 'DOUBLE':
            return np.linspace(seq['start'], seq['stop'], seq['datapoints'])
        else:
            # implements the same for non-float or non-int values too, such as boolean or combo
            # generates a list of start and stop values of length of given number of points
            if seq['start'] != seq['stop']:
                number_of_points = seq['datapoints']
                return ([seq['start']] * (number_of_points // 2)) + ([seq['stop']] * (number_of_points - (number_of_points // 2)))
            else:
                return [seq['start']] * seq['datapoints']

    def execute(self):
        """Implements the experiment: creates dynamic loops; sets input values; records measured datapoint"""
        self.logger.info(f'Starting experiment')

        datapoints = 1 # number of datapoints
        individual_sequences = []

        # generate sequences
        for input_level in self.input:
            sequences_in_level = []
            for (ins, qty) in input_level:
                sequence = self.generate_sequence(self.sequence[(ins, qty)])
                sequences_in_level.append(sequence)
                if len(sequence) == 0:
                    # TODO: handle error
                    pass
            datapoints *= len(sequences_in_level[0])
            """
            example:
            converting [[1, 2, 3], ['a', 'b', 'c']] to [(1, 'a'), (2, 'b'), (3, 'c')]
            """
            sequences_in_order = list(zip(*sequences_in_level))
            individual_sequences.append(sequences_in_order)        
        
        combined_sequences = product(*individual_sequences)

        sleep_time = 0.001
        step = 0

        # Main experiment LOOP
        for step_sequence in combined_sequences:
            # step sequence is a list of tupules [(1 , 'a'), (True, )]
            # The datapoints we record at each "step":
 
            data = {}
            for level in range(len(self.input)):
                for index in range(len(self.input[level])):
                    (ins, qty) = self.input[level][index]                
                    self.quantities[(ins, qty)].set_value(step_sequence[level][index])
                    data[self.input_data_names[(ins, qty)]] = step_sequence[level][index]
                    sleep(self.delay_time)                

            for (ins, qty) in self.output:
                data[self.output_data_names[(ins, qty)]] = float(self.quantities[(ins, qty)].get_value())
                sleep(self.delay_time)

            data['step'] = step
            self.logger.info("Data point recorded: ", data)
            self.emit('results', data)
            self.logger.debug(f'Emitting results: {data}')
            self.emit('progress', 100 * step / datapoints)

            step += 1                

            if self.should_stop():
                self.logger.warning("Caught the stop flag in the procedure")
                break


###################################################################################
# MainExperimentWindow
###################################################################################
class ExperimentRunner(ManagedWindow):

    def __init__(self, parent_gui, logger: logging.Logger, base_filename='experiment_results'):
        # Initialize the super class

        # A reference to the invoking GUI
        self.parent_gui = parent_gui
        self.DTO = self.parent_gui.experiment_DTO

        # redefining procedure class with the experiment columns received from the Experiment GUI
        # This step is performed because ManagedWindow creates PlotWidget during its instantiation
        # It only takes the procedure_class's definition so the class definition has to be modified to
        # include the new dynamically added columns for the experiment plotting
        DATA_COLS = ['step']      
        for level in self.DTO.input_quantities:
            for instrument_name, quantity_name in level:
                input_name = "Input - " + str(instrument_name) + " - " + str(quantity_name)            
                DATA_COLS.append(input_name)

        for instrument_name, quantity_name in self.DTO.output_quantities:
            output_name = "Output - " + str(instrument_name) + " - " + str(quantity_name)
            DATA_COLS.append(output_name)

        MainExperimentProcedure.DATA_COLUMNS = DATA_COLS
        
        # ManagedWindow's constructor
        super().__init__(procedure_class=MainExperimentProcedure,
                         x_axis='step',
                         y_axis='step',
                         directory_input=True)  # Enables directory input widget    

        self.icons_dir = parent_gui.icons_dir
        play_icon = QIcon(os.path.join(self.icons_dir, "playButton.png"))
        self.setWindowIcon(play_icon)

        # The logger
        self.logger = logger        

        self.base_filename = base_filename
        self.setWindowTitle('Experiment Runner')
        self.directory = os.path.dirname(os.path.realpath(__file__))

        # Constructs the file menu up top
        self.construct_menu_bar()

        # This is the outermost widget or the "main" widget
        self.main_widget = self.main
        self.main_layout = self.main_widget.layout()

        quit_btn = QtWidgets.QPushButton('Quit', self)
        quit_btn.clicked.connect(self.exit_gui)

        self.main_layout.addWidget(quit_btn)
        self.main_layout.setAlignment(quit_btn, Qt.AlignmentFlag.AlignRight)

        self.show()

    def set_parameters(self, parameters):
        self.logger.info('Setting parameter values')
        return super().set_parameters(parameters)

    def queue(self, procedure=None):
        """
        Overrides ManagedWindow's queue method
        """
        self.logger.info('Starting measurement procedure')

        # The full path to file where the experiment results will be written to
        filename = os.path.join(self.directory, self.generate_experiment_file_name(self.base_filename))
        self.logger.info(f'Writing results to file {filename}')
        if procedure is None:
            procedure = MainExperimentProcedure()
            procedure.set_parameters(self.parent_gui.experiment_DTO, self.logger)

        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)

    def generate_experiment_file_name(self, base_name: str):
        """
        Generates the experiment filename (.txt) with appended system time timestamp
        ex: <base_name>_2023_03_19-01_51_06_PM_.txt
        """
        timestamp = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")
        return f'{base_name}_{timestamp}_.txt'

    def construct_menu_bar(self):
        """
        Constructs the Menu Bar on top
        """
        experiment_menu_bar = self.menuBar()
        experiment_menu_bar.addSeparator()
        file_menu = experiment_menu_bar.addMenu("&File")

        # Defines the action to exit GUI via the menu bar File section
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.exit_gui)
        file_menu.addAction(exit_action)

        help_menu = experiment_menu_bar.addMenu("&Help")

    def exit_gui(self):
        """
        self.close() automatically calls closeEvent
        """
        self.close()
        
    def closeEvent(self, event):
        """
        Closes the experiment GUI
        """
        self.logger.info("Exiting the window")
        # disconnect log_widget slots manually to avoid
        # RuntimeError: wrapped C/C++ object of type QPlainTextEdit has been deleted
        self.log_widget.view.disconnect()
        self.log_widget.handler.emitter.record.disconnect()
        
        super().closeEvent(event)        
        self.destroy()


if __name__ == "__main__":
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    window = ExperimentRunner(None, logger)
    window.show()
    sys.exit(app.exec())
