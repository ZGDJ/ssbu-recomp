"""Compose the owned Windows child with the admission-owned final check.

No CLI, sampler or readiness defaults. The caller must supply the remaining
Boundaries fields, full packet validators and post gates. This module only
binds the actual admission lease/sample closure to OS child creation.
"""
from pathlib import Path


def native_factory(receipt_directory, *, timeout_seconds, admission, process):
    """Use the already verified module objects, preserving exception identity."""
    directory = Path(receipt_directory)
    if not directory.is_absolute():
        raise ValueError('absolute child receipt directory required')
    def create(final_creation_check):
        return process.WindowsNative(directory,
            not_created_error=admission.NativeNotCreated,
            timeout_seconds=timeout_seconds,
            verify_creation=final_creation_check)
    return create
