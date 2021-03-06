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

    // these are specific to SyntaxHighlighter from http://alexgorbatchev.com/SyntaxHighlighter/
    var _syntax_highlighter_template_map = {
            // built-ins in SyntexHighlighter
            "as3": "as3", "vb": "vb", "text": "text", "cf": "cf"
            , "c-sharp": "c-sharp", "pascal": "pascal", "csharp": "csharp"
            , "diff": "diff", "ror": "ror", "php": "php", "xml": "xml"
            , "ps": "ps", "pas": "pas", "java": "java", "scala": "scala"
            , "delphi": "delphi", "py": "py", "rails": "rails", "perl": "perl"
            , "html": "html", "xhtml": "xhtml", "erlang": "erlang"
            , "vbnet": "vbnet", "css": "css", "shell": "shell", "xslt": "xslt"
            , "python": "python", "javascript": "javascript", "js": "js"
            , "cpp": "cpp", "sql": "sql", "actionscript3": "actionscript3"
            , "ruby": "ruby","bash": "bash", "groovy": "groovy", "c": "c"
            , "coldfusion": "coldfusion", "plain": "plain", "javafx": "javafx"
            , "patch": "patch", "jscript": "jscript", "jfx": "jfx", "pl": "pl"
            , "erl": "erl", "powershell": "powershell"
            // Custom extension-to-built-in mapping. Add yours here.
            , 'txt':'text', 'cs':'csharp', 'ru':'ruby'
        }

    // this is a one-page application. Both, the git server and the UI are served
    // from exactly the same URI. Our server does not know (or care) what URL it serves.
    function get_full_application_uri(){
        return location.href.substr(0,location.href.indexOf('\/#'))
    }

    var git_hosting_providers_map = [
        // git@gitorious.org:git_http_backend_py/git_http_backend_py.git
        // http://git.gitorious.org/git_http_backend_py/git_http_backend_py.git
        // git://gitorious.org/git_http_backend_py/git_http_backend_py.git
        // translates commit's page into:
        // http://gitorious.org/git_http_backend_py/git_http_backend_py/commit/2822ec527b0e23d64436e680668bdc7a9dea1809
        // I.e. (a) ".git" is dropped. (b) "." replaced by "_"
        {
            'host_regex': 'gitorious.org',
            'url_assembler': function (url, id, jqobj_to_update) {
                var _trash
                url = url.substr(url.indexOf('gitorious.org')+ 'gitorious.org/'.length, url.length)
                try {url = url.trim()} catch (_trash){}
                url = 'http://gitorious.org/' + url.replace(/.git$/,'').replace('.','_') + '/commit/' + id
                jqobj_to_update.html('<a href="' + url + '" target="_blank">' + url.substr(7,50) + '...</a>')
            }
        },
        // git@github.com:dvdotsenko/git_http_backend.py.git
        // https://dvdotsenko@github.com/dvdotsenko/git_http_backend.py.git
        // git://github.com/dvdotsenko/git_http_backend.py.git
        // translates commit URI to:
        // httpS://github.com/dvdotsenko/git_http_backend.py/commit/c5e491e6f4f2def88b15db18b8e45697eab4663e
        // I.e. (a) ".git" is dropped.
        {
            'host_regex': 'github.com',
            'url_assembler': function (url, id, jqobj_to_update) {
                var _trash
                url = url.substr(url.indexOf('github.com')+ 'github.com/'.length, url.length)
                try {url = url.trim()} catch (_trash){}
                url = 'https://github.com/' + url.replace(/.git$/,'') + '/commit/' + id
                jqobj_to_update.html('<a href="' + url + '" target="_blank">' + url.substr(8,50) + '...</a>')
            }
        },
        // If no compatible hosting provider is found, say so.
        {
            'host_regex': '',
            'url_assembler': function (url, id, jqobj_to_update) {
                jqobj_to_update.html('Cannot be determined.')
            }
        }
    ]


    function guess_remote_homepage(response_data, jqobj_to_update) {
        // this function tries to guess the HTTP homepage for the commit
        // based on git URI.
        // at this time, detection of commit URIs for following Git hositng vendors
        // is supported:
        //  GitHub, Gitorious
        // The guessing logic is not in any way officially blessed by the vendors,
        // so expect frequent breakage caused by changes on vendors' side.

        var _full_app_uri = get_full_application_uri()
          , uri = response_data.data.url
        // uri = _full_app_uri + '/asdf/qwer/zxvc.df'
        if (uri.indexOf(_full_app_uri) > -1 ) {
            // the submodule is hosted on our own, this vary server.
            uri = uri.substr(_full_app_uri.length, uri.length)
            uri = _full_app_uri + '/#browse' + uri
            jqobj_to_update.html(
                '<a href="' + uri + '" target="_blank">' + url.substr(0,58) + '...</a>'
            )
        } else {
            for (var i = 0, l = git_hosting_providers_map.length; i < l; i++) {
                if (uri.indexOf(git_hosting_providers_map[i].host_regex) > -1) {
                    git_hosting_providers_map[i].url_assembler(
                        uri,
                        response_data.data.id,
                        jqobj_to_update
                    )
                    i = l
                }
            }
        }
    }

    function render_folder_listing(parent_jqobj, response_data) {
        var i, _t, _di
            , _path_prefix = response_data.meta.path
        for (i = response_data.data.length-1; i > -1; i--) {
            _di = response_data.data[i]
            _t = $('<span><span style="display: inline-block;"><a href="#browse'+_path_prefix+'/'+_di['name']+'">'+_di['name']+'</a></span> </span>')
            for (var prop in _di) {
                _t.attr('data-filelister-'+prop, _di[prop])
            }
            if ( _di.type == 'folder' || _di.type == 'submodule' ) {
                _t.attr('data-filelister-typegroup',1)
            } else {
                _t.attr('data-filelister-typegroup',2)
            }
            if (_di.is_repo){
                _display_type = 'repo'
            } else {
                _display_type = _di.type
            }
            _t.children('span')
                .addClass('folder_list_item_label')
                .addClass(_display_type + '_decor')
            _t.attr('data-filelister-id',i)
                .addClass('folder_list_item_inline')
                .appendTo(parent_jqobj)
        }
    }

    function sort_elements_by_attr(parent_jqobj, sortables_selector, original_rules, options) {
        /*
        (jQuery-specific) Sorts elements of a parent container by
        ranked attribute(s). This phisically moves the elements around the DOM.
        Supports multiple ranking parameters (allowing nested group sorting).

        @param parent_obj A jQuery object pointing to parent container, whose
            children will be sorted.

        @param sortable_selector A string compatible with jQuery selector format
            that allows jQuery to get a list of DOM objects to sort.

        @param original_rules An array of arrays listing the elements by which the elements
            are to be sorted. Example [['arg1','asc'],['arg2','desc'],['arg3']]
            Shorthans are allowed:
                'arg1' = [['arg1','asc']]
                ['arg1','arg2'] = [['arg1','asc'],['arg2','asc']]

        @param options (optional) An object whose properties provide auxiliary context data
            for the process.
            One wired-up option is attr_name_prefix

        @return Nothing
        */

        var i, j, _l // we use these for "for" loops
        if (!options) {options = {}}
        // we allow one-arg (string) entry for sort_by value 
        // but need to convert that into array.
        // also because we are messing around with the rules obj, we need a new one
        var rules
        if (typeof(original_rules)=='string'){
            rules = [original_rules]
        } else {
            rules = original_rules.slice(0)
        }
        for (i = 0, _l = rules.length; i < _l; i++) {
            if (typeof(rules[i])=='string'){
                rules[i] = [rules[i],'asc']
            }
        }
        rules.reverse()

        var _san // string representing full name of attribute by which we sort
            , _so // int representing the order (+1 for Asc, -1 for Desc)
            , attr_prefix = options['attr_name_prefix'] ? options['attr_name_prefix'] : ''
            , sortables = parent_jqobj.children(sortables_selector).get()
            , A, B, AN, BN
            , order_flags = {'asc':1,'ASC':1,'Asc':1,'a':1,'A':1,'desc':-1,'DESC':-1,'Desc':-1,'d':-1,'D':-1}
        for (i = 0; i < _l; i++) {
            _san = attr_prefix + rules[i][0]
            _so = order_flags[rules[i][1]]
            sortables.sort(function(a, b) {
                A = $(a).attr(_san).toLowerCase()
                B = $(b).attr(_san).toLowerCase()
                AN = Number(A)
                BN = Number(B)
                if ( !isNaN(AN) && !isNaN(BN) ) {
                    return (AN < BN) ? -1*_so : (AN > BN) ? 1*_so : 0
                } else {
                    return (A < B) ? -1*_so : (A > B) ? 1*_so : 0
                }
            })
        }
        // append of an element REMOVES it from original place because there
        // can only be one instance of an instance on the DOM. YEY!
        // Inspired by http://www.onemoretake.com/2009/02/25/sorting-elements-with-jquery/
        parent_jqobj.hide()
        $.each(sortables, function(i, obj) { parent_jqobj.append(obj) })
        parent_jqobj.show()
    }

    function relative_time_format(time) {
        /* Converts RFC 1123 timestamp strings into Date instance,
         * calculated difference from "now" and returns textual
         * representation of relative difference.
         *
         * @param time A string of format "Sun Oct 31 05:15:14 2010 UTC"
         *
         * @retrun A string like "A few seconds ago", "5 minutes ago",
         *      "2 days ago", "3 months ago"
         */

        var _d = ( new Date() - new Date(time) ) / 60000 // will be float with # of minutes ago.
        // _d is Munutes
        if (_d < 2) {
            return 'A minute'
        } else if (_d < 60) {
            return _d.toFixed(1) + ' minutes'
        } else if (_d < 1440) {
            return (_d / 60).toFixed(1) + ' hours'
        } else if (_d < 2880) {
            return 'A day'
        } else {
            return (_d / 1440).toFixed(0) + ' days'
        }
    }

    function add_path_crumbs(response_data) {
        // creating section data for clickable "crumbs" address line
        // turns 'qwer/asdf/zxvc'
        // into [['qwer','qwer'],['asdf','qwer/asdf'],...]
        var _parent_links = []
            ,_path_so_far = ''
            ,_path = response_data['meta']['path'].split('/')
        for (_e in _path){
            if (_path[_e]) {
                _path_so_far = _path_so_far + '/' + _path[_e]
                _parent_links.push([_path[_e] , _path_so_far])
            }
        }
        // Because we check for non-empty path element above, ref to root folder is lost. Adding:
        _parent_links = [[get_full_application_uri(),'/']].concat(_parent_links)
        response_data['meta']['path'] = _path_so_far // this just adds "/" when needed."
        response_data['meta']['path_last_section'] = _parent_links.pop()[0]
        if (_parent_links.length) {
            response_data['meta']['path_first_section'] = _parent_links.shift()
        }
        response_data['meta']['path_sections'] = _parent_links
    }

    function make_editable(jqobj, contents_changed_callback) {
        // path - A string with the path to the repo, relative to content_path.
        // rpc_call_name - A string with name of the RPC function that
        //  handles storage of changed data.

        jqobj.bind(
            'click',
            {'contents_changed_callback':contents_changed_callback},
            function (event)
            {
                jqobj.hide()
                var original_text = jqobj.text()
                  , ta = $('<textarea class="bodylike_text">'+ original_text +'</textarea>')
                ta.insertAfter(jqobj).elastic().focus().bind(
                    'blur',
                    {
                        'original_text':original_text,
                        'original_jqobj': jqobj,
                        'contents_changed_callback':event.data.contents_changed_callback
                    },
                    function (event){
                        var _ta = $(this)
                          , _jqobj = event.data.original_jqobj
                          , _txt = this.value
                        if (event.data.original_text != _txt) {
                            event.data.original_jqobj.text(_txt)
                            event.data.contents_changed_callback.call(
                                event.data.original_jqobj,
                                _txt
                            )
                        }
                        _ta.remove()
                        _jqobj.show()
                    }
                )
            })
    }

    function render_browser_content(response_data, parent_jqobj) {
        // adding path crumbs to the data and rendering just the crumbs
        add_path_crumbs(response_data)
        // now we need to figure out what to render.
        // 'repofile','file', 'repo' are specially formatted.
        // the rest is "folder-like" whether inside or outside of repo.
        var _b, _t = response_data.type
        if (_t == 'repoitem' || _t == 'file' ) {
            parent_jqobj.html(
                $('#browse_base_tmpl').tmpl(
                    response_data,
                    {
                        'get_full_application_uri':get_full_application_uri,
                        'title':'File details'
                    }
                )
            )
            _b = $('#browse_content', parent_jqobj)
            var _syntax_template = _syntax_highlighter_template_map[response_data.data.type.extension]
            if (!_syntax_template && response_data.data.data) {
                // Ugh!!!! File has no extension, yet body is present, so it was
                // deemed by the server to be Text-like.
                // Let's see inside and guess what type it is
                if (response_data.data.data.substr(0,2) == '#!') {
                    // do we smell hash-bang?
                    _first_line = ' ' + response_data.data.data.substr(2,50)
                        .replace('\r','\n')
                        .split('\n',1)[0]
                        .replace(/\/|\\/, ' ') + ' '
                    _m = _first_line.match(/ (python|perl|ruby|php|bash) /i)
                    if (_m) {
                        _syntax_template = _syntax_highlighter_template_map[_m[1]]
                    } else if (_first_line.match(/ \w*sh /i)) {
                        _syntax_template = 'shell'
                    }
                }
            }
            response_data.meta['syntax_template'] = _syntax_template || 'text'
            response_data.data.data = response_data.data.data || ''
            _b.html(
                $('#browse_content_repoitem_tmpl').tmpl(response_data)
            )
            if ( $('pre', _b) ) {
                _path_to_syntax_highlighter = 'static/syntaxhighlighter/'
                _css = ['styles/shCore.css','styles/shThemeDefault.css']
                _h = $("head")
                for (var i = 0, l = _css.length; i < l; i++ ){
                    _h.append('<link href="'+_path_to_syntax_highlighter+_css[i]+'" rel="stylesheet" type="text/css" />');
                }
                $.getScript(_path_to_syntax_highlighter + 'scripts/shCore.js', function(){
                    $.getScript(_path_to_syntax_highlighter + 'scripts/shAutoloader.js', function(){
                        $.getScript(_path_to_syntax_highlighter + 'scripts/autoloader_actuator.js')
                    })
                })
            }
        } else if (_t == 'repo') {
            // render repo endpoints view.
            parent_jqobj.html(
                $('#browse_base_tmpl').tmpl(
                    response_data,
                    {
                        'get_full_application_uri':get_full_application_uri,
                        'title':'Repo summary'
                    }
                )
            )
            _b = $('#browse_content', parent_jqobj)
            _b.html(
                $('#browse_content_repo_tmpl').tmpl(
                    response_data,
                    {
                        'relative_time_format_fn':relative_time_format,
                        'time_str_to_int_fn':function (t){return (new Date(t)).getTime()},
                        'get_full_application_uri':get_full_application_uri
                    }
                )
            )
            make_editable(
                $('pre', _b),
                function (new_text){
                    $.JSONRPC.call(
                        './rpc/'
                        ,'repocontrol.setdescription'
                        ,[response_data.meta.path, new_text]
                    )
                }
            )
            sort_elements_by_attr(
                $('.repo_endpoints_table tbody', _b),
                'tr',
                [['data-time_stamp','desc']]
            )
        } else if (_t == 'remotelink') {
            // git submodules
            parent_jqobj.html(
                $('#browse_base_tmpl').tmpl(
                    response_data,
                    {
                        'get_full_application_uri':get_full_application_uri,
                        'title':'Remote Link'
                    }
                )
            )
            _b = $('#browse_content', parent_jqobj)
            _b.html(
                $('#browse_content_remotelink_tmpl').tmpl(
                    response_data,
                    {
                        'get_full_application_uri':get_full_application_uri
                    }
                )
            )
            guess_remote_homepage(response_data, $('#remotelink_homepage_uri', _b))
        } else {
            parent_jqobj.html(
                $('#browse_base_tmpl').tmpl(
                    response_data,
                    {
                        'get_full_application_uri':get_full_application_uri,
                        'title':'Folder contents'
                    }
                )
            )
            $('#browse_content', parent_jqobj).html(
                $('#browse_content_folderlist_tmpl').tmpl(response_data)
            )
            _b = $('#browse_content_folderlist', parent_jqobj)
            render_folder_listing(_b, response_data)
            sort_elements_by_attr(
                _b,
                'span',
                [['typegroup','asc'],['name','asc']],
                {'attr_name_prefix':'data-filelister-'}
            )
        }
    }

    var app = $.sammy(function() {
    this.raise_errors = true
    this.debug = true
    this.run_interval_every = 300
    this.template_engine = null
    this.element_selector = '#dynamic'

    this.get('#dashboard/', function() {
        if ( this.$element().children('#dashboard').length == 0 ) {
            this.swap($('#dashboard_tmpl').tmpl({}))
        }
    });
    this.get(/\#about\/.*/, function() {
        if ( this.$element().children('#about').length == 0 ) {
            this.swap($('#about_tmpl').tmpl())
        }
    });
    this.get(/\#browse\/(.*)/, function() {
        // cutting the corner. Only rerendering if came from elsewhere.
        if ( this.$element().children('#browse_base').length == 0 ) {
            this.swap($('#browse_tmpl').tmpl())
        }

        var _p = this.params['splat'][0] // path as requested. Will be sanitized later by RPC
            ,app_root_element = this.$element() // this = SammyApp.AppContext instance
            // Used to get around the scope problems for "this" in callbacks.
            ,content_jqobj = $('#browse_base')
            // storing pointer to jq-element may seem like a
            // performance thing, but it's actually a way to
            // insure that when callback returns successfully
            // but late (after we already switched to new view)
            // and wants to update the div, a div with the same
            // id will be there, but, the pointer will not
            // be pointing to it or wnywhere.

        var successfn = function (results) {
            // Success Callback for "folder" listing data arrived.
            render_browser_content(results, content_jqobj)
            if (!results.record_time && results['meta']) {
                results['meta']['record_time'] = (new Date()).getTime()
                app_root_element.data(
                    _p, // this one is the original path we sent to RPC. It might have been sanitized after return, so original is better for caching.
                    JSON.stringify(
                        results
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
                './rpc/'
                ,'browser.path_summary'
                ,[_p]
                ,successfn
                ,errorfn
            );
        }
    });
    this.get(/\#viewer\/(.*)/, function() {
        console.log(this.params)
        console.log(this.params['splat'])
    });
    });
    $(function() {
        app.run('#dashboard/');
    });
})(jQuery);