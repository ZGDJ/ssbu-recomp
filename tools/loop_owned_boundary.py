"""Compose the owned Windows child with the admission-owned final check.

No CLI, sampler or readiness defaults. The caller must supply the remaining
Boundaries fields, full packet validators and post gates. An optional trusted
failure_observer(error) collects after proven direct-child exit when a native
receipt/cleanup error prevents admission's normal postidentity callback. It
must return None or raise. Collection never substitutes a CompletedProcess,
releases exclusion or advances the journal, even if its own persistence fails.
"""
from pathlib import Path


def native_factory(receipt_directory, *, timeout_seconds, admission, process,
                   failure_observer=None):
    """Use the already verified module objects, preserving exception identity."""
    directory = Path(receipt_directory)
    if not directory.is_absolute():
        raise ValueError('absolute child receipt directory required')
    if failure_observer is not None and not callable(failure_observer):
        raise ValueError('trusted failure observer must be callable')
    def create(final_creation_check):
        native = process.WindowsNative(directory,
            not_created_error=admission.NativeNotCreated,
            timeout_seconds=timeout_seconds,
            verify_creation=final_creation_check)
        if failure_observer is None:
            return native
        def observed_native(cmd, **kwargs):
            try:
                return native(cmd, **kwargs)
            except process.NativeProcessError as error:
                # Only the owning boundary's actual exception class can select
                # this path. Unknown creation/lifetime must not read live inputs
                # as if they were a stable post-run inventory.
                if (error.child_created is True and error.exit_proven is True and
                        type(error.returncode) is int):
                    try:
                        if failure_observer(error) is not None:
                            raise ValueError('failure observer must complete or raise')
                    except BaseException as observation_error:
                        # Keep the ORIGINAL native failure and its lifetime
                        # diagnostics, including when the output filesystem fails.
                        error.failure_observation_error = observation_error
                raise
        return observed_native
    return create
