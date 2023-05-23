Multiple languages
==================

Overview
--------

Languages are specified  using the 3 letter codes
`from ISO_639-3 <https://en.wikipedia.org/wiki/ISO_639-3>`_

The list of languages supported by each coldoc document is in the
field `languages` of the `coldoc` record; this can be changed using
the administrative interface.

All language codes may be freely used, but the codes `zxx`, `mul` and `und`
have a special significance, explained in the following.

The metadata of each UUID contains a `lang` record, which contains all language
codes that a blob is available in. So if `lang` contains `eng` and `ita` (in two
lines) then it is expected that there are two files `blob_eng.tex`
and `blob_ita.tex`

A special significance is given to the code `zxx` : when present,
it should be the only language: it means that all blobs are of the form `blob_zxx.???`,
and they do not contain linguistic content; it is used mainly for graphics.

A special significance is given to the code `und` : when present,
it should be the only language: it means that all blobs are of the form `blob_und.???`, such as
the bibliography (copied to a  `blob_und.bib`), or style files (copied to a `blob_und.sty`).

Single language document
------------------------

When importing a document using `blob_inator` with a command option `--lang xxx`,
a single-language document is created.

Each blob containing LaTeX code will be stored with name `blob_xxx.tex`

It can be later converted to a multiple-language document, see below.

Multiple language documents
---------------------------

When the coldoc document lists more than one language in the
field `languages` of the `coldoc` record, then it is
a *multiple language document*.

Each UUID must have multiple blobs, one for each language.
There are two ways to manage this.

- You can manage directly different language versions of a blob:
  in the *tools* tab, use *add* to create missing languages versions;
  use *relabel* to change the language of a blob if it is mislabeled;
  use *del* to delete a language version.
  In this case, there will  be no automatic processing (see `mul` below).
  Warning: if you add a child to this blob
  it is up to you to include `\\input` command in all language versions!

- Using the `mul` (*multiple languages*) method.
  

The `mul` (*multiple languages*) method
---------------------------------------

Suppose that  `aaa,bbb,ccc,ddd` is the list of supported languages
(as listed in the field `languages` of the `coldoc` record).

When an UUID has `mul` as the (only) language, it is subjected to
some automatic processing.

In this case, by using the web interface you will edit the blob named
`blob_mul.tex`.

Each time `blob_mul.tex` is changed, an automatic processing method will generate
all needed language blobs.

Supposing that `zzz` is a language in the list `aaa,bbb,ccc,ddd`,
when converting  `blob_mul.tex` to  `blob_zzz.tex`:

- all input-type command (that input other blobs) will be language converted, e.g.
  `\\input{UUID/0/0/F/blob_mul.tex}` will be converted to
  `\\input{UUID/0/0/F/blob_zzz.tex}`
  
- lines that begin with the header tag `\\CDLzzz` will be kept
  (and the header  `\\CDLzzz` will be deleted),
  lines beginning with `\\CDLxxx` for any other language  will be stripped.


Moreover, when compiling the blob,  *language conditionals*
of the form `\\ifCDLxxx` will be defined
for all supported languages `aaa,bbb,ccc,ddd` , and one (and only one) will
be set to true; precisely, when compiling `blob_xxx.tex` only the conditional
`\\ifCDLxxx` will be set to true.

A similar behaviour is valid for bibliographic content that has code
language `zxx` or `und` : multiple language views are compiled, using
the `aux` file from the main document (the private version).

Importing a `mul` document
--------------------------

When importing a document using `blob_inator` with a command option `--lang mul,aaa,bbb,ccc,ddd`,
a multiple-language document is created, where `aaa,bbb,ccc,ddd` is the list of supported languages.

Each blob containing LaTeX code will be stored with name `blob_mul.tex`

Before compiling the document, each `blob_mul.tex` must be converted to multiple files
`blob_xxx.tex` where `xxx` is one of `aaa,bbb,ccc,ddd`; this can be done
with the `helper.py gen_lang` command.

An example document is stored in `test/multlang` and can be imported in the test portal using `make django_multlang`.

Converting single to multi language
-----------------------------------

To convert a single-language document to multiple-language,
first you add other languages to the
field `languages` of the `coldoc` record (this can be done using
the administrative interface).

Then for each blob containing latex code, you can translate the content.

There are two ways.

- Using the *Multiple languages*  method. In the *tools* tab
  you use the `multlang` button; then
  you add translations of the content of the blob to all languages, using
  the conditionals or the header tags to mark them, as explained above.
  
- Alternatively, you can manage directly different language versions of a blob:
  in the *tools* tab, use *add* to create all neeeded languages versions,
  and then translate them one by one. In this case, there will
  be no automatic processing. Warning: if you add a child to this blob
  it is up to you to include `\\input` command in all language versions!

The former is particularly well suited for *sections* , or in general
any blob with a lot of children and little linguistic content.

The latter may be preferred for short blobs with only linguistic
content and no children.


Automatic translations
----------------------

The portal can interface to an automatic translator.

Currently there are hooks to connect to
`Microsoft translator <https://azure.microsoft.com/en-us/services/cognitive-services/translator/>`_
. If you have an account for that service, enter your credential into the `settings.py`
file in your ColDoc instance, uncommenting the lines

.. code:: Python

	  ## define these to use Microsoft Azure translation service
	  #AZURE_SUBSCRIPTION_KEY = "XXXXXXXXXXX"
	  #AZURE_LOCATION = "XXXXXXXXXXXXXX"

This will add a button `translate` in the `Tools` tab.

The portal will protect LaTeX commands, and the content of math environments,
before submitting your text to the automatic translator.
Currently, text inside math environments will not be translated.

Other tools
-----------

The command

.. code:: Python

	  ./ColDocDjango/helper.py  --coldoc-site-root ...  --coldoc-nick ...   count_untranslated_chars

will estimate how many characters are yet to be translated.

In the editor panes, the `Document checks` will also list the untranslated blobs.

