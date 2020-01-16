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

def send_amixer_command(command, value=None):
    command = ['amixer', command, AMIXER_CARD]
    if value:
        command.append(value)

    proc = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    output = stdout.decode('utf-8').split('\n  ')
    return output

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
            value = attrs[-3]

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


if __name__=='__main__':
    app.run()
