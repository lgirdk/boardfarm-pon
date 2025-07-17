"""Nokia_fx4_olt device module."""

from __future__ import annotations

import logging
import re
from argparse import Namespace
from io import StringIO
from time import sleep
from typing import TYPE_CHECKING, Any

import pandas as pd
from boardfarm3.devices.base_devices.boardfarm_device import BoardfarmDevice
from boardfarm3.exceptions import (
    ConfigurationFailure,
    DeviceConnectionError,
    EnvConfigError,
)
from boardfarm3.lib.connection_factory import connection_factory
from boardfarm3.lib.connections.connect_and_run import connect_and_run
from boardfarm3.lib.utils import get_nth_mac_address

from boardfarm3_pon.lib.dataclass.vlan_profile import VLAN_PROFILES, OPCOVLANs
from boardfarm3_pon.templates.olt import OLT

if TYPE_CHECKING:
    from boardfarm3.lib.boardfarm_pexpect import BoardfarmPexpect

_LOGGER = logging.getLogger(__name__)

_SERVICE_VLAN_COUNT = 3


class NokiaFx4OLT(OLT, BoardfarmDevice):  # pylint: disable=too-many-instance-attributes
    """Device class implementation for Nokia 7360 ISAM FX-4."""

    def __init__(self, config: dict[str, Any], cmdline_args: Namespace) -> None:
        """Initialize the Olt device.

        :param config: device config
        :type config: dict[str, Any]
        :param cmdline_args: command line arguments
        :type cmdline_args: Namespace
        :raises ConfigurationFailure: if CPE ONT ID is not present
        """
        self._prompt = ["typ:.*#"]
        self._user = "boardfarm"
        self._rtr_pw = self._rtr_username = "admin"
        self._rtr_prompt = ["\\*A:.*#", "A:.*#"]

        super().__init__(config=config, cmdline_args=cmdline_args)

        self._console: BoardfarmPexpect = None
        self._rtr_console: BoardfarmPexpect = None

        try:
            self.ont_id: str = self._config["ont_id"]
        except KeyError as exc:
            msg = "Mandatory CPE ONT ID missing!!"
            raise ConfigurationFailure(msg) from exc

        # Hardcoded VEIP and Ethernet IDs
        # Assumption: These IDs don't change across ONTs
        self._ont_slots = {
            "VEIP": {"slot": f"{self.ont_id}/4", "bridge": f"{self.ont_id}/4/1"},
            "PPTP": {"slot": f"{self.ont_id}/1", "bridge": f"{self.ont_id}/1/1"},
        }

    @property
    def _vlan(self) -> OPCOVLANs:
        """Return the VLAN list for a specific OPCO access type.

        :return: OPCO VLAN set
        :rtype: OPCOVLANs
        """
        return VLAN_PROFILES[self.opco]

    @property
    def service_vlan_data(self) -> int:
        """Return the service VLAN id configured for customer DATA service.

        :return: vlan id value
        :rtype: int
        """
        return self._config.get("service_data_vlan", -1)

    @property
    def service_vlan_voice(self) -> int:
        """Return the service VLAN id configured for VOICE service.

        :return: vlan id value
        :rtype: int
        """
        return self._config.get("service_voice_vlan", -1)

    @property
    def service_vlan_oam(self) -> int:
        """Return the service VLAN id configured for OAM service.

        :return: vlan id value
        :rtype: int
        """
        return self._config.get("service_oam_vlan", -1)

    @property
    def service_vlan_triple_play(self) -> int:
        """Return the service VLAN id configured for all triple play services.

        :return: vlan id value
        :rtype: int
        """
        return self._config.get("service_single_vlan", -1)

    @property
    def opco(self) -> str:
        """Return the OPCO country profile for which the OLT is being configured.

        :return: OPCO country profile name.
        :rtype: str
        """
        return self._config.get("opco", "")

    @property
    def bandwidth_profile(self) -> str:
        """Return the bandwidth profile configured against an OPCO.

        :return: OPCO name
        :rtype: str
        """
        return self._config.get("bandwidth_profile", "upHSI10G")

    @property
    def me_mode(self) -> str:
        """Return the ONT's ME Mode.

        Supported values ethernet/veip

        :return: ONT ME mode.
        :rtype: str
        """
        return self._config.get("me_mode", self._vlan.me_mode)

    def _connect(self) -> None:
        """Establish connection to the OLT via SSH."""
        self._console = connection_factory(
            self._config.get("connection_type"),
            f"{self.device_name}.console",
            username=self._user,
            password=f"{self._user}@12345",
            ip_addr=self._config.get("ipaddr"),
            port=self._config.get("port", "22"),
            shell_prompt=self._prompt,
            save_console_logs=self._cmdline_args.save_console_logs,
        )
        self._console.setwinsize(400, 400)
        # TODO: remove access of protected method making pwd optional
        self._console.login_to_server(
            self._console._password,  # pylint:disable=protected-access  # noqa: SLF001
        )

    def _connect_router(self) -> None:
        """Establish a connection to OLT's router via SSH.

        :raises exc_to_raise: if device does not connect.
        """
        exc_to_raise: DeviceConnectionError = None
        for _ in range(3):
            try:
                self._rtr_console = connection_factory(
                    self._config.get("connection_type"),
                    f"{self.device_name}.rtr-console",
                    username=self._rtr_username,
                    password=self._rtr_pw,
                    ip_addr=self._config.get("router_ipaddr"),
                    port=self._config.get("router_port", 22),
                    shell_prompt=self._rtr_prompt,
                    save_console_logs=self._cmdline_args.save_console_logs,
                )
                self._rtr_console.login_to_server(self._rtr_pw)
                break
            except DeviceConnectionError as exc:
                exc_to_raise = exc
                sleep(15)
        else:
            raise exc_to_raise

    def _populate_vlan_lists(self, vlan_count: int) -> tuple[list[int], list[int]]:
        """Populate customer and service vlan id.

        :param vlan_count: no. of vlans that need to be configured
        :type vlan_count: int
        :raises EnvConfigError: sku is not part of Multi-VLAN arch
        :return: ID for customer & service provider vlan
        :rtype: tuple[list[int], list[int]]
        """
        c_vlans: list[int] = []
        s_vlans: list[int] = []

        if vlan_count > 1:
            if not self._vlan.vlan_count > 1:
                msg = f"{self.opco} is not part of Multi-VLAN arch"
                raise EnvConfigError(msg)

            if self.service_vlan_data:
                c_vlans.append(self._vlan.data)
                s_vlans.append(self.service_vlan_data)

            if self.service_vlan_voice:
                c_vlans.append(self._vlan.voice)
                s_vlans.append(self.service_vlan_voice)

            if self.service_vlan_oam and vlan_count == _SERVICE_VLAN_COUNT:
                c_vlans.append(self._vlan.oam)
                s_vlans.append(self.service_vlan_oam)

        elif vlan_count == 1:
            if self._vlan.vlan_count != 1:
                _LOGGER.warning("%s is not part of Single-VLAN arch", self.opco)
                _LOGGER.warning("Only DATA vlan shall be picked up!!")
            if self.service_vlan_triple_play:
                c_vlans.append(self._vlan.data)
                s_vlans.append(self.service_vlan_triple_play)

        return c_vlans, s_vlans

    @connect_and_run
    def configure_ont_vlan(self, ont_serial: str, mac: str) -> None:
        """Configure customer and service network vlan.

        :param ont_serial: ONT's GPON serial number
        :type ont_serial: str
        :param mac: ONT's MAC address
        :type mac: str
        """
        c_vlans, s_vlans = self._populate_vlan_lists(self._config.get("vlan_count"))

        # Simpler to check all possible bridge ids, instead of reading ENV
        curr_vlans = []
        bridge_id = self._ont_slots[self.me_mode]["bridge"]
        vlan_output = self._console.execute_command(
            f"info configure bridge port {bridge_id} flat",
        )
        if not ("Error : " in vlan_output and "does not exist" in vlan_output):
            curr_vlans = [
                int(re.findall(r"vlan-id (\d+)", i)[0])
                for i in vlan_output.splitlines()
                if "vlan-id" in i
            ]

        # Remove ONT slots and replace with desired ENV slot configuration
        if set(c_vlans) != set(curr_vlans):
            self.configure_slots(ont_serial, c_vlans, s_vlans)
            self.validate_ont_configuration(c_vlans, s_vlans)
            # clear the DHCP MAC state.
            self._clear_lease_states(mac)

    @connect_and_run
    def validate_ont_configuration(
        self,
        c_vlans: list[int],
        s_vlans: list[int],
    ) -> None:
        """To validate the ont configuration.

        :param c_vlans: list of customer network vlan id
        :type c_vlans: list[int]
        :param s_vlans: list of service provider network vlan id
        :type s_vlans: list[int]
        :raises ConfigurationFailure: Failed to configure ONT slot
        :raises ConfigurationFailure: Failed to configure upstream-queues for ONT
        :raises ConfigurationFailure: Invalid VLAN configuration
        :raises ConfigurationFailure: vlan port not open
        """
        bridge_id = self._ont_slots[self.me_mode]["bridge"]
        slot_id = self._ont_slots[self.me_mode]["slot"]

        ont_mode = "veip" if self.me_mode == "VEIP" else "ethernet"

        # Validate slot
        slot_out = self._console.execute_command(
            f"info configure equipment ont slot {slot_id} flat",
        )
        if f"{slot_id} planned-card-type {ont_mode}" not in slot_out:
            msg = f"Failed to configure ONT slot properly.\nOLT output: {slot_out}"
            raise ConfigurationFailure(msg)

        # Validate QOS
        qos_out = self._console.execute_command(
            f"info configure qos interface {bridge_id} flat",
        )
        if f"{bridge_id} upstream-queue" not in qos_out:
            msg = f"Failed to configure upstream-queues for ONT.\nOLT output: {qos_out}"
            raise ConfigurationFailure(msg)

        # Validate Bridge VLAN configuration
        vlan_out = self._console.execute_command(
            f"info configure bridge port {bridge_id} flat",
        )
        for c_vlan, s_vlan in zip(c_vlans, s_vlans):
            if (
                f"vlan-id {c_vlan} tag single-tagged l2fwder-vlan {s_vlan}"
                not in vlan_out
            ):
                msg = (
                    f"Invalid VLAN configuration for {c_vlan}:{s_vlan}."
                    "\nOLT output: {vlan_out}"
                )
                raise ConfigurationFailure(msg)

        if ont_mode == "ethernet":
            for c_vlan in c_vlans:
                if "admin-up" not in self._console.execute_command(
                    "info configure interface"
                    f" port vlan-port:{bridge_id}:{c_vlan} flat",
                ):
                    msg = f"vlan-port {c_vlan} not open!"
                    raise ConfigurationFailure(msg)

    def _clean_ont_slot_config(self) -> None:
        """Clean the ONT config."""
        self._console.sendline(
            f"configure equipment ont slot {self._ont_slots['PPTP']['slot']}"
            " admin-state down",
        )
        self._console.sendline(
            f"configure equipment ont slot {self._ont_slots['VEIP']['slot']}"
            " admin-state down",
        )
        self._console.sendline(
            f"configure equipment ont no slot {self._ont_slots['PPTP']['slot']}",
        )
        self._console.sendline(
            f"configure equipment ont no slot {self._ont_slots['VEIP']['slot']}",
        )
        self._console.execute_command("exit all")

    @connect_and_run
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
        # clear all config first
        self._clean_ont_slot_config()

        if self.me_mode == "PPTP":
            self._configure_eth_port(ont_serial, c_vlans, s_vlans)
        elif self.me_mode == "VEIP":
            self._configure_veip_port(ont_serial, c_vlans, s_vlans)

    def _configure_veip_port(
        self,
        ont_serial: str,
        c_vlans: list[int],
        s_vlans: list[int],
    ) -> None:
        """To configure veip port.

        :param ont_serial: ONT's GPON serial number
        :type ont_serial: str
        :param c_vlans: list of customer network vlan id
        :type c_vlans: list[int]
        :param s_vlans: list of service provider network vlan id
        :type s_vlans: list[int]
        """
        slot_id = self._ont_slots["VEIP"]["slot"]
        bridge_id = self._ont_slots["VEIP"]["bridge"]

        veip_cmds = [
            # Add the ONT slot
            f"configure equipment ont slot {slot_id} "
            "planned-card-type veip plndnumdataports 1 plndnumvoiceports 0 "
            "admin-state up",
            f"configure interface port uni:{bridge_id} admin-up user "
            f"{ont_serial.split(':')[-1]}",
            # Configure Upstream QOS
            # Note: Hardcoded use of upHSI10G
            f"configure qos interface {bridge_id} upstream-queue 0 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
            f"configure qos interface {bridge_id} upstream-queue 3 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
            f"configure qos interface {bridge_id} upstream-queue 5 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
        ]
        for cmd in veip_cmds:
            self._console.sendline(cmd)
        self._console.execute_command("exit all")
        self._configure_bridge_vlan(bridge_id, c_vlans, s_vlans)

    def _configure_eth_port(
        self,
        ont_serial: str,
        c_vlans: list[int],
        s_vlans: list[int],
    ) -> None:
        """To configure ethernet port.

        :param ont_serial: ONT's GPON serial number
        :type ont_serial: str
        :param c_vlans: list of customer network vlan id
        :type c_vlans: list[int]
        :param s_vlans: list of service provider network vlan id
        :type s_vlans: list[int]
        """
        slot_id = self._ont_slots["PPTP"]["slot"]
        bridge_id = self._ont_slots["PPTP"]["bridge"]

        eth_cmds = [
            # Add the ONT slot for PPTP
            f"configure equipment ont slot {slot_id} "
            "planned-card-type ethernet plndnumdataports 1 plndnumvoiceports 0 "
            "admin-state up",
            # Configure the UNI for PPTP bridge ID
            f"configure interface port uni:{bridge_id} admin-up",
            # Configure Upstream QOS
            # Note: Hardcoded use of upHSI10G
            f"configure qos interface {bridge_id} upstream-queue 0 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
            f"configure qos interface {bridge_id} upstream-queue 3 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
            f"configure qos interface {bridge_id} upstream-queue 5 "
            f"bandwidth-profile name:{self.bandwidth_profile} bandwidth-sharing uni-sharing",
        ]
        for cmd in eth_cmds:
            self._console.sendline(cmd)
        self._console.execute_command("exit all")
        self._configure_bridge_vlan(bridge_id, c_vlans, s_vlans)

        for vlan_id in c_vlans:
            self._console.sendline(
                f"configure interface port vlan-port:{bridge_id}:"
                f'{vlan_id} admin-up user "{ont_serial.split(":")[-1]}"',
            )
        self._console.execute_command("exit all")

    def _configure_bridge_vlan(
        self,
        bridge_id: str,
        c_vlans: list[int],
        s_vlans: list[int],
    ) -> None:
        """To configure bridge vlan.

        This will add a VLAN translation rule for each customer VLAN (c_vlans)
        against a service VLAN (s_vlan).

        VLAN translations allows multiple ONUs from different customer
        or SKU to be tied against a common service VLAN.

        :param bridge_id: id of the bridge
        :type bridge_id: str
        :param c_vlans: list of customer network vlan id
        :type c_vlans: list[int]
        :param s_vlans: list of service provider network vlan id
        :type s_vlans: list[int]
        :raises ConfigurationFailure: When VLAN configuration fails
        """
        self._console.sendline(f"configure bridge port {bridge_id} max-unicast-mac 16")

        for c_vlan, s_vlan in zip(c_vlans, s_vlans):
            # l2fwder-vlan translates a single tagged c_vlan to a target s_vlan.
            # Eventually there can be alternative such a Q-in-Q configured.
            self._console.sendline(
                f"vlan-id {c_vlan} tag single-tagged "
                f"l2fwder-vlan {s_vlan} vlan-scope local",
            )
            self._console.sendline("exit")
        out = self._console.execute_command("exit all")
        if "invalid token" in out or "Error : VLAN MGT error" in out:
            msg = f"VLAN configuration failed for XGSPON: {bridge_id}"
            raise ConfigurationFailure(msg)

    def _clear_lease_states(self, mac: str) -> None:
        """Clear the lease state of CPE on the Headend Router (BNG).

        :param mac: mac address
        :type mac: str
        """
        self._connect_router()

        # TODO: MAC addresses for all the services should be provided by the
        # board as an argumesnt.
        # Keeping things the way they are for the moment.
        # hardcoding the logic for Triple Play within OLT.
        data_mac = get_nth_mac_address(mac, 0)
        voice_mac = get_nth_mac_address(data_mac, 4)
        oam_mac = get_nth_mac_address(data_mac, 5)

        try:
            for hw_addr in [data_mac, voice_mac, oam_mac]:
                self._rtr_console.execute_command(
                    f"clear service id 101 dhcp lease-state mac {hw_addr}",
                )
                self._rtr_console.execute_command(
                    f"clear service id 101 dhcp6 lease-state mac {hw_addr}",
                )
        finally:
            self._rtr_console.close()

    def get_cpe_pon_operational_state(self, gpon_serial_number: str) -> str:
        """Get CPE's XGS-PON operational state.

        :param gpon_serial_number: ONT's GPON serial number
        :type gpon_serial_number: str
        :return: CPE XGS-PON line status
        :rtype: str
        :raises ValueError: if CPE is not registered on OLT
        """
        command_output = self._console.execute_command(
            "show equipment ont status x-pon",
        )
        columns = [
            "x-pon",
            "ont",
            "serial number",
            "admin status",
            "operational state",
            "olt-rx-sig level",
            "ont-olt distance",
            "desc1",
            "desc2",
            "hostname",
        ]
        csv_data = pd.read_csv(
            StringIO(command_output),
            skiprows=6,
            skipfooter=4,
            names=columns,
            header=None,
            delim_whitespace=True,
            engine="python",
            index_col="serial number",
            dtype=None,
        )
        # convert gpon serial number to olt format
        if ":" not in gpon_serial_number and "SMBS" in gpon_serial_number:
            gpon_serial_number = f"SMBS:{gpon_serial_number[4:]}"
        if gpon_serial_number in csv_data.index:
            return str(csv_data.loc[gpon_serial_number]["operational state"])
        msg = f"PON status of CPE '{gpon_serial_number}' is not available"
        raise ValueError(msg)

    def _close(self) -> None:
        """Close SSH connection."""
        self._console.close()

    @connect_and_run
    def _parse_ont_interface_details(self, match: str) -> list[str]:
        """Parse the table details and retrive the value.

        :param match: key to fetch the value for.
        :type match: str
        :return: value of the field
        :rtype: list[str]
        """
        out = self._console.execute_command(
            f"show equipment ont interface {self.ont_id} "
            f"detail xml | match exact:{match}"
        )
        return re.findall(">(.*)<", out)

    def get_ont_hw_version(self) -> str:
        """Get the ONT hw version.

        :return: ont hw version
        :rtype: str
        """
        return self._parse_ont_interface_details(match="eqpt-ver-num").pop()

    def get_ont_hw_model(self) -> str:
        """Get ONT hw Model.

        :return: ont hw model value
        :rtype: str
        """
        return self._parse_ont_interface_details(match="equip-id").pop()

    def tshark_read_pcap(
        self,
        fname: str,
        additional_args: str | None = None,
        timeout: int = 30,
        rm_pcap: bool = False,
    ) -> str:
        """Read packet captures from an existing file.

        :param fname: name of the file in which captures are saved
        :param additional_args: additional arguments for tshark command
        :param timeout: time out for tshark command to be executed, defaults to 30
        :param rm_pcap: If True remove the packet capture file after reading it
        :raises NotImplementedError: not compatible with OLT
        """
        raise NotImplementedError


if __name__ == "__main__":
    # stubbed instantation of the device
    # this would throw a linting issue in case the device does not follow the template

    NokiaFx4OLT(config={}, cmdline_args=Namespace())
