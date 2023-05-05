""" Unittesting """
import unittest
from pathlib import Path

from piwaterflow import Waterflow


class Testing(unittest.TestCase):
    """ Unittesting class
    """
    def setUp(self):
        template_config_path = f'{Path(__file__).parent}/data/config-template.yml'
        self.waterflow = Waterflow(template_config_path=template_config_path, dry_run=True)

    def test_0000_loop(self):
        """ Test the loop and main high-level functionalities
        """
        self.waterflow.loop()

if __name__ == '__main__':
    unittest.main()
