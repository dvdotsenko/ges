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
        zipfile.ZipFile('./test/sample_tree_of_repos_v1.zip').extractall(_p)
        self.base_path = os.path.join(_p, 'reposbase')
        self._rpc_tree = dict(grm.assemble_methods_list(self.base_path))

    def tearDown(self):
        shutil.rmtree(self.base_path, True)

    def test_01_browser_methods(self):
        _m = self._rpc_tree['browser.listdir']
        self.assertEquals(
            _m(''),
            {'path':'/', 'dirs':[{'name':'projects'},{'name':'teams'},{'name':'users'}]}
        )
        self.assertEquals(
            _m('/'),
            {'path':'/', 'dirs':[{'name':'projects'},{'name':'teams'},{'name':'users'}]}
        )
        self.assertEquals(
            _m('\\'),
            {'path':'/', 'dirs':[{'name':'projects'},{'name':'teams'},{'name':'users'}]}
        )
        # crossing fingers and hoping the order is same on all platforms.
        self.assertEquals(
            _m('projects'),
            {'path':'/projects', 'dirs':[
                {'name':'common_files'},
                {'name':'demorepoone','is_git_dir':True},
                {'name':'projectone','is_git_dir':True}
            ]}
        )
        self.assertEquals(
            _m('projects/common_files'),
            {'path':'/projects/common_files', 'dirs':[]}
        )
        # we don't allow seeing files / folders inside repo folders
        self.assertRaises(grm.PathUnfitError, _m, 'projects/demorepoone')
        self.assertRaises(grm.PathUnfitError, _m, 'projects/demorepoone/objects')
        # on top of fobiden, it also does not exist.
        self.assertRaises(grm.PathUnfitError, _m, 'projects/demorepoone/kjhgjg')
        # all these should not exist
        self.assertRaises(grm.PathUnfitError, _m, 'projects/blah')
        self.assertRaises(grm.PathUnfitError, _m, '/blah')
        # we should forbid seeing contents of folders above base path.
        self.assertRaises(grm.PathUnfitError, _m, 'projects/../../../blah')

    def dtest_02_repoview_methods(self):
        _m = self._rpc_tree['repoview.endpoints']
        self.assertEquals(
            _m(''),
            {'path':'', 'dirs':[{'name':'repos'}]}
        )
        self.assertEquals(
            _m('/'),
            {'path':'', 'dirs':[{'name':'repos'}]}
        )
        self.assertEquals(
            _m('\\'),
            {'path':'', 'dirs':[{'name':'repos'}]}
        )
        # crossing fingers and hoping the order is same on all platforms.
        self.assertEquals(
            _m('repos'),
            {'path':'repos', 'dirs':[{'name':'folderone'},{'name':'repoone','is_git_dir':True}]}
        )
        self.assertEquals(
            _m('repos/folderone'),
            {'path':'repos/folderone', 'dirs':[]}
        )
        self.assertRaises(grm.PathUnfitError, _m, 'repos/repoone')
        self.assertRaises(grm.PathUnfitError, _m, 'repos/repoone/objects')
        self.assertRaises(grm.PathUnfitError, _m, 'repos/repoone/kjhgjg')
        self.assertRaises(grm.PathUnfitError, _m, 'repos/blah')
        self.assertRaises(grm.PathUnfitError, _m, 'repos/../../../blah')
        self.assertRaises(grm.PathUnfitError, _m, '/blah')

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite([
            unittest.TestLoader().loadTestsFromTestCase(test_GesRPCMethods),
        ])
    )
