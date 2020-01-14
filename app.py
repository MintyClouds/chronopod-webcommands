from datetime import datetime
import json
import os
from subprocess import Popen, PIPE

from flask import Flask, request
from flask_json import FlaskJSON, JsonError, json_response

AMIXER_CARD = 'Master'

app = Flask(__name__)
json = FlaskJSON(app)

app.config['JSON_ADD_STATUS'] = False
app.config['JSON_DATETIME_FORMAT'] = '%d/%m/%Y %H:%M:%S'


@app.route('/get_volume', methods=['GET'])
def get_volume():
    command = ['amixer', 'sget', AMIXER_CARD]
    proc = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    answer = stdout.decode('utf-8').split('\n  ')
    if 'Mono:' in answer:
        # merging channels
        channel_list = [answer[-2], answer[-1]]
        response = {}

        for channel in channel_list:
            attrs = channel.split(' ')

            name = attrs[0] + attrs[1]
            value = attrs[-2][1:-1]
            enabled = attrs[-1]
            if '\n' in enabled:
                 enabled = enabled.replace('\n', '')
            enabled = enabled[1:-1]
            print(attrs)
            response[name] = {'volume': value, 'enabled': enabled}


    return json_response(value=response)


if __name__=='__main__':
    app.run()
