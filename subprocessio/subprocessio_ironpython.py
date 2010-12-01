# subprocess - A .NET-specific, IronPython implementation of the Python subprocess module
# 
# Copyright (c) 2010  Daniel Dotsenko <dotsa@hotmail.com>
# Copyright (c) Jeff Hardy 2007.
#
# This source code is subject to terms and conditions of the Microsoft Public License. A 
# copy of the license can be found at 
# http://www.microsoft.com/resources/sharedsource/licensingbasics/publiclicense.mspx. If 
# you cannot locate the Microsoft Public License, please send an email to 
# jdhardy@gmail.com. By using this source code in any fashion, you are agreeing to be bound 
# by the terms of the Microsoft Public License.
#
# You must not remove this notice, or any other, from this software.
#
# This file incorporates expressly-marked work covered by the following
# copyright and permission notice:
#  Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
#  Licensed to PSF under a Contributor Agreement.
#  See http://www.python.org/2.4/license for licensing details.

import System.IO
import System.Threading
from System.Diagnostics import Process as DotNetProcess
import os
import tempfile

__all__ = ["Popen","PopenIO", "PIPE", "STDOUT", "call", "check_call", "CalledProcessError"]


PIPE = -1
STDOUT = -2

_active = []
def _cleanup():
    """Faking a cPython subprocess._active ._cleanup() mechanism
    
    cPython's unit-tests are relying on static _active property 
    to be attached to subprocess module. Whoever desided to roll 
    unit-tests for "private" methods into teardown for every other unit
    test in standard cPython test_subprocess.py, my disgust is packaged
    and is on its way to you. 

    The code is based on original source of subprocess.py exhibiting the
    following permissions and copyright notices:
    # Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
    #
    # Licensed to PSF under a Contributor Agreement.
    # See http://www.python.org/2.4/license for licensing details.
    """
    for inst in _active[:]:
        if inst.poll() >= 0:
            try:
                _active.remove(inst)
            except ValueError:
                # This can happen if two threads create a new Popen instance.
                # It's harmless that it was already removed, so ignore.
                pass

class _StreamRedirector(object):
    """IronPython-specific threaded .Net stream to Python file-like object data redirector."""
    def __init__(self, source, target):
        try:
            t = source.Read
        except:
            raise TypeError("source object must be a .Net object that is a readable file-like.")
        try:
            t = target.write
        except:
            t = False
        if not t and type(target) in (int, long) and target >= 0:
            try:
                target = os.fdopen(target, 'wb', 16384)
                t = True
            except:
                raise TypeError("target object must be a Python object that is a writable file-like or a file descriptor.")
        if not t:
            raise TypeError("target object must be a Python object that is a writable file-like or a file descriptor.")
        self.resource_lock = object() # only reference types are lockable.
        self.working = True
        self.target = target
        self.source = source
    def worker(self):
        System.Threading.Monitor.Enter(self.resource_lock)
        s = self.source
        t = self.target
        read_buff_size = 4096;
        a = System.Array.CreateInstance(System.Byte, read_buff_size)
        b = s.Read(a, 0, read_buff_size);
        # cPython 3.x has "buffer" interface built into actual bytes object and no built-in "buffer"
        # IronPython 2.6.1, against which this module is developed has "buffer" built-in and bytes don't implement buffer iface
        # or, maybe it does, but doing StringIO().write(bytes(Array[Byte])) gives an error about needing a buffer
        # So, for now we need to buffer(obj), but should IronPython ever go the cPython 3.x way,
        # let's future-proof the code a bit.
        try:
            bufferizer = buffer
        except:
            bufferizer = bytes
        while b > 0:
            t.write(bufferizer(a[:b]))
            b = s.Read(a, 0, read_buff_size)
        self.working = False
        System.Threading.Monitor.Exit(self.resource_lock)

class _StreamPersistor(object):
    """Redirects output of an in-pipe referenced by "source" into a
    .Net file-like. File-like may be memory-based or file-based depending on
    size of data and value of bufsize.
        Data size <= bufsize  = memory-based file-like
        Data size > bufsize  = file-based file-like
    Because this class is a thread, it does not return anything. Once done,
    the output object will be exposed as .target property. Once the main
    process thinks that we are done, read .target's value. Also note that the
    file-like is NOT rewound after being filled in. Rewind before use.
        thread.join()
        if thread.target:
         thread.target.seek(0)
         text = thread.target.read()
    """
    def __init__(self, source, bufsize = 65536):
        try:
            t = source.Read
        except:
            raise TypeError("source object must be a .Net object that is a readable file-like.")
        self.resource_lock = object() # only reference types are lockable.
        self.working = True
        self.target = None
        self.source = source
        self.bufsize = bufsize
    def worker(self):
        System.Threading.Monitor.Enter(self.resource_lock)
        s = self.source
        tm, tf = None, None
        maxmmap = self.bufsize
        read_buff_size = 2048;
        a = System.Array.CreateInstance(System.Byte, read_buff_size)
        b = s.Read(a, 0, read_buff_size);
        size = b
        if b and maxmmap and b <= maxmmap:
            tm = System.IO.MemoryStream()
            while b > 0 and size <= maxmmap:
                tm.Write(a,0,b)
                b = s.Read(a, 0, read_buff_size)
                size += b
        if b:
            tf = tempfile.TemporaryFile()
            try:
                bufferizer = buffer
            except:
                bufferizer = bytes
            if tm:
                tf.write(bufferizer(tm.ToArray()))
                tm.Close()
                tm = None
        while b:
            tf.write(bufferizer(a[:b]))
            b = s.Read(a, 0, read_buff_size)
        if tm:
            self.target = file(tm)
        elif tf:
            self.target = tf
        self.working = False
        System.Threading.Monitor.Exit(self.resource_lock)

class _StreamFeeder(object):
    """Normal writing into pipe-like is blocking once the buffer is filled.
    This class allows a sub-thread to seep data from a file-like into a .Net pipe
    without blocking the main thread.
    We close inpipe once the end of the source stream is reached.
    """
    def __init__(self, source, target):
        """Initializer converts acceptable "source" obj into file-like

        @param source Could be a string-like (string, unicode, bytes, bytearray,
        buffer), a file descriptor (int) or a file-like (any object with
        ".read(number_of_bytes_to_read)" method).

        @param target Could be any .Net-style stream writer (any object with
        ".Write(Array(Bytes),start,count)" method.)
        """
        try:
            trash = target.Write
        except:
            raise TypeError("target object must be a .Net-style writable stream.")
        
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
        self.resource_lock = object() # only reference types are lockable.
        self.working = True

    def worker(self):
        System.Threading.Monitor.Enter(self.resource_lock)
        s = self.source
        t = self.target
        read_buff_size = len(self.bytes) or 4096 # this allows us to process strings in one loop.
        a = System.Array.CreateInstance(System.Byte, read_buff_size)
        if self.bytes: # source was a string
            self.bytes.CopyTo(a,0)
            t.Write(a,0,read_buff_size)
        else: # the source was an file-like
            b = s.read(read_buff_size)
            l = len(b)
            while l:
                bytes(b).CopyTo(a,0)
                t.Write(a,0,l)
                b = s.read(read_buff_size)
                l = len(b)
        t.Close()
        self.working = False
        System.Threading.Monitor.Exit(self.resource_lock)

class PopenIO(object):
    """ Need documentation - copy from Python subprocess.py? """
    def __init__(self, args, bufsize=0, executable=None, stdin=None,
            stdout=None, stderr=None, preexec_fn=None, close_fds=False,
            shell=False, cwd=None, env=None, universal_newlines=False,
            startupinfo=None, creationflags=0):
        if preexec_fn:
            raise ValueError("preexec_fn is not supported on Windows platforms")
        # This arg just fails to make any sense to me. Not sure what needs to be
        # implemented, so we will pretend we are compliant.
#        if close_fds:
#            raise ValueError("close_fds is not supported on Windows platforms")
        if universal_newlines:
            raise NotImplementedError("universal_newlines feature is not implemented yet.")
        if startupinfo:
            raise ValueError("startupinfo is not supported on .NET platforms")
        if creationflags:
            raise ValueError("creationflags is not supported on .NET platforms")
        if stderr == STDOUT:
            raise NotImplementedError("Cannont redirect stderr to stdout yet.")
        # 3.x unittests need Popen to accept None as zero.
        # 2.7.x unittests need Popen to fail when we don't emit TypeError. 
        # Fricken insanity. Who in the right mind writes INPUT type-safety unittests on dynamic platforms?
        # write OUTPUT type-safety tests and throw whatever crap you want into input. If the function
        # gives back right output, it passes. The end. Grrrrr!!!!
        # 4 lines below are here only to address the unittest thing above ^
        if bufsize == None: 
            bufsize = 0
        if type(bufsize) not in (int, long): 
            raise TypeError("bufsize must be int.")
        # -1 means "system default" 
        if bufsize == -1:
            bufsize = 65536 # this becomes the size threshold for switching between memory and file-based streams.
        self._bufsize = bufsize
        
        # let's start our subprocess as soon as possible and catch up with output redirectors.
        p = DotNetProcess()
        p.StartInfo.UseShellExecute = False
        # p.StartInfo.CreateNoWindow = True
        if type(args) not in (type(''),bytes):
            args = list2cmdline(args)
        if shell:
            p.StartInfo.FileName = executable or os.environ['COMSPEC']
            p.StartInfo.Arguments = '/C ' + args
        else: #default
            if not executable:
                executable, args = chop_off_executable(args)
            p.StartInfo.FileName = executable
            p.StartInfo.Arguments = args
        if env:
            p.StartInfo.EnvironmentVariables.Clear()
            for k, v in env.items():
                p.StartInfo.EnvironmentVariables.Add(k, v)
        p.StartInfo.WorkingDirectory = cwd or os.getcwd()
        p.StartInfo.RedirectStandardInput = stdin is not None
        p.StartInfo.RedirectStandardOutput = stdout is not None
        p.StartInfo.RedirectStandardError = stderr is not None
        p.Start()
        self.pid = p.Id
        self.process = p

        self.stdin, self.stdout, self.stderr = None, None, None
        self._error_reader, self._out_reader, self._in_reader = None, None, None
        # action below is only needed for PIPE and file-like stdin, out, err.
        # Notes:
        #  - we cannot use process.OutputDataReceived event handlers.
        #    It uses String > Unicode manipulation, incorrectly guesses encoding
        #    and messes up binary data. Must implement own threaded binary stream redirectors.
        #  - we will use .Net-native IO objects as much as possible. In some cases
        #    stream redirection IO written in IronPython utilizing .Net objects
        #    (.Net threads, .Net memory and file streams) is faster than cPython's native methods.
        #  - There is little .Net optimization possible for cases when std* are file-like pointers
        #    In those cases buffered reading of the .Net pipe and Python .write to file-like is only option.
        #    There is a way to do buffered writes to python file descriptors using Array() class,
        #    but I have little desire to implement it this time because don't expect all
        #    incoming file-likes to have a fileno property, and will just convert file handles
        #    to file-likes and will use "write()" (StreamRedirector would need to support
        #    accelerated Array('B') based writing to pure file handles though alternate worker.)
        #    However, when std* are PIPE and the mode of consumption is through communicate(input)
        #    we can use pure .Net objects for all read and write in the treads, and hand the
        #    python-wrapped .Net file-likes as output in case of communicateIO(input)
        #  - .Net process's default in-pipe BaseStream buffer size is 8k. Pushing data need to be threaded
        #
        #  So, we need 3 different threaded workers:
        #    std* type | screen     | pipe consumed externally | pipe+communicate*() | file-like
        #    ----------|------------|--------------------------|---------------------|---------------
        #    stdin     | do nothing | self.stdin =file(.Net o) | StreamFeeder        | StreamFeeder
        #    stdout    | do nothing | self.stdout=file(.Net o) | StreamPersistor     | StreamRedirector
        #    stderr    | do nothing | self.stderr=file(.Net o) | StreamPersistor     | StreamRedirector
        #
        if stdin is not None:
            if stdin == PIPE:
                self.stdin = file(p.StandardInput.BaseStream)
            else:
                self._in_reader = _StreamFeeder(stdin, p.StandardInput.BaseStream)
                _in_thread = System.Threading.Thread(
                    System.Threading.ThreadStart(self._in_reader.worker)
                    )
                _in_thread.Start()
                self._child_created = True
        if stdout is not None:
            if stdout == PIPE:
                self.stdout = file(p.StandardOutput.BaseStream)
            else:
                self._out_reader = _StreamRedirector(p.StandardOutput.BaseStream, stdout)
                _out_thread = System.Threading.Thread(
                    System.Threading.ThreadStart(self._out_reader.worker)
                    )
                _out_thread.Start()
                self._child_created = True
        if stderr is not None:
            if stderr == PIPE:
                self.stderr = file(p.StandardError.BaseStream)
            else:
                self._error_reader = _StreamRedirector(p.StandardError.BaseStream, stderr)
                _error_thread = System.Threading.Thread(
                    System.Threading.ThreadStart(self._error_reader.worker)
                    )
                _error_thread.Start()
                self._child_created = True

    def get_returncode(self):
        return self.poll()
    returncode = property(get_returncode)

    def poll(self):
        return self.process.ExitCode if self.process.HasExited else None

    def wait(self):
        self.process.WaitForExit()
        # This is a fancy way to "join" the output redirector threads
        # Later I want an ability to kill threads on timeout, so opting for while + locks
        # Cannot guarantee that thread will get first to the lock object
        # we will spin in these empty lock structures until worker
        # thread gets the lock and flips ".working" to False when done.
        while self._out_reader and self._out_reader.working:
            System.Threading.Monitor.Enter(self._out_reader.resource_lock)
            System.Threading.Monitor.Exit(self._out_reader.resource_lock)
        while self._error_reader and self._error_reader.working:
            System.Threading.Monitor.Enter(self._error_reader.resource_lock)
            System.Threading.Monitor.Exit(self._error_reader.resource_lock)
        # if output capture is done, we know input thread is done for sure.
        if not self._out_reader and not self._error_reader:
            # so we will "join" inputreader only when we don't use threads for outs.
            while self._in_reader and self._in_reader.working:
                System.Threading.Monitor.Enter(self._out_reader.resource_lock)
                System.Threading.Monitor.Exit(self._out_reader.resource_lock)
        return self.process.ExitCode

    def communicateIO(self, input = None):
        """Like communicate() but takes and outputs IO objects.

        Normal Popen().communicate() takes a string and returns string
        (bytes object in 3.x). It relies on memory-based streams for capture and
        communication of results. This is an improper behavior for situations
        when output may be huge or "binary".

        @param stdin A string, bytes, bytesarray, array('B') or Python file-like
            the contents of which will be fed to the subprocess as input.
            Rewind (obj.seek(needed_position)) your IO object before passing it
            in here. Defaults to None.

        @return tuple of form (outputIO, errorIO) where both can be None or
            file-like (either memory-based or file-based).
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
            When switching streams from memory- to file-based the memory usage
            may briefly be up to 4 times the bufsize.

            Neither of outputIO or errorIO are rewound before being returned.
            If you want to use them, rewind them:
                o,e = p.communicateIO(i)
                if o and o.tell():
                    o.seek(0)
                    text = o.read()
        """
        p = self.process
        bufsize = self._bufsize

        if self.stdin:
            if not self._in_reader:
                if input:
                    self.stdin.flush() # since Python-style file wrapper can cache, and we use underlying BaseStream, need this.
                    self._in_reader = _StreamFeeder(input, p.StandardInput.BaseStream)
                    _in_thread = System.Threading.Thread(
                        System.Threading.ThreadStart(self._in_reader.worker)
                        )
                    _in_thread.Start()
                else:
                    # a requirement to put subprocess on a road to exit.
                    p.StandardInput.BaseStream.Close()
        if self.stdout and not self._out_reader:
            self._out_reader = _StreamPersistor(p.StandardOutput.BaseStream, bufsize)
            _out_thread = System.Threading.Thread(
                System.Threading.ThreadStart(self._out_reader.worker)
                )
            _out_thread.Start()
        if self.stderr and not self._error_reader:
            self._error_reader = _StreamPersistor(p.StandardError.BaseStream, bufsize)
            _error_thread = System.Threading.Thread(
                System.Threading.ThreadStart(self._error_reader.worker)
                )
            _error_thread.Start()

        returncode = self.wait()

        return_out, return_err = None, None
        if self._out_reader:
            return_out = self._out_reader.target
        if self._error_reader:
            return_err = self._error_reader.target
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
    
    def __del__(self, _active=_active, *args, **kw):
        """Faking a cPython subprocess._active mechanism
        
        cPython's unit-tests are relying on static _active property 
        to be attached to subprocess module. Whoever desided to roll 
        unit-tests for "private" methods into teardown for every other unit
        test in standard cPython test_subprocess.py, my disgust is packaged
        and is on its way to you. Why not just call del on procs after they
        are done.

        The code is based on original source of subprocess.py exhibiting the
        following permissions and copyright notices:
        # Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
        #
        # Licensed to PSF under a Contributor Agreement.
        # See http://www.python.org/2.4/license for licensing details.
        """
        if self._child_created:
            if self.poll() == None:
                _active.append(self)

Popen = PopenIO

def call(*popenargs, **kwargs):
    p = Popen(*popenargs, **kwargs)
    return p.wait()

class CalledProcessError(Exception):
    """This exception is raised when a process run by check_call() or
    check_output() returns a non-zero exit status.
    The exit status will be stored in the returncode attribute;
    check_output() will also store the output in the output attribute.

    Entire class's code, including the docstring is taken from cPython's subprocess.py
    module and is covered by the following copyright and permission notice:
    # Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
    #
    # Licensed to PSF under a Contributor Agreement.
    # See http://www.python.org/2.4/license for licensing details.
    """
    def __init__(self, returncode, cmd, output=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
    def __str__(self):
        return "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)

def check_call(*popenargs, **kwargs):
    """Run command with arguments.  Wait for command to complete.  If
    the exit code was zero then return, otherwise raise
    CalledProcessError.  The CalledProcessError object will have the
    return code in the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    check_call(["ls", "-l"])
    
    Entire class's code, including the docstring is taken from cPython's subprocess.py
    module and is covered by the following copyright and permission notice:
    # Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
    #
    # Licensed to PSF under a Contributor Agreement.
    # See http://www.python.org/2.4/license for licensing details.
    """
    retcode = call(*popenargs, **kwargs)
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd)
    return 0

def chop_off_executable(args):
    """Takes an argument string formatted per
    http://msdn.microsoft.com/en-us/library/ms880421
    and chops off the first element from the argument chain.

    This, unfortunately, is not as easy as .split(" ",1)
    """
    if not type(args) == type('') or not len(args):
        raise TypeError("Argument must be non-empty string-like")
    args = args.strip()
    if args[0] == '"':
        i = 1
        openning_quote = True
    else:
        i = 0
        openning_quote = False
    got_it = False
    escaped = False
    l = len(args)
    while not got_it and i < l:
        c = args[i]
        if (c == '"' and not escaped and openning_quote) or (c in (' ','\t') and not openning_quote):
            got_it = True
        elif c == '\\': # not double slash. To state "one slash" in python strings, i need to escape it.
            escaped = not escaped
        else: # any char, including non-closing quotes, quote-enclosed spaces.
            escaped = False
        i += 1
    return args[:i].strip(), args[i:].strip()

def list2cmdline(seq):
    """
    Translate a sequence of arguments into a command line
    string, using the same rules as the MS C runtime:
    1) Arguments are delimited by white space, which is either a
       space or a tab.
    2) A string surrounded by double quotation marks is
       interpreted as a single argument, regardless of white space
       contained within.  A quoted string can be embedded in an
       argument.
    3) A double quotation mark preceded by a backslash is
       interpreted as a literal double quotation mark.
    4) Backslashes are interpreted literally, unless they
       immediately precede a double quotation mark.
    5) If backslashes immediately precede a double quotation mark,
       every pair of backslashes is interpreted as a literal
       backslash.  If the number of backslashes is odd, the last
       backslash escapes the next double quotation mark as
       described in rule 3.

    Entire function's code, including the docstring is taken from cPython's subprocess.py
    module and is covered by the following copyright and permission notice:
    # Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
    #
    # Licensed to PSF under a Contributor Agreement.
    # See http://www.python.org/2.4/license for licensing details.
    """
    # See
    # http://msdn.microsoft.com/library/en-us/vccelng/htm/progs_12.asp
    if type(seq) in (type(''), bytes, bytearray):
        seq = [seq]
    result = []
    needquote = False
    for arg in seq:
        bs_buf = []
        # Add a space to separate this argument from the others
        if result:
            result.append(' ')
        needquote = (" " in arg) or ("\t" in arg)
        if needquote:
            result.append('"')
        for c in arg:
            if c == '\\':
                # Don't know if we need to double yet.
                bs_buf.append(c)
            elif c == '"':
                # Double backspaces.
                result.append('\\' * len(bs_buf)*2)
                bs_buf = []
                result.append('\\"')
            else:
                # Normal char
                if bs_buf:
                    result.extend(bs_buf)
                    bs_buf = []
                result.append(c)
        # Add remaining backspaces, if any.
        if bs_buf:
            result.extend(bs_buf)
        if needquote:
            result.extend(bs_buf)
            result.append('"')
    return ''.join(result)
