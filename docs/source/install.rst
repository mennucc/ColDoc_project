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

Install it, using `pip3 install .` inside the directory `plastex/plastex`.
(Do not forget the dot at the end of `pip3 install .` ).


Local variables
---------------


Settings for a deployed site are read from three files:

- the general file `${COLDOC_SRC_ROOT}/settings.py` in the ColDoc code

- `ColDocDjango.settings_local.py` if it exists

-  `${COLDOC_SITE_ROOT}/settings.py` from the `COLDOC_SITE_ROOT` directory where the
   web site is deployed.


To better test the code,
you may want to create a file `ColDocDjango.settings_local.py` to setup some variables
to enable email sending, as in this example. Or you may want to enable them in 
`${COLDOC_SITE_ROOT}/settings.py` .

.. code:: shell

	  MAIL_HOST = "smtp.server"
	  EMAIL_PORT = "587"
	  EMAIL_HOST_USER = "username"
	  EMAIL_HOST_PASSWORD = "password"
	  EMAIL_USE_TLS = True
	  DEFAULT_FROM_EMAIL = "Helpdesk <helpdesk@that_email>"

or to enhance the code, *e.g.* adding some mimetypes used in your `coldoc` s

.. code:: shell

	  import mimetypes
	  # https://bugs.freedesktop.org/show_bug.cgi?id=5455
	  for j in ('.gplt','.gnuplot'):
	      mimetypes.add_type('application/x-gnuplot',j)


See in `ColDocDjango.settings_suggested.py` for more examples.


Fix PdfLaTeX
------------

Some TeX/LaTeX versions, by default, mangle the tags in the output PDF; then
the cross-referencing machinery in ColDoc will not work.

To solve this problem, you should
edit the file `/usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg` and change
`%C  0x0000` to `%C  0x0010`.

You may use the patch `${COLDOC_SRC_ROOT}/patch/texmf.patch` for this.


Note that this file is not marked as a `configuration file` in Debian/Ubuntu,
so it would be overwritten if the package `texlive-base` is upgraded; to avoid this
problem, you may want to run (as `root` user)

.. code:: shell

	  dpkg-divert --add --rename /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  cp -a /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg.distrib  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg
	  patch  /usr/share/texlive/texmf-dist/dvipdfmx/dvipdfmx.cfg ${COLDOC_SRC_ROOT}/patch/texmf.patch


Alternatively, you may add

.. code:: TeX

	  \special{dvipdfmx:config C 0x0010}
	  \special{xdvipdfmx:config C 0x0010}

to the preamble of all LaTeX documents.
