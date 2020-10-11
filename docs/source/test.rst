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

will create a fully fledged coldoc site accessible at `http://localhost:8000`.



Blobify
-------

Or you want to *blobify* a document, just to see what it looks like.
Create a temporary directory

.. code:: shell

	  # tmpdir=$(mktemp  -d)

Then *blobify* the example document from the source into the temporary directory

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDoc/blob_inator.py --coldoc-nick=test --blobs-dir=${tmpdir} --ZS --SP --SAT --CG ${COLDOC_SRC_ROOT}/test/latex/latex_test.tex

Then open the main blob with an editor

.. code:: shell

	  # editor ${tmpdir}/main.tex 
