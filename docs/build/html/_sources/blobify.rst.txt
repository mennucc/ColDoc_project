Blobify
=======

This section explains how to import a LaTeX document
into a ColDoc portal.

Since the portal will use `plastex` to convert
LaTeX to HTML, and `pdflatex` with the `standalone` package
for compact PDF representation of UUIDs, some
changes have to be made.

Following are instructions, and you may also
want to see in the directory `test/paper` for a complete working example.

In your LaTeX document, you should set the language as

.. code:: TeX

	  \usepackage[english]{babel}

and not as

.. code:: TeX

	  \documentclass[english]{article}


Then, right after the `documentclass` statement, add

.. code:: TeX

          \newif\ifplastex\plastexfalse
	  %
	  \ifplastex\else
	  \ifdefined\CurrentFile\else
	  \usepackage{currfile}
	  \fi\fi

The conditional `\ifplastex` will be forcibly set to true when compiling using
`plastex`.
	  
This snippet will also load the package `currfile` only when compiling
with older LaTeX (older than 2019); it will be used for internal
checkpointing.

Plastex tweaks
--------------

Then wrap all code that
is not compatible with plastex (code that sets fonts etc etc)
as follows

.. code:: TeX

	  \ifplastex\else
	   % set fonts ...
	  \fi

Also, you will have to replace some packages that do not
work well with `plastex`, as in this example

.. code:: TeX

	  \ifplastex
	  % plastex does not know of these
	  \def\eqref{\ref}
	  \fi
	  %
	  \ifplastex
	  % https://github.com/mathjax/MathJax/issues/1081
	  \def\sfrac{\frac}
	  \else
	  \usepackage{xfrac}
	  \fi
	  %
	  \ifplastex
	  % plastex does not know varioref
	  \def\vref{\ref}
	  \def\vpageref{\pageref}
	  \else
	  \usepackage{varioref}
	  \fi


`See plastex docs for details <http://plastex.sourceforge.net/plastex/sect0008.html>`_

Standalone tweaks
-----------------

You should also wrap all the code in the preamble that modifies
page geometry so that it is ignored in standalone mode,
as in this example:

.. code:: TeX

	  \ifplastex\else\ifstandalone\else
	  \usepackage[margin=18ex,headheight=16pt]{geometry}
	  \usepackage{fancyhdr}
	  \pagestyle{fancy}
	  \fi\fi


`See standalone docs for details <https://ctan.org/pkg/standalone>`_



Multiple LaTeX format
---------------------

It is possible to prepare a LaTeX document
that can be compiled using different engines:
`pdflatex`, `xelatex` or `lualatex`

To this end, you should install the latest
version of the `iftex` package from
https://www.ctan.org/pkg/iftex

Then add a snippet in the document preamble
as follows:

.. code:: TeX

	  \usepackage{iftex}
	  %%%%%%%%% use conditionals to load some engine-specific packages
	  \ifplastex
	   % code for plastex
	   \newcommand\mathbbm[1]{{\mathbb{#1}}}
	  \else\iftutex
	  % code for xetex or luatex
	    \input{preamble_xelatex}
	  \else
	   % code for standard (pdf)latex
	     \input{preamble_pdflatex}
	  \fi\fi

Then put in the file `preamble_xelatex.tex` all
commands to setup fonts for `xelatex` or `lualatex`;
and similarly in `preamble_pdflatex.tex` for `pdflatex`.


Downloading, and compiling single UUIDs
---------------------------------------

You should also move all your favorite customizations
in a file `preamble_definitions.tex`

- loading of packages such as `amsthm`, `amsmath`

- definitions for theorems and such

- personal macros

- ...etc...

There is a provision in the *portal* so
that users may download the LaTeX of a single UUID:
the portal will add enough LaTeX code so that
it will be possible to compile that UUID;
so it will add to the bundle

- `preamble_pdflatex.tex` or `preamble_xelatex.tex`,
  for document-related definition;

- that file  `preamble_definitions.tex`
  so that the user will have
  a copy of all the needed macros and definitions,

to be able to compile that blob.

Check it all
------------

Check that the document compiles fine to HTML
by invoking PlasTeX on your document using

.. code:: shell

	  plastex -d output_html document.tex

(it is recommended that you use the `plastex`
version that was installed 
:doc:`in the installation phase <install>`)

And check that it still compiles fine with
standard `pdflatex`

Then try to import in a test portal. Setup the test portal as follows

.. code:: shell

	  export COLDOC_SITE_ROOT=${COLDOC_SRC_ROOT}/test/tmp/test_site
	  cd  ${COLDOC_SRC_ROOT}
	  make -C test clean
	  make -C test django_deploy

Then try to import your document in the portal

.. code:: shell

	  ColDocDjango/blob_inator.py --coldoc-site-root ${COLDOC_SITE_ROOT} --coldoc-nick=testdoc --ZS --SAT  --split-sections --editor=ed_itor --author=jsmith --lang=eng yourdir/yourdocument.tex

note that:

- if your document best compiles with a specific engine,
  use the  `--latex-engine` option of  `blob_inator.py`
  to specify which;

- if you use non-standard commands to display images,
  add them to the  command line options for `blob_inator.py`
  as  `--split-graphic mypicturecommand`.
  (Warning: it is assumed that `mypicturecommand` uses
  the same syntax of `includegraphics`).

Then check if the document can be compiled

.. code:: shell

	  ColDocDjango/latex.py --coldoc-site-root ${COLDOC_SITE_ROOT} --coldoc-nick=testdoc --url-UUID="http://localhost:8000/UUID/testdoc/" all


and eventually run the test portal

.. code:: shell

	  make -C test django_run &

and access the web portal at `http://localhost:8000`.

Try authenticating using the different users
(see the output of `django_deploy` for usernames and passwords).

Check that everything looks fine.

Check in particular that images were imported correctly.


If you are not satisfied, or if something fails:

- tweak your document,

- try different command line options for `blob_inator.py`

If the result  is satisfactory enough, that is,
if only small changes are needed,
you can also change the document *inside the portal*
by editing the files inside `${COLDOC_SITE_ROOT}/coldocs/testdoc/blobs/`.
Note that the data structure can be compiled from the command line, using

.. code:: shell

	  cd ${COLDOC_SITE_ROOT}/coldocs/testdoc/blobs/
	  pdflatex main_eng.tex
	  plastex -d main_html main_eng.tex

where *eng* may be replaced by the desired language.

Multilingual documents
----------------------

In this regard, to be able to compute a
multilingual document from the command line,
you may also add in the preamble the snippet of code

.. code:: TeX

	  %%% this part will be skipped when compiled inside ColDoc
	  \ifdefined\ColDocAPI\else
	  \usepackage{coldoc_standalone}
	  \fi

and copy that file `coldoc_standalone.sty` to
the directory of your main LaTeX file, and adapt it to your needs.
