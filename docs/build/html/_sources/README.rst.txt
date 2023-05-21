==============
ColDoc Project
==============

There are two main frameworks currently used to present information (in particular,
related to scientific fields).

- A document redacted with the standard `LaTeX` / `PDF`	toolbox.

  -  *Pros:* these documents are state-of-the-art quality.

  -  *Cons:* the final user has no way of interacting with a PDF document
     (other than sending an e-mail to the original authors)

- The *Web 2.0* way  (think of:
  `Wikipedia <https://www.wikipedia.org/>`_
  or
  `Stack Exchange <https://en.wikipedia.org/wiki/Stack_Exchange>`_
  ).

  -  *Pros:*	in those frameworks, content is continuously developed and augmented by users.

  -  *Cons:*  the end result, though, is fragmented, and cannot (in general) be presented as an unified document.

A ColDoc tries to get the best of two publishing frameworks.


Code
====

The code is open source, it is available at
https://github.com/mennucc/ColDoc_project

The code uses Django, that is implemented using the Python language;
it also uses some JavaScript snippets for interactive features.

The current version of the code is `0.2`.

Authors
-------

This software is Copyright 2019-23
`Andrea C. G. Mennucci <https://www.sns.it/it/persona/andrea-carlo-giuseppe-mennucci>`_

License
-------

See file `LICENSE.txt` in the code distribution


Features
========

Code, portal, document
----------------------

This project is structured to keep separation between
the *code*, the *portal*, and the *data*.

Foremost, we install the *code* following the instructions in the
:doc:`install section<install>`.

Then, we *deploy* the structure for a *portal* following the instructions in the
:doc:`deploy section<deploy>`.

Eventually, we add one or more *documents* in the *portal*.
See
:doc:`section <blobify>`
on how to prepare a document for its splitting and uploading into a *portal*.

(You may also deploy multiple *portals* using the same *code*).

Access management
-----------------

Access to the whole document, or parts whereof, can be tuned.

See the
:doc:`section on permissions <permission>`
for details.


UUID and blobs
--------------

When a `LaTeX` document is inserted into a *portal*, it is *blobified*: it
is divided in many small files, called *blobs*,
each identified by an `UUID` (an unique identifier).

The purpose is twofold:

- each blob can be viewed conveniently by itself: the portal
  will compile an HTML representation of it, that is easily
  accessible (it also well adapts to mobile viewers),
  as well as a compact PDF representation (using the *standalone* class).

- The UUID is a permanent identifier for that content:
  even if other material is added before that part of LaTeX,
  the UUID associated to it will not change (contrary to
  ordinary references in LaTeX); UUIDs can also be used
  to reference from *outside* of the document, using appropriate
  web URLs.

Note that an UUID can reference to different versions of the same object:

- for images, there may be different formats available;

- for text, different languages may be available.

Moreover, the portal will compile the whole document, as PDF and as HTML.
The whole document contains UUID markers, of the form `[XXX]`,
that can be used to jump to the web page of that UUID; vice-versa in the web page
of the UUID there are links to view that UUID in the context
of the whole document.


Documentation
=============

All documentation is in the "``docs``" directory.

The documentation is in RST format, so it is mostly standard text:
you can read it in the files inside `docs/source`.

By using  `sphinx` toolset, the documentation
can be compiled to other formats; an HTML version is already available,
for your convenience: browse it by

.. code:: shell

	  firefox docs/build/html/index.html


Compile
-------

To compile the documentation, you will need the `sphinx` toolset.
To install it:

.. code:: shell

	  pip3 install sphinx sphinx-copybuttons


or, if you prefer, in Debian-based systems (like Ubuntu):

.. code:: shell

	  sudo apt install python3-sphinx python3-sphinx-copybutton

Then

.. code:: shell

	  cd docs
	  make html

or any other format that you wish.


Quick start
===========

If just want to see the code in action:
install the code and the prerequisite libraries
as explained in the
:doc:`install section<install>`;
then follow commands in the
:doc:`test section<test>`
to create a test portal.

EDB portal
==========

This software is used to run the portal https://coldoc.sns.it
that serves a document containing math exercises (nicknamed *EDB*)

Getting help
============

To get more help:

coldoc.staff@sns.it



