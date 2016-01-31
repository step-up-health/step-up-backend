#!/usr/bin/env python
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse
import random
import json
class RequestHandler(BaseHTTPRequestHandler):

    # TODO friend requests

    def username_in_use(self, username):
        data = self.get_data()
        names = [x['username'] for x in data.values()]
        return username in names

    def get_data_path(self):
        if not 'OPENSHIFT_DATA_DIR' in os.environ:
            return '../data/data.json'
        else:
            return os.path.join(os.environ['OPENSHIFT_DATA_DIR'], 'data.json')

    def get_data(self):
        if not os.path.isfile(self.get_data_path()):
            with open(self.get_data_path(), 'w') as fh:
                fh.write("{}")
        data = json.load(open(self.get_data_path(), 'r'))
        print(data)
        return data

    def write_data(self, data):
        json.dump(data, open(self.get_data_path(), 'w'), sort_keys=True,
                    indent=4, separators=(',', ': '))

    def username_to_uid(self, data, username):
        for key, item in data.items():
            if 'username' in item and item['username'] == username:
                return key
        return False

    def uid_to_username(self, data, uid):
        if uid in data:
            return data[uid]['username']
        return False

    def respond(self, code, string):
        self.send_response(code)
        self.end_headers()
        if code == 200:
            self.wfile.write(bytes(string, 'utf-8'))
        else:
            self.wfile.write(bytes(str(code) + ' ' + string, 'utf-8'))

    def pin(self, data, uid, pinData, pinId):
        if 'tltoken' in data[uid]:
            url = 'https://timeline-api.getpebble.com/v1/user/pins/' + pinId
            req = urllib.request.Request(
                            url,
                            data = bytes(json.dumps(pinData), 'utf-8'),
                            method = 'PUT',
                            headers = {
                                'Content-Type': 'application/json',
                                'X-User-Token': data[uid]['tltoken']
                            })
            print('URL: -----> -----> ', req.full_url)
            print('DATA: -----> -----> ', req.data)
            print('METHOD: -----> -----> ', req.get_method())
            print('HEADERS: -----> -----> ', req.headers)
            with urllib.request.urlopen(req) as response:
                data = response.read()
                print(data)
        else:
            print('Tltoken for ' + uid + ' is missing. Not pinning.')

    def set_username(self, uid, username):
        try:
            data = self.get_data()
            for key, item in data.items():
                if key != uid:
                    if item['username'] == username.lower().strip():
                        return (400, 'Username taken')
            for key, item in data.items():
                if key == uid:
                    item['username'] = username.lower().strip()
                    self.write_data(data)
                    return (200, 'OK')
            data[uid] = {'username': username.lower().strip()}
            self.write_data(data)
            return (200, 'OK (created)')
        except ValueError as e:
            print(e)
        return (400, 'Misc failure')

    def set_timeline_token(self, uid, tltoken):
        data = self.get_data()
        for key, item in data.items():
            if key == uid:
                item['tltoken'] = tltoken
                self.write_data(data)
                return (200, 'OK')
        return (400, 'User doesn\'t exist')

    def add_data_point(self, uid, timePeriod, steps):
        try:
            steps = int(steps)
        except ValueError:
            return (400, 'Malformed Steps Data')
        data = self.get_data()
        if not uid in data:
            data[uid] = {}
        if not 'history' in data[uid]:
            data[uid]['history'] = {}
        data[uid]['history'][timePeriod] = steps
        data[uid]['history'] = pruneHistory(data[uid]['history'])
        self.write_data(data)
        return (200, 'OK')

    def get_friends(self, uid):
        data = self.get_data()
        if not uid in data:
            data[uid] = {}
        if not 'friends' in data[uid]:
            data[uid]['friends'] = []
        friends = data[uid]['friends']
        friends = [self.uid_to_username(data, friend) for friend in friends]
        return (200, json.dumps(friends))
        self.write_data(data)

    def add_friend(self, uid, friendUsername):
        data = self.get_data()
        if not uid in data:
            return (400, 'User doesn\'t exist');
        if not 'friends' in data[uid]:
            data[uid]['friends'] = []
        if len(data[uid]['friends']) >= 20:
            return (409, 'You can\'t add that many friends.')
        if self.uid_to_username(data, uid) == friendUsername:
            return (409, 'You can\'t add yourself as a friend.')
        friendUUID = self.username_to_uid(data, friendUsername)
        if friendUUID is not False:
            data[uid]['friends'] += [self.username_to_uid(data, friendUsername)]
            data[uid]['friends'] = list(set(data[uid]['friends']))
            self.write_data(data)
            return (200, json.dumps([self.uid_to_username(data, x) for x in
                                     data[uid]['friends']]))
        else:
            return (400, 'User doesn\'t exist.')

    def send_friend_request(self, uid, friendUsername):
        data = self.get_data()
        if not uid in data:
            return (400, 'Your user doesn\'t exist');
        friendUUID = self.username_to_uid(data, friendUsername)
        if friendUUID is not False:
            requestorUsername = self.uid_to_username(data, uid)
            if not 'friendReqs' in data[friendUUID]:
                data[friendUUID]['friendReqs'] = []
            if len(data[friendUUID]['friendReqs']) >= 20:
                return (409, 'That person has maxed out their friends!')
            if uid == friendUUID:
                return (409, 'You can\'t add yourself as a friend.')
            data[friendUUID]['friendReqs'] += uid
            data[friendUUID]['friendReqs'] = list(set(data[friendUUID]['friendReqs']))
            self.write_data(data)
            try:
                pinId = 'friend-request-' + str(random.randint(10**8, 10**9))
                self.pin(data, friendUUID, {
                    'time': time.strftime("%Y-%m-%dT%H:%M:%S"),
                    'id': pinId,
                    'layout': {
                        'title': 'Friend Request!',
                        'subtitle': 'Step Up!',
                        'body': requestorUsername + ' wants to be your friend on Step Up!',
                        'type': 'genericPin'
                    }
                }, pinId)
            except urllib.error.HTTPError as e:
                return (200, 'pin sending failure: ' + e.read().decode('utf-8'))
            return (200, 'OK')
        else:
            return (400, 'Friending user doesn\'t exist.')

    def remove_friend(self, uid, friendUsername):
        data = self.get_data()
        if not uid in data:
            data[uid] = {}
        if not 'friends' in data[uid]:
            data[uid]['friends'] = []
        friendUUID = self.username_to_uid(data, friendUsername)
        if not friendUUID is False:
            data[uid]['friends'] = list(set(data[uid]['friends']))
            data[uid]['friends'].remove(friendUUID)
            data[friendUUID]['friends'.remove(uid)]
            self.write_data(data)
            return (200, json.dumps(data[uid]['friends']))
        else:
            return (400, 'User doesn\'t exist.')

    def dump_data(self):
        data = self.get_data()
        out = '<!DOCTYPE html><html><head></head><body>'
        for key, value in sorted(data.items(), key=lambda x: x[0]):
            out += '<u>' + key + '</u>' +\
                   '<blockquote>'
            for propKey, propVal in sorted(value.items(), key=lambda x: x[0]):
                out += '<b>' + propKey + '</b>: ' +\
                       '<i>' + json.dumps(propVal) + '</i><br/>'
            out += '</blockquote>'
        out += '</body></html>'
        return (200, out)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        BaseHTTPRequestHandler.end_headers(self)

    def do_GET(self):
        urldata = urllib.parse.urlparse(self.path)
        qdata = urllib.parse.parse_qs(urldata.query)
        print(qdata)
        try:
            self.path.index('/dump')
            try:
                # NB this removes it in prod
                assert not 'OPENSHIFT_PYTHON_IP' in os.environ
                info = self.dump_data()
                print(info)
                self.respond(info[0], info[1])
                return
            except AssertionError:
                pass
        except ValueError:
            pass
        try:
            self.path.index('/username_in_use')
            try:
                assert 'username' in qdata
                info = self.username_in_use(qdata['username'][0])
                self.respond(200, json.dumps(str(info)))
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        except ValueError:
            pass
        try:
            self.path.index('/add_data')
            try:
                assert 'uid' in qdata and\
                       'timeperiod' in qdata and\
                       'steps' in qdata
                info = self.add_data_point(qdata['uid'][0],
                                           qdata['timeperiod'][0],
                                           qdata['steps'][0])
                if (len(info) == 2):
                    self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        except ValueError:
            pass
        try:
            self.path.index('/send_friend_request')
            try:
                assert 'uid' in qdata and\
                       'addusername' in qdata
                info = self.send_friend_request(qdata['uid'][0],
                                                qdata['addusername'][0])
                if (len(info) == 2):
                    self.respond(info[0], info[1])
                    return
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        except ValueError:
            pass
        try:
            self.path.index('/get_friends')
            try:
                assert 'uid' in qdata
                info = self.get_friends(qdata['uid'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        except ValueError:
            pass
        try:
            self.path.index('/add_friend')
            try:
                assert 'uid' in qdata and\
                       'addusername' in qdata
                info = self.add_friend(qdata['uid'][0],
                                       qdata['addusername'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        except ValueError:
            pass
        try:
            self.path.index('/delete_friend')
            try:
                assert 'uid' in qdata and\
                       'deleteusername' in qdata
                info = self.delete_friend(qdata['uid'][0],
                                       qdata['deleteusername'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        except ValueError:
            pass
        try:
            self.path.index('/get_username')
            try:
                assert 'uid' in qdata
                print(self.path)
                username = self.uid_to_username(self.get_data(), qdata['uid'][0])
                if username is not False:
                    self.respond(200, username)
                else:
                    self.respond(404, 'User not registered')
                return
            except AssertionError:
                self.respond(400, 'Malformed request')
                return
        except ValueError:
            pass
        try:
            self.path.index('/set_username')
            try:
                assert 'uid' in qdata and\
                       'username' in qdata
                print(self.path)
                info = self.set_username(qdata['uid'][0], qdata['username'][0])
                self.respond(info[0], info[1])
                return
            except AssertionError:
                self.respond(400, 'Malformed request')
                return
        except ValueError:
            pass
        try:
            self.path.index('/set_timeline_token')
            try:
                assert 'uid' in qdata and\
                       'tltoken' in qdata
                print(self.path)
                info = self.set_timeline_token(qdata['uid'][0], qdata['tltoken'][0])
                self.respond(info[0], info[1])
                return
            except AssertionError:
                self.respond(400, 'Malformed request')
                return
        except ValueError:
            pass
        self.respond(400, 'Method missing')

if __name__ == '__main__':
    if 'OPENSHIFT_PYTHON_IP' in os.environ:
        server_address = (os.environ['OPENSHIFT_PYTHON_IP'],
                          int(os.environ['OPENSHIFT_PYTHON_PORT']))
    else:
        server_address = ('', 8080)
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()
