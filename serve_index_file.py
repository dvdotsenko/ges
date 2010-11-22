#!/usr/bin/env python
'''
Copyright (c) 2010  Daniel Dotsenko <dotsa (a) hotmail com>

This file is part of Git Enablement Server Project.

Git Enablement Server Project is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

Git Enablement Server Project is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Git Enablement Server Project.  If not, see <http://www.gnu.org/licenses/>.
'''
import io
import os.path
import os

from wsgiref.headers import Headers

# needed for static content server
import time
import email.utils

class BaseWSGIClass(object):
    bufsize = 65536
    gzip_response = False
    canned_collection = {
        '304': '304 Not Modified',
        'not_modified': '304 Not Modified',
        '301': '301 Moved Permanently',
        'moved': '301 Moved Permanently',
        '400':'400 Bad request',
        'bad_request':'400 Bad request',
        '401':'401 Access denied',
        'access_denied':'401 Access denied',
        '401.4': '401.4 Authorization failed by filter',
        '403':'403 Forbidden',
        'forbidden':'403 Forbidden',
        '404': "404 Not Found",
        'not_found': "404 Not Found",
        '405': "405 Method Not Allowed",
        'method_not_allowed': "405 Method Not Allowed",
        '417':'417 Execution failed',
        'execution_failed':'417 Execution failed',
        '200': "200 OK",
        '501': "501 Not Implemented",
        'not_implemented': "501 Not Implemented"
    }

    def canned_handlers(self, environ, start_response, code = '200', headers = []):
        '''
        We convert an error code into
        certain action over start_response and return a WSGI-compliant payload.
        '''
        headerbase = [('Content-Type', 'text/plain')]
        if headers:
            hObj = Headers(headerbase)
            for header in headers:
                hObj[header[0]] = '; '.join(header[1:])
        start_response(self.canned_collection[code], headerbase)
        return ['']

    def package_response(self, outIO, environ, start_response, headers = []):

        retobj = outIO
        if hasattr(outIO,'fileno') and 'wsgi.file_wrapper' in environ:
            outIO.seek(0)
            retobj = environ['wsgi.file_wrapper']( outIO, self.bufsize )
        elif hasattr(outIO,'read'):
            outIO.seek(0)
            retobj = iter( lambda: outIO.read(self.bufsize), '' )
        start_response("200 OK", headers)
        return retobj

class ServeIndexFile(BaseWSGIClass):
    '''Serves one hardcoded file'''
    def __init__(self, **kw):
        '''
        Inputs:
            static_content_path (mandatory)
                String containing a file-system level path behaving as served root.
        '''
        self.__dict__.update(kw)

        self.filename = os.path.join(self.static_content_path, 'index.html')
        self.file_contents = open(self.filename, 'r').read()
        mtime = os.stat(self.filename).st_mtime
        self.etag, self.last_modified =  str(mtime), email.utils.formatdate(mtime)
        self.headers = [
            ('Content-type', 'text/html'),
            ('Last-Modified', self.last_modified),
            ('ETag', self.etag)
        ]

    def __call__(self, environ, start_response):

        # TODO: wire up the time to commit. Until then, there will be no caching
        #  on web client. Ugh!
        _h = self.headers[:]
        _h.append(
            ('Date', email.utils.formatdate(time.time()))
            )
        if_modified = environ.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified and (email.utils.parsedate(if_modified) >= email.utils.parsedate(self.last_modified)):
            return self.canned_handlers(environ, start_response, 'not_modified', _h)
        if_none = environ.get('HTTP_IF_NONE_MATCH')
        if if_none and (if_none == '*' or self.etag in if_none):
            return self.canned_handlers(environ, start_response, 'not_modified', _h)

        return self.package_response(
            io.BytesIO(self.file_contents),
            environ,
            start_response,
            _h)
