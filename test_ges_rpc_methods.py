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

execpath = os.getcwd()
sys.path.append(os.path.join(execpath, 'gitpython\lib'))

import unittest
import ges_rpc_methods as grm
import tempfile
import shutil
import zipfile

class test_GesRPCMethods(unittest.TestCase):

    def setUp(self):
        _p = tempfile.mkdtemp()
        zipfile.ZipFile('./test/sample_tree_of_repos_v2.zip').extractall(_p)
        self.base_path = os.path.join(_p, 'reposbase')
        self._rpc_tree = dict(grm.assemble_methods_list(self.base_path))

    def tearDown(self):
        shutil.rmtree(self.base_path, True)

    def test_01_browser_methods(self):
        _m = self._rpc_tree['browser.path_summary']

        self.assertEquals(
            _m(''),
            {
            'type':'folder'
            ,'data':[
                {'type': 'folder','name': 'projects'},
                {'type': 'folder','name': 'teams'},
                {'type': 'folder','name': 'users'}
                ]
            ,'meta':{'path':''}
            }
        )
        self.assertEquals(
            _m('/'),
            {
            'type':'folder'
            ,'data':[
                {'type': 'folder','name': 'projects'},
                {'type': 'folder','name': 'teams'},
                {'type': 'folder','name': 'users'}
                ]
            ,'meta':{'path':''}
            }
        )
        self.assertEquals(
            _m('\\'),
            {
            'type':'folder'
            ,'data':[
                {'type': 'folder','name': 'projects'},
                {'type': 'folder','name': 'teams'},
                {'type': 'folder','name': 'users'}
                ]
            ,'meta':{'path':''}
            }
        )
        # crossing fingers and hoping the order is same on all platforms.
        self.assertEquals(
            _m('projects'),
            {'data': [
                {'type': 'folder','name': 'common_files'},
                {'type': 'folder','is_repo': True, 'name': 'demorepoone'}
                ],
             'meta': {'path': 'projects'},
             'type': 'folder'}
        )
        self.assertEquals(
            _m('projects/common_files'),
            {
            'type':'folder'
            ,'data':[]
            ,'meta':{'path':'projects/common_files'}
            }
        )
        # TODO: i bet order is messing up this test. Need to break it up into pieces.
#        self.assertEquals(
#            _m('projects/demorepoone'),
#            {'data': {'endpoints': [
#                {'branches': ['master'], 'author': 'D.Dotsenko', 'author_email': 'dotsa@hotmail.com', 'tags': [], 'summary': 'Adding submodule for testing.', 'time': 'Sun Oct 31 05:15:14 2010 UTC', 'auth_time': 'SatOct 30 08:20:33 2010 UTC', 'id': '3408e8f7720eff4a1fd16e9bf654332036c39bf8'}, {'branches': ['experimental'], 'author': 'D. Dotsenko', 'author_email': 'dotsa@hotmail.com', 'tags': [], 'summary': 'Starting evern more radical feature.', 'time': 'Mon Oct 18 01:22:24 2010 UTC', 'auth_time': 'Mon Oct 18 01:22:24 2010 UTC', 'id': '885f5a29f0bede312686c9cabcef1dcd9c418fb4'}, {'branches': ['stable'], 'author': 'D. Dotsenko', 'author_email': 'dotsa@hotmail.com', 'tags': ['0.2'], 'summary': 'Adding new feature.', 'time': 'Mon Oct 18 01:18:55 2010 UTC', 'auth_time': 'Mon Oct 18 01:18:55 2010 UTC', 'id': '263e545b2227821bd7254bfb60fb11dae3aa9d0b'}, {'branches': [], 'author': 'D. Dotsenko', 'author_email': 'dotsa@hotmail.com', 'tags': ['0.1'], 'summary': 'Changed firstdoc.txt', 'time': 'Mon Oct 18 01:17:21 2010 UTC', 'auth_time': 'Mon Oct 18 01:17:21 2010 UTC', 'id': '457c6388d3d6f2608038a543e272e7fc1dfc2082'}], 'description': "Unnamed repository; edit this file 'description' to name the repository."}, 'meta': {'path': u'projects/demorepoone'}, 'type': 'repo'}
#        )
        self.assertEquals(
            _m('projects/demorepoone/master'),
            {'data': [
                {'type': 'file', 'name': 'firstdoc.txt', 'size': 65}
               ,{'url': 'git://gitorious.org/git_http_backend_py/git_http_backend_py.git'
                ,'commit_id': '74bc53cdcfd1804b9c3d1afad4db0999931a025c'
                ,'type': 'submodule', 'name': 'somesubmodule'}
               ,{'type': 'file', 'name': '.gitmodules', 'size': 262}
               ,{'type': 'file', 'name': '.gitignore', 'size': 300}
               ,{'type': 'folder', 'name': 'somefolder'}
               ]
            ,'meta': {'path': u'projects/demorepoone/master'}
            ,'type': 'repofolder'}
        )
        self.assertEquals(
            _m('projects/demorepoone/master/somefolder'),
            {'data': [
                {'url': 'git://gitorious.org/git_http_backend_py/git_http_backend_py.git'
                 , 'commit_id': '08a4dca6a06e2f8893a955d757d505f0431321cb'
                 , 'type': 'submodule'
                 , 'name': 'nestedmodule'}
            ]
            , 'meta': {'path': u'projects/demorepoone/master/somefolder'}
            , 'type': 'repofolder'}
        )
        self.assertEquals(
            _m('projects/demorepoone/master/firstdoc.txt'),
            {'data': {
                'data': 'Line one here.\r\nLine two here.\r\nLine three here.\r\nLine four here.'
                , 'type': {'mimetype': 'text/plain', 'supermimetype': 'text', 'extension': 'txt'}
                , 'name': 'firstdoc.txt'
                , 'size': 65
                }
            ,'meta': {
                'path': u'projects/demorepoone/master/firstdoc.txt'
                }
            , 'type': 'repoitem'}
        )
        # we don't allow seeing files / folders inside repo folders
        self.assertRaises(grm.PathUnfitError, _m, 'projects/demorepoone/objects')
        # on top of forbiden, it also does not exist.
        self.assertRaises(grm.PathUnfitError, _m, 'projects/demorepoone/kjhgjg')
        # all these should not exist
        self.assertRaises(grm.PathUnfitError, _m, 'projects/blah')
        self.assertRaises(grm.PathUnfitError, _m, '/blah')
        # we should forbid seeing contents of folders above base path.
        self.assertRaises(grm.PathUnfitError, _m, 'projects/../../../blah')

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite([
            unittest.TestLoader().loadTestsFromTestCase(test_GesRPCMethods),
        ])
    )
