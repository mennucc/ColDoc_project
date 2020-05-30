======
ColDoc
======

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

The code is open source, it is available, please write to coldoc.staff@sns.it for details.

It is implemented using the Python language.

Documentation
=============

All documentation is in the "``docs``" directory.

The documentation is in RST format, so it is mostly standard text:
you can read it in the files inside `docs/source`.

Compile
-------

To compile the documentation, you will need the `sphinx` toolset.
To install it:

.. code:: shell

	  # pip3 install sphinx


or, if you prefer, in Debian-based systems (like Ubuntu):

.. code:: shell

	  # sudo apt show python3-sphinx



Then

.. code:: shell

	  # cd docs
	  # make html

or any other format that you wish. Then start browsing by

.. code:: shell

	  # firefox docs/html/index.html

Quick start
===========

If you're just getting started,
here's how we recommend you read the docs:

* First, read ``docs/source/install.rst`` for instructions on installing ColDoc.

* If you want to set up an actual deployment server, read
  ``docs/source/deploy.rst`` for instructions.


Getting help
============

To get more help:

coldoc.staff@sns.it



