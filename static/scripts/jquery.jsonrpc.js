/**
 * Jsonrpc plugin
 * Intended for use with jQuery 1.4.2
 *
 * Copyright (c) 2010 Cloud4pc (www.cloud4pc.com)
 * Dual licensed under the MIT and GPL licenses:
 * http://www.opensource.org/licenses/mit-license.php
 * http://www.gnu.org/licenses/gpl.html
 *
 * @version 0.5.0
 *

Example 1
$.JsonRPC.request ("http://xxx.xxx.xxx/jsonrpcServer", method, params, {
        success: function (response) {
                // {"id":1,"result":"...","error":null}
        },
        error: function (response) {
                // {"id":1,"result":null,"error":"..."}
        }
});
EXAMPLE 2

$.JsonRPC.endPoint = "http://xxx.xxx.xxx/jsonrpcServer";
$.JsonRPC.request (null, method, params, {
        success: function (response) {
                // {"id":1,"result":"...","error":null}
        },
        error: function (response) {
                // {"id":1,"result":null,"error":"..."}
        }
});
 **/
(function($) {
	$.extend({
		JsonRPC: {
			endPoint: null,
			request: function (url, method, params, callbacks) {
			    this.version = '2.0';
			    this.url = url;
			    this.method = method;
			    this.params = params;
			    this.id = 1;

			    var postData = {};

			    // postData.jsonrpc = this.version;
			    postData.method = this.method;
			    postData.params = this.params;

			    var ajaxCall = {};
			    ajaxCall.type = 'POST';
			    ajaxCall.url = this.url + '?tm=' + new Date().getTime();
			    ajaxCall.data = JSON.stringify(postData);
			    ajaxCall.cache = false;
			    ajaxCall.processData = false;

			    ajaxCall.error = function (json) {
			        if (callbacks.error) {
			            callbacks.error (new $.JsonRPC.response());
			        } 
			    }
			    ajaxCall.success = function (json) {
			        var response = new $.JsonRPC.response (json);
//			        if (response.error) {
//			            if (callbacks.error) {
//			                callbacks.error (response);
//			            }
//			        }
			        
			        if (callbacks.success) {
			            callbacks.success (response);
			        } 
			    }
			    
			    $.ajax(ajaxCall);
			},
			
			response: function (json) {
			    if (!json) {
			        this.error = 'Internal server error';
			    }
			    else {
			        try {
			            var obj = eval ( '(' + json + ')' );
			            this.id = obj.id;
			            this.result = obj.result;
			            this.error = obj.error;
			        }
			        catch (e) {
			            this.error = 'Internal server error: ' + e;
			            this.version = '2.0';
			        }
			    }
			}
		}
	});
})(jQuery);