from lib.datatransfers.datatransfer_base import (
    WormholeDataTransferDirective,
    WormholeDataTransferInfo,  # noqa: F401
    DataTransferOperation,
)


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective
