Installing
==============

The following instructions are for people running Debian/Ubuntu, and the `bash` shell.
Other operating system may need some adjustments.

Download the latest code from GitHub

.. code:: shell

	  cd /home/.../.../somewhere
	  git clone https://github.com/mennucc/ColDoc_project
	  cd ColDoc_project
	  export COLDOC_SRC_ROOT=`pwd`

the last command sets the environmental variable `COLDOC_SRC_ROOT` to the directory where the
code was downloaded. This is fundamental in the following.
In this section, we will assume that the `CWD` (current working directory) is `COLDOC_SRC_ROOT`.

venv
----

Note that ColDoc needs `Python3` ; you may want to set up a virtualenv, so that Python3 is the default Python.

.. code:: shell
	  
	  python3 -m venv venv
	  source venv/bin/activate

Prerequisites
-------------

ColDoc has some prerequisites: `Django` (version 2 or 3),
`plasTex` (a patched version, see below), and others, as explained later.

To install them (but for plastex) you may use

.. code:: shell

	  pip3 install django  BeautifulSoup4 django-guardian django-allauth django-background-tasks

(only the first two are strictly needed, the others can be used to activate advanced features, as explained below)

Installing plasTex
------------------

Installing `plastex` is somewhat complex, since ColDoc needs a patched version.

The script `plastex/prepare.sh` can download and patch plastex for you: the patched
version is then available in  `plastex/plastex`.
So you can install it, using `python3 setup.py install` inside the directory `plastex/plastex`.


Fix PdfLaTeX
------------

Some TeX/LaTeX versions, by default, mangle the tags in the output PDF; then
the cross-referencing machinery in ColDoc will not work.

To solve this problem, you should
edit the file `/usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg` and change
`%C  0x0000` to `%C  0x0010`.

You may use the patch `patch/texmf.patch` for this.


Note that this file is not marked as a `configuration file` in Debian/Ubuntu,
so it would be overwritten if the package `texlive-base` is upgraded; to avoid this
problem, you may want to run (as `root` user)

.. code:: shell

	  dpkg-divert --add --rename /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  cp -a /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg.distrib  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  patch  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg ${COLDOC_SRC_ROOT}/patch/texmf.patch


Alternatively, you may add

.. code:: TeX

	  \ifplastex\else
	  \special{dvipdfmx:config C 0x0010}
	  \special{xdvipdfmx:config C 0x0010}
	  \fi

to the preamble of all LaTeX documents.
