"""List of supported VLAN IDs - Country/Region."""

from typing import Literal, NamedTuple


class OPCOVLANs(NamedTuple):
    """Triple Play VLAN ID details including Optical ME mode.

    If a service is not provided, mark the VLAN id as 0.
    """

    data: int
    voice: int
    oam: int
    me_mode: Literal["VEIP", "PPTP"]  # Managed Entity Mode

    @property
    def vlan_count(self) -> int:
        """Return the count of service VLANs that an OPCO supports.

        :return: vlan count
        :rtype: int
        """
        return len([idx for idx in (self.data, self.voice, self.oam) if idx])


VLAN_PROFILES = {
    "OPCO1": OPCOVLANs(100, 200, 400, "VEIP"),
}
