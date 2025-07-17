"""XGPONCPESW Template module."""

from abc import abstractmethod

from boardfarm3.templates.cpe.cpe_sw import CPESW


class XGPONCPESW(CPESW):
    """XGPONCPESW Template class."""

    @property
    @abstractmethod
    def manufacturer_oui(self) -> str:
        """Get the manufacturer oui value.

        :return: manufacturer oui
        :rtype: str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def product_id(self) -> str:
        """Get the product id value.

        :return: product id
        :rtype: str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def serial_number(self) -> str:
        """Get the serial number.

        :return: serial number
        :rtype: str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def nvram_profile(self) -> str:
        """Get the profile saved in Non-volatile RAM.

        :return: name of the profile
        :rtype: str
        """
        raise NotImplementedError
