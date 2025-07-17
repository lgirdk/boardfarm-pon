"""XGPONCPEHW Template module."""

from abc import abstractmethod

from boardfarm3.templates.cpe.cpe_hw import CPEHW


class XGPONCPEHW(CPEHW):
    """XGPONCPEHW Template class."""

    @property
    @abstractmethod
    def gpon_serial_number(self) -> str:
        """Get GPON serial number.

        ONU Serial ID that is registered on the OLT.

        :return: GPON serial ID
        :rtype: str
        """
        raise NotImplementedError
