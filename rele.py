#import RPi.GPIO as GPIO
import time 
import datetime

# Pins definition for the RELAYS
INVERTER_RELAY_PIN = 1

valves_pins = [2, 3]

programs = [
            {'start_time': datetime.datetime.strptime('09:00:00', '%H:%M:%S'), 'valves_times': [1, 2]},
            {'start_time': datetime.datetime.strptime('15:00:00', '%H:%M:%S'), 'valves_times': [3, 4]}
           ]

def setupGPIO():
    # GPIO.setmode(GPIO.BCM)

    # GPIO.setup(INVERTER_RELAY_PIN, GPIO.OUT)
    for valve in valves_pins:
        #GPIO.setup(valve, GPIO.OUT)
        pass


def recalcNextProgram(current_time):
    next_program_time = None
    program_number = -1

    # Find if next program is today
    for idx, program in enumerate(programs):
         if program['start_time'].hour > current_time.hour and program['start_time'].minute > current_time.minutes:
            next_program_time = current_time
            next_program_time.hour = program['start_time'].hour
            next_program_time.minutes = program['start_time'].minute
            program_number = idx
            break

    # If its not today, it will be tomorrow
    if next_program_time is None:
        next_program_time = current_time + datetime.timedelta(days=1)
        next_program_time = next_program_time.replace(hour=programs[0]['start_time'].hour, minute=programs[0]['start_time'].minute)
        program_number = 0

    return next_program_time, program_number

def executeProgram(program_number):
    #GPIO.output(INVERTER_RELAY_PIN, GPIO.HIGH)
    for idx, valve_time in enumerate(programs[0]['valves_times']):
        valve_pin = valves_pins[idx]
        #GPIO.output(valve_pin, GPIO.HIGH)
        time.sleep(valve_time * 60)
        #GPIO.output(valve_pin, GPIO.LOW)
    #GPIO.output(INVERTER_RELAY_PIN, GPIO.LOW)

def main():

    setupGPIO()

    current_time = datetime.datetime.utcnow()

    next_program_time, program_number = recalcNextProgram(current_time)

    while True:
        current_time = datetime.datetime.utcnow()

        if current_time > next_program_time:
            executeProgram(program_number)
            next_program_time, program_number = recalcNextProgram(current_time)

        time.sleep(60)


if __name__ == "__main__":
    main()