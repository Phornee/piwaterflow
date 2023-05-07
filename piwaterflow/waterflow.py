""" Loop for watering system. It will properly activate watering valves according to the schedulling set
    in the config file
    All times are local to the watering system location
"""
import os
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import json

try:
    from RPi import GPIO
except (ModuleNotFoundError, ImportError, RuntimeError):
    from fake_rpi.RPi import GPIO
    from fake_rpi import toggle_print
    toggle_print(False)

from influxdb_wrapper import influxdb_factory
from log_mgr import Logger
from .config_waterflow import WaterflowConfig

class Waterflow():
    """ Waterflow class that manages a loop system to activate/deactivate watering valves.
        This should run in a raspberry pi or similar, with watering valves connected through relays.
        At this moment it can support up to 2 valves, and 2 different programs alnog the day.
        Those programs/valves can be switched on/off in a forced way apart from the programs.
        This is autonomous, and could be controlled by directly changing the programs´configuration in the
        config.yml file.
        However, it can work together with the piwwwwaterflow package that serves a http page to remotely control
        the waterflow system.
    """
    def __init__(self, template_config_path: str = None, dry_run: bool = False):
        """__init__ of the function
        Args:
            template_config_path (str, optional): Template config to use. Defaults to None.
            dry_run (bool, optional): If true, it will just simulate, and wont make any change. Defaults to False.
        """
        self.homevar = os.path.join(str(Path.home()), 'var', self.class_name())

        if dry_run:
            self.dry_run = True
            self.homevar = os.path.join(self.homevar, 'dryrun')
            if os.path.exists(self.homevar): # Only one instance of waterflow can run at a time, so this is safe
                shutil.rmtree(self.homevar)
            if not os.path.exists(self.homevar):
                os.makedirs(self.homevar)
            dry_run_abs_path = ""
        else:
            self.dry_run = False
            dry_run_abs_path = None

        self.debuglogger = Logger(self.class_name(), 'waterflow', dry_run=dry_run)
        self.userlogger = Logger(self.class_name(), 'loop', dry_run=dry_run)

        if not template_config_path:
            template_config_path = os.path.join(Path(__file__).parent.resolve(), './config-template.yml')

        self.config = WaterflowConfig(package_name=self.class_name(),
                                        template_path=template_config_path,
                                        config_file_name="config.yml",
                                        dry_run_abs_path=dry_run_abs_path)

        influx_conn_type = self.config['influxdbconn'].get('type', 'influx')
        self.conn = influxdb_factory(influx_conn_type)
        self.conn.openConn(self.config['influxdbconn'])

    def __del__(self):
        if self.dry_run:
            shutil.rmtree(self.homevar)

    @classmethod
    def class_name(cls):
        """ class name """
        return "waterflow"

    def _get_homevar_path(self, rel_path):
        return os.path.join(self.homevar, rel_path)

    def update_config(self, programs: dict):
        """Updates the config file with modified programs
        Args:
            programs (dict): New programs to be modified
        """
        # Update config in mem
        self.config.update({'programs': programs})

        # Write back config to disk
        self.config.write()

    def _get_program_data(self, program):
        return next(iter(program.values()))

    @staticmethod
    def time_to_str(time_var: datetime) -> str:
        """ Transform a datetime into custom formatted string
        Args:
            time_var (datetime): Datetime
        Returns:
            str: Date written into a string
        """
        return time_var.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def str_to_time(date_str: str) -> datetime:
        """ Extracts a datetime out of a string
        Args:
            date_str (str): String containing a date
        Returns:
            datetime: Time in local timezone
        """
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').astimezone()

    def _setup_gpio(self, valves):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.config['inverter_relay_pin'], GPIO.OUT)
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)
        GPIO.setup(self.config['external_ac_signal_pin'], GPIO.IN)
        for valve in valves:
            GPIO.setup(valve['pin'], GPIO.OUT)
            GPIO.output(valve['pin'], GPIO.LOW)

    def _recalc_next_program(self, last_program_time: datetime, today: datetime = None):
        """ Calculates which is the next program to be executed, depending on the one previously executed
        Args:
            last_program_time: (datetime): Time in which previous program was executed (local aware to watering system)
            today (datetime, optional): Naive time to make the calculations. Normally used just for debug/unittesting
        Returns:
            tuple: time of next program, and program name
        """
        next_program_time = None
        program_name = None

        # Only used to get "today"... hour and minute will be overwritten for comparations with last_program_time
        if today:
            current_time = today.astimezone() # Make aware
        else:
            current_time = datetime.now().astimezone().replace(microsecond=0)

        # Transform into a list to sort them
        prog_list = []
        for key, value in self.config['programs'].items():
            temp = value
            temp['name'] = key
            prog_list.append(temp)
        prog_list.sort(key=lambda prog: prog['start_time'])

        # Find if next program is today, considering the last program time executed
        for program in prog_list:
            if program['enabled'] is True:
                candidate_time = current_time.replace(hour=program['start_time'].hour,
                                                      minute=program['start_time'].minute,
                                                      second=0).astimezone()
                # If this candidate is after the last one executed AND its not older than 10 minutes, choose it
                if candidate_time > last_program_time:
                    next_program_time = candidate_time
                    program_name = program['name']
                    break

        # If its not today, it could be tomorrow... find the first one enabled
        if next_program_time is None:
            for program in prog_list:
                if program['enabled'] is True:
                    next_program_time = current_time + timedelta(days=1)
                    next_program_time = next_program_time.replace(hour=program['start_time'].hour,
                                                                  minute=program['start_time'].minute,
                                                                  second=0).astimezone()
                    program_name = program['name']
                    break

        return next_program_time, program_name

    def _last_program_path(self):
        return self._get_homevar_path('lastprogram.yml')

    def _read_last_program_time(self):
        last_program_path = self._last_program_path()

        if os.path.exists(last_program_path):
            with open(last_program_path, 'r', encoding="utf-8") as file:
                data = file.readlines()
                last_program_time = self.str_to_time(data[0][:-1])
        else:
            last_program_time = datetime.now().astimezone()
            with open(last_program_path, 'w', encoding="utf-8") as file:
                time_str = self.time_to_str(last_program_time)
                file.writelines([time_str, time_str])
        return last_program_time

    def _write_last_program_time(self, timelist):
        last_program_path = self._last_program_path()
        with open(last_program_path, 'w', encoding="utf-8") as file:
            file.writelines(timelist)

    def get_lock(self):
        """
        This is to ensure that only one execution will run from cron at the same time
        Use file as a lock... not using DB locks because we want to maximize resiliency
        """
        lock_path = self._get_homevar_path('lock')

        if not os.path.exists(lock_path):
            with open(lock_path, 'w', encoding="utf-8"):
                return True
        else:
            modified_time = datetime.fromtimestamp(os.path.getmtime(lock_path)).astimezone()
            if (datetime.now().astimezone() - modified_time) > timedelta(minutes=self.config['max_loop_time']):
                self.userlogger.warning('Lock expired: Last loop ended abnormally?.')
                Path(lock_path).touch()  # Previous token expired (previous loop crashed?)... we will retouch to retry
                return True
        return False

    def release_lock(self):
        """Lock the loop... so the 2 loops cannot happen at the same time
        """
        lock_path = self._get_homevar_path('lock')

        if os.path.exists(lock_path):
            os.remove(lock_path)
        else:
            self.userlogger.error("Could not release lock.")

    def is_looping_correctly(self):
        """ Returns if a loop has succesfully run in the last x minutes
        Returns:
           bool: 
        """
        time_now = datetime.now().astimezone()
        return (time_now - self.last_loop_time()) < timedelta(minutes=self.config['max_loop_time'])

    def last_loop_time(self):
        """ Returns the last time in that a loop was succesfully executed
        Returns:
           datetime: Time in which last loop was executed
        """
        token_path = self._get_homevar_path('token')
        if os.path.exists(token_path):
            mod_time_since_epoc = os.path.getmtime(token_path)
            modification_time = datetime.fromtimestamp(mod_time_since_epoc).astimezone()
        else:
            modification_time = datetime.fromtimestamp(0) # Loop never run ok. Return oldest possible date

        return modification_time

    def force(self, type_force: str, value: int):
        """ Set the force-flag, so that the loop will start the execution of a program or valve
            If a program is forced, it will execute with the times defined in the config
            If a valve is forced, it will start delivering water, until manually stopped
        Args:
            type_force (str): Can be "program" or "valve"
            value (int): Index of the item to be forced

        Returns:
            bool: If forced correctly
        """
        config = self.config.get_dict()
        if (type_force == 'program' and 0 <= value < len(config['programs'])) or \
           (type_force == 'valve' and 0 <= value < len(config['valves'])):
            with open(self._get_homevar_path('force'), 'w', encoding="utf-8") as force_file:
                force_file.write(f'{{"type":"{type_force}","value":{value}}}')
                return True
        else:
            return False

    def stop(self):
        """ Set the Stop-flag, so that the loop will stop the forced valve or program execution
        Returns:
            _type_: _description_
        """
        stop_req_path = self._get_homevar_path('stop')
        Path(stop_req_path).touch()
        return True

    def stop_remove(self):
        """ Returns if a stop has already been requested
        Returns:
           bool: Return true if a stop has been requested
        """
        stop_req_path = self._get_homevar_path('stop')
        return os.remove(stop_req_path)

    def stop_requested(self):
        """ Returns if a stop has already been requested
        Returns:
           bool: Return true if a stop has been requested
        """
        stop_req_path = self._get_homevar_path('stop')
        return os.path.exists(stop_req_path)

    def get_forced_info(self):
        """ Returns the forced info of the waterflow
        Returns:
            dict: Forced info
        """
        force_file_path = self._get_homevar_path('force')
        if os.path.exists(force_file_path):
            with open(force_file_path, 'r', encoding="utf-8") as force_file:
                data = json.load(force_file)
                return data
        else:
            return None

    def get_log(self):
        """ Get the user log (not the debug log). This is the one the is shown in the wwwaterflow
        Returns:
            str: The whole user logs
        """
        return self.userlogger.get_log()

    def _sleep(self, time_sleep):
        """ Sleep "time_sleep" time, but checks every 5 seconds if a stop has been requested
        Args:
            time_sleep (int): Number of seconds to sleep
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
        self.userlogger.info(f'Valve {valve} ON.')

        self._sleep(self.config['max_valve_time']*60)

        GPIO.output(valve_pin, GPIO.LOW)
        self.userlogger.info(f'Valve {valve} OFF.')
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

    def _execute_program(self, program_name: str):
        """
        Works for regular programs, or forced ones (if program number is sent)
        """
        self.userlogger.info(f'Executing program {program_name}.')
        # inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        # if inverter_enable: # If we don't have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.userlogger.info('Inverter relay ON.')
        program_data = self._get_program_data(self.config['programs'][program_name])
        for idx, valve_time in enumerate(program_data['valves_times']):
            if valve_time > 0 and not self.stop_requested():
                valve_pin = self.config['valves'][idx]['pin']
                GPIO.output(valve_pin, GPIO.HIGH)
                self.userlogger.info(f'Valve {idx} ON.')

                self._sleep(valve_time * 60)

                GPIO.output(valve_pin, GPIO.LOW)
                self.userlogger.info(f'Valve {idx} OFF.')
            else:
                self.userlogger.info(f'Valve {idx} Skipped.')
        # if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)  # INVERTER always OFF after operations
        self.userlogger.info('Inverter relay OFF.')

    def _log_next_program_time(self, current_time):

        log = self.userlogger.get_log()

        lines = log.split('\n')

        new_next_program_time, _ = self._recalc_next_program(current_time)

        if new_next_program_time:
            string_to_log = f"Next program: {self.time_to_str(new_next_program_time)}."
        else:
            string_to_log = 'NO active program!'

        # If previous log empty, or if last line outputs different information... log it. (to avoid duplicated logs)
        if len(lines) <= 1 or (lines[-2][20:] != string_to_log and string_to_log != ''):
            self.userlogger.info(string_to_log)

    def _execute_forced(self, forced_info: dict, curr_time: datetime):
        forced_type = forced_info.get("type")
        forced_value = forced_info.get("value")
        if forced_type == "program":
            self.userlogger.info(f'Forced program {forced_value} executing now.')
            # ------------------------
            self._emit_action_metric(f'prog{forced_value}', True)
            self._execute_program(forced_value)
            self._write_last_program_time(self.time_to_str(curr_time))
        elif forced_type == "valve":
            # ------------------------
            self._emit_action_metric('valve{forced_value}', True)
            self._execute_valve(forced_value)

    def _check_and_execute_program(self, curr_time: datetime):
        last_program_time = self._read_last_program_time()
        new_next_program, new_program_name = self._recalc_next_program(last_program_time)
        if new_next_program:
            # ------------------------
            time_reached = curr_time >= new_next_program
            time_threshold_exceeded = curr_time > (new_next_program + timedelta(minutes=self.config['max_loop_time']))
            skip_program = self._skip_program()
            # If we have reached the time of the new_program_time, BUT not by more than 10 minutes...
            if time_reached and not time_threshold_exceeded and not skip_program:
                self._emit_action_metric(f'prog_{new_program_name}', False)
                self._execute_program(new_program_name)
                program_executed = True
            else:
                program_executed = False

            if program_executed or skip_program or time_threshold_exceeded:
                self._write_last_program_time(self.time_to_str(curr_time))

    def loop(self, date_now: datetime = None):
        """ Loop executed every x minutes... in crontab for example.
        Args:
            date_now (datetime): Naive date to consider the execution of the loop. 
                                 Normally used only for debuggin/unittesting
        """
        if self.get_lock():  # To ensure a single execution despite of cron overlapping
            try:
                if date_now:
                    curr_time = date_now.astimezone() # Make aware
                else:
                    curr_time = datetime.now().astimezone()
                forced_info = self.get_forced_info()

                if not self.stop_requested():
                    self.debuglogger.info('Looping...')
                    self._setup_gpio(self.config['valves'])

                    if forced_info:
                        self._execute_forced(forced_info, curr_time)
                    else:
                        self._check_and_execute_program(curr_time)
                else:
                    self.debuglogger.info('Loop skipped (Stop request).')
                    self.userlogger.info('Activity stopped.')
                    self._emit_action_metric('Stop', True)
                    self.stop_remove()

                if forced_info:
                    # Remove force token file
                    os.remove(os.path.join(self.homevar, 'force'))

                # Recalc next program time
                self._log_next_program_time(curr_time)

                # Updates "modified" time AT THE END, so that we can keep track about waterflow looping SUCCESFULLY.
                token_path = os.path.join(self.homevar, 'token')
                Path(token_path).touch()

            except Exception as ex:
                self.debuglogger.error(f'Exception looping: {str(ex)}')
                self.userlogger.error(f'Exception looping: {str(ex)}')
                raise RuntimeError(ex) from ex
            finally:
                GPIO.cleanup()
                self.release_lock()
        else:
            self.debuglogger.error('Loop executed while locked by previous execution.')
