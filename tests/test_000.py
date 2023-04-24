import unittest
import os
import sys
import inspect
from pathlib import Path

from piwaterflow import Waterflow


class Testing(unittest.TestCase):

    def test_loop(self):
        template_config_path = '{}/data/config-template.yml'.format(Path(__file__).parent)
        waterflow_instance = Waterflow(template_config_path=template_config_path)
        waterflow_instance.loop()


if __name__ == '__main__':
    unittest.main()
