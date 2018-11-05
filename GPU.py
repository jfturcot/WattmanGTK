# This file is part of WattmanGTK.
#
# Copyright (c) 2018 Bouke Haarsma
#
# WattmanGTK is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
# 
#
# WattmanGTK is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WattmanGTK.  If not, see <http://www.gnu.org/licenses/>.

import re # for searching in strings used to determine states
import glob                 # to get directories of cards
import os

class sensor:
    def __init__(self,sensorpath):
        self.path = sensorpath

    def read(self,path=None):
        # Set optional path parameter, so it can be used as parser
        return int(open(self.path).readline().rstrip())

    def read_attribute(self,attribute,replace=False):
        if replace:
            return int(open(str.split(self.path,"_")[0] + attribute).readline().rstrip())
        return int(open(self.path + attribute).readline().rstrip())

class GPU:
    # Object which stores GPU information
    def __init__(self, cardpath, linux_kernelmain, linux_kernelsub):
        # Can used for kernel specific workarounds
        self.linux_kernelmain = linux_kernelmain
        self.linux_kernelsub = linux_kernelsub

        self.pstate_clock = []      # P state clocks (GPU) [MHz]
        self.pstate_voltage = []    # P state voltages (GPU) [mV]
        self.pmem_clock = []        # Memory state clocks [Mhz]
        self.pmem_voltage = []      # Memory state voltages [mV]
        self.pstate_clockrange = [] # Minimum and Maximum P state clocks (GPU) [Mhz]
        self.pmem_clockrange = []   # Minimum and Maximum Memory state clocks [Mhz]
        self.volt_range = []        # Mimimum and Maximum voltage for both GPU and memory [mV]
        self.cardpath = cardpath    # starting path for card eg. /sys/class/drm/card0/device
        self.fansensors, self.fanpwmsensors, self.tempsensors, self.powersensors = self.get_sensors()
        self.get_states()
        self.get_currents()

    def get_states(self):
        # Gets the ranges for GPU and Memory (clocks states and voltages)
        # TODO add VEGA20 support
        # Source https://cgit.freedesktop.org/~agd5f/linux/tree/drivers/gpu/drm/amd/amdgpu/amdgpu_pm.c?h=amd-staging-drm-next
        # TODO make more robust for future updates
        filename = self.cardpath + "/pp_od_clk_voltage"
        with open(filename) as origin_file:
            if "OD_SCLK:" in origin_file.readline():
                # This will not work with VEGA 20 but will work up to Vega10
                # Read GPU clocks
                match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)", origin_file.readline())
                while match is not None:
                    self.pstate_clock.append(int(match.group(2)))
                    self.pstate_voltage.append(int(match.group(4)))
                    match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)",
                                     origin_file.readline())
                # Read Memory clocks
                match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)", origin_file.readline())
                while match is not None:
                    self.pmem_clock.append(int(match.group(2)))
                    self.pmem_voltage.append(int(match.group(4)))
                    match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)",
                                     origin_file.readline())
                # Read limits for GPU, Memory and voltages
                match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)", origin_file.readline())
                self.pstate_clockrange.append(int(match.group(2)))
                self.pstate_clockrange.append(int(match.group(4)))

                match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)", origin_file.readline())
                self.pmem_clockrange.append(int(match.group(2)))
                self.pmem_clockrange.append(int(match.group(4)))

                match = re.match(r"^(\d|\S{1,}):\s{1,}(\d{1,})(MHz|Mhz|mV)\s{1,}(\d{1,})(MHz|Mhz|mV)", origin_file.readline())
                self.volt_range.append(int(match.group(2)))
                self.volt_range.append(int(match.group(4)))
            else:
                print("Error during reading current states, WattmanGTK will not be able to continue :(")
                print("Please check if \"cat " +filename+ "\" returns something useful")
                exit()
        self.power_cap_max = self.powersensors.read_attribute('_max') / 1000000 
        self.power_cap_min = self.powersensors.read_attribute('_min') / 1000000
        self.power_cap = self.powersensors.read() / 1000000
        return self.pstate_clock, self.pstate_voltage, self.pstate_clockrange, self.pmem_clock, self.pmem_voltage, self.pmem_clockrange, self.volt_range

    def get_sensors(self):
        hwmondir = '/sys/class/hwmon/'
        amdhwmonfolder = ''
        for i,folder in enumerate(os.listdir(hwmondir)):
            if open(hwmondir + folder + '/name').readline().rstrip() == 'amdgpu':
                amdhwmonfolder = hwmondir + folder
                print('amdgpu card found in ' + amdhwmonfolder + ' hwmon folder')
                break
        sensors = []
        if amdhwmonfolder == '':
            print('WattmanGTK could not find any sensors')
            exit()
        names = ['/fan?_input','/pwm?','/temp?_input','/power?_cap']
        for i, name in enumerate(names):
            paths = glob.glob(amdhwmonfolder + name)
            if paths == []:
                sensors.append(None)
                continue
            for path in paths:
                sensors.append(sensor(path))
        return tuple(sensors)

    def read_sensor(self,filename):
        # reads sensors which only output number
        with open(self.cardpath+filename) as origin_file:
            return int(origin_file.readline())

    def read_sensor_str(self,filename):
        # reads sensor with single line string output with stripped \n
        with open(self.cardpath+filename) as origin_file:
            return origin_file.readline().rstrip()

    def get_current_clock(self, filename):
        # function used to get current clock speed information
        # outputs: clockvalue, clockstate
        with open(self.cardpath+filename) as origin_file:
            for line in origin_file:
                clock = re.match(r"^(\d):\s(\d.*)Mhz\s\*$", line)
                if clock:
                    return int(clock.group(2)), int(clock.group(1))

    def get_currents(self):
        # Gets current clocks and utilisation figures for displaying in GUI
        self.gpu_clock, self.gpu_state = self.get_current_clock("/pp_dpm_sclk")
        self.gpu_clock_utilisation = self.gpu_clock / self.pstate_clock[-1]

        self.mem_clock, self.mem_state = self.get_current_clock("/pp_dpm_mclk")
        self.mem_utilisation = self.mem_clock / self.pmem_clock[-1]

        if self.fansensors is not None:
            self.fan_speed = self.fansensors.read()
            self.fan_speed_pwm = self.fanpwmsensors.read()
            self.fan_speed_utilisation = self.fan_speed_pwm / 255
        else:
            self.fan_speed = None
            self.fan_speed_pwm = None
            self.fan_speed_utilisation = 0

        self.temperature = self.tempsensors.read()/ 1000
        self.temperature_crit = self.tempsensors.read_attribute("_crit",True) / 1000
        self.temp_utilisation = self.temperature / self.temperature_crit
