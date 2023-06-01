""" Unittesting """
import os
import time
import unittest
from pathlib import Path

from piwaterflow import Waterflow


class Testing(unittest.TestCase):
    """ Unittesting class
    """
    def setUp(self):
        template_config_path = f'{Path(__file__).parent}/data/config-template.yml'
        self.waterflow = Waterflow(template_config_path=template_config_path, dry_run=True)

    def test_0030_loop(self):
        """ Test the loop and main high-level functionalities
        """
        first_lock = self.waterflow.get_lock()
        self.assertTrue(first_lock)

        second_lock = self.waterflow.get_lock()
        self.assertFalse(second_lock)

        # Simulate lock expiring
        lock_path = self.waterflow._get_homevar_path('lock') # pylint: disable=protected-access
        past_epoch = time.time() - 1260
        os.utime(lock_path, (past_epoch, past_epoch) ) # 21 minutes before to simulate expiring
        third_lock = self.waterflow.get_lock()
        self.assertTrue(third_lock)


if __name__ == '__main__':
    unittest.main()
