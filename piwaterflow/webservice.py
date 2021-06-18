from flask import Flask, request, make_response, render_template, redirect, url_for, jsonify
from flask_compress import Compress
from datetime import datetime
from .waterflow import Waterflow
import json
import copy

class PiWWWaterflowService:

    def __init__(self,  template_folder, static_folder):
        self.app = Flask(__name__,  template_folder=template_folder, static_folder=static_folder)
        self.app.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.app.add_url_rule('/service', 'service', self.service, methods=['GET', 'POST'])
        self.app.add_url_rule('/log', 'log', self.log, methods=['GET'])
        self.app.add_url_rule('/force', 'force', self.force, methods=['GET', 'POST'])
        self.app.add_url_rule('/stop', 'stop', self.stop, methods=['GET', 'POST'])
        self.app.add_url_rule('/config', 'config', self.config, methods=['GET'])
        self.app.add_url_rule('/waterflow', 'waterflow', self.waterflow, methods=['GET', 'POST'])
        Compress(self.app)
        self.waterflow = Waterflow()

    def getApp(self):
        return self.app

    def run(self):
        self.app.run()

    def index(self):
        return 'This is the Pi server.'

    def _getPublicConfig(self):
        config = self.waterflow.getConfig()
        del config['influxdbconn']
        return config

    def service(self):
        if request.method == 'GET':
            responsedict = {'dateutc': datetime.utcnow().strftime('%H:%M:%S'),
                            'log': self.waterflow.getLog(),
                            'forced': self.waterflow.getForcedInfo(),
                            'stop': self.waterflow.stopRequested(),
                            'config': self._getPublicConfig(),
                            'alive': self.waterflow.isLoopingCorrectly()
                            }
            # Change to string so that javascript can manage with it
            responsedict['config']['programs'][0]['start_time'] = responsedict['config']['programs'][0]['start_time'].strftime('%H:%M:%S')
            responsedict['config']['programs'][1]['start_time'] = responsedict['config']['programs'][1]['start_time'].strftime('%H:%M:%S')

            response = jsonify(responsedict)
            response.headers['Pragma'] = 'no-cache'
            response.headers["Expires"] = 0
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response

    # log
    def log(self):
        log_string = self.waterflow.getLog()

        response = make_response(log_string)
        response.headers["content-type"] = "text/plain"
        response.body = log_string
        return response

    def force(self):
        if request.method == 'POST':
            type_force = request.form.get('type')
            value_force = request.form.get('value')
            self.waterflow.force(type_force, int(value_force))
            return redirect(url_for('waterflow'))
        elif request.method == 'GET':
            forced_data = self.waterflow.getForcedInfo()
            return json.dumps(forced_data)

    def stop(self):
        if request.method == 'GET':
            stop_requested = self.waterflow.stopRequested()
            return "true" if stop_requested else "false"
        else:
            stop_requested = self.waterflow.stop()
            return "true" if stop_requested else "false"

    def config(self):
        if request.method == 'GET':
            parsed_config = self._getPublicConfig()
            # API should only expose non-secret parameters. Lets remove secrets
            response = make_response(parsed_config)
            response.headers["content-type"] = "text/plain"
            response.body = parsed_config
            return response

    def _changeProgram(self, program, form_time_name, form_valve_0_name, form_valve_1_name, form_enabled_name):
        #program['start_time'] = datetime.strptime(program['start_time'], '%H:%M:%S')
        time1 = datetime.strptime(request.form.get(form_time_name), '%H:%M:%S')
        new_datetime = program['start_time'].replace(hour=time1.hour, minute=time1.minute)
        #program['start_time'] = new_datetime.strftime('%H:%M:%S')
        program['start_time'] = new_datetime
        program['valves_times'][0] = int(request.form.get(form_valve_0_name))
        program['valves_times'][1] = int(request.form.get(form_valve_1_name))
        enabled1_checkbox_value = request.form.get(form_enabled_name)
        program['enabled'] = enabled1_checkbox_value is not None

    def waterflow(self):
        parsed_config = self.waterflow.getConfig()

        if request.method == 'POST':  # this block is only entered when the form is submitted
            self._changeProgram(parsed_config['programs'][0], 'time1', 'valve11', 'valve12', 'prog1enabled')
            self._changeProgram(parsed_config['programs'][1], 'time2', 'valve21', 'valve22', 'prog2enabled')

            self.waterflow.writeConfig(parsed_config)

            return redirect(url_for('waterflow'))  # Redirect so that we dont RE-POST same data again when refreshing

        return render_template('form.html')


