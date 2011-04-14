"""
Python JSON-RPC (protocol v1.0) module.

Copyright (c) 2010 Daniel Dotsenko <dotsa@hotmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import io
import unittest
import tempfile
import zipfile
import shutil
import os
import sys

sys.path.append(os.getcwd())

import fuzzy_path_handler as subject

class test_WSGIFuzzyApplication(unittest.TestCase):

    preset = '{"id":"%s", "method":"%s", "params":["%s"]}'

    def _start_response(self, code, headers):
        if not code == "200 OK":
            raise Exception('RPC call returned HTTP error: %s' % code)

    def _string_from_iterator(self, obj):
        return ''.join(obj)

    def setUp(self):
        _p = tempfile.mkdtemp()
        zipfile.ZipFile('./test/sample_tree_of_repos_v2.zip').extractall(_p)
        self.base_path = os.path.join(_p,'reposbase')

        options = dict([
            ['content_path', self.base_path],
            ['static_content_path', None],
            ['uri_marker',''],
            ['port', None],
            ['devel', False],
            ['demo',False],
            ['remove_temp',False]
        ])
        self.h = subject.FuzzyPathHandler(**options)

    def tearDown(self):
        shutil.rmtree(os.path.split(self.base_path)[0], True)

    def test_01_getting_repo_folder_as_zip(self):
        response = self.h(
            {
                'wsgi.version': (1,1),
                'REQUEST_METHOD': 'GET',
                'wsgi.input': io.BytesIO(''),
                'PATH_INFO':'projects/demorepoone/master'
            },
            self._start_response
            )

        self.skipTest("We need to find a better way to test contents of zips. New versions of git create different binary zip.")

        self.assertEquals(
            ''.join(response)
            , open('./test/sample_git_archive_output.zip','rb').read()
            )

def suite():
        return unittest.TestSuite([
            # unittest.TestLoader().loadTestsFromTestCase(test_JSONRPCHandlerRouter) ,
            unittest.TestLoader().loadTestsFromTestCase(test_WSGIFuzzyApplication)
        ])
            
if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(
        suite()
    )
