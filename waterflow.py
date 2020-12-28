import RPi.GPIO as GPIO
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from ManagedClass.ManagedClass import ManagedClass

class Waterflow(ManagedClass):

    def __init__(self):
        super().__init__(classname='waterflow', execpath=__file__)

    def readConfig(self):
        super().readConfig()

        # Convert the date from string to datetime object
        for program in self.config['programs']:
            program['start_time'] = datetime.strptime(program['start_time'], '%H:%M:%S')

        # Sort the programs by time
        self.config['programs'].sort(key=lambda prog: prog['start_time'])

    def setupGPIO(self, valves):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.config['inverter_relay_pin'], GPIO.OUT)
        GPIO.output(self.config['inverter_relay_pin'], GPIO.LOW)
        GPIO.setup(self.config['external_ac_signal_pin'], GPIO.IN)
        for valve in valves:
            GPIO.setup(valve['pin'], GPIO.OUT)
            GPIO.output(valve['pin'], GPIO.LOW)
            pass


    def recalcNextProgram(self, current_time, programs):
        next_program_time = None
        program_number = -1

        # Find if next program is today
        for idx, program in enumerate(programs):
            if program['enabled'] == True:
                candidate = current_time.replace(hour=program['start_time'].hour,
                                                 minute=program['start_time'].minute,
                                                 second=0)
                if candidate > current_time:
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

    def executeProgram(self, program_number):
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

    def readLastProgramTime(self):
        file_folder = Path(__file__).parent
        last_program_path = os.path.join(file_folder, 'lastprogram.yml')

        try:
            with open(last_program_path, 'r') as file:
                data = file.readlines()
                last_program_time = datetime.strptime(data[0][:-1], '%Y-%m-%d %H:%M:%S.%f')
                next_program_time = datetime.strptime(data[1][:-1], '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            last_program_time = datetime.now()
            next_program_time = last_program_time
            with open(last_program_path, 'w') as file:
                time_str = last_program_time.strftime('%Y-%m-%d %H:%M:%S.%f\n')
                file.writelines([time_str, time_str])
                self.logger.info('First Loop execution: Initializing...' )
        return last_program_time, next_program_time


    def writeLastProgramTime(self, timelist):
        file_folder = Path(__file__).parent
        last_program_path = os.path.join(file_folder, 'lastprogram.yml')
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
                self.warning.info('Lock expired: Last loop ended abnormally?.')
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
        token = os.path.join(file_folder, 'token')

        modTimesinceEpoc = os.path.getmtime(token)
        modificationTime = datetime.utcfromtimestamp(modTimesinceEpoc)

        return (datetime.utcnow() - modificationTime) < timedelta(minutes=10)

    def loop(self):
        if self.getLock():  # To ensure a single execution
            try:
                # Updates "modified" time, so that we can keep track about waterflow looping
                with open('token', 'w'):
                    pass

                self.setupGPIO(self.config['valves'])

                last_program_time, old_next_program_time = self.readLastProgramTime()

                new_next_program_time, program_number = self.recalcNextProgram(last_program_time, self.config['programs'])

                if new_next_program_time is None:
                    self.logger.info('NO active program!')
                else:
                    if (new_next_program_time != old_next_program_time): # If "next program time" has changed, reflect in log
                        self.logger.info('Next program: %s.' % new_next_program_time.strftime('%Y-%m-%d %H:%M:%S'))

                    current_time = datetime.now()

                    if current_time >= new_next_program_time:
                        # ------------------------------------
                        self.executeProgram(program_number)
                        # ------------------------------------
                        self.writeLastProgramTime([current_time.strftime('%Y-%m-%d %H:%M:%S.%f\n'),
                                                   new_next_program_time.strftime('%Y-%m-%d %H:%M:%S.%f\n')])
                    else:
                        self.writeLastProgramTime([last_program_time.strftime('%Y-%m-%d %H:%M:%S.%f\n'),
                                                   new_next_program_time.strftime('%Y-%m-%d %H:%M:%S.%f\n')])

            except Exception as e:
                self.logger.error(f"Exception looping: {e}")
            finally:
                GPIO.cleanup()
                self.releaseLock()


if __name__ == "__main__":
    waterflow_instance = Waterflow()
    waterflow_instance.loop()
