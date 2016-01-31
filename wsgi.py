#!/usr/bin/env python
import os
import json
import .server
#
# Below for testing only
#

print(server)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('localhost', 8051, application)
    # Wait for a single request, serve it and quit.
    httpd.handle_request()
