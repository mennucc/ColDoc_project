Deploying
==============

Here we explain how to start a new ColDoc collaborative document.

We assume that the ColDoc source code was download in the directory COLDOC_SRC_ROOT

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


In particular it will deploy a copy of the config file for the new document as  $(COLDOC_SITE_ROOT)/config.ini .
Edit it at taste.


Then initialize `django`

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py makemigrations
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

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/blob_inator.py --coldoc-nick=test --ZS  --author=jsmith  --SP --SAT --CG   ${COLDOC_SRC_ROOT}/test/latex/latex_test.tex

Start the simplest Django server and access the portal

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  runserver 8000
	  # firefox http://localhost:8000/
