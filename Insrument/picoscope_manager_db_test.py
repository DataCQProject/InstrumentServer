from picoscope_manager import PicoscopeManager
from InstrumentServer.instrument_connection_service import *

details = {"cute_name": "Picoscope 6000",
           "interface": "USB",
           "ip_address": "N/A",
           "serial": "False",
           "visa": "False",
           "path": r'C:\GitHub\jkoo\InstrumentServer\Picoscope_6000.ini'
           }

connect_result, msg = add_instrument_to_database(details)

print(connect_result)
print(msg)

#
#
# driver = r'C:\GitHub\jkoo\InstrumentServer\Picoscope_6000.ini'
# ps6000 = PicoscopeManager(driver)
# try:
#     print(ps6000.get_value('Frequency'))
#     print(ps6000.get_value('Offset'))
#     print(ps6000.get_value('Amplitude'))
#     print(ps6000.get_value('Wave Type'))
#
#     ps6000.set_value('Frequency', 1000)
#     ps6000.set_value('Offset', 0)
#     ps6000.set_value('Amplitude', 4)
#     ps6000.set_value('Wave Type', "Sine")
#
#     print("----------------------------")
#     print(ps6000.get_value('Frequency'))
#     print(ps6000.get_value('Offset'))
#     print(ps6000.get_value('Amplitude'))
#     print(ps6000.get_value('Wave Type'))
#
#     ps6000._signal_generator()
#
# except Exception as e:
#     print(e)
# finally:
#     ps6000._close()
