""" Unittesting """
import unittest
from pathlib import Path
from datetime import datetime, timezone

from piwaterflow import Waterflow


class Testing(unittest.TestCase):
    """ Unittesting class
    """
    def setUp(self):
        template_config_path = f'{Path(__file__).parent}/data/config-template_reverse.yml'
        self.waterflow = Waterflow(template_config_path=template_config_path, dry_run=True)

    def test_0000_loop(self):
        """ Test the loop
        """
        self.waterflow.loop()

    def test_0001_recalc_next_program(self):
        """ Test the recalc_next_program function
        """
        # Checks if _recalc_next_program works fine if last_program was "yesterday"
        last_program_time_utc = self.waterflow._str_to_time_utc('2023-04-26 23:30:27') # pylint: disable=protected-access
        today = self.waterflow._str_to_time_utc('2023-04-27 00:01:00') # pylint: disable=protected-access
        time_utc, program_name = self.waterflow._recalc_next_program(last_program_time_utc, today) # pylint: disable=protected-access
        self.assertTrue(time_utc == datetime(2023, 4, 27, 5, 6, tzinfo=timezone.utc))
        self.assertTrue(program_name == 'second')

        # Checks if _recalc_next_program works fine if last_program is today before first program
        last_program_time_utc = self.waterflow._str_to_time_utc('2023-04-27 00:30:00') # pylint: disable=protected-access
        time_utc, program_name = self.waterflow._recalc_next_program(last_program_time_utc, today) # pylint: disable=protected-access
        self.assertTrue(time_utc == datetime(2023, 4, 27, 5, 6, tzinfo=timezone.utc))
        self.assertTrue(program_name == 'second')

        # Checks if _recalc_next_program works fine if last_program is between two programs
        last_program_time_utc = self.waterflow._str_to_time_utc('2023-04-27 10:30:00') # pylint: disable=protected-access
        time_utc, program_name = self.waterflow._recalc_next_program(last_program_time_utc, today) # pylint: disable=protected-access
        self.assertTrue(time_utc == datetime(2023, 4, 27, 23, 30, tzinfo=timezone.utc))
        self.assertTrue(program_name == 'first')

        # Checks if _recalc_next_program works fine if last_program is after all  programs
        last_program_time_utc = self.waterflow._str_to_time_utc('2023-04-27 23:59:00') # pylint: disable=protected-access
        time_utc, program_name = self.waterflow._recalc_next_program(last_program_time_utc, today) # pylint: disable=protected-access
        self.assertTrue(time_utc == datetime(2023, 4, 28, 5, 6, tzinfo=timezone.utc))
        self.assertTrue(program_name == 'second')

if __name__ == '__main__':
    unittest.main()
