"""Setu: an eligibility agent that only states what it can prove against a fetched source.

Design invariant enforced across this package:
  No scheme name, URL, threshold, or eligibility rule is written in source code.
  Every scheme fact is derived at runtime from bytes the system actually fetched,
  and is traceable to the byte range it came from.
"""
