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
import os.path
import os
import sys

import git_http_backend
import wsgiserver
import jsonrpc_wsgi_application as jrpc
import ges_rpc_methods
import fuzzy_path_handler
import serve_index_file

# we are using a custom version of subprocess.Popen - PopenIO 
# with communicateIO() method that starts reading into mem
# and switches to hard-drive persistence after mem threshold is crossed.
if sys.platform == 'cli':
    import subprocessio.subprocessio_ironpython as subprocess
else:
    import subprocess
try:
    # will fail on cPython
    t = subprocess.PopenIO
except:
    import subprocessio.subprocessio as subprocess

def assemble_ges_app(*args, **kw):
    '''
    Assembles G.E.S. WSGI application.

    path_prefix = '.',
    static_content_path = './static'
    repo_uri_marker = ''

    path_prefix (Defaults to '.' = "current" directory)
        The path to the folder that will be the root of served files. Accepts relative paths.

    repo_uri_marker (Defaults to '')
        Acts as a "virtual folder" separator between decorative URI portion and
        the actual (relative to path_prefix) path that will be appended to
        path_prefix and used for pulling an actual file.

        the URI does not have to start with contents of repo_uri_marker. It can
        be preceeded by any number of "virtual" folders. For --repo_uri_marker 'my'
        all of these will take you to the same repo:
            http://localhost/my/HEAD
            http://localhost/admysf/mylar/zxmy/my/HEAD
        This WSGI hanlder will cut and rebase the URI when it's time to read from file system.

        Default of '' means that no cutting marker is used, and whole URI after FQDN is
        used to find file relative to path_prefix.

    returns WSGI application instance.
    '''

    default_options = [
        ['content_path','.'],
        ['static_content_path', './static'],
        ['uri_marker',''],
        ['devel', False]
    ]
    options = dict(default_options)
    options.update(kw)
    args = list(args) # need this to allow .pop method on it.
    while default_options and args:
        _d = default_options.pop(0)
        _a = args.pop(0)
        options[_d[0]] = _a
    for _e in ['content_path','static_content_path']:
        options[_e] = os.path.abspath(options[_e].decode('utf8'))
    options['uri_marker'] = options['uri_marker'].decode('utf8')
    if not os.path.isfile(os.path.join(options['static_content_path'],'favicon.ico')):
        raise Exception('G.E.S.: Specified static content directory - "%s" - does not contain expected files. Please, provide correct "static_content_path" variable value.' % options['static_content_path'])

    # assembling JSONRPC WSGI app
    # it has two parts:
    #  (a) ges-specific RPC methods that return JSON-compatible objects
    #  (b) generic WSGI JSONRPC wrapper for stuff like (a)
    _methods_list = ges_rpc_methods.assemble_methods_list(
        options['content_path']
        )
    _jsonrpc_app = jrpc.WSGIJSONRPCApplication()
    for path, method_pointer in _methods_list:
        _jsonrpc_app.add_method(path, method_pointer)

    _serve_index_file = serve_index_file.ServeIndexFile(**options)

    # assembling static file server WSGI app
    _static_server_app = git_http_backend.StaticWSGIServer(content_path = options['static_content_path'])

    # git_http_backend-specific server components.
    git_inforefs_handler = git_http_backend.GitHTTPBackendInfoRefs(**options)
    git_rpc_handler = git_http_backend.GitHTTPBackendSmartHTTP(**options)
    fuzzy_handler = fuzzy_path_handler.FuzzyPathHandler(**options)

    if options['uri_marker']:
        marker_regex = r'(?P<decorative_path>.*?)(?:/'+ options['uri_marker'] + ')'
    else:
        marker_regex = ''
    selector = git_http_backend.WSGIHandlerSelector()
    selector.add(
        marker_regex + r'/$',
        _serve_index_file)
    selector.add(
        marker_regex + r'/rpc[/]*$',
        _jsonrpc_app)
    selector.add(
        marker_regex + r'/favicon.ico$',
        GET = _static_server_app,
        HEAD = _static_server_app)
    selector.add(
        marker_regex + r'/static/(?P<working_path>.*)$',
        GET = _static_server_app,
        HEAD = _static_server_app)
    selector.add(
        marker_regex + r'(?P<working_path>.*?)/info/refs\?.*?service=(?P<git_command>git-[^&]+).*$',
        GET = git_inforefs_handler,
        HEAD = git_inforefs_handler
        )
    selector.add(
        marker_regex + r'(?P<working_path>.*)/(?P<git_command>git-[^/]+)$',
        POST = git_rpc_handler
        )
    selector.add(
        marker_regex + r'(?P<working_path>.*)$',
        GET = fuzzy_handler,
        HEAD = fuzzy_handler)

    if 'devel' in options and options['devel']:
        import wsgilog
        return wsgilog.WsgiLog(selector, tostream=True, toprint=True)
    return selector

class ShowVarsWSGIApp(object):
    def __init__(self, *args, **kw):
        pass
    def __call__(self, environ, start_response):
        status = '200 OK'
        response_headers = [('Content-type','text/plain')]
        start_response(status, response_headers)
        for key in sorted(environ.keys()):
            yield '%s = %s\n' % (key, unicode(environ[key]).encode('utf8'))

def run_with_command_line_input():
    _help = r'''
ges.py - Git Enablement Server v1.0

Note only the folder that contains folders and object that you normally see
in .git folder is considered a "repo folder." This means that either a
"bare" folder name or a working folder's ".git" folder will be a "repo" folder
discussed in the examples below.

This server automatically creates "bare" repo folders on push.

Note, the folder does NOT have to have ".git" in the name to be a "repo" folder.
You can name bare repo folders whatever you like. If the signature (right files
and folders are found inside) matches a typical git repo, it's a "repo."

Options:
--content_path (Defaults to '.' - current directory)
	Serving contents of folder path passed in. Accepts relative paths,
	including things like "./../" and resolves them agains current path.

	If you set this to actual .git folder, you don't need to specify the
	folder's name on URI.

--uri_marker (Defaults to '')
	Acts as a "virtual folder" - separator between decorative URI portion
	and the actual (relative to path_prefix) path that will be appended
	to path_prefix and used for pulling an actual file.

	the URI does not have to start with contents of repo_uri_marker. It can
	be preceeded by any number of "virtual" folders.
	For --repo_uri_marker 'my' all of these will take you to the same repo:
		http://localhost/my/HEAD
		http://localhost/admysf/mylar/zxmy/my/HEAD
	If you are using reverse proxy server, pick the virtual, decorative URI
	prefix / path of your choice. This hanlder will cut and rebase the URI.

	Default of '' means that no cutting marker is used, and whole URI after
	FQDN is used to find file relative to path_prefix.

--port (Defaults to 8080)

Examples:

cd c:\myproject_workingfolder\.git
c:\tools\ges\ges.py --port 80
	(Current path is used for serving.)
	This project's repo will be one and only served directly over
	 http://localhost/

cd c:\repos_folder
c:\tools\ges\ges.py
	(note, no options are provided. Current path is used for serving.)
	If the c:\repos_folder contains repo1.git, repo2.git folders, they
	become available as:
	 http://localhost:8080/repo1.git  and  http://localhost:8080/repo2.git

~/myscripts/ges.py --content_path "~/somepath/repofolder" --uri_marker "myrepo"
	Will serve chosen repo folder as http://localhost/myrepo/ or
	http://localhost:8080/does/not/matter/what/you/type/here/myrepo/
	This "repo uri marker" is useful for making a repo server appear as a
	part of some REST web application or make it appear as a part of server
	while serving it from behind a reverse proxy.

./ges.py --content_path ".." --port 80
	Will serve the folder above the "ges" (in which
	ges.py happened to be located.) A functional url could be
	 http://localhost/ges/ges.py
	Let's assume the parent folder of ges folder has a ".git"
	folder. Then the repo could be accessed as:
	 http://localhost/.git/
	This allows ges.py to be "self-serving" :)
'''
    import sys

    command_options = dict([
        ['content_path','.'],
        ['static_content_path', None],
        ['uri_marker',''],
        ['port', '8888'],
        ['devel', False]
    ])

    lastKey = None
    for item in sys.argv:
        if item.startswith('--'):
            command_options[item[2:]] = True
            lastKey = item[2:]
        elif lastKey:
            command_options[lastKey] = item.strip('"').strip("'")
            lastKey = None

    if not command_options['static_content_path']:
        print(dir())
        if '__file__' in dir() and os.path.isfile(os.path.join(os.path.split(__file__)[0],'static','favicon.ico')):
            command_options['static_content_path'] = os.path.join(os.path.split(__file__)[0],'static')
        else:
            raise Exception('G.E.S.: Specified static content directory - "%s" - does not contain expected files. Please, provide correct "static_content_path" variable value.' %  command_options['static_content_path'])

    if 'help' in command_options:
        print _help
    else:
        app = assemble_ges_app(**command_options)

        import wsgiserver
        httpd = wsgiserver.CherryPyWSGIServer(('127.0.0.1',int(command_options['port'])),app)
#        from wsgiref import simple_server
#        httpd = simple_server.make_server('127.0.0.1',int(command_options['port']),app)

        if command_options['uri_marker']:
            _s = '"/%s/".' % command_options['uri_marker']
            example_URI = '''http://localhost:%s/whatever/you/want/here/%s/myrepo.git
    (Note: "whatever/you/want/here" cannot include the "/%s/" segment)''' % (
            command_options['port'],
            command_options['uri_marker'],
            command_options['uri_marker'])
        else:
            _s = 'not chosen.'
            example_URI = 'http://localhost:%s/' % (command_options['port'])
        print '''
===========================================================================
Run this command with "--help" option to see available command-line options

Starting GES server...
	Port: %s
	Chosen repo folders' base file system path: %s
	URI segment indicating start of git repo foler name is %s

Application URI:
    %s

Use Keyboard Interrupt key combination (usually CTRL+C) to stop the server
===========================================================================
''' % (command_options['port'], os.path.abspath(command_options['content_path']), _s, example_URI,example_URI)

        # running with CherryPy's WSGI Server
        try:
            httpd.start()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.stop()
#        # running with cPython's builtin WSGIREF
#        try:
#            httpd.serve_forever()
#        except KeyboardInterrupt:
#            pass

if __name__ == "__main__":
    run_with_command_line_input()
