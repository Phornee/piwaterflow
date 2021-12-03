import copy
from baseutils_phornee import Config
from datetime import datetime

def _setTimezoneUTC(date):
    import pytz
    return pytz.timezone('UTC').localize(date)

class WaterflowConfig(Config):

    def _readConfig(self):
        super()._readConfig()

        # Customize values
        for program in self.config['programs']:
            progtime = datetime.strptime(program['start_time'], '%H:%M:%S')
            progtime = _setTimezoneUTC(progtime)
            program['start_time'] = progtime

        # Sort the programs by time
        self.config['programs'].sort(key=lambda prog: prog['start_time'])

    def _prepareWritting(self):
        configcopy = self.getDictCopy()
        # Convert the date back from datetime to string
        for program in configcopy['programs']:
            program['start_time'] = program['start_time'].strftime('%H:%M:%S')

        return configcopy

