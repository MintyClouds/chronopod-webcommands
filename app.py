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

    print(command)
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


def send_bluetoothctl_show():
    daemon = 'bluetoothctl'
    command = 'show'

    result = send_cmdline_command(daemon, command, delimiter='\n\t')
    return result


def send_bluetoothctl_discoverable(state):
    daemon = 'bluetoothctl'
    command = 'discoverable'

    result = send_cmdline_command(daemon, command, [state])
    return result


def is_stereo_card(data):
    playback_channels = data[2].split(': ')
    return False if playback_channels[1] == 'Mono' else True


def request_amixer_volume(output_splitted=False):
    answer = send_amixer_command('sget')

    card_stereo = is_stereo_card(answer)

    channel_values = {}
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


def request_bluetoothctl_state():
    state = send_bluetoothctl_show()
    state_dict = {}
    last_controller = None

    for item in state:
        if 'Controller' in item:
            name = item.split(' ')[1]
            last_controller = name
            state_dict[name] = {}
            state_dict[name]['profiles'] = {}

        elif item == '':
            continue
        else:
            if '\n' in item:
                item = item.replace('\n', '')

            controller = state_dict[last_controller]
            controller_profiles = controller['profiles']

            uuid_parse = False
            if 'UUID' not in item:
                split_symbol = ': '
                result_dict = controller
            else:
                item = item[6:]
                split_symbol = '('
                uuid_parse = True
                result_dict = controller_profiles

            keyvalue = item.split(split_symbol)
            item_key = keyvalue[0]
            item_value = keyvalue[1]
            if uuid_parse:
                item_key = item_key.rstrip()
                item_value = item_value[1:-1]
            result_dict[item_key] = item_value

    answer = {'controllers': state_dict}

    return answer
    # return state


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
        value += '%'

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
            mute_setting = 'mute'
        else:
            mute_setting = 'unmute'

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


@app.route('/get_bluetooth_discoverable', methods=['GET'])
def get_bluetooth_discoverable_state():
    return json_response(result=request_bluetoothctl_state())


@app.route('/set_bluetooth_discoverable', methods=['POST'])
def bluetoothctl_discoverable():
    data = request.get_json(force=True)
    print(data)

    if 'value' not in data:
        return json_response(error=['value not passed'])

    state = data['value']
    answer = send_bluetoothctl_discoverable(state)
    state = request_bluetoothctl_state()
    return json_response(result=state)


if __name__=='__main__':
    app.run()
