""" _main_ To be properly executed from crontab --> python -m piwaterflow """
from .waterflow import Waterflow

waterflow_instance = Waterflow()
waterflow_instance.loop()
