from lib.datatransfers.datatransfer_base import (
    StreamerDataTransferDirective,
    StreamerDataTransferInfo,  # noqa: F401
    DataTransferOperation,
)


class StreamerDataTransferOperation(DataTransferOperation):
    transfer_directives: StreamerDataTransferDirective
