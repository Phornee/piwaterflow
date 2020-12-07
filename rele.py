#import RPi.GPIO as GPIO
import time 
import datetime
import logging

# Pins definition for the RELAYS
INVERTER_RELAY_PIN = 1
EXTERNAL_AC_SIGNAL_PIN = 10

valves_pins = [2, 3]

programs = [
            {'start_time': datetime.datetime.strptime('10:51:00', '%H:%M:%S'), 'valves_times': [1, 2]},
            {'start_time': datetime.datetime.strptime('11:33:00', '%H:%M:%S'), 'valves_times': [3, 4]}
           ]

logger = logging.getLogger('Waterflow_Log')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('waterflow.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

def setupGPIO():
    # GPIO.setmode(GPIO.BCM)

    # GPIO.setup(INVERTER_RELAY_PIN, GPIO.OUT)
    # GPIO.setup(EXTERNAL_AC_SIGNAL_PIN, GPIO.IN)
    for valve in valves_pins:
        #GPIO.setup(valve, GPIO.OUT)
        pass


def recalcNextProgram(current_time):
    next_program_time = None
    program_number = -1

    # Find if next program is today
    for idx, program in enumerate(programs):
        candidate = current_time.replace(hour=program['start_time'].hour, minute=program['start_time'].minute)
        if candidate > current_time:
            next_program_time = candidate
            program_number = idx
            break

    # If its not today, it will be tomorrow
    if next_program_time is None:
        next_program_time = current_time + datetime.timedelta(days=1)
        next_program_time = next_program_time.replace(hour=programs[0]['start_time'].hour, minute=programs[0]['start_time'].minute)
        program_number = 0

    return next_program_time, program_number

def executeProgram(program_number):

    #if not GPIO.input(EXTERNAL_AC_SIGNAL_PIN): # If we dont have external 220V power input, then activate inverter
    #   GPIO.output(INVERTER_RELAY_PIN, GPIO.HIGH)
    logger.info('Inverter relay ON.')
    for idx, valve_time in enumerate(programs[0]['valves_times']):
        valve_pin = valves_pins[idx]
        #GPIO.output(valve_pin, GPIO.HIGH)
        logger.info('Valve %s ON.' % idx)
        time.sleep(valve_time * 60)
        #GPIO.output(valve_pin, GPIO.LOW)
        logger.info('Valve %s OFF.' % idx)
    #GPIO.output(INVERTER_RELAY_PIN, GPIO.LOW) #INVERTER always OFF after operations
    logger.info('Inverter relay OFF.')

def main():
    logger.info('Irrigation system started.')

    setupGPIO()

    current_time = datetime.datetime.now()

    next_program_time, program_number = recalcNextProgram(current_time)

    while True:
        current_time = datetime.datetime.now()

        if current_time > next_program_time:
            executeProgram(program_number)
            next_program_time, program_number = recalcNextProgram(current_time)

        time.sleep(30)


if __name__ == "__main__":
    main()