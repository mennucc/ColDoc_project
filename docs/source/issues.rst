Known issues
============

Sometimes an incompatibility arises when using the option `backref` in
`hyperref` and using `\\url` in bibliographical entries inside the
`\\begin{thebibliography}` environment; reformatting entries, (adding
`\\newblock`, adding an extra newline before `\\end{thebibliography}`
) may solve it.
For some unfathomable reason, this `bug` is not
triggered when `\\url` is used in bibliographical entries inside a
`.bib` file, later processed with `bibtex`.
