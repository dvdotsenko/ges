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

import io
import json
import unittest

import jsonrpc_wsgi_application as jrpc

def good(value):
    return value
def yield_unencodable(*args, **kw):
    return
def bad(*args, **kw):
    1/0

class test_JSONRPCHandlerRouter(unittest.TestCase):

    preset = '{"id":"%s", "method":"%s", "params":["%s"]}'

    def setUp(self):
        self.h = jrpc.JSONRPCHandlerRouter()
        self.h.add_method('good_method', good)
        self.h.add_method('bad_method', bad)
        self.h.add_method(['namespace','nested_method'], good)
        self.h.add_method(['namespace','deeperspace.nested_method'], good)
        self.h.add_method('unencodable_method', yield_unencodable)

    def test_02_good_method(self):
        self.assertEquals(
            json.loads(self.h.process_request(self.preset % (1, "good_method", "sample text"))),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))

    def test_03_nested_method(self):
        self.assertEquals(
            json.loads(self.h.process_request(
                self.preset % (1, "namespace.nested_method", "sample text"))),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))
        self.assertEquals(
            json.loads(self.h.process_request(
                self.preset % (1, "namespace.deeperspace.nested_method", "sample text"))),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))

    def test_04_broken_method(self):
        _o = json.loads(self.h.process_request(
                self.preset % (1, "bad_method", "sample text")))
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32603) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Internal error') # JSONRPCv2.0

    def test_05_not_found(self):
        _o = json.loads(self.h.process_request(
                self.preset % (1, "should_not_be_there", "sample text")))
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32601) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Method not found') # JSONRPCv2.0

    def test_06_missing_request_parts(self):
        _o = json.loads(self.h.process_request('{"id":"1"}'))
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32600) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Invalid request') # JSONRPCv2.0

    def test_07_missshaped_request_parts(self):
        _o = json.loads(self.h.process_request('{"id":"1", "method":"not_there", "params":null}'))
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32600) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Invalid request') # JSONRPCv2.0

    def test_08_bad_json(self):
        _o = json.loads(self.h.process_request("this is not JSON"))
        self.assertEquals(_o['id'],None)
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32700) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Parse error') # JSONRPCv2.0

class test_WSGIJSONRPCApplication(unittest.TestCase):

    preset = '{"id":"%s", "method":"%s", "params":["%s"]}'

    def _start_response(self, *args, **kw):
        pass

    def _string_from_iterator(self, obj):
        return ''.join(obj)

    def setUp(self):
        self.h = jrpc.WSGIJSONRPCApplication()
        self.h.add_method('good_method', good)
        self.h.add_method('bad_method', bad)
        self.h.add_method(['namespace','nested_method'], good)
        self.h.add_method(['namespace','deeperspace.nested_method'], good)
        self.h.add_method('unencodable_method', yield_unencodable)

    def test_02_good_method(self):
        self.assertEquals(
            json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO(self.preset % (1, "good_method", "sample text"))
                    },
                    self._start_response)
                    )
            ),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))

    def test_03_nested_method(self):
        self.assertEquals(
            json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO(self.preset % (1, "namespace.nested_method", "sample text"))
                    },
                    self._start_response)
                    )
                ),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))
        self.assertEquals(
            json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO(self.preset % (1, "namespace.deeperspace.nested_method", "sample text"))
                    },
                    self._start_response)
                    )
                ),
            json.loads('{"id":"1", "result":"sample text", "error":null}'))

    def test_04_broken_method(self):
        _o = json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO(self.preset % (1, "bad_method", "sample text"))
                    },
                    self._start_response)
                    )
                )
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32603) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Internal error') # JSONRPCv2.0

    def test_05_not_found(self):
        _o = json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO(self.preset % (1, "should_not_be_there", "sample text"))
                    },
                    self._start_response)
                    )
                )
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32601) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Method not found') # JSONRPCv2.0

    def test_06_missing_request_parts(self):
        _o = json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO('{"id":"1"}')
                    },
                    self._start_response)
                    )
                )
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32600) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Invalid request') # JSONRPCv2.0

    def test_07_missshaped_request_parts(self):
        _o = json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO('{"id":"1", "method":"not_there", "params":null}')
                    },
                    self._start_response)
                    )
                )
        self.assertEquals(_o['id'],'1')
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32600) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Invalid request') # JSONRPCv2.0

    def test_08_bad_json(self):
        _o = json.loads(
                ''.join(self.h(
                    {
                        'wsgi.version': (1,1),
                        'wsgi.input': io.BytesIO('this is not JSON')
                    },
                    self._start_response)
                    )
                )
        self.assertEquals(_o['id'],None)
        self.assertEquals(_o['result'], None)
        self.assertTrue(_o['error'])
        self.assertEquals(_o['error']['code'],-32700) # JSONRPCv2.0
        self.assertEquals(_o['error']['message'],'Parse error') # JSONRPCv2.0

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite([
            unittest.TestLoader().loadTestsFromTestCase(test_JSONRPCHandlerRouter) ,
            unittest.TestLoader().loadTestsFromTestCase(test_WSGIJSONRPCApplication)
        ])
    )
