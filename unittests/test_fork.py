"""
run this as
$ python3 ./unittests/test_fork.py
or
$ pytest-3 ./unittests/test_fork.py 
"""

import os, sys, io, unittest, tempfile, shutil, time
from os.path import join as osjoin

testdir = os.path.dirname(os.path.realpath(__file__))
sourcedir = os.path.dirname(testdir)

sys.path.append(osjoin(sourcedir,'ColDocDjango'))

from ColDoc.utils import fork_class

def fakesum(a,b,c):
    return a + b + c

def fakediv(a,b):
    return a / b


class TestFork(unittest.TestCase):

    def test_fork_wrong_order(self):
        subproc = fork_class()
        with self.assertRaises(Exception):
            subproc.wait()

    def test_fork(self):
        subproc = fork_class()
        subproc.run(fakesum, 1, 2, 3)
        r = subproc.wait()
        self.assertEqual(r , 6)

    def test_fork_raises(self):
        subproc = fork_class()
        subproc.run(fakediv, 1, 0)
        with self.assertRaises(ZeroDivisionError):
            r = subproc.wait()

    def test_nofork(self):
        subproc = fork_class(False)
        subproc.run(fakesum, 1, 2, 3)
        r = subproc.wait()
        self.assertEqual(r , 6)

    def test_nofork_raises(self):
        subproc = fork_class(False)
        subproc.run(fakediv, 1, 0)
        with self.assertRaises(ZeroDivisionError):
            r = subproc.wait()


if __name__ == '__main__':
    unittest.main()
