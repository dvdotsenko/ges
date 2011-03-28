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
import jsonrpc_wsgi_application as jrpc
import ges_rpc_methods
import fuzzy_path_handler
import serve_index_file

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
        ['uri_marker','']
    ]
    options = dict(default_options)
    options.update(kw)

    # this unfolds args into options in order of default_options
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
        marker_regex = r''
    selector = git_http_backend.WSGIHandlerSelector()
    selector.add(
        (marker_regex or '/') + '$',
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
        marker_regex + r'/(?P<working_path>.*?)/info/refs\?.*?service=(?P<git_command>git-[^&]+).*$',
        GET = git_inforefs_handler,
        HEAD = git_inforefs_handler
        )
    selector.add(
        marker_regex + r'/(?P<working_path>.*)/(?P<git_command>git-[^/]+)$',
        POST = git_rpc_handler
        )
    selector.add(
        marker_regex + r'/(?P<working_path>.*)$',
        GET = fuzzy_handler,
        HEAD = fuzzy_handler)

    if 'devel' in options or 'debug' in options:
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

def assisted_start(options):
    _help = r'''
ges.py - Git Enablement Server v1.1

Note only the folder that contains folders and object that you normally see
in .git folder is considered a "repo folder." This means that either a
"bare" folder name or a working folder's ".git" folder will be a "repo" folder
discussed in the examples below.

This server automatically creates "bare" repo folders on push.

Note, the folder does NOT have to have ".git" in the name to be a "repo" folder.
You can name bare repo folders whatever you like. If the signature (right files
and folders are found inside) matches a typical git repo, it's a "repo."

Options:
--content_path (Defaults to random temp folder)
    Serving contents of folder path passed in. Accepts relative paths,
    including things like "./../" and resolves them agains current path.

    (If you set this to actual .git folder, you don't need to specify the
    folder's name on URI as the git repo will be served at the root level
    of the URI.)

    If not specified, a random, temp folder is created in the OS-specific
    temporary storage path. This folder will be NOT be deleted after
    server exits unless the switch "--remove_temp" is used.

--remove_temp (Defaults to False)
    When --content_path is not specified, this server will create a folder
    in a temporary file storage location that is OS-specific and will NOT
    remove it after the server shuts down.
    This switch, if included on command line, enables automatic removal of
    the created folder and all of its contents.

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

--port (Defaults to 8888)

--demo (Defaults to False)
    You do not have to provide any arguments for this option. It's a switch.
    If "--demo" is part of the command-line options, a sample tree of folders
    with some repos will be extracted into the folder specified as content_path.

    If --content_path was not specified (we use temp folder) and "--demo"
    switch is present, we assume --remove_temp is on.

Examples:

ges.py
    (no arguments)
    A random temp folder is created on the file system and now behaves as the
    root of the served git repos folder tree.

ges.py --demo
    This server is shipped with a small demo tree of Git repositories. This
    command deploys that tree into a temp folder and deletes that temp folder
    after the server is shut down.

ges.py --content_path "~/somepath/repofolder" --uri_marker "myrepo"
    Will serve chosen repo folder as http://localhost/myrepo/ or
    http://localhost:8888/does/not/matter/what/you/type/here/myrepo/
    This "repo uri marker" is useful for making a repo server appear as part of
    a server applications structure while serving from behind a reverse proxy.

cd c:\myproject_workingfolder\.git
ges.py --port 80 --content_path '.'
    This project's repo will be one and only served directly over
    http://localhost/
'''

#    options = dict([
#        ['content_path',None],
#        ['static_content_path', None],
#        ['uri_marker',''],
#        ['port', None],
#        ['devel', False],
#        ['demo',False],
#        ['remove_temp',False]
#    ])

    # let's decide what port to serve on.
    port = options['port']
    if not port:
        import socket
        # let's see if we can reuse our preferred default of 8888
        s = socket.socket()
        try:
            s.bind(('',8888))
            ip, port = s.getsockname()
        except:
            pass
        s.close()
        del s
        if not port:
            # looks like our default of 8888 is already occupied.
            # taking next available port.
            s = socket.socket()
            s.bind(('',0))
            ip, port = s.getsockname()
            s.close()
            del s
    options['port'] = port

    # next we determine if the static server contents folder is visible to us.
    if not options['static_content_path'] or not os.path.isfile(
                os.path.join(
                    options['static_content_path'],
                    'static',
                    'favicon.ico'
                    )):
        if sys.path[0] and os.path.isfile(os.path.join(sys.path[0],'static','favicon.ico')):
            options['static_content_path'] = os.path.join(sys.path[0],'static')
        else:
            raise Exception('G.E.S.: Specified static content directory - "%s" - does not contain expected files. Please, provide correct "static_content_path" variable value.' %  options['static_content_path'])

    # now we pick a random temp folder for Git folders tree if none were specified.
    if options['content_path']:
        CONTENT_PATH_IS_TEMP = False
    else:
        import tempfile
        import shutil
        CONTENT_PATH_IS_TEMP = True
        options['content_path'] = tempfile.mkdtemp()

    if options['demo']:
        import zipfile
        demo_repos_zip = os.path.join(sys.path[0],'test','sample_tree_of_repos_v2.zip')
        try:
            zipfile.ZipFile(demo_repos_zip).extractall(options['content_path'])
        except:
            pass

    if 'help' in options:
        print _help
    else:
        app = assemble_ges_app(**options)

        import wsgiserver
        httpd = wsgiserver.CherryPyWSGIServer(('0.0.0.0',int(options['port'])),app)

        if options['uri_marker']:
            _s = '"/%s/".' % options['uri_marker']
            example_URI = '''http://localhost:%s/whatever/you/want/here/%s/myrepo.git
    (Note: "whatever/you/want/here" cannot include the "/%s/" segment)''' % (
            options['port'],
            options['uri_marker'],
            options['uri_marker'])
        else:
            _s = 'not chosen.'
            example_URI = 'http://localhost:%s/' % (options['port'])
        print '''
===========================================================================
Run this command with "--help" option to see available command-line options

Chosen repo folders' base file system path:
    %s

Starting GES server on port %s

URI segment indicating start of git repo foler name is %s

Application URI:
    %s

Use Keyboard Interrupt key combination (usually CTRL+C) to stop the server
===========================================================================
''' % (os.path.abspath(options['content_path']),
        options['port'],
        _s,
        example_URI)

        # running with CherryPy's WSGI Server
        try:
            httpd.start()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.stop()
            if (CONTENT_PATH_IS_TEMP and options['remove_temp']) or (CONTENT_PATH_IS_TEMP and options['demo']):
                shutil.rmtree(options['content_path'], True)

if __name__ == "__main__":

    options = dict([
        ['content_path',None],
        ['static_content_path', None],
        ['uri_marker',''],
        ['port', None],
        ['demo',False],
        ['remove_temp',False]
    ])
    # simple command-line options parser that works only with '--option ["va lue"]'
    lastKey = None
    for item in sys.argv:
        if item.startswith('--'):
            options[item[2:]] = True
            lastKey = item[2:]
        elif lastKey:
            options[lastKey] = item.strip('"').strip("'")
            lastKey = None

    assisted_start(options)
