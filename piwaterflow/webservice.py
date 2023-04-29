from datetime import datetime

from flask import Flask, request, render_template, redirect, url_for
from flask_compress import Compress
from flask_socketio import SocketIO

from .waterflow import Waterflow

from importlib_metadata import version


class PiWWWaterflowService:

    def __init__(self,  template_folder, static_folder):
        self.waterflow = Waterflow()

        self.app = Flask(__name__,  template_folder=template_folder, static_folder=static_folder)
        self.app.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.app.add_url_rule('/waterflow', 'waterflow', self.waterflow_endpoint, methods=['GET'])
        Compress(self.app)
        self.socketio = SocketIO(self.app)
        self.socketio.on_event('service_request', self.on_service_request)
        self.socketio.on_event('force', self.on_force)
        self.socketio.on_event('stop', self.on_stop)
        self.socketio.on_event('save', self.on_save)

    def getApp(self):
        return self.app

    def getSocket(self):
        return self.socketio

    def run(self):
        # self.app.run()
        self.socketio.run(self.app)

    def index(self):
        return 'This is the Pi server.'

    def _get_public_config(self):
        config = self.waterflow.config.get_dict_copy()
        del config['influxdbconn']
        return config

    def on_service_request(self, data):
        print('Service requested...')
        service_dict = self._get_service()
        if 'first_time' in data:
            service_dict['first_time'] = data['first_time']
        self.socketio.emit('service', service_dict)

    def _get_service(self):
        try:
            ver = version('piwaterflow')
        except Exception:
            ver = '?.?.?'

        responsedict = {'log': self.waterflow.getLog(),
                        'forced': self.waterflow.getForcedInfo(),
                        'stop': self.waterflow.stopRequested(),
                        'config': self._getPublicConfig(),
                        'lastlooptime': self.waterflow.getLastLoopTime().strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        'version': ver
                        }
        # Change to string so that javascript can manage with it
        responsedict['config']['programs'][0]['start_time'] = responsedict['config']['programs'][0]['start_time'].strftime('%H:%M')
        responsedict['config']['programs'][1]['start_time'] = responsedict['config']['programs'][1]['start_time'].strftime('%H:%M')
        return responsedict

    def on_force(self, data):
        print(f'Force requested... {data}')
        type_force = data['type']
        value_force = data['value']
        self.waterflow.force(type_force, int(value_force))

    def on_stop(self, data):
        print('Stop requested...')
        self.waterflow.stop()

    def _changeProgram(self, program, new_program):
        inputbox_text = new_program['time']
        time1 = datetime.strptime(inputbox_text, '%H:%M')
        new_datetime = program['start_time'].replace(hour=time1.hour, minute=time1.minute)
        program['start_time'] = new_datetime
        program['valves_times'][0] = new_program['valve1']
        program['valves_times'][1] = new_program['valve2']
        program['enabled'] = new_program['enabled'] is not None

    def waterflow_endpoint(self):
        return render_template('form.html')

    def on_save(self, data):
        parsed_config = self.waterflow.config.getDictCopy()
        self._changeProgram(parsed_config['programs'][0], data['prog1'])
        self._changeProgram(parsed_config['programs'][1], data['prog2'])

        self.waterflow.updateConfig(programs=parsed_config['programs'])
