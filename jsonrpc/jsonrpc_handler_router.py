""" 
Python JSON-RPC (protocol v1.0) module.

Copyright (c) 2010 Daniel Dotsenko <dotsa@hotmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 2.1 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# TODO: Consider class method decorators so that classes added to tree would
#       expose their marked methods as RPC methods.

import json

# the errors strucutre is stolen from JSONRPC 2.0. v.1.0 does
# not prescribe any particular way of dressing up error objects.
class ExceptionParseError(Exception):
    ''' Invalid JSON was received by the server.
    An error occurred on the server while parsing the JSON text
    '''
    def __init__(self, *args, **kw):
        Exception.__init__(self, *args, **kw)
        self.code = -32700
        self.message = 'Parse error'
        self.data = ''
class ExceptionInvalidRequest(Exception):
    '''The JSON sent is not a valid Request object per JSONRPC v1.0'''
    def __init__(self, *args, **kw):
        Exception.__init__(self, *args, **kw)
        self.code = -32600
        self.message = 'Invalid request'
        self.data = ''
class ExceptionMethodNotFound(Exception):
    '''The method does not exist / is not available.'''
    def __init__(self, *args, **kw):
        Exception.__init__(self, *args, **kw)
        self.code = -32601
        self.message = 'Method not found'
        self.data = ''
class ExceptionInternalError(Exception):
    '''Error internal to JSON-RPC server.'''
    def __init__(self, *args, **kw):
        Exception.__init__(self, *args, **kw)
        self.code = -32603
        self.message = 'Internal error'
        self.data = ''

class JSONRPCHandlerRouter(object):

    def __init__(self):
        self.methods = {}

    def add_method(self, path, method_pointer):
        '''Adds a virtual path to the tree of RPC methods.

        @param path A list, tuple or a string declaring the virtual
            calling path to the method. Last element in the chain
            is the name of the method. If string, scope names
            must be delimited by dots (".")
            Example: ['asdf.qwer','zxcv','method'] or 'asdf.qwer.zxcv.method'
        @param method A pointer to a method. Should be either a function or a method
            of an instantiated class, or a callable instance of a class, or
            a callable method of a static class.

        Examples:
            obj.add_method(['namespace','morenamespace','method_name'], method_ptr)
            obj.add_method('namespace.morenamespace.method_name', method_ptr)
            obj.add_method(['namespace.morenamespace','method_name'], method_ptr)
        '''
        if not path:
            raise ValueError("Path must be non-empty string.")
        if not method_pointer:
            raise ValueError("Method must be a pointer to a method.")
        if type(path) in (list, tuple):
            path = '.'.join(path).split('.')
        else:
            path = path.split('.')
        method_name = path.pop(-1)
        _o = self.methods
        for section in path:
            if section:
                try:
                    _o = _o[section]
                except:
                    _o[section] = {} # note if before _o[section] was a function, override. By Design.
                    _o = _o[section]
        _o[method_name] = method_pointer

    def _convert_string_to_json(self, json_string):
        try:
            return json.loads(json_string)
        except:
            raise ExceptionParseError()

    def _extract_request_elements(self, elements, json_obj):
        try:
            elements['id'] = json_obj['id']
            elements['method'] = json_obj['method']
            elements['params'] = json_obj['params']
            if type(elements['params']) not in (tuple, list):
                raise
        except:
            raise ExceptionInvalidRequest()
        finally:
            del json_obj

    def _find_method(self, method_name):
        '''We support dotted method names - methods with namespaces
        prepended and demarkated by period character.
        '''
        _o = self.methods
        try:
            for section in method_name.split('.'):
                _o = _o[section]
        except KeyError:
            raise ExceptionMethodNotFound()
        return _o

    def _call_method(self, method_obj, params):
        try:
            return method_obj(*params)
        except Exception as e:
            raise ExceptionInternalError()

    def _encode_response_data(self, obj):
        try:
            return json.dumps(obj)
        except Exception as e:
            raise ExceptionInternalError()

    def process_request(self, json_string):
        '''Handles a single icoming JSON-RPC v1.0 request.

        @param json_string A string-like with textual representation of
        JSON data to be processed as request.

        @returns A string with textual representation of JSON data object
        to be sent back as the reply.
        '''
        # TODO: Add code to handle JSONRPC "Notification" http://json-rpc.org/wiki/specification
        # TODO: Add ability to handle streaming JSON.
        request_elements = {'id':None}
        try:
            self._extract_request_elements(
                request_elements,
                self._convert_string_to_json(json_string)
                )
            return_string = self._encode_response_data({
                "error":None,
                "id":request_elements['id'],
                "result":self._call_method(
                    self._find_method(request_elements['method']),
                    request_elements['params']
                    )
                })
        except (ExceptionParseError,
                ExceptionInvalidRequest,
                ExceptionInternalError,
                ExceptionMethodNotFound) as e:
            return_string = self._encode_response_data({
                "id":request_elements['id'],
                "result":None,
                "error":{
                    "code":e.code,
                    "message": e.message,
                    "data": e.data or json_string
                    }
                })
        del request_elements
        return return_string
