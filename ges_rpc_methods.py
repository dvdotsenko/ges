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
import git.utils

class PathBoundsError(Exception):
    pass

class PathUnfitError(Exception):
    pass

class PathContainsRepoDirError(Exception):
    pass

class browser_rpc(object):
    def __init__(self, path_prefix):
        self.base_path = os.path.abspath(path_prefix)
        self.base_path_len = len(self.base_path)

    def _sanitize_dir_path(self, relative_path, strict = True):
        '''Takes a relative path and evaluates it against base path.

        The relative path must be a folder within the base path.
        Else, an Exception is raised.

        @param relative_path A string like "qwer/asdf/zvcv"

        @param strict A boolean flag If True, all folders in the chain
        from base to the end must be NOT on restricted type list.
            Restricted type list:
             - git repo folder

        @returns relative_path Sanitized relative path string.
        '''
        try:
            _u = unicode
        except:
            _u = str
        if type(relative_path) not in (bytes, str, type(''),_u):
            raise PathUnfitError('Path argument is not of right type.')
        _full_path = os.path.abspath(os.path.join(
            self.base_path,
            relative_path.strip('\\').strip('/')
            ))
        if not _full_path.startswith(self.base_path):
            raise PathUnfitError('Path is outside of allowed range.')
        if not os.path.isdir(_full_path):
            raise PathUnfitError('Path is not a directory')
        relative_path = _full_path[self.base_path_len:].strip('/').strip('\\')
        if strict and relative_path:
            path_chain = relative_path.split(os.sep)
            while path_chain:
                if git.utils.is_git_dir(os.path.join(self.base_path, *path_chain)):
                    raise PathUnfitError('A parent folder on the path is a Git repo folder. Browsing inside of Git repo folders is meaningless.')
                trash = path_chain.pop(-1)
        return relative_path

    def list_dirs(self, path):
        '''Returns a list of dictionaries containing dir name and some metadata
        on the dir for each dir.

        @param path A string with relative path to a folder of interest.
            Path must be relative to the 'repo folders base path' preset at
            the time of server instantiation.
        '''
        # note, the _sanitize.. call below may raise Exception('Explanation')
        path = os.path.join(
            self.base_path,
            self._sanitize_dir_path(path, True)
            )
        dirs = []
        for name in os.listdir(path):
            if os.path.isdir(os.path.join(path, name)):
                if git.utils.is_git_dir(os.path.join(path,name)):
                    dirs.append({
                        "name":name,
                        "is_git_dir":True
                        })
                else:
                    dirs.append({
                        "name":name
                        })
        path = path[self.base_path_len:].replace(os.sep, '/') #.strip('/')
        return {'path':path, 'dirs':dirs}

def assemble_methods_list(path_prefix, uri_marker = '', settings = {}):
    _browser = browser_rpc(path_prefix)
    return [
        ('browser_listdir',_browser.list_dirs),
        ('browser.listdir',_browser.list_dirs)
        ]
