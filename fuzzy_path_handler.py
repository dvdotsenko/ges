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
import os
import git
from wsgiref.headers import Headers
import urllib

# needed for static content server
import time
import email.utils
import mimetypes
mimetypes.add_type('application/x-git-packed-objects-toc','.idx')
mimetypes.add_type('application/x-git-packed-objects','.pack')

import tempfile

class PathBoundsError(Exception):
    pass
class PathUnfitError(Exception):
    pass
class PathContainsRepoDirError(Exception):
    pass

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

        newheaders = headers
        headers = [('Content-type', 'application/octet-stream')] # my understanding of spec. If unknown = binary
        headersIface = Headers(headers)

        for header in newheaders:
            headersIface[header[0]] = '; '.join(header[1:])

        retobj = outIO
        if hasattr(outIO,'fileno') and 'wsgi.file_wrapper' in environ:
            outIO.seek(0)
            retobj = environ['wsgi.file_wrapper']( outIO, self.bufsize )
        # TODO: I think this does not work well on NWSGI 2.0. Talk to Jeff about this for 3.0
        elif hasattr(outIO,'read'):
            outIO.seek(0)
            retobj = iter( lambda: outIO.read(self.bufsize), '' )
        start_response("200 OK", headers)
        return retobj

class FuzzyPathHandler(BaseWSGIClass):
    '''An WSGI app that handles requests for Path elements within a virtual tree.

    This is going to be a pile up of helper handlers, most of which will
    be handling requests for objects within repos' virtual file trees, and
    some that will be getting recources from physical file system in a funny way.
    '''
    # Need:
    # - file server for inter-repo requests.
    # - folder (tree path) as zip handler for inter-repo requests.

    #file:
    # - sanitize the path.
    #
    def __init__(self, **kw):
        '''
        Inputs:
            content_path (mandatory)
                String containing a file-system level path behaving as served root.
        '''
        self.__dict__.update(kw)
        self.base_path = os.path.abspath(kw['content_path'])
        self.base_path_len = len(self.base_path)
        self.git_folder_signature = set(['head', 'info', 'objects', 'refs'])

    def _sanitize_path(self, relative_path):
        '''Takes a relative path and cleans it and evaluates it against base path.

        We are mostly concerned with unmangling of path.
        What we check for:
        - when all "../../" are unpacked, the path is a child of self.base_path
        - path does not have to be real physical path. It just has to start
          with real physical path.

        @param relative_path A string like "qwer/asdf/zvcv"

        @returns relative_path Sanitized relative path string.
        '''

        #TODO: decode URL-encoded, form-encoded paths.
        #      decode('utf8') is very subpar and will break.

        try:
            _u = unicode
        except:
            _u = str
        if type(relative_path) not in (bytes, str, type(''), _u):
            raise PathUnfitError('Path argument is not of right type.')
        _full_path = os.path.abspath(
            os.path.join(
                self.base_path,
                relative_path.decode('utf8').strip('/\\')
                )
            )
        if not _full_path.startswith(self.base_path):
            raise PathUnfitError('Path is outside of allowed range.')
        return _full_path[self.base_path_len:].strip('/\\').replace('\\','/')

    def _find_repo_in_path(self, relative_path):
        '''Takes a path relative to base path and tries to
        find a repo folder somewhere on the path. Breaks the
        loop if repo is found or if mid-path is not a folder anymore.

        The function is useful for separating "virtual" paths to repo
        contents into "real" and "repo-relative" paths. Example:

        If [base/]realfolder/realrepofolder exists on file system,
         realfolder/realrepofolder/commit_label/virtfold/virtfile
        will be split this way:
         ('realfolder/realrepofolder','commit_label/virtfold/virtfile')

        If [base/]realfolder/realrepofolder is a file on file system,
         realfolder/realrepofolder/commit_label/virtfold/virtfile
        will be split this way:
         (None,'realrepofolder/commit_label/virtfold/virtfile')

        @param relative_path A string like "asdf/qwer/zxcv" or ""
            representing the path relative to the base path.

        @returns (repo_path, unconsumed_path) A tuple of two strings.
            If no repo is found repo_path is None (not "") If found
            it is a string with ABSOLUTE path.
            unconsumed_path will be non-empty and will contain unix-styled
            remainder of the path when at some point on the path we run
            out of real filesystem folders. It may be non-empty regardless
            of if the repo was found on the path or not.
            unconsumed_path will "" if all is consumed.
        '''
        # we expect completely sanitized paths here.
        # this means no leading slashes, dirs are separated by unix-like slash /
        repo_path = None
        _path_chain = relative_path.split('/')
        if _path_chain[0] != '':
            # because we don't get leading slash, on non-root paths we don't
            # get a reference to the root - '' - in the array. Inserting:
            _path_chain.insert(0, '')
        _p = self.base_path
        while _path_chain:
            _p = os.path.join(_p,_path_chain.pop(0))
            _d = os.path.isdir(_p)
            if _d and self.git_folder_signature.issubset([i.lower() for i in os.listdir(_p)]):
                repo_path = _p
                break
            elif not _d:
                # it's not a folder. Likely a shortcut or a file. Either way,
                # it's not what we need or can work with .
                # intentionally interrupting the "while" to signal that remaining
                # section of path does not point to a real file system path.
                _path_chain.insert(0,os.path.split(_p)[1])
                break
        del _d, _p
        return repo_path, '/'.join(_path_chain)

    ################
    # Git repo-specific discovery methods.
    ################

    def _get_repo_item_contents(self, repo_path, commit_name, obj_path = ''):
        '''Returns contents of tree or file for a commit (Commit ID, Tag or Branch name)

        @param repo_path A relative file-system path to repo folder against
            self.base_param. Always unix-formatted slashes.

        @param commit_name A string denoting a commit's ID or tag's or branch's name.

        @param obj_path A string (or None) with virtual path to a file or folder
            within the repo.

        @returns (type, data) A tuple of:
            type A string containing the name of object type.
                (Possible values: 'repo', 'repofolder', 'repoitem', None)
            data A JSON-compatible list or dictionary with object-type-specific data.
        '''
        _r = git.Repo(
            os.path.join(
                self.base_path,
                repo_path
                )
            )
        # TODO: evil hackers may give some trash instead of commit name.
        # since gitpython is a wrapper for command line git, this may be scary.
        # Put in the code to sanitize commit_name.
        try:
            _t = _r.commit(commit_name).tree
        except:
            raise PathUnfitError(
                'Requested object "%s" is not found in the repository %s.' % (
                    commit_name + "/" + obj_path
                    ,os.path.join(self.base_path,repo_path)
                    )
                )
        for _i in obj_path.strip('/').split('/'):
            if _i:
                try:
                    _t = _t[_i]
                except:
                    raise PathUnfitError(
                        'Requested object "%s" is not found in the repository %s.' % (
                            '/'.join([commit_name,obj_path])
                            ,os.path.join(self.base_path,repo_path)
                            )
                        )
        if type(_t) == git.Blob:
            # returning: dataIO, mimetype, size, recommended file name.
            return (
                    io.BytesIO(_t.data)
                    ,mimetypes.guess_type(obj_path, False)[0] or 'application/octet-stream'
                    ,len(_t.data)
                    ,os.path.split(obj_path)[1]
                    )
        elif type(_t) == git.Tree:
            _trash, _p = os.path.split(repo_path)
            if _p:
                name_elements = [_p, commit_name]
            else:
                name_elements = [commit_name]
            # the tempfile use is a bit of trickery.
            # we need temp file because it self-destructs when .close()
            # yet, we need git command like to write to it from outside of python.
            # what we do is create the temp file, get name, ask
            # git to put data into that file name in the back
            # When we read() we read from start of what used to be empty file.
            # If git is successful there will be data in it.
            # If zip download stops working, then either the underlying
            # python interpreter is weird (IronPython, Jython) or
            # the tempfile implemnetation had changed to cache the "empty"
            # state of the temp file.
            _tf = tempfile.NamedTemporaryFile(
                suffix = '_%s.zip' % '_'.join(name_elements)
                , delete = True
                )
            try:
                _trash = git.Repo(
                    os.path.join(self.base_path,repo_path)
                    ).git.archive(
                        commit_name
                        ,obj_path
                        ,output = _tf.name
                        ,format = "zip"
                        ,prefix = "%s/" % '/'.join(name_elements)
                        )
                _tf.seek(0) # this is just in case the TF wrapper cached position / old data.
            except:
                raise PathUnfitError(
                            'Requested object "%s" cannot be served in zip format.' % (
                                '/'.join(name_elements)
                                )
                            )
            # returning:
            #   data_IO_obj,
            #   mimetype,
            #   size in bytes. None for size is OK. We send Chunked.
            #   recommended file name.
            return (
                    _tf
                    , 'application/zip'
                    , None
                    , '%s.zip' % '_'.join(name_elements)
                    )
        else:
            raise PathUnfitError(
                        'Requested object "%s" cannot be served in raw format.' % (
                            '/'.join([commit_name,obj_path])
                            )
                        )

    def _get_path_contents(self,relative_path):
        '''Takes a relative path, sanitizes and returns adequate
        summary about the path, if viewing that is allowed.

        @param relative_path A string like "qwer/asdf/zvcv"

        Design notes (may become stale with time):
        # now, we need to figure out what the path represents. Choices:
        # 1. Physical path to folder
        # 2. Physical path to file (we don't support viewing these.)
        # 3. Physical path to repo folder
        # 4. physical path to actual filesystem object inside repo folder
        # 5. Nonexistent path, with start of path a normal folder
        # 6. Nonexistent path, with start of path a normal file
        # 7. Nonexistent path, with start of path a repo folder
        #       and ending in commit (branch, tag) name inside of repo
        # 8. Nonexistent path, with start of path a repo folder
        #       and ending in folder inside repo
        # 9. Nonexistent path, with start of path a repo folder
        #       and ending in file inside repo

        # 2, 6, 4, 5 we error out.
        # 1 - type = "folder" contents = returned from _dir_contents
        # 3 - type = 'repo', contents = returned from _repo_dir_contents('master')
        # 7,8 - type = 'repofolder'
        #       contents = returned from _repo_dir_contents
        # 9 - type = 'repoitem'
        #       contents = returned from _repo_blob
        '''
        # notes:
        # - control flow is done through exceptions. Wrapping code catches
        #   ,interprets and wraps the replies appropriately.
        # - _p (working variable for Path) is always relative to self.base_path
        #   and is always formatted with unix-style slash - "/", even on windows.

        # contracts things like "/../" and ensures that the path is a
        # child of self.base_path. Exception otherwise.
        _p = self._sanitize_path(relative_path)
        # if repo is somewhere on the path, _repo_path is non-Null
        # _unconsumed_path = loosely, a part of path that is not
        #         actually present on file system.
        _repo_path, _unconsumed_path = self._find_repo_in_path(_p)

        if _repo_path == None:
            raise PathUnfitError('Requested path may not be viewed.')
#            if _unconsumed_path:
#                # half-way through the path, we bumped into a real filesystem
#                # object like a file or a shortcut, not a folder.
#                raise PathUnfitError('Requested path may not be viewed.')
#            else:
#                # repo is not on the path, and path is fully present on file
#                # system and points to a folder.
#                # Returns tuple of "type", contents IO obj, sanitized path.
#                return ('folder', _dir_contents(_p), _p)

        # repo is on the path. _unconsumed, thus, points to virtual objects
        # (commits, files, folders) inside of the repo
        # this call may return either file- or folder-specific content.

        # we interpret all obj_path to be like so
        # "[branch|tag|commit][/[resource path within the commit]]"
        # We don't really care if a _commit is a branch, tag, or commit id,
        # because we serve the "element of a tree" view for all.
        # in some cases the "tree" view is a zip of contents. In others,
        # it the contents of a file.
        if not _unconsumed_path:
            # means we need to pick default commit.
            _unconsumed_path = 'HEAD'
        _vpath = _unconsumed_path.strip('/').split('/',1)
        if len(_vpath) == 2:
            # point to commit + object within a commit.
            # returning : dataIOobj, _mimetype, size_in_bytes
            return self._get_repo_item_contents(_repo_path, _vpath[0], _vpath[1])
        else:
            # points to commit's root tree.
            return self._get_repo_item_contents(_repo_path, _vpath[0])

    def __call__(self, environ, start_response):
        selector_matches = (environ.get('wsgiorg.routing_args') or ([],{}))[1]
        if 'working_path' in selector_matches:
            # working_path is a custom key that I just happened to decide to use
            # for marking the portion of the URI that is palatable for static serving.
            # 'working_path' is the name of a regex group fed to WSGIHandlerSelector
            path_info = selector_matches['working_path'].decode('utf8')
        else:
            path_info = environ.get('PATH_INFO', '').decode('utf8')

        # this, i hope, safely turns the relative path into OS-specific, absolute.
        full_path = os.path.abspath(os.path.join(self.content_path, path_info.strip('/\\')))
        _pp = os.path.abspath(self.content_path)
        if not full_path.startswith(_pp):
            return self.canned_handlers(environ, start_response, 'forbidden')
        _p = full_path[len(_pp):].strip('/\\')

        try:
            file_like, _mimetype, _size, _file_name = self._get_path_contents(_p)
        except:
            return self.canned_handlers(environ, start_response, '404')

        # TODO: wire up the time to commit. Until then, there will be no caching
        #  on web client. Ugh!
        mtime = time.time()
        etag, last_modified =  str(mtime), email.utils.formatdate(mtime)
        headers = [
            ('Content-type', 'text/plain')
            ,('Date', email.utils.formatdate(time.time()))
            ,('Last-Modified', last_modified)
            ,('ETag', etag)
        ]
        headersIface = Headers(headers)
        if_modified = environ.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified and (email.utils.parsedate(if_modified) >= email.utils.parsedate(last_modified)):
            return self.canned_handlers(environ, start_response, 'not_modified', headers)
        if_none = environ.get('HTTP_IF_NONE_MATCH')
        if if_none and (if_none == '*' or etag in if_none):
            return self.canned_handlers(environ, start_response, 'not_modified', headers)

        if _size != None:
            headersIface['Content-Length'] = str(_size)
        headersIface['Content-Type'] = _mimetype
        if _file_name:
            # See:
            #  RFC5987
            #   http://greenbytes.de/tech/webdav/rfc5987.html
            #  Use of the Content-Disposition Header Field in the Hypertext Transfer Protocol (HTTP)
            #   http://datatracker.ietf.org/doc/draft-ietf-httpbis-content-disp/?include_text=1
            #  Percent-quoting in Python:
            #   http://stackoverflow.com/questions/1695183/how-to-percent-encode-url-parameters-in-python
            #   http://stackoverflow.com/questions/1361604/how-to-encode-utf8-filename-for-http-headers-python-django
            #  Browser support for RFC5987
            #   http://greenbytes.de/tech/tc2231/#attfnboth
            # Note:
            #  we are using "safe" chars as defined per RFC5987
            _efn = urllib.quote(
                _file_name.encode('utf8')
                , "!#$%&+-^_`{}~"
                )
            if _file_name == _efn:
                # no funky or unicode chars in the name
                headersIface['Content-Disposition'] = (
                    'attachment; filename="%s"' % _file_name
                    ).encode('utf8')
                    
            else:
                # providing both, crippled Latin-1 and utf8-encoded file names.
                # it's possible that the difference is just a space in the file's name.
                _cfn = []
                for c in _file_name:
                    if ord(c) > 255:
                        _cfn.append('_')
                    else:
                        _cfn.append(c)
                headersIface['Content-Disposition'] = (
                    'attachment; filename="%s"; filename*=utf-8\'\'%s' % (
                        ''.join(_cfn)
                        ,_efn
                        )
                    ).encode('utf8')
                    

        return self.package_response(file_like, environ, start_response, headers)
