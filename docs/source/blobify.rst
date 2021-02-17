Blobify
=======

This section explains how to import a LaTeX document

Prepare for PlasTeX
-------------------

Add

.. code:: shell

          \newif\ifplastex\plastexfals

on top of the preamble, and wrap all code that
is not compatible with plastex (sets fonts etc etc)

.. code:: shell

	  \ifplastex\else ... \fi

`See plastex docs for details <http://plastex.sourceforge.net/plastex/sect0008.html>`_


Check by invoking PlasTeX on your document

.. code:: shell

	  plastex -d output_html document.tex

Prepare for standalone
----------------------

Load the standalone package very early in the main document.

`See standalone docs for details <https://ctan.org/pkg/standalone>`_



You should wrap all the code that modifies
page geometry so that it is ignored in standalone mode

.. code:: shell

	  \ifstandalone\else
	  \usepackage[margin=18ex,headheight=16pt]{geometry}
	  \usepackage{fancyhdr}
	  \pagestyle{fancy}
	  \fi


You should set the language as

.. code:: shell

	  \usepackage[english]{babel}

and not as

.. code:: shell

	  \documentclass[english]{article}
