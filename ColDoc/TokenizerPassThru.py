from plasTeX.Tokenizer import *

class TokenizerPassThru(Tokenizer):
    def __init__(self, *args, **kwargs):
        self._pass_comments_ = True
        super().__init__(*args, **kwargs)
    @property
    def pass_comments(self):
        return self._pass_comments_
    @pass_comments.setter
    def pass_comments(self, value):
        self._pass_comments_ = value
    #
    def __iter__(self):
        """
        Iterate over tokens in the input stream

        Returns:
        generator that iterates through tokens in the stream

        """
        # Cache variables to prevent globol lookups during generator
        global Space, EscapeSequence
        Space = Space
        EscapeSequence = EscapeSequence
        mybuffer = self._tokBuffer
        charIter = self.iterchars()
        context = self.context
        pushChar = self.pushChar
        STATE_N = self.STATE_N
        STATE_M = self.STATE_M
        STATE_S = self.STATE_S
        ELEMENT_NODE = Node.ELEMENT_NODE
        CC_LETTER = Token.CC_LETTER
        CC_OTHER = Token.CC_OTHER
        CC_SPACE = Token.CC_SPACE
        CC_EOL = Token.CC_EOL
        CC_ESCAPE = Token.CC_ESCAPE
        CC_EOL = Token.CC_EOL
        CC_COMMENT = Token.CC_COMMENT
        CC_ACTIVE = Token.CC_ACTIVE
        prev = None

        while 1:

            # Purge mybuffer first
            while mybuffer:
                yield mybuffer.pop(0)

            # Get the next character
            try:
                token = next(charIter)
            except StopIteration:
                return

            if token.nodeType == ELEMENT_NODE:
                raise ValueError('Expanded tokens should never make it here')

            code = token.catcode

            # Short circuit letters and other since they are so common
            if code in (CC_LETTER, CC_OTHER):
                self.state = STATE_M

            # Whitespace
            elif code == CC_SPACE:
                ##if self.state  == STATE_S or self.state == STATE_N:
                ##    continue
                self.state = STATE_S
                ##token = Space(' ')

            # End of line
            elif code == CC_EOL:
                state = self.state
                if state == STATE_S:
                    self.state = STATE_N
                    ##continue
                elif state == STATE_M:
                    ##token = Space(' ')
                    code = CC_SPACE
                    self.state = STATE_N
                elif state == STATE_N:
                    # ord(token) != 10 is the same as saying token != '\n'
                    # but it is much faster.
                    if ord(token) != 10:
                        self.lineNumber += 1
                        if self._pass_comments_:
                            yield(Comment(self.readline()))
                        else:
                            self.readline()
                    ##token = EscapeSequence('par')
                    # Prevent adjacent paragraphs
                    ##if prev == token:
                    ##   continue
                    code = CC_ESCAPE

            # Escape sequence
            elif code == CC_ESCAPE:

                # Get name of command sequence
                self.state = STATE_M

                for token in charIter:

                    if token.catcode == CC_LETTER:
                        word = [token]
                        for t in charIter:
                            if t.catcode == CC_LETTER:
                                word.append(t)
                            else:
                                pushChar(t)
                                break
                        token = EscapeSequence(''.join(word))

                    elif token.catcode == CC_EOL:
                        #pushChar(token)
                        #token = EscapeSequence()
                        token = Space(' ')
                        self.state = STATE_S

                    else:
                        token = EscapeSequence(token)
#
# Because we can implement macros both in LaTeX and Python, we don't
# always want the whitespace to be eaten.  For example, implementing
# \chardef\%=`% would be \char{`%} in TeX, but in Python it's just
# another macro class that would eat whitspace incorrectly.  So we
# have to do this kind of thing in the parse() method of Macro.
#
                    if token.catcode != CC_EOL:
# HACK: I couldn't get the parse() thing to work so I'm just not
#       going to parse whitespace after EscapeSequences that end in
#       non-letter characters as a half-assed solution.
                        if token[-1] in encoding.stringletters():
                            # Absorb following whitespace
                            self.state = STATE_S

                    break

                else: token = EscapeSequence()

                # Check for any \let aliases
                token = context.get_let(token)

                # TODO: This action should be generalized so that the
                #       tokens are processed recursively
                if token is not token and token.catcode == CC_COMMENT:
                    if self._pass_comments_:
                        yield(Comment(self.readline()))
                    else:
                        self.readline()
                    self.lineNumber += 1
                    self.state = STATE_N
                    continue

            elif code == CC_COMMENT:
                if self._pass_comments_:
                    yield(Comment(self.readline()))
                else:
                    self.readline()
                self.lineNumber += 1
                self.state = STATE_N
                continue

            elif code == CC_ACTIVE:
                token = EscapeSequence('active::%s' % token)
                token = context.get_let(token)
                self.state = STATE_M

            else:
                self.state = STATE_M

            prev = token

            yield token
