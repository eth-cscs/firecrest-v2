from lib.datatransfers.datatransfer_base import (
    S3DataTransferDirective,
    DataTransferOperation,
)


class S3DataTransferOperation(DataTransferOperation):
    transfer_directives: S3DataTransferDirective
