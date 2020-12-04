import RPi.GPIO as io
import time 

io.setmode(io.BCM)
io.setup(7,io.OUT)
io.output(7, 0)
time.sleep(5)
io.output(7,1)

