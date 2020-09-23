Deploying
==============

Here we explain how to start a new ColDoc collaborative document.

We assume that the ColDoc source code was downloaded in the directory
whose name is saved in the environment variable COLDOC_SRC_ROOT.

You need to use a terminal where you can insert shell commands.

We assume that the new document will be contained in `/home/.../test_site` . Make
sure that this directory is empty, and set its name in an environ variable as follows.

.. code:: shell

	  # export COLDOC_SITE_ROOT=/home/.../test_site
	  # mkdir ${COLDOC_SITE_ROOT}

In the following you may omit the part `${COLDOC_SRC_ROOT}/`
if you are sure that the current working directory of the shell is the directory
where the ColDoc source code is located.

This command will create the structure for the new ColDoc portal

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py  deploy


In particular it will deploy a copy of the config file for the new document as  
${COLDOC_SITE_ROOT}/config.ini.
Edit it at taste.


It will also create an empty settings.py file
${COLDOC_SITE_ROOT}/settings.py where you may override the values in 
${COLDOC_SRC_ROOT}/settings.py 

Social auth
-----------

If you wish to use social authentication, you may set `use_allauth` to True
in ${COLDOC_SITE_ROOT}/config.ini and install `django-allauth`

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


`See docs for more details <https://django-allauth.readthedocs.io/en/latest/index.html>`_

Moreover you may need to setup the Django smtp machinery, to send emails
(emails are sent automatically to verify emails addresses or reset passwords).

Late adding of social auth
--------------------------

If you did not turn `social authentication` on at first, you may turn it on later,
by following the above instructions; and then you have to run

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py migrate
	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py collectstatic

to update the databases.


Initalize
---------

Then initialize `django` for your deployed site

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py migrate
	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py collectstatic

Add test material
-----------------

To test the portal we may populate it with the test LaTeX document.

Before we create some fake users, to be able to interact with the portal.

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py  create_fake_users

(The list of users and passwords will be printed on terminal)

We insert the test LaTeX document in the portal. Note that `jsmith` is the author of all blobs, and will have special access rights.

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/blob_inator.py --coldoc-nick=test --ZS  --author=jsmith  --SP --SAT    ${COLDOC_SRC_ROOT}/test/latex/latex_test.tex

Then you should generate all PDF and HTML associated to the test paper

.. code:: shell

	  # COLDOC_URL="http://localhost:8000/UUID/test/"
	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py --coldoc-nick=test --url-UUID=${COLDOC_URL}  all


(The command line option `--url-UUID` is needed so that the hyperlinks inside the PDF version will point to the correct URL)

Start the simplest Django server and access the portal

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  runserver 8000
	  # firefox http://localhost:8000/
