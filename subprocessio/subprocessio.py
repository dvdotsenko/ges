#!/usr/bin/env python
'''
@module subprocess_communicateio

Module extends cPython subprocess.Popen class and adds a communicateIO method to it.
PopenIO.communicateIO is similar to Popen.communicate, but can operate (take and return)
file-like objects in order to accommodate very large subprocess input / outputs.

Depending on the setting of the bufsize argument, the stdout and stderr may be
stored in memory-based file-like and later switch to file-based file-like. It's like
using tempfile.SpooledTemporaryFile() but without creating any file handles in the beginning.

I hope this functionality (file-system-persisted communicate + IO objects returned) makes
it into the official subprocess.py. Will gladly reassign the copyright, change license.

Until then:

Copyright (c) 2010  Daniel Dotsenko <dotsa@hotmail.com>

This project is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 of the License, or
(at your option) any later version.

This project is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with the project.  If not, see <http://www.gnu.org/licenses/>.
'''

import tempfile
import threading
from subprocess import *
import io

__all__ = ["Popen","PopenIO", "PIPE", "STDOUT", "call", "check_call", "CalledProcessError"]

class _StreamFeeder(threading.Thread):
    """Normal writing into pipe-like is blocking once the buffer is filled.
    This thread allows a thread to seep data from a file-like into a pipe
    without blocking the main thread.
    We close inpipe once the end of the source stream is reached.

    Copyright (c) 2010  Daniel Dotsenko <dotsa@hotmail.com>
    """
    def __init__(self, source, target):
        super(_StreamFeeder,self).__init__()
        self.daemon = True
        filelike = False
        self.bytes = b''
        if type(source) in (type(''),bytes,bytearray): # string-like
            self.bytes = bytes(source)
        else: # can be either file pointer or file-like
            if type(source) in (int, long): # file pointer it is
                ## converting file descriptor (int) stdin into file-like
                try:
                    source = os.fdopen(source, 'rb', 16384)
                except:
                    pass
            # let's see if source is pure file-like by now
            try:
                filelike = source.read
            except:
                pass
        if not filelike and not self.bytes:
            raise TypeError("source object must be a Python object that is a readable file-like, a file descriptor, or a string-like.")
        self.source = source
        self.target = target
        
    def run(self):
        t = self.target
        if self.bytes:
            t.write(self.bytes)
        else:
            s = self.source
            b = s.read(4096)
            while b:
                t.write(b)
                b = s.read(4096)
        t.close()

class _StreamPersistor(threading.Thread):
    """Redirects output of an in-pipe referenced by "source" into a
    file-like. File-like may be memory-based or file-based depending on
    size of data and value of bufsize. 
        Data size <= bufsize  = memory-based file-like
        Data size > bufsize  = file-based file-like
    Because this class is a thread, it does not return anything. Once done
    the output object will be exposed as .target property. Once the main 
    process thinks that we are done, get .target's value:
        thread.join()
        IOobj = thread.target

    Copyright (c) 2010  Daniel Dotsenko <dotsa@hotmail.com>
    """
    def __init__(self, source, bufsize = 65536):
        super(_StreamPersistor,self).__init__()
        self.daemon = True
        self.source = source
        self.target = None
        self.bufsize = bufsize
    def run(self):
        s = self.source
        t = None
        b = s.read(4096)
        bs = self.bufsize
        if b and bs and len(b) <= bs:
            t = io.BytesIO()
            while b and t.tell() <= bs:
                t.write(b)
                b = s.read(4096)
        if b:
            tf = tempfile.TemporaryFile()
            if t:
                t.seek(0)
                tf.write(t.read())
                t.close()
            t = tf
        while b:
            t.write(b)
            b = s.read(4096)
        self.target = t

class PopenIO(Popen):
    """Class wraps subprocess.Popen for the whole purpose of extending
    the Popen().communicate() method into taking and returning IOs.

    Copyright (c) 2010  Daniel Dotsenko <dotsa@hotmail.com>
    """    
    def communicateIO(self, stdin = None, bufsize = 65536):
        """Like communicate() but takes and outputs IO objects.
        
        Normal Popen().communicate() takes a string and returns strings.
        It relies on memory-based streams for capture and communication of results.
        This is an improper behavior for situations when output may be huge and binary.

        @param stdin A string, bytes, bytesarray, array('B') or file-like the
            contents of which will be fed to the subprocess as input.
            Rewind (obj.seek(needed_position)) your IO object before passing it in here.
            Defaults to None.
        @param bufsize An int stating the (approximate) max size of memory-stream
            to be used for storing process's output, until we are switched to a file-based
            stream. Setting it to zero effectively starts file-based file-like from the start. 
            Defaults to 65536
        
        @return tuple of form (outputIO, errorIO) where both outputIO and errorIO 
            can be None or file-like (either memory-based or file-based)
            The elements will be non-None only if the Popen() was initiated with
            stdout = subprocess.PIPE, stderr = subprocess.PIPE

            If bufsize is more than zero, outputIO object will start its life as
            some sort of memory-based file-like and will be switched to 
            file-based file-like when bufsize is crossed.
            Note about "some sort of file-like" Don't test the type and don't 
            rely on having non-standard-to-file-likes methods of a particular IO
            obj to be there as the underlying IO obj may change with time to 
            accommodate performance needs.
            
            Note, bufsize is per each stream - out and err. If both are filled, 
            your memory usage will be double of bufsize.
            
            Neither of outputIO or errorIO are rewound before being returned.
            If you want to use them, rewind them using .seek(needed_position):
                o,e = p.communicateIO()
                if o and o.tell(): # non-zero tell() = something was written there.
                    o.seek(0)
                    text = o.read()
        """        
        # we need to set up threaded output writers first, before we flood input with data and block the main thread.
        if self.stdout:
            out_thread = _StreamPersistor(self.stdout, bufsize)
            out_thread.start()
        if self.stderr:
            error_thread = _StreamPersistor(self.stderr, bufsize)
            error_thread.start()
        if self.stdin:
            if not stdin:
                self.stdin.close()
            else:
                in_thread = _StreamFeeder(stdin, self.stdin)
                in_thread.start()
                # thread will close the Popen's input by itself when input obj reaches EOF.
        return_out = None
        return_err = None
        if self.stdout:
            out_thread.join()
            return_out = out_thread.target
        if self.stderr:
            error_thread.join()
            return_err = error_thread.target
        if not self.stdout and not self.stderr and self.stdin:
            in_thread.join()
        returncode = self.wait()
        return (return_out, return_err)

    def communicate(self, input=None):
        o, e = self.communicateIO(input)
        if o:
            o.seek(0)
            o = o.read()
        elif self.stdout:
            o = ''
        if e:
            e.seek(0)
            e = e.read()
        elif self.stderr:
            e = ''
        return (o, e)
