#!/usr/bin/env python
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse
import random
import json

allwhitespace = u"\u0009\u000A\u000B\u000C\u000D\u0020\u0085\u00A0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u200B\u2028\u2029\u202F\u205F\u3000\u180E\u200B\u200C\u200D\u2060\uFEFF"

class RequestHandler(BaseHTTPRequestHandler):
    def username_in_use(self, username):
        if len(username) < 1:
            return True
        if len(username) > 20:
            return True
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
        return data

    def write_data(self, data):
        json.dump(data, open(self.get_data_path(), 'w'), sort_keys=True,
                    indent=4, separators=(',', ': '))

    def get_own_api_root(self):
        if 'OPENSHIFT_DATA_DIR' in os.environ:
            return 'https://pythonbackend-stepupforpebble.rhcloud.com/'
        else:
            return 'http://localhost:8080/'

    def username_to_uid(self, data, username):
        for key, item in data.items():
            if 'username' in item and item['username'] == username:
                return key
        return False

    def uid_to_username(self, data, uid):
        if uid in data:
            return data[uid]['username']
        return False

    def prune_history(self, hist):
        histItems = sorted(hist.items(), key=lambda x:x[0])[-6:]
        histItems = {x[0]: x[1] for x in histItems}
        return histItems

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
            username = username.lower()
            for char in allwhitespace:
                username = username.replace(char, ' ')
            username = username.strip()
            data = self.get_data()
            if len(username) < 1:
                return (400, 'Username too short (min 1 character)')
            if len(username) > 20:
                return (400, 'Username too long (max 20 characters)')
            for key, item in data.items():
                if key != uid:
                    if 'username' in item and\
                            item['username'] == username.lower():
                        return (400, 'Username taken')
            for key, item in data.items():
                if key == uid:
                    item['username'] = username.lower()
                    self.write_data(data)
                    return (200, 'OK')
            data[uid] = {'username': username}
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
        data[uid]['history'] = self.prune_history(data[uid]['history'])
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
        friendUsername = friendUsername.lower()
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

    def get_outgoing_friend_reqs(self, uid):
        data = self.get_data()
        if not uid in data:
            return (400, 'User doesn\'t exist');
        if not 'friends' in data[uid]:
            data[uid]['friends'] = []
        outgoingReqs = []
        for friendUUID, friend in data.items():
            if not 'friendReqs' in friend:
                continue
            if uid in friend['friendReqs']:
                outgoingReqs += [friend['username']]
        return (200, json.dumps(outgoingReqs))

    def get_incoming_friend_reqs(self, uid):
        data = self.get_data()
        if not uid in data:
            return (400, 'User doesn\'t exist');
        if not 'friendReqs' in data[uid]:
            data[uid]['friendReqs'] = []
        incomingReqs = []
        for friendUUID in data[uid]['friendReqs']:
            if friendUUID in data:
                incomingReqs += [data[friendUUID]['username']]
        return (200, json.dumps(incomingReqs))

    def send_friend_request(self, uid, friendUsername):
        # TODO dont allow sending friend reqs to people you've already friended.
        data = self.get_data()
        if not uid in data:
            return (400, 'Your user doesn\'t exist');
        friendUUID = self.username_to_uid(data, friendUsername)
        if friendUUID is not False and\
           friendUUID in data:
            requestorUsername = self.uid_to_username(data, uid)
            if not 'friendReqs' in data[friendUUID]:
                data[friendUUID]['friendReqs'] = []
            if not 'friendReqs' in data[uid]:
                data[uid]['friendReqs'] = []
            if len(data[friendUUID]['friendReqs']) >= 20:
                return (409, 'That person has maxed out their friends!')
            if len(data[uid]['friendReqs']) >= 20:
                return (409, 'You have maxed out their friends!')
            if uid == friendUUID:
                return (409, 'You can\'t add yourself as a friend.')

            if not 'friends' in data[uid]:
                data[uid]['friends'] = []
            if not 'friends' in data[friendUUID]:
                data[friendUUID]['friends'] = []

            if friendUUID in data[uid]['friends']:
                return (200, 'Already befriended')
            elif friendUUID in data[uid]['friendReqs']:
                # Yay! Friend request acception time!
                print('mutual acception', uid, friendUUID)
                try:
                    data[friendUUID]['friends'] += [uid]
                    data[uid]['friends'] += [friendUUID]
                    data[friendUUID]['friends'] = list(set(data[friendUUID]['friends']))
                    data[uid]['friends'] = list(set(data[uid]['friends']))
                    if uid in data[friendUUID]['friendReqs']:
                        data[friendUUID]['friendReqs'].remove(uid)
                    if friendUUID in data[uid]['friendReqs']:
                        data[uid]['friendReqs'].remove(friendUUID)
                    for _uuid, _username in [(uid, friendUsername),
                                             (friendUUID, requestorUsername)]:
                        pinId = 'friend-request-' + str(random.randint(10**8, 10**9))
                        self.pin(data, _uuid, {
                            'time': time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            'id': pinId,
                            'layout': {
                                'type': 'genericPin',
                                'title': 'New Friend!',
                                'subtitle': 'Step Up!',
                                'body': _username + ' is now your friend on Step Up!'
                            },
                            'createNotification': {
                                'layout': {
                                    'type': 'genericNotification',
                                    'title': 'New Friend!',
                                    'body': 'You and ' + _username + ' are now friends on Step Up!'
                                }
                            }
                        }, pinId)
                except ValueError as e:
                    print(e)
                except urllib.error.HTTPError as e:
                    print('HTTPError happened!!')
                    print(e)
                self.write_data(data)
                return (200, 'OK')
            else:
                # Let's go make some friends!
                data[friendUUID]['friendReqs'] += [uid]
                data[friendUUID]['friendReqs'] = list(set(data[friendUUID]['friendReqs']))
                self.write_data(data)
                try:
                    pinId = 'friend-request-' + str(random.randint(10**8, 10**9))
                    self.pin(data, friendUUID, {
                        'time': time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        'id': pinId,
                        'layout': {
                            'type': 'genericPin',
                            'title': 'Friend Request!',
                            'subtitle': 'Step Up!',
                            'body': requestorUsername + ' wants to be your friend on Step Up!'
                        },
                        'createNotification': {
                            'layout': {
                                'type': 'genericNotification',
                                'title': 'Friend Request!',
                                'body': requestorUsername +
                                    ' wants to be your friend on Step Up!\n' +
                                    'Select "More" from actions to accept.'
                            }
                        },
                        'actions': [
                            {
                                'type': 'http',
                                'method': 'GET',
                                'title': 'Accept',
                                'url': self.get_own_api_root() +
                                       'send_friend_request?uid=' + friendUUID +
                                       '&addusername=' + requestorUsername
                            }
                        ]
                    }, pinId)
                except urllib.error.HTTPError as e:
                    return (200, 'pin sending failure: ' + e.read().decode('utf-8'))
                return (200, 'OK')
        else:
            return (400, 'Friending user doesn\'t exist.')

    def delete_friend(self, uid, friendUsername):
        data = self.get_data()
        if not uid in data:
            data[uid] = {}
        if not 'friends' in data[uid]:
            data[uid]['friends'] = []
        friendUUID = self.username_to_uid(data, friendUsername)
        requestorUsername = self.uid_to_username(data, uid)

        data[uid]['friends'] = list(set(data[uid]['friends']))
        if friendUUID in data[uid]['friends']:
            data[uid]['friends'].remove(friendUUID)

        if not friendUUID is False:
            data[friendUUID]['friends'] = list(set(data[friendUUID]['friends']))
            if uid in data[friendUUID]['friends']:
                data[friendUUID]['friends'].remove(uid)

            self.write_data(data)
            return (200, 'OK')
        else:
            return (400, 'User doesn\'t exist.')

    def date_to_timeperiod_str(self, dt):
        return dt.isoformat()

    def is_recent_ish(self, timestring):
        import datetime
        stamp = int(time.time()) + 24*60*60
        valids = []
        for x in range(stamp - 2 * 24*60*60, stamp + 1, 24*60*60):
            dt = datetime.date.fromtimestamp(int(x))
            print(timestring, dt)
            if self.date_to_timeperiod_str(dt) in timestring:
                return True;
        return False;

    def get_active_friends(self, uid, partOfDay):
        data = self.get_data()
        if uid in data:
            if 'friends' in data[uid] and len(data[uid]['friends']) > 0:
                friends = []
                for friendUUID in data[uid]['friends']:
                    if not friendUUID in data:
                        continue
                    friend = data[friendUUID]
                    if 'history' in friend:
                        history = friend['history']
                        history = sorted(history.items(), key=lambda x: x[0],
                            reverse=True)
                        history.pop() # Most recent value may be incomplete
                        try:
                            print(history)
                            print(data[friendUUID]['username'])
                            item = [x for x in history if partOfDay in x[0] and
                                    self.is_recent_ish(x[0])][-1]
                        except IndexError:
                            continue # not enough (& old enough) data.
                        friends.append(
                            {
                                'username': friend['username'],
                                'steps': item[1],
                                'timePeriod': item[0]
                            }
                        )
                friends.sort(key=lambda x: x['steps'])
                friends.sort(key=lambda x: x['timePeriod'])
                return (200, json.dumps(friends))
            else:
                return (200, json.dumps([]))
        else:
            return (400, 'User missing')

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
        print(json.dumps(qdata))
        if '/dump' in self.path:
            try:
                # NB this removes it in prod
                assert not 'OPENSHIFT_PYTHON_IP' in os.environ
                info = self.dump_data()
                print(info)
                self.respond(info[0], info[1])
                return
            except AssertionError:
                pass
        elif '/username_in_use' in self.path:
            try:
                assert 'username' in qdata,\
                       'uid' in qdata
                ownerUid = self.username_to_uid(self.get_data(), qdata['username'][0])
                if len(qdata['username'][0]) < 1 or len(qdata['username'][0]) > 20:
                    self.respond(200, json.dumps('"True"'))
                    return
                if ownerUid == qdata['uid'][0] or ownerUid is False:
                    self.respond(200, json.dumps('"False"'))
                    return
                self.respond(200, json.dumps('"True"'))
                return
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        elif '/get_active_friends' in self.path:
            try:
                assert 'uid' in qdata and\
                       'dayhalf' in qdata
                assert qdata['dayhalf'][0] in ['AM', 'PM']
                info = self.get_active_friends(qdata['uid'][0],
                                               qdata['dayhalf'][0])
                self.respond(info[0], info[1])
                return
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        elif '/add_data_point' in self.path:
            try:
                assert 'uid' in qdata and\
                       'timeperiod' in qdata and\
                       'steps' in qdata
                info = self.add_data_point(qdata['uid'][0],
                                           qdata['timeperiod'][0],
                                           qdata['steps'][0])
                if (len(info) == 2):
                    self.respond(info[0], info[1])
                    return
            except AssertionError:
                self.respond(400, 'Malformed Request')
                return
        elif '/send_friend_request' in self.path:
            try:
                assert 'uid' in qdata and\
                       'addusername' in qdata
                info = self.send_friend_request(qdata['uid'][0],
                                                qdata['addusername'][0])
                if (len(info) == 2):
                    self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed Request')
            return
        elif '/get_friends' in self.path:
            try:
                assert 'uid' in qdata
                info = self.get_friends(qdata['uid'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/delete_friend' in self.path:
            try:
                assert 'uid' in qdata and\
                       'deleteusername' in qdata
                info = self.delete_friend(qdata['uid'][0],
                                          qdata['deleteusername'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/get_username' in self.path:
            try:
                assert 'uid' in qdata
                print(self.path)
                username = self.uid_to_username(self.get_data(), qdata['uid'][0])
                if username is not False:
                    self.respond(200, json.dumps(username))
                else:
                    self.respond(404, 'User not registered')
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/get_outgoing_friend_reqs' in self.path:
            try:
                assert 'uid' in qdata
                print(self.path)
                info = self.get_outgoing_friend_reqs(qdata['uid'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/get_incoming_friend_reqs' in self.path:
            try:
                assert 'uid' in qdata
                print(self.path)
                info = self.get_incoming_friend_reqs(qdata['uid'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/set_username' in self.path:
            try:
                assert 'uid' in qdata and\
                       'username' in qdata
                print(self.path)
                info = self.set_username(qdata['uid'][0], qdata['username'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        elif '/set_timeline_token' in self.path:
            try:
                assert 'uid' in qdata and\
                       'tltoken' in qdata
                print(self.path)
                info = self.set_timeline_token(qdata['uid'][0], qdata['tltoken'][0])
                self.respond(info[0], info[1])
            except AssertionError:
                self.respond(400, 'Malformed request')
            return
        self.respond(400, 'Method missing')

if __name__ == '__main__':
    if 'OPENSHIFT_PYTHON_IP' in os.environ:
        server_address = (os.environ['OPENSHIFT_PYTHON_IP'],
                          int(os.environ['OPENSHIFT_PYTHON_PORT']))
    else:
        server_address = ('', 8080)
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()
