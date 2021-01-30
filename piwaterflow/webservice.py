from flask import Flask, request, make_response, render_template, redirect, url_for
from datetime import datetime
from .waterflow import Waterflow

class PiWWWaterflowService:

    def __init__(self,  template_folder):
        self.app = Flask(__name__,  template_folder=template_folder)
        self.app.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.app.add_url_rule('/service', 'service', self.service, methods=['GET', 'POST'])
        self.app.add_url_rule('/log', 'log', self.log, methods=['GET'])
        self.app.add_url_rule('/force_program', 'force_program', self.force_program, methods=['POST'])
        self.app.add_url_rule('/config', 'config', self.config, methods=['GET'])
        self.app.add_url_rule('/waterflow', 'waterflow', self.waterflow, methods=['GET', 'POST'])

    def run(self):
        self.app.run()

    # mainpage
    def index(self):
        return 'This is the Pi server.'

    def service(self):
        process_running = Waterflow.isLoopingCorrectly()
        if request.method == 'GET':
             return "true" if process_running else "false"

    # log
    def log(self):
        log_string = Waterflow.getLog()

        response = make_response(log_string)
        response.headers["content-type"] = "text/plain"
        response.boy = log_string
        return response

    def force_program(self):
        Waterflow.forceProgram(int(request.data))

        return redirect(url_for('waterflow'))

    def config(self):
        if request.method == 'GET':
            parsed_config = Waterflow.getConfig()
            response = make_response(parsed_config)
            response.headers["content-type"] = "text/plain"
            response.body = parsed_config
            return response

    def waterflow(self):
        parsed_config = Waterflow.getConfig()

        if request.method == 'POST':  # this block is only entered when the form is submitted
            parsed_config['programs'][0]['start_time'] = datetime.strptime(parsed_config['programs'][0]['start_time'],
                                                                             '%H:%M:%S')
            time1 = datetime.strptime(request.form.get('time1'), '%H:%M')
            new_datetime = parsed_config['programs'][0]['start_time'].replace(hour=time1.hour, minute=time1.minute)
            parsed_config['programs'][0]['start_time'] = new_datetime.strftime('%H:%M:%S')
            parsed_config['programs'][0]['valves_times'][0] = int(request.form.get('valve11'))
            parsed_config['programs'][0]['valves_times'][1] = int(request.form.get('valve12'))
            enabled1_checkbox_value = request.form.get('prog1enabled')
            parsed_config['programs'][0]['enabled'] = enabled1_checkbox_value is not None

            parsed_config['programs'][1]['start_time'] = datetime.strptime(parsed_config['programs'][1]['start_time'],
                                                                             '%H:%M:%S')
            time2 = datetime.strptime(request.form.get('time2'), '%H:%M')
            new_datetime = parsed_config['programs'][1]['start_time'].replace(hour=time2.hour, minute=time2.minute)
            parsed_config['programs'][1]['start_time'] = new_datetime.strftime('%H:%M:%S')
            parsed_config['programs'][1]['valves_times'][0] = int(request.form.get('valve21'))
            parsed_config['programs'][1]['valves_times'][1] = int(request.form.get('valve22'))
            enabled2_checkbox_value = request.form.get('prog2enabled')
            parsed_config['programs'][1]['enabled'] = enabled2_checkbox_value is not None

            Waterflow.setConfig(parsed_config)

            return redirect(url_for('waterflow'))  # Redirect so that we dont RE-POST same data again when refreshing

        for program in parsed_config['programs']:
            program['start_time'] = datetime.strptime(program['start_time'], '%H:%M:%S')

        # Sort the programs by time
        parsed_config['programs'].sort(key=lambda prog: prog['start_time'])

        return render_template('form.html'
                               , time1=("{:02}:{:02}".format(parsed_config['programs'][0]['start_time'].hour,
                                                             parsed_config['programs'][0]['start_time'].minute))
                               , valve11=parsed_config['programs'][0]['valves_times'][0]
                               , valve12=parsed_config['programs'][0]['valves_times'][1]
                               , enabled1=parsed_config['programs'][0]['enabled']
                               , time2=("{:02}:{:02}".format(parsed_config['programs'][1]['start_time'].hour,
                                                             parsed_config['programs'][1]['start_time'].minute))
                               , valve21=parsed_config['programs'][1]['valves_times'][0]
                               , valve22=parsed_config['programs'][1]['valves_times'][1]
                               , enabled2=parsed_config['programs'][1]['enabled']
                               )


