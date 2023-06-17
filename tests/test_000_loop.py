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

    def test_0000_loop_noprog(self):
        """ Test the loop and main high-level functionalities. No program will run at that time
        """
        self.waterflow.loop(Waterflow.str_to_time('2023-05-27 08:30:00'))

        events = self.waterflow._read_events() # pylint: disable=protected-access
        if events:
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0][1] == "LastProg" and events[0][2] == "2023-05-27 09:51:00")
        else:
            self.fail("not the right events generated.")

    def test_0001_loop_prog(self):
        """ Test the loop and main high-level functionalities. Program will run at that time
        """
        self.waterflow._write_last_program_time(Waterflow.str_to_time('2023-05-26 23:59:00')) # pylint: disable=protected-access
        self.waterflow.loop(Waterflow.str_to_time('2023-05-27 09:52:00'))

        events = self.waterflow._read_events() # pylint: disable=protected-access
        if events:
            self.assertEqual(len(events), 8)
            self.assertTrue(events[0][1] == "ExecProg" and events[0][2] == "first")
            self.assertTrue(events[1][1] == "InverterON" and events[1][2] is None)
            self.assertTrue(events[2][1] == "ValveON" and events[2][2] == "main")
            self.assertTrue(events[3][1] == "ValveOFF" and events[3][2] == "main")
            self.assertTrue(events[4][1] == "ValveON" and events[4][2] == "grass")
            self.assertTrue(events[5][1] == "ValveOFF" and events[5][2] == "grass")
            self.assertTrue(events[6][1] == "InverterOFF" and events[6][2] is None)
            self.assertTrue(events[7][1] == "LastProg" and events[7][2] == "2023-05-27 19:04:00")
        else:
            self.fail("not the right events generated.")

    def test_0002_loop_prog_forced(self):
        """ Test the loop and main high-level functionalities. Program will run at that time
        """
        self.waterflow._write_last_program_time(Waterflow.str_to_time('2023-05-26 23:59:00')) # pylint: disable=protected-access
        self.waterflow.force('program', 'first')
        self.waterflow.loop(Waterflow.str_to_time('2023-05-27 09:52:00'))

        events = self.waterflow._read_events() # pylint: disable=protected-access
        if events:
            self.assertEqual(len(events), 9)
            self.assertTrue(events[0][1] == "ForcedProg" and events[0][2] == "first")
            self.assertTrue(events[1][1] == "ExecProg" and events[1][2] == "first")
            self.assertTrue(events[2][1] == "InverterON" and events[2][2] is None)
            self.assertTrue(events[3][1] == "ValveON" and events[3][2] == "main")
            self.assertTrue(events[4][1] == "ValveOFF" and events[4][2] == "main")
            self.assertTrue(events[5][1] == "ValveON" and events[5][2] == "grass")
            self.assertTrue(events[6][1] == "ValveOFF" and events[6][2] == "grass")
            self.assertTrue(events[7][1] == "InverterOFF" and events[7][2] is None)
            self.assertTrue(events[8][1] == "LastProg" and events[8][2] == "2023-05-27 19:04:00")
        else:
            self.fail("not the right events generated.")

    def test_0003_loop_valve_forced(self):
        """ Test the loop and main high-level functionalities. Program will run at that time
        """
        self.waterflow._write_last_program_time(Waterflow.str_to_time('2023-05-26 23:59:00')) # pylint: disable=protected-access
        self.waterflow.force('valve', 'grass')
        self.waterflow.loop(Waterflow.str_to_time('2023-05-27 09:52:00'))

        events = self.waterflow._read_events() # pylint: disable=protected-access
        if events:
            self.assertEqual(len(events), 7)
            self.assertTrue(events[0][1] == "ForcedValve" and events[0][2] == "grass")
            self.assertTrue(events[1][1] == "ExecValve" and events[1][2] == "grass")
            self.assertTrue(events[2][1] == "InverterON" and events[2][2] is None)
            self.assertTrue(events[3][1] == "ValveON" and events[3][2] == "grass")
            self.assertTrue(events[4][1] == "ValveOFF" and events[4][2] == "grass")
            self.assertTrue(events[5][1] == "InverterOFF" and events[5][2] is None)
            self.assertTrue(events[6][1] == "LastProg" and events[6][2] == "2023-05-27 19:04:00")
        else:
            self.fail("not the right events generated.")

if __name__ == '__main__':
    unittest.main()

