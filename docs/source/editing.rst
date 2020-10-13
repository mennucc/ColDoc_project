Editing
==============

There are many tools to operate on the coldoc; most have a `command line` and a `web` interface as well.

Command line tools have many options (not documented here), see respective `--help`.

One useful operation is to add new nodes to the tree of blobs.
From command line,

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py  add_blob



If you edit the blobs directly in the filesystem, and not using the web interface,
then the django database will be desyncronized regarding metadata: run

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/helper.py   --coldoc-nick NICK reparse_all

Moreover from time to time you will need to recreate the PDF and HTML representations.

Use

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py   --coldoc-nick NICK main_private

to recreate the complete HTML PDF (visible only to editors);
use

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py   --coldoc-nick NICK main_public

to recreate the public HTML PDF (visible only to everybody); use

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py   --coldoc-nick NICK tree

to recreate the HTML PDF for each blob (this is useful if you edited many blobs in the filesystem); use

.. code:: shell

	  # python3 ${COLDOC_SRC_ROOT}/ColDocDjango/latex.py   --coldoc-nick NICK all

to run all of the above.

Note that when you edit a blob using the web interface, it is automatically reparsed
and HTML and PDF are recomputed; but the `main` and `anon` complete documents are not recompiled.
