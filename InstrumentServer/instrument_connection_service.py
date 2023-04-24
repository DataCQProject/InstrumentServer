import pyvisa
import requests
import logging
from enum import Enum
from http import HTTPStatus
from Instrument.instrument_manager import InstrumentManager
import sys
import importlib
import os


class INST_INTERFACE(Enum):
    USB = 'USB'
    GPIB = 'GPIB'
    TCPIP = 'TCPIP'
    SERIAL = 'SERIAL'
    ASRL = 'ASRL'
    COM = 'COM'


class AlreadyConnectedError(Exception):
    pass


class InstrumentConnectionService:
    def __init__(self, logger: logging.Logger) -> None:
        self._connected_instruments = {}
        self._my_logger = logger

    @property
    def connected_instruments(self):
        return self._connected_instruments

    @property
    def my_logger(self):
        return self._my_logger

    def is_connected(self, cute_name: str) -> bool:
        return cute_name in self._connected_instruments.keys()

    def connect_to_visa_instrument(self, cute_name: str):
        """Creates and stores connection to given VISA instrument"""

        if self.is_connected(cute_name):
            raise AlreadyConnectedError(f'{cute_name} is already connected.')

        # Use cute_name to determine the interface (hit endpoint for that)
        url = r'http://127.0.0.1:5000/instrumentDB/getInstrument'
        response = requests.get(url, params={'cute_name': cute_name})

        # raise exception for error
        if HTTPStatus.OK < response.status_code >= HTTPStatus.MULTIPLE_CHOICES:
            response.raise_for_status()

        driver_dict = dict(response.json())
        interface = driver_dict['instrument_interface']['interface']
        address = driver_dict['instrument_interface']['address']

        self._my_logger.debug(f'Cute_name: {cute_name} uses interface: {interface} and address: {address}')

        # Get list of resources to compare to
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        connection_str = None

        if interface == INST_INTERFACE.TCPIP.name:
            connection_str = self.make_conn_str_tcip_instrument(address)

        elif interface == INST_INTERFACE.USB.name and INST_INTERFACE.ASRL.name in address:
            # Serial instruments do not have "USB" in the connection string
            for resource in resources:
                if address in resource:
                    connection_str = resource
                    break

        else:
            # Get the connection string (used to get PyVISA resource)
            for resource in resources:
                if interface in resource and address in resource:
                    connection_str = resource
                    break

        if connection_str is None:
            raise ConnectionError(f"Could not connect to {cute_name}. Available resources are: {resources}")

        # Connect to instrument
        self._my_logger.debug('Using connection string: {connection_str} to connect to {cute_name}')

        driver_path = driver_dict["general_settings"]["driver_path"]
        if driver_path:
            # importing custom driver module from the driver_path
            # Assumption: driver_path and driver are the same
            driver_path = driver_dict["general_settings"]["driver_path"]
            module_location = os.sep.join(driver_path.split(os.sep)[:-1])
            module_name = driver_path.split(os.sep)[-1].replace(".py", "")

            sys.path.append(module_location)
            custom_driver = importlib.import_module(module_name)

            ManagerClass = getattr(custom_driver, module_name)
        else:
            ManagerClass = InstrumentManager

        try:
            im = ManagerClass(cute_name, connection_str, driver_dict, self._my_logger)
            self._connected_instruments[cute_name] = im
            self._my_logger.info(f"VISA connection established to: {cute_name}.")
        # InstrumentManager may throw value error, this service should throw a Connection error
        except Exception as e:
            raise ConnectionError(e)

    def connect_to_none_visa_instrument(self, cute_name: str):
        """Creates and stores connection to given NONE_VISA instrument"""
        if cute_name in self._connected_instruments.keys():
            raise ValueError(f'{cute_name} is already connected.')

        # Use cute_name to determine the interface (hit endpoint for that)
        url = r'http://127.0.0.1:5000/instrumentDB/getInstrument'
        response = requests.get(url, params={'cute_name': cute_name})
        # raise exception for error
        if 200 < response.status_code >= 300:
            response.raise_for_status()

        response_dict = dict(response.json())
        try:
            # importing custom driver module from the driver_path
            driver_path = response_dict["general_settings"]["driver_path"]
            if os.path.exists(driver_path):
                self._my_logger.info(f"Custom module file {driver_path} exists.")
            module_name = driver_path.split(os.sep)[-1].replace(".py", "")
            module_location = os.sep.join(driver_path.split(os.sep)[:-1])
            sys.path.append(module_location)
            custom_driver = importlib.import_module(module_name)
            im = getattr(custom_driver, module_name)(name=cute_name, driver=response_dict, logger=self.my_logger)
            self._connected_instruments[cute_name] = im

            self._my_logger.info(f"Connected to {cute_name}.")

        # InstrumentManager may throw value error, this service should throw a Connection error
        except ValueError as e:
            raise ConnectionError(e)

    def disconnect_instrument(self, cute_name: str):
        if cute_name not in self._connected_instruments.keys():
            return

        del self._connected_instruments[cute_name]
        self.my_logger.debug(f"Disconnected {cute_name}.")

    def disconnect_all_instruments(self):
        instr_names = list(self._connected_instruments.keys())
        list_of_failures = list()

        for instrument_name in instr_names:
            try:
                self.disconnect_instrument(instrument_name)
            except:
                list_of_failures.append(instrument_name)

        if len(list_of_failures) > 0:
            raise Exception(f"Failed to disconnect from the following instruments: {list_of_failures}")

    def get_instrument_manager(self, cute_name):
        if cute_name not in self._connected_instruments.keys():
            raise KeyError(f"{cute_name} is not currently connected.")

        return self._connected_instruments[cute_name]

    def make_conn_str_tcip_instrument(self, address: str) -> str:
        """
        Construct a connection string for TCPIP instruments
        Example: TCPIP0::192.168.0.7::INSTR
        """
        # Default TCPIP Interface
        TCPIP_INTERFACE = 'TCPIP0'
        END = 'INSTR'

        return f'{TCPIP_INTERFACE}::{address}::{END}'

    def add_instrument_to_database(self, details: dict):
        url = r'http://127.0.0.1:5000/instrumentDB/addInstrument'
        response = requests.post(url, json=details)
        if HTTPStatus.MULTIPLE_CHOICES > response.status_code <= HTTPStatus.OK:
            return True, response.json()
        else:
            return False, response.json()

    def remove_instrument_from_database(self, cute_name: str):

        try:
            # disconnect instrument only if it's connected
            if cute_name in self._connected_instruments.keys():
                self.disconnect_instrument(cute_name)

        except KeyError:
            self._my_logger.info(f'Instrument {cute_name} is not currently connected.')
        except Exception as e:
            self._my_logger.info(f'Instrument {cute_name} is not currently connected.')

        url = r'http://127.0.0.1:5000/instrumentDB/removeInstrument'
        response = requests.get(url, params={'cute_name': cute_name})
        if HTTPStatus.MULTIPLE_CHOICES > response.status_code <= HTTPStatus.OK:
            return "Instrument removed."
        else:
            self._my_logger.fatal(response.raise_for_status())
        return "Failed to remove the instrument."
