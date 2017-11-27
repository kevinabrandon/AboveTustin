import sys


def error(fmt, *args):
    sys.stdout.flush()
    sys.stderr.write((fmt % args) + '\n')
