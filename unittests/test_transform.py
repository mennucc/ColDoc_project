import os, sys, io, unittest

testdir = os.path.dirname(os.path.realpath(__file__))
sourcedir = os.path.dirname(testdir)

if __name__ == '__main__':
    sys.path.append(sourcedir)

from ColDoc import transform as T



latex_file = os.path.join(sourcedir, 'test', 'paper', 'sec1.tex')

latex_correct =  r"""
\begin{A}{\begin{B}%comment
\begin{equation}
  \exp  w
 \end{equation}
\bgroup
  \(\cos  x \)
  \[\sin  y\]
  $\log   t$
  $$\int   z$$
\egroup
\end{B}\end{A}
"""

class TestTransform(unittest.TestCase):

    def test_tokenizer(self):
        helper=T.squash_helper_token2unicode()
        #print('max key', helper.max_key())
        s = set()
        for k in range(helper.max_key()):
            u = helper.key2text(k)
            assert u not in s
            s.add(u)
            j = helper.text2key(u)
            assert j == k

    def test_out_of_range(self):
        helper=T.squash_helper_token2unicode()
        with self.assertRaises(ValueError):
            helper.text2key('A')

    def test_accents_to_unicode(self):
        helper=T.squash_helper_accents_to_unicode()
        inp = io.StringIO(r'\~u\`{e}')
        out = io.StringIO()
        T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , r'ũè')
        self.assertFalse(helper.stack)


    def test_dedollarize_inline(self):
        helper=T.squash_helper_dedollarize()
        inp = io.StringIO(r'$\cos$')
        out = io.StringIO()
        T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , r'\(\cos\)')
        self.assertFalse(helper.stack)

    def test_dedollarize_displayed(self):
        helper=T.squash_helper_dedollarize()
        inp = io.StringIO(r'$$\cos$$')
        out = io.StringIO()
        T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , r'\[\cos\]')
        self.assertFalse(helper.stack)

    def test_dedollarize_mixed(self):
        helper=T.squash_helper_dedollarize()
        inp = io.StringIO(r'$${\cos\text{$\sin$}}$$')
        out = io.StringIO()
        T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , r'\[{\cos\text{\(\sin\)}}\]')
        self.assertFalse(helper.stack)

    @unittest.skipIf(sys.version_info < (3,10,0), 'Needs Python 3.10')
    def test_closed_groups_no_log(self):
        inp = io.StringIO(latex_correct)
        out = io.StringIO()
        helper=T.squash_helper_stack()
        with self.assertNoLogs() as cm:
            T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , s)
        self.assertFalse(helper.stack)

    def test_closed_groups(self):
        inp = io.StringIO(latex_correct)
        out = io.StringIO()
        helper=T.squash_helper_stack()
        T.squash_latex(inp,out,{},helper)
        self.assertEqual(out.getvalue() , latex_correct)
        self.assertFalse(helper.stack)

    def test_unclosed_group_log(self):
        s = r"""
        \begin{G}
        \endgroup
        \end{G}
        """
        helper=T.squash_helper_stack()
        inp = io.StringIO(s)
        out = io.StringIO()
        with self.assertLogs() as cm:
            T.squash_latex(inp,out,{},helper)
        for r in cm.records:
            if ( '-vv' in sys.argv):
                sys.stdout.write('\n logs: ' + r.funcName + ' : ' + str(r.lineno) + ' : ' + r.msg % r.args + '\n')
            self.assertTrue('disaligned' in r.msg)
        self.assertEqual(out.getvalue() , s)
        self.assertFalse(helper.stack)

    def __test_tokenize_detokenize(self, text, willlog=False):
        helper=T.squash_helper_token2unicode()
        inp = io.StringIO(text)
        out = io.StringIO()
        if willlog:
            with self.assertLogs() as cm:
                T.squash_latex(inp,out,{},helper)
            R = cm.records
        elif sys.version_info >= (3,10,0):
            with self.assertNoLogs() as cm:
                T.squash_latex(inp,out,{},helper)
        else:
            T.squash_latex(inp,out,{},helper)
            R = []
        #json.dump(helper.token_map, open(tokens,'w'), indent=2)
        detok=T.unsquash_unicode2token(out.getvalue(), helper)
        if ( '-vv' in sys.argv): 
            print('\n',helper.unicode_map,'\n')
        self.assertEqual(detok, text)
        self.assertFalse(helper.stack)

    def test_tokenize_detokenize(self):
        return self.__test_tokenize_detokenize(latex_correct)

    def test_tokenize_detokenize_endgroup(self):
        return self.__test_tokenize_detokenize(r'\endgroup' + latex_correct, willlog=True)

    def test_tokenize_detokenize_end_itemize(self):
        return self.__test_tokenize_detokenize(r'\end{itemize}' + latex_correct, willlog=True)


    @unittest.skip('macros inside arguments of macros have an extra space at the end')
    def test_tokenize_detokenize_sec1(self):
        F=open(latex_file)
        text = F.read()
        F.close()
        self.maxDiff = None 
        return self.__test_tokenize_detokenize(text)



if __name__ == '__main__':
    unittest.main()
