from datetime import datetime
import json
import os
from subprocess import Popen, PIPE

from flask import Flask, request
from flask_json import FlaskJSON, JsonError, json_response

from settings_local import AMIXER_CARD

app = Flask(__name__)
FlaskJSON(app)

app.config['JSON_ADD_STATUS'] = False
app.config['JSON_DATETIME_FORMAT'] = '%d/%m/%Y %H:%M:%S'

def send_cmdline_command(daemon, command, args=None, delimiter='\n  ', perm=False):
    command = [daemon, command]

    if args is not None:
        for arg in args:
            command.append(arg)

    if perm:
        command.insert(0, 'sudo')

    proc = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    output = stdout.decode('utf-8').split(delimiter)
    return output

def send_amixer_command(command, value=None):
    daemon = 'amixer'
    args = [AMIXER_CARD]
    if value:
        args.append(value)

    result = send_cmdline_command(daemon, command, args)
    return result

def send_systemctl_plexamp(command):
    daemon = 'systemctl'
    args = ['plexamp']
    additional_perm = True

    result = send_cmdline_command(daemon, command, args, '\n   ', additional_perm)
    return result

def is_stereo_card(data):
    playback_channels = data[2].split(': ')
    return False if playback_channels[1] == 'Mono' else True

def request_amixer_volume(output_splitted=False):
    answer = send_amixer_command('sget')

    card_stereo = is_stereo_card(answer)

    channel_values = {}
    channels_synced = None
    if card_stereo:
        # getting value for each channel
        channel_list = [answer[-2], answer[-1]]
    else:
        channel_list = [answer[-1]]

    for channel in channel_list:
        attrs = channel.split(' ')

        name = attrs[0]
        if card_stereo:
            name +=  attrs[1][:-1]
            value = attrs[-2][1:-1]
        else:
            name = name[:-1]
            value = attrs[-3][1:-1]

        enabled = attrs[-1]
        if '\n' in enabled:
             enabled = enabled.replace('\n', '')
        enabled = enabled[1:-1]

        channel_values[name] = {'volume': value, 'enabled': enabled}

    card_state = {
        'stereo': card_stereo,
        'channels': channel_values
    }

    card_values_inversed = {str(value): key for key, value in channel_values.items()}
    channels_synced = False if len(card_values_inversed.keys()) != 1 else True

    if not output_splitted and card_stereo and channels_synced:
        merged_value = eval(list(card_values_inversed.keys())[0])
        card_state['channels'] = merged_value

    if card_stereo:
        card_state['channels_synced'] = channels_synced

    return card_state

def request_plexamp_state():
    state = send_systemctl_plexamp('status')
    print(state)
    active = state[2].split(' ')[2][1:-1]
    return active


@app.route('/get_volume', methods=['GET', 'POST'])
def get_volume():
    splitted = False
    if 'splitted' in request.args:
        arg_splitted = request.args.get('splitted')
        if arg_splitted == 'true':
            splitted = True

    volume = request_amixer_volume(splitted)
    return json_response(result=volume)


@app.route('/set_volume', methods=['POST'])
def set_volume():
    data = request.get_json(force=True)

    if 'value' not in data:
        return json_response(error={'value not passed'})

    value = str(data['value'])
    if '%' not in value:
        value+= '%'

    answer = send_amixer_command('sset', value)
    volume = request_amixer_volume()
    return json_response(result=volume)


@app.route('/set_mute', methods=['POST'])
def set_mute():
    data = request.get_json(force=True)

    if 'value' not in data:
        return json_response(error={'value not passed'})

    muted = data['value']
    if not isinstance(muted, bool):
        if muted == 'on':
#            muted = True
            mute_setting = 'mute'
        else:
#            muted = False
            mute_setting = 'unmute'

#    if muted:
#        mute_setting = 'mute'
#    else:
#        mute_setting = 'unmute'

    answer = send_amixer_command('sset', mute_setting)
    volume = request_amixer_volume()
    print(volume)
    return json_response(result=volume)


@app.route('/get_plexamp_state', methods=['GET'])
def get_plexamp_state():
    return json_response(result=request_plexamp_state())

@app.route('/set_plexamp_state', methods=['POST'])
def systemctl_plexamp():
    data = request.get_json(force=True)

    if 'value' not in data:
        return json_response(error={'value not passed'})

    state = data['value']
    if not isinstance(state, bool):
        if state == 'on':
            state_setting = 'start'
        else:
            state_setting = 'stop'


    answer = send_systemctl_plexamp(state_setting)
    state = request_plexamp_state()
    return json_response(result=state)


if __name__=='__main__':
    app.run()
