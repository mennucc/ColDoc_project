Deploying
==============

Here we explain how to bootstrap a new ColDoc *web portal*, or *site*.

We assume that the ColDoc source code was downloaded in the directory
whose name is saved in the environment variable COLDOC_SRC_ROOT.
For details see the
:doc:`install section<install>`

ColDoc keeps a strict separation between *code* and *data*.

The same *code* directory can be used to run many *sites*.

In turn, each *site* can host many *documents*.

In the
:doc:`install section<install>`
we installed the *code*.
Here we will prepare the structure for the data and settings for a *portal*.


To start a new ColDoc site, you need to setup a directory
containing some files. This process is called `deploying`.
The directory name must be saved in the `COLDOC_SITE_ROOT`
environmental variable.

You need to use a terminal where you can insert shell commands.

Serving with Apache
-------------------

To serve the portal using Apache2 in Debian or Ubuntu, you may install the packages

.. code:: shell

	  sudo apt install apache2 libapache2-mod-wsgi-py3


It is advisable to put the portal under `/var/www`
(or otherwise, you should edit `/etc/apache2/apache2.conf`
otherwise `apache` will not serve your content).
Here is an example shell code:

.. code:: shell

	  export COLDOC_SITE_ROOT=/var/www/test_site
	  sudo mkdir ${COLDOC_SITE_ROOT}
	  sudo chown owner.group ${COLDOC_SITE_ROOT}

where `owner.group` is who is performing the install.

Serving without Apache
----------------------

If you want to run the portal by some other means (there are
`many ways to deploy Django, see here <https://docs.djangoproject.com/en/dev/howto/deployment/>`_
) then
you may setup the test site anywhere, let's say `/home/.../test_site` . Make
sure that this directory is empty, and set its name in an environ variable as follows.

.. code:: shell

	  export COLDOC_SITE_ROOT=/home/.../test_site
	  mkdir ${COLDOC_SITE_ROOT}


Deploying the skeleton
----------------------

In the following you may omit the part `${COLDOC_SRC_ROOT}/`
if you are sure that the current working directory of the shell is the directory
where the ColDoc source code is located.

This command will create the structure for the new ColDoc portal

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py  deploy


In particular it will deploy the *config file* for the new document as
${COLDOC_SITE_ROOT}/config.ini.
This contains some fundamental settings for the site,
and it can also be used to activate/deactivate special features for the portal,
such as: social authentication, background tasks, comments, *etc*.
Edit it at taste.


Local variables
---------------

There are many settings for a Django portal (the `config.ini` file will setup
only the most important ones).

At startup, Django reads a `settings.py` file. In this case,
settings for a deployed site are read from three files:

- the general file `${COLDOC_SRC_ROOT}/ColDocDjango/ColDocDjango/settings.py` in the ColDoc code;

- `${COLDOC_SRC_ROOT}/ColDocDjango/settings_local.py` if it exists;

- `${COLDOC_SITE_ROOT}/settings.py` from the `COLDOC_SITE_ROOT` directory where the web site is deployed.

Each one overrides the previous.

The last file is prepopulated with some useful examples (all commented out).
In particular, there is a snippet and instructions to use MySQL instead of sqlite as backend database.

To better test the code,
you may want to create a file `${COLDOC_SRC_ROOT}/ColDocDjango/settings_local.py`
to setup some variables to enable email sending, as in this example.


.. code:: shell

	  MAIL_HOST = "smtp.server"
	  EMAIL_PORT = "587"
	  EMAIL_HOST_USER = "username"
	  EMAIL_HOST_PASSWORD = "password"
	  EMAIL_USE_TLS = True
	  DEFAULT_FROM_EMAIL = "Helpdesk <helpdesk@that_email>"

or to enhance the code, *e.g.* adding some mimetypes used in your `coldoc` s

.. code:: Python

	  import mimetypes
	  # https://bugs.freedesktop.org/show_bug.cgi?id=5455
	  for j in ('.gplt','.gnuplot'):
	      mimetypes.add_type('application/x-gnuplot',j)

Or you may want to enable them in `${COLDOC_SITE_ROOT}/settings.py` for your specific site.

See in `${COLDOC_SRC_ROOT}/ColDocDjango/settings_suggested.py` for more examples.



Social auth
-----------

If you wish to use social authentication, you may set `use_allauth` to True
in `${COLDOC_SITE_ROOT}/config.ini` and install `django-allauth`

**Note that once you set `use_allauth` to True, you cannot change it back to `False`.**


In particular, you may add stanzas for `django-allauth` in ${COLDOC_SITE_ROOT}/settings.py
such as providers and configs, something like

.. code:: python

	INSTALLED_APPS += [
		'allauth.socialaccount.providers.google']
	SOCIALACCOUNT_PROVIDERS = {
	    'google': {
	        'SCOPE': [
	            'profile',
	            'email',
	        ],
	        'AUTH_PARAMS': {
	            'access_type': 'online',
	        }
	    }
	}

and don't forget to connect to the `admin` interface and to create
a `social application` in the database, that contains all credentials
(in the above case, for Google OAuth2).


`See django-allauth docs for more details <https://django-allauth.readthedocs.io/en/latest/index.html>`_

Moreover you may need to setup the Django smtp machinery, to send emails
(emails are sent automatically to verify emails addresses or reset passwords).

Late adding of social auth
--------------------------

If you did not turn `social authentication` on at first, you may turn it on later,
by following the above instructions; and then you have to run

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py migrate
	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py collectstatic

to update the databases.


Initalize
---------

Then initialize `django` for your deployed site

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py migrate
	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py collectstatic



Add test material
-----------------

To test the portal we may populate it with the test LaTeX document.

Before we create some fake users, to be able to interact with the portal.

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py  create_fake_users

(The list of users and passwords will be printed on terminal)

We insert the test LaTeX document in the portal. Note that `jsmith` is the author of all blobs, and will have special access rights; similarly `ed_itor` is the editor, and will have access to some administrative information in the coldoc main page.

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/blob_inator.py --coldoc-nick=test --lang=eng --ZS --editor=ed_itor --author=jsmith  --SP --SAT    ${COLDOC_SRC_ROOT}/test/paper/paper.tex

Then you should generate all PDF and HTML associated to the test paper

.. code:: shell

	  COLDOC_URL="http://localhost:8000/UUID/test/"
	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py --coldoc-nick=test --url-UUID=${COLDOC_URL}  all


(The command line option `--url-UUID` is needed so that the hyperlinks inside the PDF version will point to the correct URL)

Activate the Apache portal 
--------------------------

If you are preparing the web site to be served by Apache2, you should

.. code:: shell

	  sudo chown -R www-data:www-data ${COLDOC_SITE_ROOT}

otherwise Apache will not be able to access it. Then set up Apache as follows:


.. code:: shell

	  sudo cp ${COLDOC_SITE_ROOT}/apache2.conf /etc/apache2/sites-available/test_site.conf
	  sudo a2ensite test_site
	  sudo a2enmod wsgi
	  sudo systemctl reload apache2

To enjoy advanced caching capabilities you may also

.. code:: shell

	  sudo a2enmod expires
	  sudo a2enmod headers

If you activated `whitenoise` you may also tweak caching timings,
as explained in `apache2.conf` .


Serve without Apache
--------------------

Start the simplest Django server and access the portal

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  runserver 8000
	  firefox http://localhost:8000/


Note that in this case *django* will not serve the static files, unless you set *debug* to *True* in
`${COLDOC_SITE_ROOT}/config.ini`
; and you may need to change

.. code:: shell

	  dedup_root = %(site_root)s/static_local/dedup
	  dedup_url = /static/dedup

in that file.

Software upgrade and/or template changes
----------------------------------------

Note that each time you upgrade the software you need to

.. code:: shell

	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py migrate
	  python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py collectstatic

This is particularly important when you use  `whitenoise` otherwise the
cache will not work and your server will return 500.

Final remarks
-------------

ColDoc keeps a strict separation between `code` and `data`.
You may even install the code using an account, let's say
`coldoc_sw`, then deploy a portal, and assign all the files
in the portal to a different user, let's say `coldoc_data`:
in this case you need to tell Apache about this change,
by adding the `user` and `group` directives in the line starting as `WSGIDaemonProcess`,
as follows

.. code:: shell

	  WSGIDaemonProcess coldoc.group python-home=/...virtualenv.... python-path=${coldoc_src_root}  locale=en_US.UTF-8  lang=en_US.UTF-8 user=coldoc_data group=coldoc_data

This may improve security.




