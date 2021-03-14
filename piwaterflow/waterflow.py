import RPi.GPIO as GPIO
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from baseutils_phornee import ManagedClass
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import json

min_date = datetime(1971, 11, 24, 0, 0, 0)

class Waterflow(ManagedClass):

    def __init__(self):
        super().__init__(execpath=__file__)

        token = self.config['influxdbconn']['token']
        self.org = self.config['influxdbconn']['org']
        self.bucket = self.config['influxdbconn']['bucket']

        self.conn = InfluxDBClient(url=self.config['influxdbconn']['url'], token=token)

    @classmethod
    def getClassName(cls):
        return "waterflow"

    @classmethod
    def getLog(cls):
        log_path = os.path.join(cls.getHomevarPath(), 'log/waterflow.log')

        with open(log_path, 'r') as file:
            return file.read()

    def readConfig(self):
        super().readConfig()

        # Convert the date from string to datetime object
        for program in self.config['programs']:
            program['start_time'] = datetime.strptime(program['start_time'], '%H:%M:%S')

        # Sort the programs by time
        self.config['programs'].sort(key=lambda prog: prog['start_time'])

    def _timeToStr(self, time_var):
        return time_var.strftime('%Y-%m-%d %H:%M:%S\n')

    def _setupGPIO(self, valves):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.config['inverter_relay_pin'], GPIO.OUT)
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)
        GPIO.setup(self.config['external_ac_signal_pin'], GPIO.IN)
        for valve in valves:
            GPIO.setup(valve['pin'], GPIO.OUT)
            GPIO.output(valve['pin'], GPIO.LOW)
            pass


    def _recalcNextProgram(self, last_program_time):
        next_program_time = None
        program_number = -1

        current_time = datetime.now().replace(microsecond=0)

        # Find if next program is today
        for idx, program in enumerate(self.config['programs']):
            if program['enabled'] == True:
                candidate_time = current_time.replace(hour=program['start_time'].hour,
                                                      minute=program['start_time'].minute,
                                                      second=0)
                if candidate_time > last_program_time:
                    next_program_time = candidate_time
                    program_number = idx
                    break

        # If its not today, it could be tomorrow... find the first one enabled
        if next_program_time is None:
            for idx, program in enumerate(self.config['programs']):
                if program['enabled'] == True:
                    next_program_time = current_time + timedelta(days=1)
                    next_program_time = next_program_time.replace(hour=program['start_time'].hour,
                                                                  minute=program['start_time'].minute,
                                                                  second=0)
                    program_number = idx
                    break

        return next_program_time, program_number

    def _getLastProgramPath(self):
        return os.path.join(self.homevar, 'lastprogram.yml')

    def _readLastProgramTime(self):
        last_program_path = self._getLastProgramPath()

        try:
            with open(last_program_path, 'r') as file:
                data = file.readlines()
                last_program_time = datetime.strptime(data[0][:-1], '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            last_program_time = datetime.now()
            with open(last_program_path, 'w') as file:
                time_str = self._timeToStr(last_program_time)
                file.writelines([time_str, time_str])
        return last_program_time

    def _writeLastProgramTime(self, timelist):
        last_program_path = self._getLastProgramPath()
        with open(last_program_path, 'w') as file:
            file.writelines(timelist)

    def getLock(self):
        """
        Use file as a lock... not using DB locks because we want to maximize resiliency
        """
        lock_path = os.path.join(self.homevar, 'lock')

        if not os.path.exists(lock_path):
            with open(lock_path, 'w'):
                return True
        else:
            modified_time = datetime.fromtimestamp(os.path.getmtime(lock_path))
            if (datetime.utcnow() - modified_time) > timedelta(minutes=20):
                self.logger.warning('Lock expired: Last loop ended abnormally?.')
                return True
        return False

    def releaseLock(self):
        lock_path = os.path.join(self.homevar, 'lock')

        if os.path.exists(lock_path):
            os.remove(lock_path)
        else:
            self.logger.error(f"Could not release lock.")

    @classmethod
    def isLoopingCorrectly(cls):
        tokenpath = os.path.join(cls.getHomevarPath(), 'token')

        modTimesinceEpoc = os.path.getmtime(tokenpath)
        modificationTime = datetime.utcfromtimestamp(modTimesinceEpoc)

        return (datetime.utcnow() - modificationTime) < timedelta(minutes=10)

    @classmethod
    def force(cls, type_force, value):
        config = cls.getConfig()
        if (type_force == 'program' and 0 <= value < len(config['programs'])) or \
           (type_force == 'valve' and 0 <= value < len(config['valves'])):
            force_file_path = os.path.join(cls.getHomevarPath(), 'force')
            with open(force_file_path, 'w') as force_file:
                force_file.write('{{"type":"{0}","value":{1}}}'.format(type_force, value))
                return True
        else:
            return False

    @classmethod
    def stop(cls):
        stop_req_path = os.path.join(cls.getHomevarPath(), 'stop')
        Path(stop_req_path).touch()
        return True

    @classmethod
    def stopRequested(cls):
        stop_req_path = os.path.join(cls.getHomevarPath(), 'stop')
        return os.path.exists(stop_req_path)

    @classmethod
    def stopRemove(cls):
        stop_req_path = os.path.join(cls.getHomevarPath(), 'stop')
        return os.remove(stop_req_path)

    @classmethod
    def getForcedInfo(cls):
        force_file_path = os.path.join(cls.getHomevarPath(), 'force')
        if os.path.exists(force_file_path):
            with open(force_file_path, 'r') as force_file:
                data = json.load(force_file)
                return data
        else:
            return None

    def _sleep(self, time_sleep):
        time_count = 0
        while not self.stopRequested() and time_count < time_sleep:
            time_count = time_count + 5
            time.sleep(5)  # Every X seconds

    def _emitMetric(self, action, forced):
        write_api = self.conn.write_api(write_options=SYNCHRONOUS)

        point = Point('piwaterflow') \
            .tag('action', action) \
            .tag('forced', forced) \
            .field('fake', 0) \
            .time(datetime.utcnow(), WritePrecision.NS)

        write_api.write(self.bucket, self.org, point)

    def _executeValve(self, valve):
        # ------------------------------------
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.logger.info('Inverter relay ON.')
        valve_pin = self.config['valves'][valve]['pin']
        GPIO.output(valve_pin, GPIO.HIGH)
        self.logger.info('Valve %s ON.' % valve)

        self._sleep(5*60)

        GPIO.output(valve_pin, GPIO.LOW)
        self.logger.info('Valve %s OFF.' % valve)
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.logger.info('Inverter relay OFF.')

    def _executeProgram(self, program_number):
        """
        Works for regular programs, or forced ones (if program number is sent)
        """
        self.logger.info('Executing program %s.' % program_number)
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we don't have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.logger.info('Inverter relay ON.')
        for idx, valve_time in enumerate(self.config['programs'][program_number]['valves_times']):
            if valve_time > 0 and not self.stopRequested():
                valve_pin = self.config['valves'][idx]['pin']
                GPIO.output(valve_pin, GPIO.HIGH)
                self.logger.info('Valve %s ON.' % idx)

                self._sleep(valve_time * 60)

                GPIO.output(valve_pin, GPIO.LOW)
                self.logger.info('Valve %s OFF.' % idx)
            else:
                self.logger.info('Valve %s Skipped.' % idx)
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.logger.info('Inverter relay OFF.')

    def _logNextProgramTime(self, current_time):

        log = self.getLog()

        lines = log.split('\n')
        last_line = lines[-2]

        new_next_program_time, _ = self._recalcNextProgram(current_time)
        if new_next_program_time is not None:
            string_to_log = 'Next program: %s.' % new_next_program_time.strftime('%Y-%m-%d %H:%M')
        else:
            string_to_log = 'NO active program!'

        if last_line[20:] != string_to_log and string_to_log != '':
            self.logger.info(string_to_log)

    def loop(self):
        if self.getLock():  # To ensure a single execution
            try:
                # Updates "modified" time, so that we can keep track about waterflow looping
                token_path = os.path.join(self.homevar, 'token')
                Path(token_path).touch()

                current_time = datetime.now()
                forced_info = self.getForcedInfo()

                if not self.stopRequested():
                    self._setupGPIO(self.config['valves'])
                    last_program_time = self._readLastProgramTime()

                    if forced_info is not None:
                        forced_type = forced_info.get("type")
                        forced_value = forced_info.get("value")
                        if forced_type == "program":
                            self.logger.info('Forced program {} executing now.'.format(forced_value))
                            # ------------------------
                            self._emitMetric('prog{}'.format(forced_value), True)
                            self._executeProgram(forced_value)
                            self._writeLastProgramTime(self._timeToStr(current_time))
                        elif forced_type == "valve":
                            # ------------------------
                            self._emitMetric('valve{}'.format(forced_value), True)
                            self._executeValve(forced_value)
                    else:
                        new_next_program_time, calculated_program_number = self._recalcNextProgram(last_program_time)
                        if new_next_program_time is not None and current_time >= new_next_program_time:
                            # ------------------------
                            self._emitMetric('prog{}'.format(calculated_program_number), False)
                            self._executeProgram(calculated_program_number)
                            self._writeLastProgramTime(self._timeToStr(current_time))

                if forced_info is not None:
                    # Remove force token file
                    os.remove(os.path.join(self.getHomevarPath(), 'force'))

                if self.stopRequested():
                    self.logger.info('Activity stopped.')
                    self._emitMetric('Stop', True)
                    self.stopRemove()

                # Recalc next program time
                self._logNextProgramTime(current_time)
            except Exception as e:
                self.logger.error(f"Exception looping: {e}")
            finally:
                GPIO.cleanup()
                self.releaseLock()


if __name__ == "__main__":
    waterflow_instance = Waterflow()
    waterflow_instance.loop()

