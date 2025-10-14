from lib.datatransfers.datatransfer_base import (
    WormholeDataTransferDirective,
    WormholeDataTransferInfo,
    DataTransferOperation,
)


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective
