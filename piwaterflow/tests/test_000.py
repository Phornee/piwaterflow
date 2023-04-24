import unittest
import os
import sys
import inspect
from pathlib import Path

THIS_FOLDER = os.path.dirname(inspect.getfile(inspect.currentframe()))
sys.path.insert(0, os.path.dirname(THIS_FOLDER))
from waterflow import Waterflow  #noqa 


class Testing(unittest.TestCase):
    # templates_path = "{}/templates".format(Path().absolute())
    # static_path = "{}/static".format(Path().absolute())
    # service = HomeServices(template_folder=templates_path, static_folder=static_path, db_connector='mock')
    # client = service.getApp().test_client()

    def test_influx_down(self):
        pass
        # self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
