import os
import json
import hashlib

def get_data_path():
    if not 'OPENSHIFT_DATA_DIR' in os.environ:
        return '../data/data.json'
    else:
        return os.path.join(os.environ['OPENSHIFT_DATA_DIR'], 'data.json')

def get_data():
    if not os.path.isfile(get_data_path()):
        with open(get_data_path(), 'w') as fh:
            fh.write("{}")
    data = json.load(open(get_data_path(), 'r'))
    return data

def weird_hash(data):
    hashed = hashlib.md5()
    hashed.update(data.encode('utf-8'))
    digest = hashed.hexdigest()
    uppercase_offset = ord('A') - ord('0')
    for x in range(ord('0'), ord('9')):
        digest = digest.replace(chr(x), chr(x + uppercase_offset))
    return digest

out = 'graph main {\n'
dot_usernames = ''
dot_relations = ''

data = get_data()

for k in data:
    user = data[k]
    username = user['username']
    dot_usernames += weird_hash(k) + '[label="' + weird_hash(k)[:5] + '"]' + '\n'
    if not 'friends' in user:
        continue
    for friend in user['friends']:
        if not (weird_hash(friend) + '--' +
                weird_hash(k) + '\n') in dot_relations:
            dot_relations += weird_hash(k) + '--' + \
                             weird_hash(friend) + '\n'
out += dot_usernames
out += dot_relations
out += '}'

print(out)
