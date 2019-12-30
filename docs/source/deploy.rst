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

Deploy a copy of the config file for the new document.

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/config.py deploy ${COLDOC_SITE_ROOT}/config.ini


Edit it at taste.

Create the space where the document tree will be stored.

.. code:: shell

	  # ( cd ${COLDOC_SITE_ROOT} ; mkdir blobs templates var static media )

(All above directories may be customized by editing ${COLDOC_SITE_ROOT}/config.ini )

To test the portal we may populate it with the test LaTeX document

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDoc/blob_inator.py --blobs-dir=${COLDOC_SITE_ROOT}/blobs --ZS --SP --SE=document --SL=itemize --SAT --CG   ${COLDOC_SRC_ROOT}/test/latex/latex_test.tex

Start the simplest Django server and access the portal

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  runserver 8000
	  # firefox http://localhost:8000/

