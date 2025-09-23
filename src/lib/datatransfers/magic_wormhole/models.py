from lib.datatransfers.datatransfer_base import (
    WormholeDataTransferDirective,
    DataTransferOperation,
)


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective
