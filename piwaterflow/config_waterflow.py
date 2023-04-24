""" Config override for piwaterflow """
from datetime import datetime
import pytz

from config_yml import Config

def _set_timezone_utc(date: datetime):
    return pytz.timezone('UTC').localize(date)


class WaterflowConfig(Config):
    """Config override for piwaterflow
    """
    def _read_config(self):
        super()._read_config()

        # Customize values
        for program in self.config['programs']:
            progtime = datetime.strptime(program['start_time'], '%H:%M:%S')
            progtime = _set_timezone_utc(progtime)
            program['start_time'] = progtime

        # Sort the programs by time
        self.config['programs'].sort(key=lambda prog: prog['start_time'])

    def _prepare_writting(self):
        """ Transforms the data before being written to the config file
        Returns:
            dict: Transformed config dictionary
        """
        configcopy = self.get_dict_copy()
        # Convert the date back from datetime to string
        for program in configcopy['programs']:
            program['start_time'] = program['start_time'].strftime('%H:%M:%S')

        return configcopy
