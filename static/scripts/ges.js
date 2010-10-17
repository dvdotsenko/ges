/*
Git Enablement Server - main JS app code

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
*/

(function($) {

  var app = $.sammy(function() {
    this.raise_errors = true
    this.debug = true
    this.run_interval_every = 300
    this.template_engine = null
    this.element_selector = '#dynamic'

    this.get('#/dashboard/', function() {
      if ( this.$element().children('#dashboard').length == 0 ) {
        this.swap($('#dashboard_tmpl').tmpl({}))
      }
    });
    this.get(/\#\/about\/.*/, function() {
      if ( this.$element().children('#about').length == 0 ) {
        this.swap($('#about_tmpl').tmpl())
      }
    });
    this.get(/\#\/(.*)/, function() {
        // cutting the corner. Only rerendering if came from elsewhere.
        if ( this.$element().children('#repo_browser').length == 0 ) {
            this.swap($('#repo_browser_base_tmpl').tmpl())
        }

        var _p = this.params['splat'][0] // path as requested. Will be sanitized later by RPC
            ,app_root_element = this.$element() // this = SammyApp.AppContext instance
            // Used to get around the scope problems for "this" in callbacks.
            ,content_jqobj = $('#repo_browser_content')
            // storing pointer to jq-element may seem like a
            // performance thing, but it's actually a way to
            // insure that when callback returns successfully
            // but late (after we already switched to new view)
            // and wants to update the div, a div with the same
            // id will be there, but, the pointer will not
            // be pointing to it or wnywhere.

        var successfn = function (result) {
            // Success Callback

            // creating section data for clickable "crumbs" address line
            // turns 'qwer/asdf/zxvc'
            // into [['qwer','qwer'],['asdf','qwer/asdf'],...]
            var _parent_links = []
                ,_dir_details = result
                ,_path_so_far = '/'
                ,_path = _dir_details['path'].split('/')
            for (_e in _path){
                if (_path[_e]) {
                    _path_so_far = _path_so_far + _path[_e] + '/'
                    _parent_links.push([_path[_e] , _path_so_far])
                }
            }
            // Because we check for non-empty path element above, ref to root folder is lost. Adding:
            _parent_links = [['(Main folder)','/']].concat(_parent_links)

            _dir_details['path'] = _path_so_far // this just adds "/" when needed."
            _dir_details['path_last_section'] = _parent_links.pop()[0]
            _dir_details['path_sections'] = _parent_links
            content_jqobj.html($('#repo_browser_content_tmpl').tmpl(_dir_details))
            if (!_dir_details.record_time) {
                _dir_details['record_time'] = (new Date()).getTime()
                app_root_element.data(
                    _p, // this one is the original path we sent to RPC. It might have been sanitized after return, so original is better for caching.
                    JSON.stringify(
                        _dir_details
                    )
                )
            }
        }
        var errorfn = function (response) {
            // Error Callback
            content_jqobj.html("Invalid directory listing.")
        }

        var _cached_dir_details = app_root_element.data(_p)

        if (_cached_dir_details) {
            successfn(JSON.parse(_cached_dir_details))
        } else {
            content_jqobj.html("Loading...")
            $.JSONRPC.call(
                '/rpc/'
                ,'browser.listdir'
                ,[_p]
                ,successfn
                ,errorfn
            );
        }
    });
    this.get(/\#\/viewer\/(.*)/, function() {
      document.asdf = this.params;
      alert(this.params['splat'].length)
      alert(this.params['splat']);
    });
  });

  $(function() {
    app.run('#/dashboard/');
  });
})(jQuery);