Installing
==============

The following instructions are for people running Debian/Ubuntu, and the `bash` shell.
Other operating system may need some adjustments.

Download the latest code from GitHub

.. code:: shell

	  # cd /home/.../.../somewhere
	  # git clone ...
	  # cd ColDoc
	  # export COLDOC_SRC_ROOT=`pwd`

the last command sets the envirnmental variable COLDOC_SRC_ROOT to the directory where the
code was downloaded.

Note that ColDoc needs Python3 ; you may wish to set up a virtualenv, so that Python3 is the default Python.

ColDoc has some prerequisites: Djago (version 2 or 3), plastex (a patched version, see below) 


Installing plasTex
------------------

Installing `plastex` is somewhat complex, since ColDoc needs a patched version.

The script `plastex/prepare.sh` can download and patch plastex for you

Install it, using `pip3 intstall .` inside the directory `plastex/plastex`.



