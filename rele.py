import RPi.GPIO as GPIO
import os
import time
import datetime
import logging
import yaml
from pathlib import Path
from shutil import copyfile

# Pins definition for the RELAYS
INVERTER_RELAY_PIN = 31
EXTERNAL_AC_SIGNAL_PIN = 10

logger = logging.getLogger('Waterflow_Log')

def setupLogger(logfile):
    file_folder = Path(__file__).parent
    log_path = os.path.join(file_folder, logfile)

    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def setupGPIO(valves):
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)

    GPIO.setup(INVERTER_RELAY_PIN, GPIO.OUT)
    GPIO.output(INVERTER_RELAY_PIN, GPIO.LOW)
    GPIO.setup(EXTERNAL_AC_SIGNAL_PIN, GPIO.IN)
    for valve in valves:
        GPIO.setup(valve['pin'], GPIO.OUT)
        GPIO.output(valve['pin'], GPIO.LOW)
        pass


def recalcNextProgram(current_time, programs):
    next_program_time = None
    program_number = -1

    # Find if next program is today
    for idx, program in enumerate(programs):
        candidate = current_time.replace(hour=program['start_time'].hour,
                                         minute=program['start_time'].minute,
                                         second=0)
        if candidate > current_time:
            next_program_time = candidate
            program_number = idx
            break

    # If its not today, it will be tomorrow
    if next_program_time is None:
        next_program_time = current_time + datetime.timedelta(days=1)
        next_program_time = next_program_time.replace(hour=programs[0]['start_time'].hour,
                                                      minute=programs[0]['start_time'].minute,
                                                      second=0)
        program_number = 0

    return next_program_time, program_number

def executeProgram(program_number, config):

    #if not GPIO.input(EXTERNAL_AC_SIGNAL_PIN): # If we dont have external 220V power input, then activate inverter
    GPIO.output(INVERTER_RELAY_PIN, GPIO.HIGH)
    logger.info('Inverter relay ON.')
    for idx, valve_time in enumerate(config['programs'][program_number]['valves_times']):
        valve_pin = config['valves'][idx]['pin']
        GPIO.output(valve_pin, GPIO.HIGH)
        logger.info('Valve %s ON.' % idx)
        time.sleep(valve_time * 60)
        GPIO.output(valve_pin, GPIO.LOW)
        logger.info('Valve %s OFF.' % idx)
    GPIO.output(INVERTER_RELAY_PIN, GPIO.LOW) #INVERTER always OFF after operations
    logger.info('Inverter relay OFF.')

def loop(config):
    file_folder = Path(__file__).parent    
    last_program_path = os.path.join(file_folder, config['lastprogrampath'])

    try:
        with open(last_program_path, 'r') as file:
            data = file.read()
            last_program_time = datetime.datetime.strptime(data, '%Y-%m-%d %H:%M:%S.%f')
    except Exception as e:
        last_program_time = datetime.datetime.now()
        with open(last_program_path, 'w') as file:
            file.write(last_program_time.strftime('%Y-%m-%d %H:%M:%S.%f'))
            logger.info('First Loop execution: Initializing "Last program" to %s.' % last_program_time.strftime(
                        '%Y-%m-%d %H:%M:%S.%f'))

    next_program_time, program_number = recalcNextProgram(last_program_time, config['programs'])
    logger.info('Next program start at %s.' % next_program_time.strftime('%Y-%m-%d %H:%M:%S.%f'))

    current_time = datetime.datetime.now()

    if current_time >= next_program_time:
        executeProgram(program_number, config)
        with open(last_program_path, 'w') as file:
            file.write(current_time.strftime('%Y-%m-%d %H:%M:%S.%f'))

def readConfig():
    file_folder = Path(__file__).parent
    config_yml_path = os.path.join(file_folder, 'config.yml')

    # If config file doesn't exist yet, create it from the template
    if not os.path.isfile(config_yml_path):
        config_template_yml_path = os.path.join(file_folder, 'config-template.yml')
        copyfile(config_template_yml_path, config_yml_path)

    with open(config_yml_path, 'r') as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)

        # Convert the date from string to datetime object
        for program in config['programs']:
            program['start_time'] = datetime.datetime.strptime(program['start_time'], '%H:%M:%S')

        # Sort the programs by time
        config['programs'].sort(key=lambda prog: prog['start_time'])
        return config

def main():
    config = readConfig()

    setupLogger(config['logpath'])

    logger.info('Irrigation system started.')
    try:
        setupGPIO(config['valves'])

        while True:
            logger.info('Looping...')

            config = readConfig()
            loop(config)
            time.sleep(config['loop_freq'] * 60)

            if os.path.isfile("stop"):
                os.remove("stop")
                logger.info('Exiting loop by explicit request...')
                break

    except KeyboardInterrupt:
        logger.info('Exiting gently...')
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    import sys

    if sys.platform.startswith("win"):
        main()
    elif sys.platform.startswith("linux"):
        import daemon

        with daemon.DaemonContext():
            main()

