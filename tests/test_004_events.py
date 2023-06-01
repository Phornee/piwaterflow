""" Unittesting """
import unittest
from pathlib import Path
import gc

from piwaterflow import Waterflow


class Testing(unittest.TestCase):
    """ Unittesting class
    """
    def setUp(self):
        template_config_path = f'{Path(__file__).parent}/data/config-template.yml'
        self.waterflow = Waterflow(template_config_path=template_config_path, dry_run=True)

    def tearDown(self):
        del self.waterflow
        gc.collect()

    def test_0000_read_write_events(self):
        """ Test the loop and main high-level functionalities. No program will run at that time
        """
        self.waterflow._add_event('LastProg', '2023-05-27 09:51:00') # pylint: disable=protected-access

        events = self.waterflow._read_events() # pylint: disable=protected-access
        if events:
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0][1] == "LastProg" and events[0][2] == "2023-05-27 09:51:00")
        else:
            self.fail("not the right events generated.")

if __name__ == '__main__':
    unittest.main()

