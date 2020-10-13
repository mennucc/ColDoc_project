Testing
=======

To test it, you may use the tests in the `test` directory (go there and type `make` to see a list).

.. code:: shell

	  # cd test
	  # make

For example the commands

.. code:: shell

	  # cd test
	  # make clean
	  # make django_deploy
	  # make django_paper
	  # make django_run

This will *blobify* the test document from  `${COLDOC_SRC_ROOT}/test/paper/paper.tex`
and create a coldoc called `paper`.

The data for the coldoc `paper` will be stored in `${COLDOC_SRC_ROOT}/test/tmp/test_site/coldocs/paper/blobs`
so you can open the main file
`${COLDOC_SRC_ROOT}/test/tmp/test_site/coldocs/paper/blobs/main.tex`
with an editor, or compile it with `pdflatex` ; otherwise you can access
the web portal at `http://localhost:8000`.
and edit it thru the web interface.
(Usernames and passwords for interacting with the test web server are printed when
issuing `make django_deploy` )
Note that if you edit the latex files on disk, then
you will need to issue some commands to keep web interface
in sync:
:doc:`editing <editing>`

Blobify
-------

Or you want to *blobify* a document without using the Django web interface, just to see what it looks like.
Create a temporary directory

.. code:: shell

	  # tmpdir=$(mktemp  -d)

Then *blobify* the example document from the source into the temporary directory

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDoc/blob_inator.py --coldoc-nick=test --blobs-dir=${tmpdir} --ZS --SP --SAT --CG ${COLDOC_SRC_ROOT}/test/latex/latex_test.tex

Then open the main blob with an editor

.. code:: shell

	  # editor ${tmpdir}/main.tex 
