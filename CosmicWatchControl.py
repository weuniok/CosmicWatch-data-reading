"""
Pawel Pietrzak 29.09.2020
Project: Cosmic ray measurements in automation cycle using Python programming
TeFeNica 2020 Summer Student Internship
Saving data sent by the CosmicWatch Detector
Contact: pawel.pietrzak7.stud@pw.edu.pl
"""

from PyQt5.QtCore import pyqtSignal, QObject
import datetime
from pathlib import Path
from threading import Thread, Event
import serial

class CosmicWatch(QObject):
    '''
    port_name: com port, string, e.g. 'com7'
    detector: pySerial serial object, opened serial port
    directory: folder path to save in, e.g. 'C:\\Program Files\\"
    device_id: detector ID
    mode: master/slave
    full_path: full path to saved file, e.g. 'C:\\Program Files\\example.csv'
    '''

    # variables used by the GUI must be declared outside of __init__
    port_name = '' # com port used
    detector = serial.Serial() #pySerial serial object used for COM port communication
    directory = '' # directory of measurements folder
    device_id = 'N/A'
    mode = 'N/A' # Master or Slave
    full_path = 'N/A' # e.g. 'C:\Program Files\example.csv'
    amplitude = 'N/A' # SiPM voltage of last event
    number = 'N/A' # event number
    time = 'N/A' # event time
    rate = 'N/A' # event rate/s
    rate_error = 'N/A' # +/- error of rate
    time_start = 0
    deadtime = 0
    fail_counter = 0 # data reading will stop after 4 failed attempts to read data
    stop = False

    distance = '' # sent by GUI, distance between detectors
    angle = '' # sent by GUI, angle between detectors

    # amplitudes_list = [] # list of all amplitudes
    # adc_list = [] # list of all digital amplitudes

    paused = False # bool value whether detector is in pause mode in which it ignores reading

    table_updater = pyqtSignal() # signal sent to GUI to update table
    chart_initializer = pyqtSignal() # signal sent to GUI to initialize chart when it's ready


    def __init__(self):
        # clear ampliudes and adc lists, to make sure GUI won't keep old values
        self.amplitudes_list = []
        self.adc_list = []
        self.amplitudes_list.clear()
        self.adc_list.clear()

        super().__init__()

    def read_header(self):
        '''
        Reads header and first 2 lines sent by CosmicWatch detector connected through cosmic_watch serial port.
        These first 2 lines are expected to contain detector ID and mode.
        :returns: header sent by CosmicWatch
        '''
        header = []
        for i in range(5):  # read 5 lines even if they don't start with
                            # because of possible SD Card alert before header
            try:
                new_line = self.detector.readline().decode()
                header.append(new_line)
                print(new_line)
                if new_line[0] == '#':
                    break
            except:
                pass

        while new_line[0] == '#': # read the rest of the header
            try:
                new_line = self.detector.readline().decode()
            except:
                print('WARNING: A line was not read correctly')
                #TODO log warning
            header.append(new_line)
            print(new_line)
        # first message not starting with #, expected: 'DetectorID: ***'
        if new_line[0:8] == 'Detector':
            self.device_id = new_line[12:-2]  # read the name, removed characters are CR LF
        else:
            self.device_id = 'Unknown'
            print('WARNING: Detector Name not read correctly. Saving as "Unknown"')
            #TODO log wraning
        # now expected: 'DetectorMode: Master/Slave'
        new_line = self.detector.readline().decode()
        header.append(new_line)
        print(new_line)
        self.mode = new_line[14:-2]
        if self.mode == 'Master':
            pass
        elif self.mode == 'Slave':
            pass
        else:
            # raise Error('Mode not read correctly')
            print("WARNING: Detector Mode not read correctly. Assuming Master.")
            self.mode = 'Master'

        return header

    def create_file(self, header):
        '''
        Creates file with name depending on local time and the device connected.
        Updates self.full_path with full file path.
        '''
        # Get workplace directory
        self.directory = self.masterGUI.current_measurement_folder + '\\'
        results_name = ''
        results_name += self.time_start.strftime('%Y%m%d_%H%M%S')
        # Identify the device
        if self.mode == 'Master':
            results_name += ('_MASTER_')
        else:
            results_name += ('_SLAVE_')
        results_name += self.device_id
        results_name += '.csv'
        print(results_name)

        # MOVED TO GUI
        # try:
        #     Path(self.directory).mkdir(exist_ok=True, parents=True)  # Create CosmicWatch directory if doesn't exist
        # except FileNotFoundError:
        #     print('Incorrect path.')
        #     # what next? *************
        # except PermissionError:
        #     print('This path requires additional permissions.')
        #     # what next? *************

        self.full_path = self.directory + results_name

        with open(self.full_path, 'w', newline='') as results:
            # TODO better header edition
            # TODO editing not ignoring arduino header
            header[-4] = '### Comp_date Comp_time Event Ardn_time[ms] ' \
                         'ADC[0-1023] SiPM[mV] Deadtime[ms] Temp[C] Rate[N/s]\r\n'

            header[
                -4] = '### Distance: ' + self.distance + ' cm; Angle: ' + self.angle + ' degrees\r\n' + header[-4]

            #
            for string in header:
                results.write(string)
            results.write('\r\n')
            print('\r\n')

        self.masterGUI.update_log('Detector connected on port: ' +self.port_name + '. ID: ' + self.device_id + \
                                  '. Mode: '+ self.mode)
        self.masterGUI.update_log('Measurements file for ID ' + self.device_id + ', Mode: ' + self.mode + \
                                  ', created. Path: ' + self.full_path)

    def read_data(self):
        '''
        Reads data from serial port, saves it to specified file and prints it in console.
        Calls self.update_values() to update values tracked by GUI.
        '''
        with open(self.full_path, 'a', newline='') as cosmic_file:
            while True:
                # reads line from the port and prints it
                try:
                    feedback = self.detector.readline().decode()
                    if self.paused == True:
                        pass
                    elif feedback == '':
                        pass
                    elif feedback[0] == '#':
                        print(feedback)
                        cosmic_file.write(feedback)
                    else:
                        time_now = datetime.datetime.now(datetime.timezone.utc)
                        comp_date = time_now.strftime('%Y-%m-%d ')
                        comp_time = time_now.time().strftime('%H:%M:%S.%f')
                        comp_time = comp_time[0:-3] + ' '
                        time_delta = int((time_now - self.time_start).total_seconds() * 1000)  # milliseconds since launch
                        record = comp_date + comp_time + feedback

                        printable_record = self.update_values(record, time_delta)
                        self.table_updater.emit()

                        print(printable_record)
                        cosmic_file.write(printable_record)

                    if self.fail_counter >=4:
                        message =  'Connection with ' + self.port_name + \
                                  ' restored. Connected CosmicWatch ID: ' + \
                                  self.device_id + ' Mode: ' + self.mode + '.'
                        self.masterGUI.update_log(message)
                    self.fail_counter = 0

                except Exception as exc:
                    if self.fail_counter <= 4:
                        self.fail_counter += 1
                        message = 'Port: ' + self.port_name + '. Data line cannot be read. Retrying.  Exception: ' + \
                                  repr(exc)
                        self.masterGUI.update_log(message)
                    elif self.fail_counter == 4:
                        self.fail_counter += 1
                        message = 'Data cannot be read 4 times. Connection with ' + self.port_name + \
                                  ' lost. Disconnected CosmicWatch ID: ' + \
                                  self.device_id + ' Mode: ' + self.mode + '.'
                        self.masterGUI.update_log(message)
                    print(repr(exc))
                    break

    def run_detector(self):
        '''
        Open serial port -> read header -> Update GUI datatable -> Create file using header -> Read data
        '''
        self.detector = serial.Serial(self.port_name, 9600, timeout=10)  # initialize serial port
        header = self.read_header()  # reads device name
        self.masterGUI.init_table(self)  # initialize
        self.table_updater.emit()
        self.chart_initializer.emit()

        self.create_file(header)  # gets full directory to results file
        # while self.fail_counter < 4:
        #     self.read_data()  # read data from cosmic_watch port into created_file file

        #debug
        event = Event()
        while True:
            self.read_data()  # read data from cosmic_watch port into created_file file
            if self.stop == True:
                break
            try:
                self.detector = serial.Serial(self.port_name, 9600, timeout=10)  # initialize serial port
            except:
                pass
            event.wait(3.0)

    def run(self):
        '''
        Open serial port -> read header -> Update GUI datatable -> Create file using header -> Read data
        '''
        #try:
        self.detector = serial.Serial(self.port_name, 9600, timeout=10)  # initialize serial port
        header = self.read_header()  # reads device name
        self.masterGUI.init_table(self) # initialize
        #   self.table_updater.emit()

        self.create_file(header)  # gets full directory to results file
        self.read_data()  # read data from cosmic_watch port into created_file file
        # except Exception as exc:
        #     message = 'Port: ' + self.port_name + '. Error. Exception: ' + \
        #               repr(exc)
        #     self.masterGUI.update_log(message)

    def start_program(self):
        '''
        Run detector in thread.
        '''
        self.run_thread = Thread(target=self.run_detector)
        self.run_thread.start()

    def stop_program(self):
        '''
        Closes the serial port to stop the program via an exception.
        '''
        # reset data lists
        self.detector.reset_input_buffer()
        self.detector.close()
        self.stop = True # end thread via exception
        #self.run_thread.

    def update_values(self, record, time_delta):
        '''
        Updates values tracked by GUI and returns it to be saved back to self.read_data
        :param record: string from self.read_data with read values.
        :param time_delta: time since start in milliseconds from OS
        '''
        record = record.split()
        self.time = record[1]
        self.number = record[2]
        number = float(self.number)
        self.adc = record[4]
        self.amplitude = record[5]
        
        realtime = time_delta/1000 # in seconds
        rate = number / realtime

        self.deadtime = float(record[6]) / 1000 + self.masterGUI.pause_deadtime_seconds   # in seconds, adjusted for pause
        livetime = realtime - self.deadtime  # in seconds

        self.rate = str(round(rate, 3))
        self.rate_error = (number**(1/2) / livetime) / rate
                          # sqrt(number) / ( total time - dead time) in percent
        self.rate_error = "{:.3%}".format(self.rate_error)

        # data for charts
        self.adc_list.append(float(self.adc))
        self.amplitudes_list.append(float(self.amplitude))

        #adjust record
        record[6] = int(self.deadtime * 1000)
        #add rate
        printable_record = " ".join(map(str, record)) + ' ' + self.rate

        return printable_record + "\r\n"

        # this is a good place to print something for debugging purpose