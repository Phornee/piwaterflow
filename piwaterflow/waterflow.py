""" Loop for watering system. It will properly activate watering valves according to the schedulling set
    in the config file
"""
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import pytz
from tzlocal import get_localzone

from RPi import GPIO
from influxdb_wrapper import influxdb_factory
from log_mgr import Logger
from piwaterflow import WaterflowConfig

class Waterflow():
    """_summary_
    """
    def __init__(self):
        super().__init__(execpath=__file__)

        self.homevar = os.path.join(str(Path.home()), 'var', self.get_class_name())

        self.logger = Logger(self.get_class_name(), 'waterflow')
        self.looplogger = Logger(self.get_class_name(), 'loop')

        if not template_config_path:
            template_config_path = os.path.join(Path(__file__).parent.resolve(), './config-template.yml')

        self.config = WaterflowConfig(self.get_class_name(), template_config_path, "config.yml")

        influx_conn_type = self.config['influxdbconn'].get('type', 'influx')
        self.conn = influxdb_factory(influx_conn_type)
        self.conn.openConn(self.config['influxdbconn'])

    @classmethod
    def get_class_name(cls):
        """ class name """
        return "waterflow"

    def update_config(self, programs: dict):
        """Updates the config file with modified programs
        Args:
            programs (dict): New programs to be modified
        """
        # Update config in mem
        self.config.update({'programs': programs})

        # Write back config to disk
        self.config.write()

    def _get_now_utc(self):
        return datetime.now(timezone.utc)

    def _time_to_str(self, time_var):
        return time_var.strftime('%Y-%m-%d %H:%M:%S\n')

    def _setup_gpio(self, valves):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.config['inverter_relay_pin'], GPIO.OUT)
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)
        GPIO.setup(self.config['external_ac_signal_pin'], GPIO.IN)
        for valve in valves:
            GPIO.setup(valve['pin'], GPIO.OUT)
            GPIO.output(valve['pin'], GPIO.LOW)

    def _recalc_next_program(self, last_program_time_utc):
        """
        Calculates which is the next program to be executed
        Return: UTC time of next program
        """
        next_program_time_utc = None
        program_number = -1

        current_time = datetime.now().replace(microsecond=0)

        # Find if next program is today, considering the last program time executed
        for idx, program in enumerate(self.config['programs']):
            if program['enabled'] is True:
                candidate_time = current_time.replace(hour=program['start_time'].hour,
                                                      minute=program['start_time'].minute,
                                                      second=0)
                candidate_time_utc = candidate_time.astimezone(pytz.utc)
                # If this candidate is after the last one executed AND its not older than 10 minutes, choose it
                if candidate_time_utc > last_program_time_utc:
                    next_program_time_utc = candidate_time_utc
                    program_number = idx
                    break

        # If its not today, it could be tomorrow... find the first one enabled
        if next_program_time_utc is None:
            for idx, program in enumerate(self.config['programs']):
                if program['enabled'] is True:
                    next_program_time = current_time + timedelta(days=1)
                    next_program_time_utc = next_program_time.replace(hour=program['start_time'].hour,
                                                                      minute=program['start_time'].minute,
                                                                      second=0).astimezone(pytz.utc)
                    program_number = idx
                    break

        return next_program_time_utc, program_number

    def _get_last_program_path(self):
        return os.path.join(self.homevar, 'lastprogram.yml')

    def _read_last_program_time(self):
        last_program_path = self._get_last_program_path()

        try:
            with open(last_program_path, 'r', encoding="utf-8") as file:
                data = file.readlines()
                last_program_time = datetime.strptime(data[0][:-1], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        except Exception:
            last_program_time = self._get_now_utc()
            # last_program_time = datetime.now()
            with open(last_program_path, 'w', encoding="utf-8") as file:
                time_str = self._time_to_str(last_program_time)
                file.writelines([time_str, time_str])
        return last_program_time

    def _write_last_program_time(self, timelist):
        last_program_path = self._get_last_program_path()
        with open(last_program_path, 'w', encoding="utf-8") as file:
            file.writelines(time_utc_last)

    def get_lock(self):
        """
        This is to ensure that only one execution will run from cron at the same time
        Use file as a lock... not using DB locks because we want to maximize resiliency
        """
        lock_path = self._getHomePath('lock')

        if not os.path.exists(lock_path):
            with open(lock_path, 'w', encoding="utf-8"):
                return True
        else:
            modified_time = datetime.fromtimestamp(os.path.getmtime(lock_path))
            if (datetime.utcnow() - modified_time) > timedelta(minutes=20):
                self.userlogger.warning('Lock expired: Last loop ended abnormally?.')
                Path(lock_path).touch()  # Previous token expired (previous loop crashed?)... we will retouch to retry
                return True
        return False

    def release_lock(self):
        """Lock the loop... so the 2 loops cannot happen at the same time
        """
        lock_path = self._getHomePath('lock')

        if os.path.exists(lock_path):
            os.remove(lock_path)
        else:
            self.userlogger.error(f"Could not release lock.")

    def is_looping_correctly(self):
        return (datetime.utcnow() - self.get_last_loop_time()) < timedelta(minutes=10)

    def get_last_loop_time(self):
        tokenpath = os.path.join(self.homevar, 'token')

        mod_time_since_epoc = os.path.getmtime(tokenpath)
        modification_time = datetime.utcfromtimestamp(mod_time_since_epoc)

        return modification_time

    def force(self, type_force, value):
        config = self.config.get_dict()
        if (type_force == 'program' and 0 <= value < len(config['programs'])) or \
           (type_force == 'valve' and 0 <= value < len(config['valves'])):
            force_file_path = os.path.join(self.homevar, 'force')
            with open(force_file_path, 'w', encoding="utf-8") as force_file:
                force_file.write(f'{{"type":"{type_force}","value":{value}}}')
                return True
        else:
            return False

    def stop(self):
        stop_req_path = os.path.join(self.homevar, 'stop')
        Path(stop_req_path).touch()
        return True

    def stop_requested(self):
        stop_req_path = os.path.join(self.homevar, 'stop')
        return os.path.exists(stop_req_path)

    def stop_remove(self):
        stop_req_path = os.path.join(self.homevar, 'stop')
        return os.remove(stop_req_path)

    def get_forced_info(self):
        force_file_path = os.path.join(self.homevar, 'force')
        if os.path.exists(force_file_path):
            with open(force_file_path, 'r', encoding="utf-8") as force_file:
                data = json.load(force_file)
                return data
        else:
            return None

    def get_log(self):
        return self.logger.get_log()

    def _sleep(self, time_sleep):
        """
        Sleep "time_sleep" time, but checks every 5 seconds if a stop has been requested
        """
        time_count = 0
        while not self.stop_requested() and time_count < time_sleep:
            time_count = time_count + 5
            time.sleep(5)  # Every X seconds

    def _emit_action_metric(self, action, forced):
        if self.config['metrics'] and self.conn:
            action_body = [
                {
                    "tags": {"action": action, "forced": forced},
                    "fields": {"fake": 0}
                }
            ]
            self.conn.insert("piwaterflow", action_body)

    def _execute_valve(self, valve):
        # ------------------------------------
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.userlogger.info('Inverter relay ON.')
        valve_pin = self.config['valves'][valve]['pin']
        GPIO.output(valve_pin, GPIO.HIGH)
        self.logger.info(f'Valve {valve} ON.')

        self._sleep(self.config['max_valve_time']*60)

        GPIO.output(valve_pin, GPIO.LOW)
        self.logger.info(f'Valve {valve} OFF.')
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.userlogger.info('Inverter relay OFF.')

    def _skip_program(self):
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

    def _execute_program(self, program_number):
        """
        Works for regular programs, or forced ones (if program number is sent)
        """
        self.logger.info(f'Executing program {program_number}.')
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we don't have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.userlogger.info('Inverter relay ON.')
        for idx, valve_time in enumerate(self.config['programs'][program_number]['valves_times']):
            if valve_time > 0 and not self.stop_requested():
                valve_pin = self.config['valves'][idx]['pin']
                GPIO.output(valve_pin, GPIO.HIGH)
                self.logger.info(f'Valve {idx} ON.')

                self._sleep(valve_time * 60)

                GPIO.output(valve_pin, GPIO.LOW)
                self.logger.info(f'Valve {idx} OFF.')
            else:
                self.logger.info(f'Valve {idx} Skipped.')
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.userlogger.info('Inverter relay OFF.')

    def _log_next_program_time(self, current_time_utc):

        log = self.logger.get_log()

        lines = log.split('\n')

        new_next_program_time_utc, _ = self._recalc_next_program(current_time_utc)

        if new_next_program_time_utc:
            new_next_program_time_local = new_next_program_time_utc.astimezone(get_localzone())

            string_to_log = f"Next program: {new_next_program_time_local.strftime('%Y-%m-%d %H:%M')}."
        else:
            string_to_log = 'NO active program!'

        # If previous log empty, or if last line outputs different information... log it. (to avoid duplicated logs)
        if len(lines) <= 1 or (lines[-2][20:] != string_to_log and string_to_log != ''):
            self.userlogger.info(string_to_log)

    def _execute_forced(self, forced_info: dict, curr_time_utc):
        forced_type = forced_info.get("type")
        forced_value = forced_info.get("value")
        if forced_type == "program":
            self.logger.info(f'Forced program {forced_value} executing now.')
            # ------------------------
            self._emit_action_metric(f'prog{forced_value}', True)
            self._execute_program(forced_value)
            self._write_last_program_time(self._time_to_str(curr_time_utc))
        elif forced_type == "valve":
            # ------------------------
            self._emit_action_metric('valve{forced_value}', True)
            self._execute_valve(forced_value)

    def _check_and_execute_program(self, curr_time_utc):
        last_program_time = self._read_last_program_time()
        new_next_program_utc, new_program_number = self._recalc_next_program(last_program_time)
        if new_next_program_utc:
            # ------------------------
            time_reached = curr_time_utc >= new_next_program_utc
            time_threshold_exceeded = curr_time_utc > (new_next_program_utc + timedelta(minutes=10))
            skip_program = self._skip_program()
            # If we have reached the time of the new_program_time, BUT not by more than 10 minutes...
            if time_reached and not time_threshold_exceeded and not skip_program:
                self._emit_action_metric(f'prog{new_program_number}', False)
                self._execute_program(new_program_number)
                program_executed = True
            else:
                program_executed = False

            if program_executed or skip_program or time_threshold_exceeded:
                self._write_last_program_time(self._time_to_str(curr_time_utc))

    def loop(self):
        """ Loop executed every x minutes... in crontab for example.
        """
        if self.get_lock():  # To ensure a single execution despite of cron overlapping
            try:
                curr_time_utc = self._get_now_utc()
                forced_info = self.get_forced_info()

                if not self.stop_requested():
                    self.debuglogger.info('Looping...')
                    self._setup_gpio(self.config['valves'])

                    if forced_info:
                        self._execute_forced(forced_info, curr_time_utc)
                    else:
                        self._check_and_execute_program(curr_time_utc)
                else:
                    self.debuglogger.info('Loop skipped (Stop request).')
                    self.userlogger.info('Activity stopped.')
                    self._emit_action_metric('Stop', True)
                    self.stop_remove()

                if forced_info:
                    # Remove force token file
                    os.remove(os.path.join(self.homevar, 'force'))

                # Recalc next program time
                self._log_next_program_time(curr_time_utc)

                # Updates "modified" time AT THE END, so that we can keep track about waterflow looping SUCCESFULLY.
                token_path = self._getHomePath('token')
                Path(token_path).touch()

            except Exception as ex:
                self.logger.error(f'Exception looping: {str(ex)}')
                raise
            finally:
                GPIO.cleanup()
                self.release_lock()


