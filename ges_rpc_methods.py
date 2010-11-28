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

import os
from collections import defaultdict
import time

import git

class PathBoundsError(Exception):
    pass
class PathUnfitError(Exception):
    pass
class PathContainsRepoDirError(Exception):
    pass

import mimetypes
mimetypes.add_type('application/x-git-packed-objects-toc','.idx')
mimetypes.add_type('application/x-git-packed-objects','.pack')
mimetypes.add_type('text/plain','.cs')

class BaseRPCClass(object):

    def __init__(self, base_path):
        self.base_path = os.path.abspath(base_path)
        self.base_path_len = len(self.base_path)
        self.git_folder_signature = set(['head', 'info', 'objects', 'refs'])

    def _sanitize_path(self, relative_path):
        '''Takes a relative path and evaluates it against base path.

        We are mostly concerned with turning unmangling of path.
        What we check for:
        - when all "../../" are unpacked, the path is a child of self.base_path
        - path does not have to be real physical path. It just has to start
          with real physical path.

        @param relative_path A string like "qwer/asdf/zvcv"

        @param strict A boolean flag If True, all folders in the chain
        from base to the end must be NOT on restricted type list.
            Restricted type list:
             - git repo folder

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
                relative_path.decode('utf8').strip('/').strip('\\')
                )
            )
        if not _full_path.startswith(self.base_path):
            raise PathUnfitError('Path is outside of allowed range.')
        # note, on windows, this path will be delimited with '\' not '/'
        # TODO: Decide if we want to replace the slashes.
        return _full_path[self.base_path_len:].strip('/').strip('\\').replace('\\','/')

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

class PathSummaryProducer(BaseRPCClass):
    '''This class is the mothership for all various functionality
    that produces JSON summary packets for a given path.
    Path can be a real filesystem path and a virtual assembly of
    real + repo + relative-to-repo.
    
    Our client app (JavaScript in the browser) is dumb and cannot know ahead of
    time what type of path is requested, so it cannot route the requests to 
    different, type-specific RPC calls. This is THE RPC function that will
    sort things out and return right, path-type-specific info.
    
    Types supported at this time:
    - regular folder - return list of contents (type 'folder')
    - git repo head - return list of clickable milestones, 'endpoints' (type 'repo')
    - git repo's commit - same as tree.
    - git repo tree - return list of contents (type 'repofolder')
    - git repo blob - return blob info summary with poiters for details.(type 'repoblob')
    '''

    ################
    # File system-specific discovery methods.
    ################

    def _list_dir(self, relative_path):
        '''Returns a list of dictionaries, each containing dir name and some
        metadata on the dir for each dir.

        This is to be called only on a real filesystem dir. This method should
        never be called directly. You should get here through mathership wrapper
        that ensures that the path is real filesystem path.

        We return ONLY the contained dir-type entries. We ignore files.

        @param relative_path A string with relative path to a folder of interest.
            Path must be relative to the 'repo folders base path' preset at
            the time of server instantiation.

        @returns A list of dictionaries of following structure:
            [
                {'name':"folder's name" |, 'is_repo':True |},
                ...
            ]
        '''

        # we get here only when parent code already checked that the relative_path
        # actually refers to an actual file system path and that we are
        # authorized to give an answer.

        _p = os.path.join(
            self.base_path,
            relative_path
            )
        dirs = []
        for name in os.listdir(_p):
            _s = os.path.join(_p, name)
            if os.path.isdir(_s):
                if self.git_folder_signature.issubset([i.lower() for i in os.listdir(_s)]):
                    dirs.append({
                        "name":name,
                        "type":"folder",
                        "is_repo":True
                        })
                else:
                    dirs.append({
                        "name":name,
                        "type":"folder"
                        })
        return dirs

    ################
    # Git repo-specific discovery methods.
    ################

    def _repo_virt_item_summary(self, repo_path, commit_name, obj_path = ''):
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
            _size = _t.size
            _ext = os.path.splitext(_t.name)[1].strip('.')
            if not _ext and _t.size < 64000:
                _mime = 'text/plain'
            else:
                _mime = mimetypes.guess_type(_t.name, False)[0] or 'application/octet-stream'
            _r = (
                'repoitem'
                , {'type': {
                        'mimetype': _mime
                        ,'supermimetype': _mime.split('/',1)[0]
                        ,'extension': _ext
                        }
                    ,'name':_t.name
                    ,'size':_size
                    }
                )
            if _size < 64000 and _mime.startswith('text'): # add: and mime_type is some sort of plain-text or image.
                _r[1]['data'] = _t.data
            return _r
        elif type(_t) == git.Tree:
            items = []
            for _o in _t.values():
                if type(_o) == git.Blob:
                    items.append({'type':'file',
                        'name':_o.name,
                        'size':_o.size,
                        # 'mimetype':_o.mime_type
                        })
                elif type(_o) == git.Tree:
                    items.append({'type':'folder',
                        'name':_o.name
                        })
                elif type(_o) == git.Submodule:
                    items.append({'type':'submodule',
                        'name':_o.name,
                        'url':_o.url,
                        'commit_id':_o.id
                        })
                else:
                    items.append({'type':'unknown',
                        'name':_o.name
                        })
            return 'repofolder', items
        elif type(_t) == git.Submodule:
            return (
                'remotelink'
                , {'type': {
                        'system': 'git',
                        'class': 'submodule'
                        }
                    ,'name':_t.name
                    ,'url':_t.url
                    ,'id':_t.id
                    }
                )
        else:
            raise Exception("Repo object is of unsupported type.")

    def _repo_endpoints_helper(self, _data, _commit):
        _data['id'] = _commit.id
        _data['time'] = time.asctime(_commit.committed_date) + ' UTC' # Without UTC JavaScript thinks
        _data['auth_time'] = time.asctime(_commit.authored_date) + ' UTC' # ... it's a local time stamp.
        _data['author'] = _commit.author.name
        _data['author_email'] = _commit.author.email
        _data['summary'] = _commit.summary

    def _repo_endpoints(self, repo_path):
        _r = git.Repo(
            os.path.join(
                self.base_path,
                repo_path
                )
            )
        _commits = defaultdict(
            lambda: {
                'id':None,
                'time':None,
                'tags': [],
                'branches': []
                }
            )

        for _e in _r.tags:
            # Hmm.. Tags have their own commits it seems.
            # Getting .id from tag gets an commit ID that does not
            # point to a real commit, at least with git-python lib.
            # this is a workaround - asking for commit with name of tag
            # gets us real commit ID.
            _tag_commit = _r.commit(_e.name)
            _commit_data = _commits[_tag_commit.id]
            self._repo_endpoints_helper(_commit_data, _tag_commit)
            _commit_data['tags'].append(_e.name)
        for _e in _r.branches:
            _commit_data = _commits[_e.commit.id]
            self._repo_endpoints_helper(_commit_data, _e.commit)
            _commit_data['branches'].append(_e.name)

        _e = _r.commit('HEAD')
        _commit_data = _commits[_e.id]
        if not _commit_data['id']:
            self._repo_endpoints_helper(_commit_data, _e)
            _commit_data['branches'].append('HEAD')

        _commits_list = [_commits[key] for key in _commits.keys()]
        _commits_list.sort(cmp=lambda a,b: cmp(a['time'],b['time']), reverse=True)
        _d = _r.description
        del _r

        # note, we are returning 2 things here - type of data and data.
        # all repo-info producing methods must do the same.
        # parent code puts 'type' value into proper place in RPC response.
        return 'repo', {
            'endpoints':_commits_list
            ,'description':_d
            }

    def _repo_object_summary(self, repo_path, obj_path):
        '''Entry point method used for getting summary on
        repo random repo objects.

        @param repo_path A string with relative path (against self.base_path)
            to the repo folder. This is already sanitized. Example:
            "projects/super/duperproject.git"

        @param obj_path A string that points to inter-repo virtual objects like
            commits, tags, branches, folders, files. Example:
            "master/folder/file.c"

        @returns A dictionary of info applicable to a type of resource.
        '''
        # obj_path may point to:
        # 1. file inside of a commit (blob)
        # 2. folder inside of a commit (tree)
        # 3. commit (tag, branch, plain commit)
        # 4. nowhere (i.e. = '') which we interpret as "give repo summary"
        # 5. some object that does not exist > Exception.

        # thus, we interpret all obj_path to be like so
        # "[branch|tag|commit][/[resource path within the commit]]"
        # We don't really care if a _commit is a branch, tag, or commit id,
        # because we serve the same "tree" view for all.
        if not obj_path:
            # note, returns tuple of (object_type_string, data_object)
            return self._repo_endpoints(repo_path)
        else:
            _vpath = obj_path.strip('/').split('/',1)
            if len(_vpath) == 2:
                return self._repo_virt_item_summary(repo_path, _vpath[0], _vpath[1])
            else:
                return self._repo_virt_item_summary(repo_path, _vpath[0])

    def get_path_summary(self, relative_path):
        '''Takes a relative path, sanitizes and returns adequate
        summary about the path, if viewing that is allowed.

        @param relative_path A string like "qwer/asdf/zvcv"

        @returns JSON-compatible, complex dictionary object with
             following structure:

        {
           type: |'folder','repo','repoitem','repofolder',null|
           ,data: [
                |list of dictionaries with structure specific to object_type|
            ]
           ,meta: |some object of TBD structure, providing context to the data|
        }

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
        # 1 - type = "folder" contents = returned from _listdir
        # 3 - type = 'repo', contents = returned from repo_end_points
        # 7,8 - type = 'repofolder'
        #       contents = returned from repo_obj_summary
        # 9 - type = 'repoitem'
        #       contents = returned from repo_obj_summary.
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
            if _unconsumed_path:
                # half-way through the path, we bumped into a real filesystem
                # object like a file or a shortcut, not a folder.
                raise PathUnfitError('Requested path may not be viewed.')
            else:
                # repo is not on the path, and path is fully present on file
                # system and points to a folder.
                return {
                    'type':'folder',
                    'data':self._list_dir(_p),
                    'meta':{'path':_p}
                    }
        else:
            # repo is on the path. _unconsumed, thus, points to virtual objects
            # (files, folders) inside of the repo
            data_type, data = self._repo_object_summary(_repo_path, _unconsumed_path)
            return {
                'type':data_type,
                'data':data,
                'meta':{'path':_p}
                }

def assemble_methods_list(path_prefix, *args, **kw):
    return [
        ('browser.path_summary',PathSummaryProducer(path_prefix).get_path_summary)
        ]
