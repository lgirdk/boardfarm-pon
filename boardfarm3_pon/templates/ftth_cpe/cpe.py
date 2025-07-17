"""XGPON CPE template."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from boardfarm3.templates.cpe.cpe import CPE

if TYPE_CHECKING:
    from boardfarm3_pon.templates.ftth_cpe.cpe_hw import XGPONCPEHW
    from boardfarm3_pon.templates.ftth_cpe.cpe_sw import XGPONCPESW


class XGPONCPE(CPE):
    """CPE Template."""

    @property
    @abstractmethod
    def hw(self) -> XGPONCPEHW:  # pylint: disable=invalid-name
        """CPE Software."""
        raise NotImplementedError

    @property
    @abstractmethod
    def sw(self) -> XGPONCPESW:  # pylint: disable=invalid-name
        """CPE Software."""
        raise NotImplementedError

    @abstractmethod
    def get_managed_entity_mode(self) -> str:
        """Get the XGS-PON operation mode.

        :return: XGS-PON operation mode of CPE, VEIP/PPTP
        :rtype: str
        """
        raise NotImplementedError

    @abstractmethod
    def get_pon_operational_state(self) -> str:
        """Return the operational status of the GPON interface on the board.

        :return: the PON state (G-PON/E-PON/XGS-PON)
        :rtype: str
        """
        raise NotImplementedError

    def get_pon_serial_number(self) -> str:
        """Return the ONU serial number.

        The ONU / ONT serial number is a unique ID (non-rewritable) defined
        for each optical communication device.

        According to the standard, the serial number is defined as 8 bytes,
        but the upper 4 bytes are defined as the vendor ID (Vendor ID) and
        the lower 4 bytes are defined as the serial number defined by the
        vendor.

        :return: ONU serial number
        :rtype: str
        """
        return self.hw.gpon_serial_number
