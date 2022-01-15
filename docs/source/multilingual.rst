Multiple languages
==================

Overview
--------

Languages are specified  using the 3 letter codes
`from ISO_639-3 <https://en.wikipedia.org/wiki/ISO_639-3>`_

The list of languages supported by each coldoc document is in the
field `languages` of the `coldoc` record; this can be changed using
the administrative interface.

All language codes may be freely used, but the code `zxx` , `mul` and `und`
have a special significance, explained in the following.

The metadata of each blob contains a `lang` record, which contains all codes that
a blob is available in. So if `lang` contains `eng` and `ita` (in two
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

It can be later converted to a multiple-language document.

Multiple language documents
---------------------------

When importing a document using `blob_inator` with a command option `--lang mul,aaa,bbb,ccc,ddd`,
a multiple-language document is created, where `aaa,bbb,ccc,ddd` is the list of supported languages.

Each blob containing LaTeX code will be stored with name `blob_mul.tex`

Before compiling the document, each `blob_mul.tex` will be converted to multiple files
`blob_xxx.tex` where `xxx` is one of `aaa,bbb,ccc,ddd`.

In this phase, supposing that `zzz` is a language in the list `aaa,bbb,ccc,ddd`,
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

An example document is stored in `test/multlang` and can be imported in the test portal using `make django_multlang`.

Converting single to multi
--------------------------

To convert a single-language document to multiple-language,
first you add other languages to the
field `languages` of the `coldoc` record (this can be done using
the administrative interface).

Then for each blob containing latex code, you can translate the content.

There are two ways.

- Using the `Multiple languages` (`mul`) method. In the *tools* tab
  you relabel the blob to `Multiple languages` language;
  and you add translations of the content of the blob to all languages, using
  the conditionals or the header tags to mark them.
  
- Alternatively, you can manage directly different language versions of a blob:
  in the *tools* tab, use *add* to create all neeeded languages versions,
  and then translate them one by one. In this case, there will
  be no automatic processing. Warning: if you add a child to this blob
  it is up to you to include `\\input` command in all language versions!

The former is particularly well suited for *sections* , or in general
any blob with a lot of children and little linguistic content.

The latter may be preferred for short blobs with only linguistic
content and no children.


