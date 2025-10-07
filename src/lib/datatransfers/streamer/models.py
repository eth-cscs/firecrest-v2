from lib.datatransfers.datatransfer_base import (
    StreamerDataTransferDirective,
    DataTransferOperation,
)


class StreamerDataTransferOperation(DataTransferOperation):
    transfer_directives: StreamerDataTransferDirective
