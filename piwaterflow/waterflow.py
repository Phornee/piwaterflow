import RPi.GPIO as GPIO
import os
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from baseutils_phornee import ManagedClass

min_date = datetime(1971, 11, 24, 0, 0, 0)

class Waterflow(ManagedClass):

    def __init__(self):
        super().__init__(classname='waterflow', execpath=__file__)

    @classmethod
    def getConfig(cls):
        config_yml_path = os.path.join(Path(__file__).parent, 'config.yml')
        with open(config_yml_path) as config_file:
            config = yaml.load(config_file, Loader=yaml.FullLoader)
            return config

    @classmethod
    def setConfig(cls, config):
        config_yml_path = os.path.join(Path(__file__).parent, 'config.yml')

        with open(config_yml_path, 'w') as config_file:
            yaml.dump(config, config_file)

    @classmethod
    def getLog(cls):
        log_path = os.path.join(Path(__file__).parent, 'log/waterflow.log')

        with open(log_path, 'r') as file:
            return file.read()


    @classmethod
    def getModulePath(cls):
        return Path(__file__).parent

    def readConfig(self):
        super().readConfig()

        # Convert the date from string to datetime object
        for program in self.config['programs']:
            program['start_time'] = datetime.strptime(program['start_time'], '%H:%M:%S')

        # Sort the programs by time
        self.config['programs'].sort(key=lambda prog: prog['start_time'])

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


    def _recalcNextProgram(self, last_program_time, programs):
        next_program_time = None
        program_number = -1

        current_time = datetime.now().replace(microsecond=0)

        # Find if next program is today
        for idx, program in enumerate(programs):
            if program['enabled'] == True:
                candidate = current_time.replace(hour=program['start_time'].hour,
                                                 minute=program['start_time'].minute,
                                                 second=0)
                if candidate > last_program_time:
                    next_program_time = candidate
                    program_number = idx
                    break

        # If its not today, it could be tomorrow
        if next_program_time is None:
            if programs[0]['enabled'] == True:
                next_program_time = current_time + timedelta(days=1)
                next_program_time = next_program_time.replace(hour=programs[0]['start_time'].hour,
                                                              minute=programs[0]['start_time'].minute,
                                                              second=0)
                program_number = 0

        return next_program_time, program_number

    def _executeProgram(self, program_number):
        #inverter_enable =  not GPIO.input(self.config['external_ac_signal_pin'])
        #if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.HIGH)
        self.logger.info('Inverter relay ON.')
        for idx, valve_time in enumerate(self.config['programs'][program_number]['valves_times']):
            valve_pin = self.config['valves'][idx]['pin']
            GPIO.output(valve_pin, GPIO.HIGH)
            self.logger.info('Valve %s ON.' % idx)
            time.sleep(valve_time * 60)
            GPIO.output(valve_pin, GPIO.LOW)
            self.logger.info('Valve %s OFF.' % idx)
        #if inverter_enable: # If we dont have external 220V power input, then activate inverter
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW) #INVERTER always OFF after operations
        self.logger.info('Inverter relay OFF.')

    def _getLastProgramPath(self):
        file_folder = Path(__file__).parent
        return os.path.join(file_folder, 'lastprogram.yml')

    def _readLastProgramTime(self):
        last_program_path = self._getLastProgramPath()

        try:
            with open(last_program_path, 'r') as file:
                data = file.readlines()
                last_program_time = datetime.strptime(data[0][:-1], '%Y-%m-%d %H:%M:%S')
                next_program_time = datetime.strptime(data[1][:-1], '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            last_program_time = datetime.now()
            next_program_time = last_program_time
            with open(last_program_path, 'w') as file:
                time_str = last_program_time.strftime('%Y-%m-%d %H:%M:%S\n')
                file.writelines([time_str, time_str])
                self.logger.info('First Loop execution: Initializing...' )
        return last_program_time, next_program_time

    def _writeLastProgramTime(self, timelist):
        last_program_path = self._getLastProgramPath()
        with open(last_program_path, 'w') as file:
            file.writelines(timelist)

    def getLock(self):
        """
        Use file as a lock... not using DB locks because we want to maximize resiliency
        """
        if not os.path.exists('lock'):
            with open('lock', 'w'):
                return True
        else:
            modified_time = datetime.fromtimestamp(os.path.getmtime('lock'))
            if (datetime.utcnow() - modified_time) > timedelta(minutes=20):
                self.logger.warning.info('Lock expired: Last loop ended abnormally?.')
                return True
        return False

    def releaseLock(self):
        if os.path.exists('lock'):
            os.remove('lock')
        else:
            self.logger.error(f"Could not release lock.")

    @classmethod
    def isLoopingCorrectly(cls):
        file_folder = Path(__file__).parent
        tokenpath = os.path.join(file_folder, 'token')

        modTimesinceEpoc = os.path.getmtime(tokenpath)
        modificationTime = datetime.utcfromtimestamp(modTimesinceEpoc)

        return (datetime.utcnow() - modificationTime) < timedelta(minutes=10)

    @classmethod
    def forceProgram(cls, program_number):
        config = cls.getConfig()
        if program_number >= 0 and program_number < len(config['programs']):
            file_folder = Path(__file__).parent
            force_file_path = os.path.join(file_folder, 'force')
            with open(force_file_path, 'w') as force_file:
                force_file.write("{}".format(program_number))
                return True
        else:
            return False

    def loop(self):
        if self.getLock():  # To ensure a single execution
            try:
                forced = False
                # Updates "modified" time, so that we can keep track about waterflow looping
                file_folder = Path(__file__).parent
                tokenpath = os.path.join(file_folder, 'token')
                Path(tokenpath).touch()

                self._setupGPIO(self.config['valves'])

                last_program_time, old_next_program_time = self._readLastProgramTime()

                new_next_program_time, program_number = self._recalcNextProgram(last_program_time, self.config['programs'])

                force_file_path = os.path.join(file_folder, 'force')
                if os.path.exists(force_file_path):
                    with open(force_file_path, 'r') as force_file:
                        program_number = int(force_file.readline())
                        new_next_program_time = datetime.now()
                        forced = True
                    os.remove(force_file_path)

                if new_next_program_time is None:
                    if old_next_program_time != min_date:
                        self._writeLastProgramTime([last_program_time.strftime('%Y-%m-%d %H:%M:%S\n'),
                                                    min_date.strftime('%Y-%m-%d %H:%M:%S\n')])
                        self.logger.info('NO active program!')
                else:
                    if forced:
                        self.logger.info('Forced program {} executing now.'.format(program_number))
                    elif (new_next_program_time != old_next_program_time): # If "next program time" has changed, reflect in log
                        self.logger.info('Next program: %s.' % new_next_program_time.strftime('%Y-%m-%d %H:%M'))

                    current_time = datetime.now()

                    if current_time >= new_next_program_time:
                        # ------------------------------------
                        self._executeProgram(program_number)
                        # ------------------------------------
                        self._writeLastProgramTime([current_time.strftime('%Y-%m-%d %H:%M:%S\n'),
                                                   new_next_program_time.strftime('%Y-%m-%d %H:%M:%S\n')])
                    else:
                        self._writeLastProgramTime([last_program_time.strftime('%Y-%m-%d %H:%M:%S\n'),
                                                   new_next_program_time.strftime('%Y-%m-%d %H:%M:%S\n')])

            except Exception as e:
                self.logger.error(f"Exception looping: {e}")
            finally:
                GPIO.cleanup()
                self.releaseLock()


if __name__ == "__main__":
    waterflow_instance = Waterflow()
    waterflow_instance.loop()

