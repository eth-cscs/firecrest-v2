from lib.datatransfers.datatransfer_base import (
    WormholeDataTransferDirective,
    WormholeDataTransferInfo,  # F401
    DataTransferOperation,
)


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective
