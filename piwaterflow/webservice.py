from flask import Flask, request, make_response, render_template, redirect, url_for
import datetime
from .waterflow import Waterflow

app = Flask(__name__)

def findWaterflowProcess():
    import psutil
    found = False
    for i in psutil.process_iter():
        try:
            cmdline = i.cmdline()
            if cmdline[0].find('python') != -1:
                for cmd in cmdline:
                    if cmd.find('rele.py') != -1:
                        found = True
                        break
                if found:
                    break
        except Exception as e:
            pass
    return found

@app.route('/service', methods=['GET', 'POST'])  # allow both GET and POST requests
def service():
    process_running = Waterflow.isLoopingCorrectly()
    if request.method == 'GET':
         return "true" if process_running else "false"

    # process_running = findWaterflowProcess()
    # if request.method == 'GET':
    #     return "true" if process_running else "false"
    # elif request.method == 'POST':
    #     activate = request.form.get('activate') == 'true'
    #     if activate:
    #         if not process_running:
    #             from subprocess import Popen, PIPE, DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP
    #             p = Popen(['python', '../PiWaterflow/rele.py'], stdin=PIPE, stdout=PIPE, stderr=PIPE, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
    #     else:
    #         if process_running:
    #             with open("../PiWaterflow/stop", "w"):  # create marker file so that loop ends smootly
    #                 pass
    #
    #     return redirect(url_for('waterflow'))  # Redirect so that we dont RE-POST same data again when refreshing

# mainpage
@app.route('/')
def index():
    return 'This is the Pi server.'


# log
@app.route('/log', methods=['GET'])
def log():
    log_string = Waterflow.getLog()

    response = make_response(log_string)
    response.headers["content-type"] = "text/plain"
    response.boy = log_string
    return response

@app.route('/force', methods=['POST'])
def force_program():
    Waterflow.forceProgram(int(request.data))

    return redirect(url_for('waterflow'))


@app.route('/config', methods=['GET'])
def config():
    if request.method == 'GET':
        parsed_config = Waterflow.getConfig()
        response = make_response(parsed_config)
        response.headers["content-type"] = "text/plain"
        response.body = parsed_config
        return response


@app.route('/waterflow', methods=['GET', 'POST'])  # allow both GET and POST requests
def waterflow():
    parsed_config = Waterflow.getConfig()

    if request.method == 'POST':  # this block is only entered when the form is submitted
        parsed_config['programs'][0]['start_time'] = datetime.datetime.strptime(parsed_config['programs'][0]['start_time'],
                                                                         '%H:%M:%S')
        time1 = datetime.datetime.strptime(request.form.get('time1'), '%H:%M')
        new_datetime = parsed_config['programs'][0]['start_time'].replace(hour=time1.hour, minute=time1.minute)
        parsed_config['programs'][0]['start_time'] = new_datetime.strftime('%H:%M:%S')
        parsed_config['programs'][0]['valves_times'][0] = int(request.form.get('valve11'))
        parsed_config['programs'][0]['valves_times'][1] = int(request.form.get('valve12'))
        enabled1_checkbox_value = request.form.get('prog1enabled')
        parsed_config['programs'][0]['enabled'] = enabled1_checkbox_value is not None

        parsed_config['programs'][1]['start_time'] = datetime.datetime.strptime(parsed_config['programs'][1]['start_time'],
                                                                         '%H:%M:%S')
        time2 = datetime.datetime.strptime(request.form.get('time2'), '%H:%M')
        new_datetime = parsed_config['programs'][1]['start_time'].replace(hour=time2.hour, minute=time2.minute)
        parsed_config['programs'][1]['start_time'] = new_datetime.strftime('%H:%M:%S')
        parsed_config['programs'][1]['valves_times'][0] = int(request.form.get('valve21'))
        parsed_config['programs'][1]['valves_times'][1] = int(request.form.get('valve22'))
        enabled2_checkbox_value = request.form.get('prog2enabled')
        parsed_config['programs'][1]['enabled'] = enabled2_checkbox_value is not None

        Waterflow.setConfig(parsed_config)

        return redirect(url_for('waterflow'))  # Redirect so that we dont RE-POST same data again when refreshing

    for program in parsed_config['programs']:
        program['start_time'] = datetime.datetime.strptime(program['start_time'], '%H:%M:%S')

    # Sort the programs by time
    parsed_config['programs'].sort(key=lambda prog: prog['start_time'])

    found = findWaterflowProcess()

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
                           , looprunning=found
                           )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

