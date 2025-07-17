"""OLT device template."""

from abc import abstractmethod

from boardfarm3.templates.line_termination import LTS


class OLT(LTS):
    """OLT device template."""

    @property
    @abstractmethod
    def service_vlan_data(self) -> int:
        """Return the service VLAN id configured for customer DATA service.

        :return: vlan id value
        :rtype: int
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def service_vlan_voice(self) -> int:
        """Return the service VLAN id configured for VOICE service.

        :return: vlan id value
        :rtype: int
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def service_vlan_oam(self) -> int:
        """Return the service VLAN id configured for OAM service.

        :return: vlan id value
        :rtype: int
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def service_vlan_triple_play(self) -> int:
        """Return the service VLAN id configured for all triple play services.

        :return: vlan id value
        :rtype: int
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def opco(self) -> str:
        """Return the OPCO name for which the OLT is being configured.

        :return: OPCO name
        :rtype: str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def bandwidth_profile(self) -> str:
        """Return the bandwidth profile configured against an OPCO.

        :return: OPCO name
        :rtype: str
        """
        raise NotImplementedError

    @abstractmethod
    def configure_ont_vlan(self, ont_serial: str, mac: str) -> None:
        """Configure customer and service network vlan.

        :param ont_serial: ONT's GPON serial number
        :type ont_serial: str
        :param mac: ONT's MAC address
        :type mac: str
        """
        raise NotImplementedError

    @abstractmethod
    def configure_slots(
        self,
        ont_serial: str,
        c_vlans: list[int],
        s_vlans: list[int],
    ) -> None:
        """To configure the slots.

        :param ont_serial: ONT's GPON serial number
        :type ont_serial: str
        :param c_vlans: list of customer network vlan id
        :type c_vlans: list[int]
        :param s_vlans: list of service provider network vlan id
        :type s_vlans: list[int]
        """
        raise NotImplementedError

    @abstractmethod
    def get_cpe_pon_operational_state(self, gpon_serial_number: str) -> str:
        """Get CPE's XGS-PON operational state.

        :param gpon_serial_number: ONT's GPON serial number
        :type gpon_serial_number: str
        :return: CPE XGS-PON line status
        :rtype: str
        """
        raise NotImplementedError

    @abstractmethod
    def get_ont_hw_version(self) -> str:
        """Get the ONT hw version.

        :return: ont hw version
        :rtype: str
        """
        raise NotImplementedError

    @abstractmethod
    def get_ont_hw_model(self) -> str:
        """Get ONT hw Model.

        :return: ont hw model value
        :rtype: str
        """
        raise NotImplementedError
