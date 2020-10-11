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


Local variables
---------------


Settings for a deployed site are read from three files:

- the general file `${COLDOC_SRC_ROOT}/settings.py` in the ColDoc code

- `ColDocDjango.settings_local.py` if it exists

-  `${COLDOC_SITE_ROOT}/settings.py` from the `COLDOC_SITE_ROOT` directory where the
   web site is deployed.


To better test the code,
you may want to create a file `ColDocDjango.settings_local.py` to setup some variables
to enable email sending, as in this example.

.. code:: shell

	  MAIL_HOST = "smtp.server"
	  EMAIL_PORT = "587"
	  EMAIL_HOST_USER = "username"
	  EMAIL_HOST_PASSWORD = "password"
	  EMAIL_USE_TLS = True
	  DEFAULT_FROM_EMAIL = "Helpdesk <helpdesk@that_email"



