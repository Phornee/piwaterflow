import RPi.GPIO as GPIO
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from baseutils_phornee import ManagedClass, Logger
from .configwaterflow import WaterflowConfig
from influxdb import InfluxDBClient

import json

class Waterflow(ManagedClass):

    def __init__(self):
        super().__init__(execpath=__file__)

        self.logger = Logger({'modulename': self.getClassName(), 'logpath': 'log'})
        self.config = WaterflowConfig({'modulename': self.getClassName(), 'execpath': __file__})

        try:
            host = self.config['influxdbconn']['host']
            user = self.config['influxdbconn']['user']
            password = self.config['influxdbconn']['password']
            bucket = self.config['influxdbconn']['bucket']
        except Exception as e:
            self.logger.warning('Error getting connection credentials to InfluxDB.')
            pass

        try:
            self.conn = InfluxDBClient(host=host, username=user, password=password, database=bucket)
        except Exception as e:
            self.logger.warning('Connection to InfluxDB failed: %s.' % host)
            self.conn = None
            pass

    @classmethod
    def getClassName(cls):
        return "waterflow"

    def updateConfig(self, programs):
        # Update config in mem
        self.config.update({'programs': programs})

        # Write back config to disk
        self.config.write()

    def _setTimezoneUTC(self, date):
        import pytz

        return pytz.timezone('UTC').localize(date)

    def _getNowUTC(self):
        return datetime.now(timezone.utc)

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
        """
        Calculates which is the next program to be executed
        """
        next_program_time = None
        program_number = -1

        #current_time = self._getNowUTC().replace(microsecond=0)
        current_time = datetime.now()

        # Find if next program is today, considering the last program time executed
        for idx, program in enumerate(self.config['programs']):
            if program['enabled'] == True:
                candidate_time = current_time.replace(hour=program['start_time'].hour,
                                                      minute=program['start_time'].minute,
                                                      second=0)
                # If this candidate is after the last one executed AND its no more that 10 minutes in the past, choose it
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
                last_program_time = datetime.strptime(data[0][:-1], '%Y-%m-%d %H:%M:%S', tzinfo=datetime.timezone.utc)
        except Exception as e:
            #last_program_time = self._getNowUTC()
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
        This is to ensure that only one execution will run from cron at the same time
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
                Path(lock_path).touch() # Previous token expired (previous loop crashed?)... so we will retouch to try again
                return True
        return False

    def releaseLock(self):
        lock_path = os.path.join(self.homevar, 'lock')

        if os.path.exists(lock_path):
            os.remove(lock_path)
        else:
            self.logger.error(f"Could not release lock.")

    def isLoopingCorrectly(self):
        return (datetime.utcnow() - self.getLastLoopTime()) < timedelta(minutes=10)

    def getLastLoopTime(self):
        tokenpath = os.path.join(self.getHomevarPath(), 'token')

        modTimesinceEpoc = os.path.getmtime(tokenpath)
        modificationTime = datetime.utcfromtimestamp(modTimesinceEpoc)

        return modificationTime

    def force(self, type_force, value):
        config = self.getConfig()
        if (type_force == 'program' and 0 <= value < len(config['programs'])) or \
           (type_force == 'valve' and 0 <= value < len(config['valves'])):
            force_file_path = os.path.join(self.getHomevarPath(), 'force')
            with open(force_file_path, 'w') as force_file:
                force_file.write('{{"type":"{0}","value":{1}}}'.format(type_force, value))
                return True
        else:
            return False

    def stop(self):
        stop_req_path = os.path.join(self.getHomevarPath(), 'stop')
        Path(stop_req_path).touch()
        return True

    def stopRequested(self):
        stop_req_path = os.path.join(self.getHomevarPath(), 'stop')
        return os.path.exists(stop_req_path)

    def stopRemove(self):
        stop_req_path = os.path.join(self.getHomevarPath(), 'stop')
        return os.remove(stop_req_path)

    def getForcedInfo(self):
        force_file_path = os.path.join(self.getHomevarPath(), 'force')
        if os.path.exists(force_file_path):
            with open(force_file_path, 'r') as force_file:
                data = json.load(force_file)
                return data
        else:
            return None

    def getLog(self):
        return self.logger.getLog()

    def _sleep(self, time_sleep):
        """
        Sleep "time_sleep" time, but checks every 5 seconds if a stop has been requested
        """
        time_count = 0
        while not self.stopRequested() and time_count < time_sleep:
            time_count = time_count + 5
            time.sleep(5)  # Every X seconds

    def _emitActionMetric(self, action, forced):
        if self.conn:
            json_body = [
                {
                    "measurement": "piwaterflow",
                    "tags": {
                        "action": action,
                        "forced": forced
                    },
                    "time": datetime.utcnow(),
                    "fields": {
                        "fake": 0
                    }
                }
            ]
            self.conn.write_points(json_body)

    def _executeValve(self, valve):
        # ------------------------------------
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.logger.info('Inverter relay ON.')
        valve_pin = self.config['valves'][valve]['pin']
        GPIO.output(valve_pin, GPIO.HIGH)
        self.logger.info('Valve %s ON.' % valve)

        self._sleep(self.config['max_valve_time']*60)

        GPIO.output(valve_pin, GPIO.LOW)
        self.logger.info('Valve %s OFF.' % valve)
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.logger.info('Inverter relay OFF.')

    def _skipProgram(self):
        # print(self.config['humidity_threshold'])
        # if self.is_raspberry_pi():
        #     import adafruit_dht
        #     dhtSensor = adafruit_dht.DHT22(self.config['pin'])
        #     humidity = dhtSensor.humidity
        #     temp_c = dhtSensor.temperature
        #     if humidity >= self.config['humidity_threshold']:
        #         self.logger.info('(humidity {} > {}.'.format(humidity, self.config['humidity_threshold']))
        #         return True
        #     else:
        #         return False
        # else:
        #    return False
        return False

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

        log = self.logger.getLog()

        lines = log.split('\n')
        last_line = lines[-2]

        new_next_program_time, _ = self._recalcNextProgram(current_time)
        if new_next_program_time:
            string_to_log = 'Next program: %s.' % new_next_program_time.strftime('%Y-%m-%d %H:%M')
        else:
            string_to_log = 'NO active program!'

        if last_line[20:] != string_to_log and string_to_log != '':
            self.logger.info(string_to_log)

    def loop(self):
        if self.getLock():  # To ensure a single execution despite of cron overlapping
            try:
                #current_time = self._getNowUTC()
                current_time = datetime.now()
                forced_info = self.getForcedInfo()

                if not self.stopRequested():
                    self._setupGPIO(self.config['valves'])
                    last_program_time = self._readLastProgramTime()

                    if forced_info:
                        forced_type = forced_info.get("type")
                        forced_value = forced_info.get("value")
                        if forced_type == "program":
                            self.logger.info('Forced program {} executing now.'.format(forced_value))
                            # ------------------------
                            self._emitActionMetric('prog{}'.format(forced_value), True)
                            self._executeProgram(forced_value)
                            self._writeLastProgramTime(self._timeToStr(current_time))
                        elif forced_type == "valve":
                            # ------------------------
                            self._emitActionMetric('valve{}'.format(forced_value), True)
                            self._executeValve(forced_value)
                    else:
                        new_next_program_time, calculated_program_number = self._recalcNextProgram(last_program_time)
                        if new_next_program_time:
                            # ------------------------
                            time_reached = current_time >= new_next_program_time
                            time_threshold_exceeded = current_time > (new_next_program_time + timedelta(minutes=10))
                            skip_program = self._skipProgram()
                            # If we have reached the time of the new_program_time, BUT not by more than 10 minutes...
                            if time_reached and not time_threshold_exceeded and not skip_program:
                                self._emitActionMetric('prog{}'.format(calculated_program_number), False)
                                self._executeProgram(calculated_program_number)
                                program_executed = True
                            else:
                                program_executed = False

                            if program_executed or skip_program or time_threshold_exceeded:
                                self._writeLastProgramTime(self._timeToStr(current_time))

                if forced_info:
                    # Remove force token file
                    os.remove(os.path.join(self.getHomevarPath(), 'force'))

                if self.stopRequested():
                    self.logger.info('Activity stopped.')
                    self._emitActionMetric('Stop', True)
                    self.stopRemove()

                # Recalc next program time
                self._logNextProgramTime(current_time)

                # Updates "modified" time AT THE END, so that we can keep track about waterflow looping SUCCESFULLY.
                token_path = os.path.join(self.homevar, 'token')
                Path(token_path).touch()

            except Exception as e:
                self.logger.error("Exception looping: {}".format(str(e)))
                raise
            finally:
                GPIO.cleanup()
                self.releaseLock()

if __name__ == "__main__":

    waterflow_instance = Waterflow()
    waterflow_instance.loop()


