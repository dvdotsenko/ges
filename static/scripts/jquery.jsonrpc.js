/*
JSONRPC (protocol v1.0) plugin for jQuery

Copyright (c) 2010  Daniel Dotsenko <dotsa (a) hotmail com>

A successful call will return ONLY the contents of the "result"
element of the returned JSON object. Our calling code should not
care if the RPC call was JSONRPC variety or some other type. Thus,
none of the "packetizer" metadata is returned to the Success callback.

If an error happens (either AJAX, or server error communicated as
non-null Error element in the response) we call the error callback
with the contents (actual of received, or simulated) of the Error
element of JSONRPC response object. It has specific structure:

Althught the plugin targets JSONRPC v1.0, because v1.0 does
not define what "error" element must look like, we borrow 
the error object structure from JSONRPC v2.0. Thus, when AJAX error
callback is called, it gets the contents of "error" element per
JSONRPC v2.0.


Usage example:

$.JSONRPC.call(
    "http://example.com/rpc", 
    method, 
    params,
    function (answer) {
            // answer = JS object - the actual return value of the RPC method.
    },
    function (answer) {
            // answer = error object per JSONRPC v2.0 spec. 
            // Ex: {'code':#, 'message':'...', 'data': some_object_but_likely_string}
    }
})

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
*/

(function($) {
    var _JSONRPC_request_ID_prefix = Math.floor(Math.random() * 10000).toString(16)
    $.extend({
        JSONRPC: {
            call: function (uri, method, params, success_call, error_call) {
                var _id = _JSONRPC_request_ID_prefix + (new Date()).getTime().toString(16)
                var ajaxSettings = {
                    type: 'POST'
                    ,url: uri
                    ,data: JSON.stringify({'id':_id,'method':method,'params':params})
                    ,cache: false
                    ,processData: false
                    ,error: function (obj) {
                        if (error_call) {
                            error_call(obj)
                        }
                    }
                    ,success: function (obj) {
                        try {
                            var jsobj = obj , _e, _r
                            if (_id != jsobj.id) {
                                throw "Incorrect ID element in the response JSON"
                            }
                            if (jsobj.error) {
                                throw jsobj.error
                            }
                            //if (!jsobj.result) {
                            //    throw "Returned Result element is empty"
                            success_call(jsobj.result);
                        }
                        catch (obj) {
                            if (error_call) {
                                error_call(obj)
                            }
                        }
                    }
                }
                $.ajax(ajaxSettings);
            }
        }
    })
})(jQuery);