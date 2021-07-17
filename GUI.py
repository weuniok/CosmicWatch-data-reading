"""
Pawel Pietrzak 29.09.2020
Project: Cosmic ray measurements in automation cycle using Python programming
TeFeNica 2020 Summer Student Internship
GUI for CosmicWatch data collection. Uses CosmicWatchControl.py
Contact: pawel.pietrzak7.stud@pw.edu.pl
"""

import os
import sys
import time
import webbrowser

import matplotlib.animation as anim
import matplotlib.figure as mpl_fig
import serial.tools.list_ports
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QPixmap, QFont, QColor, QIntValidator
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                             QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QRadioButton,
                             QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from numpy import polyfit, poly1d
from numpy import array


from CosmicWatchControl import *


class CosmicWatchError(Exception):
    pass

class InvalidInputError(CosmicWatchError):
    pass

class InvalidCOMError(CosmicWatchError):
    pass

class FakeCosmicWatch():
    '''
    Empty class with 2 attributes - amplitudes_list and adc_list that pretends to be CosmicWatch for StaticChart purpose
    '''
    def __init__(self):
        self.amplitudes_list = []  # list of all amplitudes
        self.adc_list = []  # list of all digital amplitudes
        self.angle = 0
        self.distance = 0
        self.rate = 0
        self.amplitudes_list.clear()
        self.adc_list.clear()

class GUIControl(QWidget):
    '''
    Main GUI window
    '''
    detectors = []
    port_list = []
    selected_ports = []

    paused = False
    pause_deadtime_seconds = 0

    charts = [] # List to store Chart_Window objects in, if not referenced they are cleared by garbage collector

    file_path = ''
    directory = os.getcwd()
    print(directory)
    directory = directory +'\\Measurements\\' # directory for file saving
    current_measurement_folder = '' # directory\\current measurement sub-folder
    print(directory)

    # used colors, can be either rgb values, names or # values,
    # colors for data table: odd_rgb and even_rgb must be a QColor object
    warning_text_rgb = 'black'
    info_text_rgb = 'black'
    warning_rgb = "#EB8D96"
    background_rgb = '#f7f9d4'
    info_background_rgb = '#FFFFFF'
    distance_background_rgb ='#FFFFFF'
    odd_rgb = QColor('#31B3E8')
    even_rgb = QColor('#FFE135')
    title_color = '#2D3843'

    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('CosmicWatch')

        #Color
        self.setStyleSheet("background-color: " + self.background_rgb)

        first_row = self.create_first_row()
        first_row.setAlignment(Qt.AlignTop)
        second_row = self.create_second_row()
        self.create_clock()
        # TODO: change names so fourth row is third row
        fourth_row = self.create_fourth_row()
        # Stitch the GUI
        entire_thing = QVBoxLayout()
        entire_thing.addLayout(first_row)
        entire_thing.addLayout(second_row)
        entire_thing.addLayout(fourth_row)

        self.setLayout(entire_thing)
        self.show()

        self.display_ports()

    def create_log_file(self):
        '''
        :return:
        '''
        time_now = self.time_start.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
        #TODO check if it works without astimezone it is probably redundant
        self.current_measurement_folder = self.directory
        self.current_measurement_folder += time_now.strftime('%Y%m%d_%H%M%S')
        timestamp = time.strftime('[%Y-%m-%d_%H:%M:%S]: ')

        try:
            Path(self.current_measurement_folder).mkdir(exist_ok=True, parents=True)  # Create subfolder if doesn't exist
        except FileNotFoundError:
            print('Incorrect path.')
            # what next? *************
        except PermissionError:
            print('This path requires additional permissions.')
            # what next? *************

        with open(self.current_measurement_folder + '\\log.txt', 'w', newline='') as log_file:
            log_file.write('Date [UTC]: Information\r\n')
        message = 'Start button pressed. Log file created.'
        self.update_log(message)
        self.update_log('Angle = ' + self.angle + ' degrees. Distance = ' + self.distance + ' cm.')


    def update_log(self, message):
        time_now = datetime.datetime.now(datetime.timezone.utc)
        timestamp = time_now.strftime('[%Y-%m-%d_%H:%M:%S]: ')
        with open(self.current_measurement_folder + '\\log.txt', "a", newline='') as log:
            log.write(timestamp + message + '\r\n')

    def create_clock(self):

        times_timer = QTimer(self)
        times_timer.start(1000)
        times_timer.timeout.connect(self.refresh_timers)


    def refresh_timers(self):
        '''
        Set which detector controls the timers.
        '''
        #TODO rethink this,it will always set detectors[0] as time controller, its probably not right
        updated = False
        for detector in self.detectors:
            if detector.mode == 'Slave':
                self.update_timers(detector)
                updated = True
        if len(self.detectors) > 0 and updated == False:
            self.update_timers(self.detectors[0])


    def update_timers(self, detector):
        '''
        Updates realtime, deadtime, livetime timers. Ticks every seconds. Updates self.pause_deadtime_seconds on pause.
        :param detector: CosmicWatch detectors
        '''
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.paused == True:
            self.pause_deadtime_seconds = self.pause_deadtime_seconds + 1
        realtime = now - detector.time_start
        deadtime = datetime.timedelta(seconds=detector.deadtime)
        #TODO make sure its not needed
        #deadtime_pause = datetime.timedelta(seconds=self.pause_deadtime_seconds)
        livetime = realtime - deadtime #- deadtime_pause

        deadtime_fraction = (deadtime.total_seconds() + self.pause_deadtime_seconds)/ realtime.total_seconds()
        deadtime_percentage = "{:.3%}".format(deadtime_fraction)

        self.realtime_label.setText('Real Time: ' + str(realtime)[:-7])
        self.livetime_label.setText('Live Time: ' + str(livetime)[:-7])
        self.deadtime_label.setText('Dead Time: ' + str(deadtime_percentage))


    def create_fourth_row(self):
        '''
        Consists of: info_panel
        '''
        fourth_row = QHBoxLayout()

        self.info_panel = QLineEdit()
        fourth_row.addWidget(self.info_panel)
        #info_panel.setAlignment(Qt.AlignRight)
        self.info_panel.setReadOnly(True)
        self.info_panel.setStyleSheet("background-color:" + self.info_background_rgb)

        return fourth_row

    def reset_info_panel(self):
        '''
        Resets look of self.info_panel to empty string with starting colors.
        '''
        self.info_panel.setStyleSheet("background-color:" + self.info_background_rgb +"; color: " + self.info_text_rgb)
        self.info_panel.setText('')

    def update_info_panel(self, message):
        '''
        Resets info_panel and displays given message in default colors.
        :param message: string, message to be displayed
        :return:
        '''
        self.reset_info_panel()
        self.info_panel.setText(message)
        try:
            self.update_log(message)
        except: pass

    def warning_info_panel(self, message):
        '''
        Resets info_panel and displays given message in warning colors.
        :param message: stirng, a warning to be displayed
        :return:
        '''
        self.info_panel.setText(message)
        self.info_panel.setStyleSheet("background-color: " + self.warning_rgb + "; color: " + self.warning_text_rgb + ';')

    def create_control_panel(self):
        '''
        Control panel consists of: start, pause, stop, resume buttons.
        '''
        # Control Panel
        control_panel = QGroupBox('Control Panel')
        control_panel.setStyleSheet('background-color: ' + self.info_background_rgb + ';')
        button_layout = QVBoxLayout()
        control_panel.setLayout(button_layout)
        self.start = QPushButton('Start')
        self.start.clicked.connect(self.start_detectors)
        stop = QPushButton('Stop')
        stop.clicked.connect(self.stop_detectors)

        pause_layout = QHBoxLayout()
        self.pause_button = QPushButton('Pause')
        self.pause_button.paused = True
        self.pause_button.setDown(True)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_reading)
        self.resume_button = QPushButton('Resume')
        self.resume_button.paused = False
        self.resume_button.setDown(True)
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self.resume_reading)
        pause_layout.addWidget(self.pause_button)
        pause_layout.addWidget(self.resume_button)


        button_layout.addWidget(self.start)
        button_layout.addLayout(pause_layout)
        button_layout.addWidget(stop)

        return control_panel

    def pause_reading(self):
        '''
        Set self.paused and detector.paused for each detector to True. Disable pause button. Enable resume button.
        '''
        self.pause_time = datetime.datetime.now()
        self.paused = True
        for detector in self.detectors:
            detector.paused = True
        self.resume_button.setDown(False)
        self.resume_button.setEnabled(True)
        self.pause_button.setDown(True)
        self.pause_button.setEnabled(False)

        self.update_info_panel('Measurements paused.')

    def resume_reading(self):
        '''
        Set self.paused and detector.paused for each detector to False. Disable resume button. Enable pause button.
        '''
        self.paused = False
        for detector in self.detectors:
            detector.paused = False
        self.resume_button.setDown(True)
        self.resume_button.setEnabled(False)
        self.pause_button.setDown(False)
        self.pause_button.setEnabled(True)

        self.update_info_panel('Measurements resumed.')

    def create_additional_settings(self):
        '''
        Additional setting consists of:
        first_column layout = stretch + file_reading_group = [Recreate chart from file, open file in notepad],
        second_column layout = stretch + charts_group = [Open live charts]
        time_group = [Realtime, livetime, deadtime]
        '''
        # Additional settings panel
        ad_settings_group = QGroupBox('Additional functions')
        #ad_settings_group.setMinimumHeight(225)
        ad_settings_group.setStyleSheet('background-color: ' + self.info_background_rgb)

        ad_settings_first_row = QHBoxLayout()
        ad_settings_second_row = QHBoxLayout()
        ad_settings_layout = QVBoxLayout()
        ad_settings_layout.addLayout(ad_settings_first_row)
        ad_settings_layout.addStretch()
        ad_settings_layout.addLayout(ad_settings_second_row)
        ad_settings_group.setLayout(ad_settings_layout)

        # Chart loading group
        file_reading_group = QGroupBox('File reading')
        file_reading_layout = QVBoxLayout()
        file_reading_group.setLayout(file_reading_layout)

        multiple_charts = QPushButton('Chart multiple files')
        multiple_charts.clicked.connect(self.chart_multiple_files)

        file_select = QPushButton('Open file as chart')
        file_select.clicked.connect(self.open_as_chart)

        self.create_chart = QPushButton('Open data file')
        self.create_chart.clicked.connect(self.open_in_notepad)

        file_reading_layout.addWidget(file_select)
        file_reading_layout.addWidget(multiple_charts)
        file_reading_layout.addWidget(self.create_chart)
        file_reading_layout.addStretch()
        ###
        first_column = QVBoxLayout()
        first_column.addWidget(file_reading_group)
        first_column.addStretch()

        # Live charts
        second_column = QVBoxLayout()

        charts_group = QGroupBox('Live charts')
        charts_layout = QVBoxLayout()
        charts_group.setLayout(charts_layout)
        show_charts_button = QPushButton('Show charts')
        show_charts_button.clicked.connect(self.show_live_charts)
        charts_layout.addWidget(show_charts_button)
        charts_layout.addStretch()

        second_column.addStretch()
        second_column.addWidget(charts_group)
        second_column.addStretch()

        # Times
        time_column = QVBoxLayout()
        time_group = QGroupBox('Time')
        time_layout = QVBoxLayout()
        time_group.setLayout(time_layout)

        self.realtime_label = QLabel()
        self.deadtime_label = QLabel()
        self.livetime_label = QLabel()
        self.realtime_label.setText('Real Time: 00:00:00')
        self.livetime_label.setText('Live Time: 00:00:00')
        self.deadtime_label.setText('Dead Time: 00:00:00')

        time_layout.addStretch()
        time_layout.addWidget(self.realtime_label)
        time_layout.addWidget(self.livetime_label)
        time_layout.addWidget(self.deadtime_label)
        time_layout.addStretch()

        time_column.addStretch()
        time_column.addWidget(time_group)
        time_column.addStretch()
        # Log comment
        log_column = QVBoxLayout()
        log_group = QGroupBox('Log file comment (Press start before commenting)')
        log_layout = QHBoxLayout()
        log_group.setLayout(log_layout)
        comment_button = QPushButton('Save to log')
        comment_button.clicked.connect(self.add_comment_log)

        comment_line = QLineEdit()
        comment_line.setStyleSheet("background-color:" + self.distance_background_rgb)
        self.comment = comment_line

        log_layout.addWidget(comment_line)
        log_layout.addWidget(comment_button)

        log_column.addStretch()
        log_column.addWidget(log_group)
        log_column.addStretch()

        # Stiching first row
        ad_settings_first_row.addLayout(first_column)
        ad_settings_first_row.addStretch()
        ad_settings_first_row.addLayout(second_column)
        ad_settings_first_row.addStretch()
        ad_settings_first_row.addLayout(time_column)

        # Second row
        ad_settings_second_row.addLayout(log_column)

        # Finish up
        charts = QHBoxLayout()
        charts.addWidget(ad_settings_group)
        return charts

    def chart_multiple_files(self):
        '''
        Display several files on one chart
        '''
        #self.get_multiple_file_paths()
        try:
            chart = Chart_Window('Multiple files ', FakeCosmicWatch(), False, True, self, len(self.charts))
            self.charts.append(chart)
        except Exception as ChartError:
            self.warning_info_panel('Chart creation failed. Function: chart_multiple_files. Error: ' +repr(ChartError))

    def add_comment_log(self):
        '''
        Add custom comment in log
        '''
        message = str(self.comment.text())
        if message == '':
            self.warning_info_panel('ERROR: Comment box empty.')
            raise InvalidInputError
        else:
            self.update_info_panel('COMMENT: ' + message)

    def open_as_chart(self):
        self.get_file_path()
        self.open_chart_file()

    def open_in_notepad(self):
        '''
        Opens selected .txt or .csv file in default system notepad.
        '''
        self.get_file_path()
        webbrowser.open(self.file_path)

    def get_file_path(self):
        '''
        Opens dialog box for file select of .txt and .csv and saves it full path to self.file_path.
        '''
        open_file = QFileDialog.getOpenFileName(self, 'Open measurements file', '', 'Text files (*.txt *.csv)')
        self.file_path = open_file[0]
        if self.file_path == '':
            self.update_info_panel('No file was selected.')
        else:
            self.update_info_panel('Selected file: ' + self.file_path)

    def open_chart_file(self):
        '''
        Opens selected .txt or .csv file as chart. Requires empty line after header or no header (raw data).
        '''
        file_name = self.file_path.split('/')[-1][:-4]
        try:
            data_pack = self.prepare_data(self.file_path)
        except Exception as DataReadingError:
            self.warning_info_panel('Data reading failed. Error: ' + repr(DataReadingError))
            return
        try:
            chart = Chart_Window(file_name, data_pack, False, False, self, len(self.charts))
            self.charts.append(chart)
        except Exception as ChartReadingError:
            self.warning_info_panel('Chart creation failed. Function: open_chart_file. Error :' + repr(ChartReadingError))

    def prepare_data(self, path):
        '''
        Reads file. If it has no header or header is separated by empty line reads it into list of lists of specific
        columns. Currently only read adc and amplitudes column but can be modified to read others, like temperature.
        :param path: full path of text file with data
        :return data pack = list of two lists: adc_list and amplitudes_list
        '''
        data_pack = FakeCosmicWatch()
        angle = -1 #-1 means failed to read properly
        distance = -1
        rate = -1

        with open(path, 'r') as og_file:
            lines = og_file.readlines()
        # Ignore header
        i = 0
        empty_line_found = False
        for line in lines:
            #TODO distance reading
            try:
                if len(line) > 15:
                    if line[0:13] == '### Distance:':
                        line_list = line.split(' ')
                        distance = line_list[2]
                        angle = line_list[5]
            except:
                pass

            if line.strip() == '':
                empty_line_found = True
                break
            i += 1
        if empty_line_found == True:
            lines = lines[i+1:]
        elif len(lines[0].split()) < 6:
            print(lines[0].split())
            raise

        # Read data to lists
        # TODO maybe read to numpy arrays?
        for line in lines:
            line_list = line.split(' ')
            # other columns can be added in a same way. NOTE: it requires modification of FakeCosmicWatch class
            data_pack.adc_list.append(float(line_list[4]))
            data_pack.amplitudes_list.append(float(line_list[5]))

        # reading rate
        # TODO read rate from time and number
        # reads rate assuming it's 9th element of data line
        try:
            last_line = lines[-1]
            last_line = last_line.split(' ')
            if len(last_line) > 8:
                rate = float(last_line[8])
                if rate > 10:
                    self.warning_info_panel('ERROR: Read rate [9th element] bigger than 10. Suspicious value.')
                    raise InvalidInputError
        except:
            pass

        data_pack.angle = float(angle)
        data_pack.distance = float(distance)
        data_pack.rate = rate

        return data_pack

    def create_second_row(self):
        '''
        Second row consists of: data_table, com_group (control panel)
        '''
        detector_group = self.create_data_table()
        com_group = self.create_settings()

        ad_settings = self.create_additional_settings()
        control_panel = self.create_control_panel()

        # # Stitching row
        # third_row = QHBoxLayout()
        # third_row.addLayout(charts)
        # third_row.addStretch()
        # third_row.addWidget(control_panel)

        first_column = QVBoxLayout()
        second_column = QVBoxLayout()

        first_column.addWidget(self.data_table) #####
        #first_column.addWidget(detector_group) #####
        first_column.addLayout(ad_settings)
        first_column.addStretch()

        second_column.addWidget(com_group)
        second_column.addStretch()
        second_column.addWidget(control_panel)
        second_column.addStretch()

        # Stitching row
        second_row = QHBoxLayout()
        #second_row.addWidget(detector_group)
        second_row.addLayout(first_column)
        second_row.addStretch()
        second_row.addLayout(second_column)
        return second_row

    def create_settings(self):
        '''
        Fills in COM group for control panel.
        '''
        # COM Group
        com_group = QGroupBox('Detector settings')
        com_group.setStyleSheet('background-color: ' + self.info_background_rgb)
        com_layout = QVBoxLayout()
        com_group.setLayout(com_layout)
        input_group = self.create_input_group()
        # Buttons
        button_layout = QVBoxLayout()
        display_ports_b = QPushButton('Scan ports')
        display_ports_b.clicked.connect(self.display_ports)
        button_layout.addStretch()
        button_layout.addWidget(input_group)  # TEMP
        button_layout.addWidget(display_ports_b)
        button_layout.addStretch()
        # input + button
        input_button_layout = QHBoxLayout()
        # input_button_layout.addWidget(input_group)  #TEMP
        input_button_layout.addLayout(button_layout)
        input_button_layout.setAlignment(Qt.AlignTop)
        # COM detectors
        com_legend = QGridLayout()
        no = QLabel()
        no1 = QLabel()
        no2 = QLabel()
        no.setText('No.')
        no1.setText('1.')
        no2.setText('2.')
        com = QLabel()
        com.setText('COM')
        self.COM1 = QComboBox()
        self.COM2 = QComboBox()
        self.fill_com_combobox(self.COM1)
        self.fill_com_combobox(self.COM2)
        self.COM1.setMinimumWidth(70)
        com_legend.addWidget(no, 0, 0)
        com_legend.addWidget(no1, 1, 0)
        com_legend.addWidget(no2, 2, 0)
        com_legend.addWidget(com, 0, 1)
        com_legend.addWidget(self.COM1, 1, 1)
        com_legend.addWidget(self.COM2, 2, 1)
        com.setAlignment(Qt.AlignCenter)
        com_legend.setColumnStretch(0, 0)
        com_legend.setColumnStretch(1, 1)
        # #experimental
        # horizontal = QHBoxLayout()
        # horizontal.addLayout(input_button_layout)
        # horizontal.addLayout(com_legend)
        # com_layout.addLayout(horizontal)
        # Stitch com group
        com_layout.addLayout(input_button_layout)
        com_layout.addLayout(com_legend)
        com_layout.addStretch()
        return com_group

    def fill_com_combobox(self, combobox):
        combobox.clear()
        combobox.addItem('')
        for port in self.port_list:
            combobox.addItem(port)

    def create_data_table(self):
        '''
        Creates data table with det name, status, amplitude, time, rate, error, number of detections
        '''
        # Detector group
        detector_group = QGroupBox('Detectors - Measurements')
        detector_layout = QVBoxLayout()
        detector_group.setLayout(detector_layout)
        self.data_table = QTableWidget()
        #detector_layout.addWidget(self.data_table) ###########
        self.data_table.setColumnCount(7)
        self.data_table.setHorizontalHeaderLabels(['Det. Name', '\nStatus\n',
                                                   'Amplitude\n[mV]', 'Time\n[hh:mm:ss.sss]',
                                                   'Rate\n[N/s]', 'Error\n[+/-]', 'Number'])
        #self.data_table.horizontalHeader().setFont(QFont('Helvetica', 9, ))
        # Adjust column size
        self.data_table.setColumnWidth(0, 100)
        self.data_table.setColumnWidth(1, 80)
        self.data_table.setColumnWidth(2, 80)
        self.data_table.setColumnWidth(3, 100)
        self.data_table.setColumnWidth(4, 60)
        self.data_table.setColumnWidth(5, 70)
        self.data_table.setColumnWidth(6, 80)
        # Adjust table size
        self.data_table.setMinimumWidth(585)
        self.data_table.setFixedHeight(140)
        self.data_table.setStyleSheet("background-color:" + self.info_background_rgb)

        detector_group.setObjectName('DetectorGroup')
        detector_group.setStyleSheet('QGroupBox#DetectorGroup {border: 1px solid gray; border-radius: 3px;}')

        return detector_group

    def create_input_group(self):
        '''
        Create input group(angle, distance) for control panel
        '''
        # Input group = Angle + Distance
        input_group = QGroupBox()
        input_layout = QHBoxLayout()
        # Angle box
        angle_layout = QVBoxLayout()
        angle_label = QLabel()
        angle_label.setText('Angle [deg]')
        angle_box = QComboBox()
        angle_box.addItem('')
        for i in range(13):
            degree = str(7.5 * i)
            angle_box.addItem(degree)
        angle_box.setFixedWidth(70)
        angle_layout.addWidget(angle_label)
        angle_layout.addWidget(angle_box)
        angle_layout.addStretch()
        # Distance box
        distance_layout = QVBoxLayout()
        distance_label = QLabel()
        distance_label.setText('Distance [cm]')
        distance_line = QLineEdit()
        distance_line.setValidator(QIntValidator())
        distance_line.setFixedWidth(80)
        distance_line.setStyleSheet("background-color:" + self.distance_background_rgb)
        distance_layout.addWidget(distance_label)
        distance_layout.addWidget(distance_line)
        distance_layout.addStretch()
        # Stitch input group
        input_layout.addLayout(angle_layout)
        input_layout.addLayout(distance_layout)
        input_group.setLayout(input_layout)

        self.angle_input = angle_box
        self.distance_input = distance_line
        return input_group

    def create_first_row(self):
        '''
        Name, date, logos.
        '''
        logo_height = 75 #85
        NCBJ_logo = QLabel()
        NCBJ_logo_pixmap = QPixmap('ncbj_logo.png').scaledToHeight(logo_height)
        NCBJ_logo.setPixmap(NCBJ_logo_pixmap)
        # NCBJ_logo.setAlignment(Qt.AlignLeft)

        WUT_logo = QLabel()
        WUT_logo_pixmap = QPixmap('pw_logo.png').scaledToHeight(logo_height)
        WUT_logo.setPixmap(WUT_logo_pixmap)

        NICA_logo = QLabel()
        NICA_logo_pixmap = QPixmap('nica_logo.png').scaledToHeight(logo_height-15)
        NICA_logo.setPixmap(NICA_logo_pixmap)

        title = QLabel()
        title.setAlignment(Qt.AlignCenter)
        title.setText('CosmicWatch')
        title.setFont(QFont('Helvetica', 30, QFont.Bold ))  # QFont.Bold
        title.setStyleSheet("color: " + self.title_color)

        # title.setStyleSheet('border: 1px solid black')

        date = QLabel()
        date.setAlignment(Qt.AlignRight)
        date.setAlignment(Qt.AlignTop)
        date.setText(QDate.currentDate().toString(Qt.DefaultLocaleShortDate))
        date.setFont(QFont('Helvetica', 15))
        #date.setStyleSheet("border: 1px solid gray; border-radius: 3px;")

        #testing
        time_layout = QVBoxLayout()
        time_layout.addWidget(date)
        time_layout.addWidget(NICA_logo)

        first_row = QHBoxLayout()

        first_row.addWidget(NCBJ_logo)
        first_row.addWidget(WUT_logo)
        #first_row.addWidget(NICA_logo)
        first_row.addStretch()
        first_row.addWidget(title)
        first_row.addStretch()
        #first_row.addWidget(date)
        first_row.addLayout(time_layout)

        title.setAlignment(Qt.AlignCenter)

        return first_row

    def set_up_detectors(self):
        '''
        Fills "detectors" list with CosmicWatch class objects. Only supports 2 detector.
        '''
        distance, angle, com1, com2 = self.read_inputs()
        self.angle = angle
        self.distance = distance

        # temporary; TODO adjust to make using more detectors possible
        # TODO: connecting all detectors as master, without audio cable and then doing the coincidence mode in the program
        # TODO: would allow for more detectors working in the cooincidence mode at the same time, also doesnt require audio jack

        if com1 != '':
            Albert = CosmicWatch()
            Albert.port_name = com1
            Albert.row = 0
            self.detectors.append(Albert)
            Albert.table_updater.connect(lambda: self.modify_table(Albert))
            Albert.chart_initializer.connect(lambda: self.add_live_chart(Albert))

        if com2 != '':
            Bernard = CosmicWatch()
            Bernard.port_name = com2
            Bernard.row = 1
            self.detectors.append(Bernard)
            Bernard.table_updater.connect(lambda: self.modify_table(Bernard))
            Bernard.chart_initializer.connect(lambda: self.add_live_chart(Bernard))

        for detector in self.detectors:
            detector.masterGUI = self
            detector.directory = self.directory
            detector.angle = angle
            detector.distance = distance

    def start_detectors(self):
        '''
        Starts detectors (CosmicWatch class). Enables pause button.
        '''
        self.reset_info_panel()
        try:
            self.validate_input()
        except:
            return
        try:
            self.set_up_detectors()
        except:
            self.warning_info_panel('ERROR: Detector initialization failed.')
        self.info_panel.setText('Start successful.')

        self.data_table.setRowCount(len(self.detectors))
        # disable start
        self.start.setDown(True)
        self.start.setEnabled(False)
        self.pause_button.setDown(False)
        self.pause_button.setEnabled(True)
        self.pause_deadtime_seconds = 0
        self.paused = False

        self.time_start = datetime.datetime.now(datetime.timezone.utc)

        try: self.create_log_file()  #TUTEJ
        except: pass

        for detector in self.detectors:
            time.sleep(0.2) # To force detector2 into slave mode by initializing master earlier
            # Thread(target=detector.start_program()).start()
            detector.time_start = self.time_start
            detector.start_program()

    def add_live_chart(self, detector):
        '''
        Opens live chart showing detector data
        :param detector: detector of wchich data will be displayed
        '''
        chart = Chart_Window(detector.mode, detector, True, False, self, len(self.charts))
        self.charts.append(chart) # it has to be referenced not to be deleted by garbage collector

    def show_live_charts(self):
        '''
        Opens live charts of all detectors by calling self.add_live_chart()
        '''
        self.update_info_panel('"Show live charts" button pressed.')
        for detector in self.detectors:
            self.add_live_chart(detector)

    def validate_input(self):
        '''
        User input validation. Raises predicted errors and displays them on info panel.
        '''
        if str(self.distance_input.text()) == '' or str(self.angle_input.currentText()) == '':
            self.warning_info_panel('ERROR: Please fill distance and angle boxes.')
            raise InvalidInputError

        if str(self.distance_input.text())[0] == '-':
            self.warning_info_panel('ERROR: Distance negative.')
            raise InvalidInputError

        if str(self.COM1.currentText()) == '' and str(self.COM2.currentText()) == '':
            self.warning_info_panel('ERROR: No serial [COM] ports were selected.')
            raise InvalidCOMError

        if str(self.COM1.currentText()) == str(self.COM2.currentText()):
            self.warning_info_panel('ERROR: One port cannot be selected twice.')
            raise InvalidCOMError

        if str(self.distance_input.text())[0] == '0' and len(str(self.distance_input.text())) > 1:
            self.warning_info_panel('ERROR: First digit of the distance is 0.')
            raise InvalidInputError

    def read_inputs(self):
        '''
        Reads data given by user.
        :return: distance, angle, com1, com2 <- strings
        '''
        distance = str(self.distance_input.text())
        angle = str(self.angle_input.currentText())
        com1 = str(self.COM1.currentText())
        com2 = str(self.COM2.currentText())
        return distance, angle, com1, com2

    def stop_detectors(self):
        '''
        Stops detectors (CosmicWatch class). Disables pause and resume buttons. Sets self.paused to False.
        '''
        self.update_log('"Stop" button pressed')
        for detector in self.detectors:
            detector.stop_program()
        self.detectors.clear()
        self.start.setDown(False)
        self.start.setEnabled(True)

        self.resume_button.setDown(True)
        self.resume_button.setEnabled(False)
        self.pause_button.setDown(True)
        self.pause_button.setEnabled(False)
        self.paused = False

    def init_table(self, detector):
        '''
        Initializes table row for given detector
        :param detector: CosmicWatch() class
        :return:
        '''
        row = detector.row
        self.data_table.setItem(row, 0, QTableWidgetItem(detector.device_id))
        self.data_table.setItem(row, 1, QTableWidgetItem(detector.mode))
        self.data_table.setItem(row, 2, QTableWidgetItem(detector.amplitude))
        self.data_table.setItem(row, 3, QTableWidgetItem(detector.time))
        self.data_table.setItem(row, 4, QTableWidgetItem(detector.rate))
        self.data_table.setItem(row, 5, QTableWidgetItem(detector.rate_error))
        self.data_table.setItem(row, 6, QTableWidgetItem(detector.number))

        self.format_table(row)

    def modify_table(self, detector):
        '''
        Updates table row of given detector.
        :param detector:
        :return: CosmicWatch() class
        '''
        row = detector.row

        self.data_table.setItem(row, 0, QTableWidgetItem(detector.device_id))
        self.data_table.setItem(row, 1, QTableWidgetItem(detector.mode))
        self.data_table.setItem(row, 2, QTableWidgetItem(detector.amplitude))
        self.data_table.setItem(row, 3, QTableWidgetItem(detector.time))
        self.data_table.setItem(row, 4, QTableWidgetItem(detector.rate))
        self.data_table.setItem(row, 5, QTableWidgetItem(detector.rate_error))
        self.data_table.setItem(row, 6, QTableWidgetItem(detector.number))
        # self.data_table.item(row, 0).setText(str(detector.device_id))
        # self.data_table.item(row, 1).setText(str(detector.mode))
        # self.data_table.item(row, 2).setText(str(detector.amplitude))
        # self.data_table.item(row, 3).setText(str(detector.time))
        # self.data_table.item(row, 4).setText(str(detector.rate))
        # self.data_table.item(row, 5).setText(str(detector.rate_error))
        # self.data_table.item(row, 6).setText(str(detector.number))

        try:
            self.format_table(row)
        except:
            pass

    def format_table(self, row):
        '''
        Format table row.
        :param row: int
        :return:
        '''

        # Center Text
        for column in range(1, self.data_table.columnCount(), 1):
            item = self.data_table.item(row, column)
            item.setTextAlignment(Qt.AlignCenter)
        # Color background
        for column in range(self.data_table.columnCount()):
            item = self.data_table.item(row, column)
            if row% 2 == 1:
                item.setBackground(self.odd_rgb)
            else:
                item.setBackground(self.even_rgb)
                pass

    def display_ports(self):
        '''
        Resets self.port_list and refills it with detected ports.
        '''
        self.reset_info_panel()
        self.port_list = []

        ports = serial.tools.list_ports.comports()
        port_names = ''
        for port in ports:
            port_names += ' ' + port.device + ','
            self.port_list.append(port.device)
        if port_names == '':
            message = 'No COM ports detected.'
        else:
            message = 'Detected ports:' + port_names
            message = message [:-1]
            message += '.'
        self.fill_com_combobox(self.COM1)
        self.fill_com_combobox(self.COM2)
        self.update_info_panel(message)


class Chart_Window(QWidget):
    '''
    Secondary window displaying chart. Can run StaticChart or AnimatedChart.
    :param mode = Title of window or chart.
    :param detector = CosmicWatch() class or FakeCosmicWatch() class. It must have attributes used by charts.
    :param animated = bool
    :param multiple = bool
    :param masterGUI = GUIControl() class, the master GUI
    :param chart_list_index = int, index of this window on chart_list of GUI. Used for memory clearing.
    '''

    chart_updater = pyqtSignal() # signal used to update chart on button change

    color_dict = {
        'Blue': '#31B3E8',
        'Red': '#ff0000',
        'Black': '#000000',
        'Violet': '#ee82ee',
        'Green': '#228b22',
        'Brown': '#a52a3a',
        'Chocolate': '#d2691e',
        'Orange': '#ffa500'
    }

    def __init__(self, mode, detector, animated, multiple, masterGUI, chart_list_index):
        super().__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.data_pack_list = []
        self.masterGUI = masterGUI
        self.multiple = multiple
        self.chart_list_index = chart_list_index
        layout = QVBoxLayout()
        self.setLayout(layout)


        if multiple == True:
            self.setWindowTitle(mode)
            #self.myFig = MultipleChart(mode, self, self.chart_updater)
            self.myFig = RatesChart(mode, self, self.chart_updater)
        elif animated == False:
            self.setWindowTitle(mode)
            self.myFig = StaticChart(mode, detector, self.chart_updater)
        else:
            self.setWindowTitle(mode + ' [Online]')
            self.myFig = AnimatedChart(mode, detector)

        toolbar = NavigationToolbar(self.myFig, self)
        layout.addWidget(toolbar)
        layout.addWidget(self.myFig)

        if multiple == True:
            buttons = self.create_buttons_rates()
        else:
            buttons = self.create_buttons()

        layout.addLayout(buttons)

        self.setStyleSheet('background-color: #f7f9d4')
        self.show()

    def create_buttons_rates(self):
        '''
         Creates radio buttons
         Scales: linear vs log
         Xscale: distance vs angle
         Bars: empty vs filled
          '''
        #.adc = x scale unit

        # button settings
        buttons = QGridLayout()
        scales = QButtonGroup(self)
        values = QButtonGroup(self)
        buttons.setAlignment(Qt.AlignHCenter)

        linear_scale = QRadioButton('Linear scale')
        linear_scale.log = False
        linear_scale.setChecked(True)
        linear_scale.toggled.connect(self.change_scale)
        scales.addButton(linear_scale)
        buttons.addWidget(linear_scale, 1, 0)

        log_scale = QRadioButton('Log scale')
        log_scale.log = True
        log_scale.toggled.connect(self.change_scale)
        scales.addButton(log_scale)
        buttons.addWidget(log_scale, 0, 0)

        distance_values = QRadioButton('Compare distances')
        distance_values.adc = True  # x axis distance
        distance_values.xlabel = 'Distance [cm]'
        distance_values.toggled.connect(self.change_values)
        values.addButton(distance_values)
        buttons.addWidget(distance_values, 0, 1)

        angle_values = QRadioButton('Compare angles')
        angle_values.adc = False  # x axis = angle
        angle_values.xlabel = 'Angle [deg]'
        angle_values.toggled.connect(self.change_values)
        angle_values.setChecked(True)
        values.addButton(angle_values)
        buttons.addWidget(angle_values, 1, 1)

        add_chart_button = QPushButton('Add graph')
        add_chart_button.clicked.connect(self.add_chart)

        edit_chart_button = QPushButton('Edit graph')
        edit_chart_button.clicked.connect(self.edit_chart)

        buttons.addWidget(add_chart_button, 1, 3)
        buttons.addWidget(edit_chart_button, 0, 3)

        return buttons

    def create_buttons(self):
        '''
        Creates radio buttons
        Scales: linear vs log
        Xscale: amplitudes vs adc
        Bars: empty vs filled
        '''
        # button settings
        buttons = QGridLayout()
        scales = QButtonGroup(self)
        values = QButtonGroup(self)
        buttons.setAlignment(Qt.AlignHCenter)

        linear_scale = QRadioButton('Linear scale')
        linear_scale.log = False
        linear_scale.setChecked(True)
        linear_scale.toggled.connect(self.change_scale)
        scales.addButton(linear_scale)
        buttons.addWidget(linear_scale, 1, 0)

        log_scale = QRadioButton('Log scale')
        log_scale.log = True
        log_scale.toggled.connect(self.change_scale)
        scales.addButton(log_scale)
        buttons.addWidget(log_scale, 0, 0)

        digital_values = QRadioButton('Digital values')
        digital_values.adc = True
        digital_values.xlabel = 'ADC [0-1023]'
        digital_values.toggled.connect(self.change_values)
        values.addButton(digital_values)
        buttons.addWidget(digital_values, 0, 1)

        analog_values = QRadioButton('Analog amplitudes')
        analog_values.adc = False
        analog_values.xlabel = 'Amplitude [mV]'
        analog_values.toggled.connect(self.change_values)
        analog_values.setChecked(True)
        values.addButton(analog_values)
        buttons.addWidget(analog_values, 1, 1)

        filling = QButtonGroup()

        filled = QRadioButton('Bars filled')
        filled.fill = 'stepfilled'
        filled.toggled.connect(self.change_fill)
        filling.addButton(filled)
        buttons.addWidget(filled, 0, 2)

        empty = QRadioButton('Bars empty')
        empty.fill = 'step'
        empty.setChecked(True)
        empty.toggled.connect(self.change_fill)
        filling.addButton(empty)
        buttons.addWidget(empty, 1, 2)

        if self.multiple == False:
            color_box = QComboBox()
            color_list = sorted(self.color_dict.keys())
            for color in color_list:
                color_box.addItem(color)
            color_box.setCurrentIndex(1)
            color_box.currentIndexChanged.connect(self.change_color)
            buttons.addWidget(color_box, 1, 3)

            color_label = QLabel()
            color_label.setText('Color selection:')
            buttons.addWidget(color_label, 0, 3)
        else:
            add_chart_button = QPushButton('Add graph')
            add_chart_button.clicked.connect(self.add_chart)

            edit_chart_button = QPushButton('Edit graph')
            edit_chart_button.clicked.connect(self.edit_chart)

            buttons.addWidget(add_chart_button, 1, 3)
            buttons.addWidget(edit_chart_button, 0, 3)

        return buttons

    def add_chart(self):
        '''
        Opens dialog box for file select of .txt and .csv and saves it full path to self.file_path.
        Opens selected .txt or .csv file as chart. Requires empty line after header or no header (raw data).
        '''
        open_file = QFileDialog.getOpenFileName(self, 'Open measurements file', '', 'Text files (*.txt *.csv)')
        file_path = open_file[0]
        if file_path == '':
            self.masterGUI.update_info_panel('No file was selected.')
        else:
            self.masterGUI.update_info_panel('Selected file: ' + file_path)
            #Opens selected .txt or .csv file as chart. Requires empty line after header or no header (raw data).
            try:
                data_pack = self.masterGUI.prepare_data(file_path)
                self.data_pack_list.append(data_pack)
            except Exception as DataReadingError:
                self.masterGUI.warning_info_panel('Data reading failed. Error: ' + repr(DataReadingError))
        self.chart_updater.emit()

    def edit_chart(self):
        pass

    def change_scale(self):
        button = self.sender()
        if button.isChecked():
            self.myFig.log = button.log
            self.chart_updater.emit()

    def change_values(self):
        button = self.sender()
        if button.isChecked():
            self.myFig.adc_mode = button.adc
            self.myFig.xlabel = button.xlabel
            self.chart_updater.emit()

    def change_fill(self):
        button = self.sender()
        if button.isChecked():
            self.myFig.fill = button.fill
            self.chart_updater.emit()

    def change_color(self):
        box = self.sender()
        color = box.currentText()
        self.myFig.color = self.color_dict[color]
        self.chart_updater.emit()

    def closeEvent(self, event):
        '''
        On window closing delete references to this window from masterGUI.charts to let it be handled by garbage collector
        :return:
        '''
        # Chart closed
        self.masterGUI.charts.remove(self)

class AnimatedChart(FigureCanvas, anim.FuncAnimation):
    '''
    Animated Chart
    :param mode -> see class ChartWindow
    :param detector -> see class ChartWindow
    '''
    #stopped = False
    log = False

    def __init__(self, mode, detector) -> None:
        FigureCanvas.__init__(self, mpl_fig.Figure())
        self.mode = mode
        self.detector = detector

        self.log = False
        self.fill = 'step'
        self.xlabel = 'Amplitude [mV]'
        self.adc_mode = False
        self.color = '#31B3E8'
        self.adc_bin = 128
        self.amplitude_bin = 60

        self.axes = self.figure.subplots()
        self.figure.set_facecolor('#f7f9d4')
        self.axes.set_facecolor('#f7f9d4')

        self.axes.set_ylabel('Number of detections')
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_title(self.mode + ' histogram')

        if self.adc_mode == False:
            self.chart = self.axes.hist(self.detector.amplitudes_list, bins=self.amplitude_bin, color = self.color, histtype = self.fill, log = True)
        else:
            self.chart = self.axes.hist(self.detector.adc_list, bins=self.adc_bin, color= self.color, histtype=self.fill, log= True)

        self.draw()
        self.animation = anim.FuncAnimation.__init__(self, self.figure, self.update_chart, interval=1000)

    def update_chart(self, i):
        self.axes.clear()

        if self.log == True:
            self.adc_binb = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("log")
        else:
            self.adc_bin = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("linear")

        if self.adc_mode == False:
            self.chart = self.axes.hist(self.detector.amplitudes_list, bins=self.amplitude_bin, color = self.color, histtype = self.fill, log = True)
        else:
            self.chart = self.axes.hist(self.detector.adc_list, bins=self.adc_bin, color= self.color, histtype=self.fill, log= True)

        self.axes.set_ylabel('Number of detections')
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_title(self.mode + ' histogram')

        return self.chart

class StaticChart(FigureCanvas):
    '''
    Static chart
    :param mode -> see class ChartWindow
    :param CosmicWatch -> see class ChartWindow
    :param chart_updater -> see class ChartWindow
    '''

    # lists used as data references for chart
    adc_list = []
    amplitudes_list = []

    def __init__(self, mode, CosmicWatch, chart_updater) -> None:
        FigureCanvas.__init__(self, mpl_fig.Figure())
        self.mode = mode
        chart_updater.connect(self.update_chart)

        self.log = False
        self.fill = 'step'
        self.xlabel = 'Amplitude [mV]'
        self.adc_mode = False
        self.color = '#31B3E8'

        self.adc_bin = 128
        self.amplitude_bin = 60

        self.amplitudes_list.clear()
        self.adc_list.clear()
        self.amplitudes = CosmicWatch.amplitudes_list
        self.adc_list = CosmicWatch.adc_list

        self.axes = self.figure.subplots()
        self.figure.set_facecolor('#f7f9d4')
        self.axes.set_facecolor('#f7f9d4')

        if self.adc_mode == False:
            self.chart = self.axes.hist(self.amplitudes, bins=128, color = self.color, histtype = self.fill, log = True)

        else:
            self.chart = self.axes.hist(self.adc_list, bins=128, color= self.color, histtype=self.fill, log= True)

        self.draw()

    def update_chart(self):

        self.axes.clear()

        if self.log == True:
            self.adc_bin = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("log")
        else:
            self.adc_bin = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("linear")

        if self.adc_mode == False:
            self.chart = self.axes.hist(self.amplitudes, bins=self.amplitude_bin, color = self.color, histtype = self.fill, log = True)
        else:
            self.chart = self.axes.hist(self.adc_list, bins=self.adc_bin, color= self.color, histtype=self.fill, log= True)

        self.axes.set_ylabel('Number of detections')
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_title(self.mode + ' histogram')

        self.draw()

class MultipleChart(FigureCanvas):
    '''
    Static chart
    :param mode -> see class ChartWindow
    :param CosmicWatch -> see class ChartWindow
    :param chart_updater -> see class ChartWindow
    '''

    # lists used as data references for chart
    adc_list = []
    amplitudes_list = []

    def __init__(self, mode, chart_window, chart_updater) -> None:
        FigureCanvas.__init__(self, mpl_fig.Figure())
        self.mode = mode
        chart_updater.connect(self.update_chart)
        self.chart_window = chart_window
        self.color_list = ['Blue', 'Red', 'Black', 'Violet', 'Green', 'Brown', 'Chocolate', 'Orange']

        self.log = False
        self.fill = 'step'
        self.xlabel = 'Amplitude [mV]'
        self.adc_mode = False
        self.color = '#31B3E8'

        self.adc_bin = 128
        self.amplitude_bin = 60

        # self.amplitudes_list.clear()
        # self.adc_list.clear()
        # self.amplitudes = CosmicWatch.amplitudes_list
        # self.adc_list = CosmicWatch.adc_list

        self.axes = self.figure.subplots()
        self.figure.set_facecolor('#f7f9d4')
        self.axes.set_facecolor('#f7f9d4')
        #
        # if self.adc_mode == False:
        #     self.chart = self.axes.hist(self.amplitudes, bins=128, color = self.color, histtype = self.fill, log = True)
        # else:
        #     self.chart = self.axes.hist(self.adc_list, bins=128, color= self.color, histtype=self.fill, log= True)

        self.draw()

    def update_chart(self):

        self.axes.clear()

        if self.log:
            self.adc_bin = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("log")
        else:
            self.adc_bin = 128
            self.amplitude_bin = 60
            self.axes.set_xscale("linear")

        color_index = 0
        charts = []
        data_pack_list = self.chart_window.data_pack_list
        for pack in data_pack_list:
            print('Graphing number: ' + repr(color_index))
            print(repr(pack))
            if self.adc_mode == False:
                chart = self.axes.hist(pack.amplitudes_list, bins=self.amplitude_bin,
                               color = self.chart_window.color_dict[self.color_list[color_index]],
                               histtype = self.fill, log = True)
            else:
                chart = self.axes.hist(pack.adc_list, bins=self.adc_bin,
                               color= self.chart_window.color_dict[self.color_list[color_index]],
                               histtype=self.fill, log= True)
            color_index += 1
            charts.append(chart)

        self.axes.set_ylabel('Number of detections')
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_title(self.mode + ' histogram')

        self.draw()

class RatesChart(FigureCanvas):
    '''
    Static chart
    :param mode -> see class ChartWindow
    :param CosmicWatch -> see class ChartWindow
    :param chart_updater -> see class ChartWindow
    '''

    # lists used as data references for chart
    distance_list = []
    angle_list = []
    rate_list = []

    def __init__(self, mode, chart_window, chart_updater) -> None:
        FigureCanvas.__init__(self, mpl_fig.Figure())
        self.mode = mode
        chart_updater.connect(self.update_chart)
        self.chart_window = chart_window

        self.log = False
        self.fill = 'step'
        self.xlabel = 'Distance [cm]'
        self.adc_mode = False
        self.color = '#31B3E8'

        self.axes = self.figure.subplots()
        self.figure.set_facecolor('#f7f9d4')
        self.axes.set_facecolor('#f7f9d4')

        self.draw()

    def update_chart(self):

        self.axes.clear()

        if self.log == True:
            self.axes.set_xscale("log")
        else:
            self.axes.set_xscale("linear")

        color_index = 0
        charts = []
        data_pack_list = self.chart_window.data_pack_list
        self.distance_list = [-1]*len(data_pack_list)
        self.rate_list = [-1]*len(data_pack_list)
        self.angle_list = [-1]*len(data_pack_list)

        i = -1

        for pack in data_pack_list:
            i+=1
            print('Graphing number: ' + repr(color_index))
            print(repr(pack))
            print(len(data_pack_list))

            #self.distance_list[i] = pack.distance
            #self.angle_list[i] = pack.angle
            #
            try:
                self.rate_list[i] = pack.rate
                self.distance_list[i] = pack.distance
                self.angle_list[i] = pack.angle

                print(self.distance_list)
                print(self.rate_list)

            except Exception as PackError:
                print(repr(PackError))
                #TODO log the error

        try:
            distance_list, rate_dist = zip(*sorted(zip(self.distance_list, self.rate_list)))
            angle_list, rate_angle = zip(*sorted(zip(self.angle_list, self.rate_list)))

            z_dist = polyfit(self.distance_list, self.rate_list, 1)
            trendline_dist = poly1d(z_dist)
            z_angle = polyfit(self.angle_list, self.rate_list, 1)
            trendline_angle = poly1d(z_angle)

            # plot rates
            if self.adc_mode == True:  # True -> distance; False -> Angle
                #chart = self.axes.scatter(self.distance_list, self.rate_list)
                chart = self.axes.plot(distance_list, rate_dist, 'bo', linewidth = 1, linestyle = '--')
                print(distance_list)
                self.axes.plot(self.distance_list, trendline_dist, 'r--')
            else:
                chart = self.axes.plot(angle_list, rate_angle, 'bo', linewidth = 1, linestyle = '--')
                self.axes.plot(self.angle_list, trendline_angle, 'r--')
            #TODO hideable trendline and lines [linewidth 0?]
            #TODO fix trendline on >2 points not apperaing and on =2 points mirrored
            charts.append(chart)

        except Exception as DrawError:
            print(repr(DrawError))
            #TODO log the error

        self.axes.set_ylabel('Rate [N/s]')
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_title(self.mode + ' comparison')

        self.draw()



app = QApplication(sys.argv)
app.setStyle('Fusion')
a_window = GUIControl()

app.aboutToQuit.connect(a_window.stop_detectors) # on program exit stop detectors
sys.exit(app.exec_())
