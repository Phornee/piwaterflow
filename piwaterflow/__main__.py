""" _main_ To be properly executed from crontab --> python -m piwaterflow """
from log_mgr import Logger
from .waterflow import Waterflow

logger = Logger('piwaterflow', log_file_name='piwaterflow')

waterflow_instance = Waterflow()
waterflow_instance.loop()
