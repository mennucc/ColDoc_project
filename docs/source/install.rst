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

ColDoc has some prerequisites: `Django` (version 2, 3 or 4),
`plasTex` (a patched version, see below), and others, as explained later.

Some packages are required for the code to work properly; others are recommended, to activate advanced features.

Long story short. To install most of them, you may use

.. code:: shell

	  pip3 install django BeautifulSoup4 pycountry lockfile django-guardian django-allauth django-select2 pylatexenc whitenoise django-simple-captcha

or

.. code:: shell

	  pip3 install -r requirements.txt

that will install versions that are known to work fine.

Then, you  install `plastex`, `wallet`, `CodeMirror`, and `django-background-tasks` manually.


Installing plasTex
------------------

Installing `plastex` is somewhat complex, since ColDoc needs a patched version.

The script `plastex/prepare.sh` can download and patch plastex for you: the patched
version is then available in  `plastex/plastex`.
So you can install it, using `pip3 install .` inside the directory `plastex/plastex`.

Installing django-background-tasks
----------------------------------

Compiling the whole LaTeX file can be long, and hence the HTTP connection
scheduling those compilation will hang for long time, and eventually timeout.
This makes for a lousy user experience.

When `django-background-tasks` is installed and activated in the `config` file,
those compilations will run in background.

(Results of compilations will be email to the editors:
do not forget to properly configure the email parameters.)

Note that (as of 2021-12-21)  `django-background-tasks`  is incompatible with Django4 :
you have to manually install the version at `https://github.com/mennucc/django-background-tasks` .
This is made available as a git submodule, so it is enough to

.. code:: shell

	  cd ${COLDOC_SRC_ROOT}/sub/django-background-tasks
	  pip install .



Installing CodeMirror
---------------------

Editing of LaTeX files with the standard web forms is tedious; for this reason,
your portal can integrate the online editor `CodeMirror`.


The script `bin/install_CodeMirror.sh` can install all the needed files, and link them into the portal.

wallet
------

The portal has an internal currency that can be used to buy permissions and downloads.
This is implemented in the library `django-simplewallet`, that is made
available as a git submodule `sub/django-simplewallet`, and is already linked into the main code.

Note that, to use it, you must also install `django-guardian`.

unicode2latex
-------------

The LaTeX editor has a `normalize` button that can convert accents and
other symbols for easier reading, for example `\\'e` will become `è`.
This is implemented in the library `unicode2latex`, that is made
available as a git submodule `sub/unicode2latex`, and is already linked into the main code.

Fix PdfLaTeX
------------

Some TeX/LaTeX versions, by default, mangle the tags in the output PDF; then
the cross-referencing machinery in ColDoc will not work.

To solve this problem, you should
edit the file `/usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg` and change
`%C  0x0000` to `%C  0x0010`.

You may use the patch `patches/texmf.patch` for this.


Note that this file is not marked as a `configuration file` in Debian/Ubuntu,
so it would be overwritten if the package `texlive-base` is upgraded; to avoid this
problem, you may want to run (as `root` user)

.. code:: shell

	  dpkg-divert --add --rename /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  cp -a /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg.distrib  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  patch  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg ${COLDOC_SRC_ROOT}/patches/texmf.patch


Alternatively, you may add

.. code:: TeX

	  \ifplastex\else
	  \special{dvipdfmx:config C 0x0010}
	  \special{xdvipdfmx:config C 0x0010}
	  \fi

to the preamble of all LaTeX documents.



Prerequisites, in detail
------------------------

Eventually, here is the long story.

Some packages are required: `django`, `plastex`, `BeautifulSoup4`. The code will not work without them.

The package `lockfile` is used to protect data on disk against racing conditions, `eg`
two users modifying the same file on disk at the same time. You want to install it.

Some are recommended, for better user experience: `pycountry`,  `django-select2`, `pylatexenc`.

`whitenoise` provides advanced caching features when serving static files.
Instructions on how to activate them is in
:doc:`deploy section<deploy>`.

There is an internal provision for an user to send an email to another user:
`django-simple-captcha` protects against abuse of this feature.

`django-guardian` provides fine access control, and
is needed for an user to buy access to restricted parts of a document.

`django-allauth` is a fantastic package that will enable your users to login
using external providers (Google, Facebook, etc). It is a bit complex
to setup, but wholly worth it.

By default, a `coldoc` portal will use `sqlite` as database; to use other databases,
you may need to install an adapter, `eg` for `MySQL` you may install `mysqlclient`.
(There are easy instructions on how to use `MySQL`, please read on in
:doc:`deploy section<deploy>`.
.)

