from lib.datatransfers.datatransfer_base import (
    S3DataTransferDirective,
    S3DataTransferInfo,  # F401
    DataTransferOperation,
)


class S3DataTransferOperation(DataTransferOperation):
    transfer_directives: S3DataTransferDirective
