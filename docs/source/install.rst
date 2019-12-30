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

Download plastex; version 2.1 is OK; you may want to download from 	git@github.com:plastex/plastex.git

Patch it, using the patch  `patches/0001-add-Tokenizer-to-input.patch`

