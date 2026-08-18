"""Errors for the `members` domain."""

class MemberNotFound(Exception):
    pass


class MemberDuplicateException(Exception):
    pass


class MemberPasswordMismatch(Exception):
    pass
