from dataclasses import dataclass
from ipaddress import (
    IPv4Address,
    IPv6Address,
    IPv4Network,
    IPv6Network,
    ip_address,
    ip_network,
)


@dataclass(frozen=True)
class IPAddress:
    value: IPv4Address | IPv6Address


def canonical_address(
    value: str | IPv4Address | IPv6Address,
) -> IPv4Address | IPv6Address:
    """Treat IPv4-mapped IPv6 addresses as their underlying IPv4 identity."""
    address = (
        value if isinstance(value, (IPv4Address, IPv6Address)) else ip_address(value)
    )
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def canonical_network(value: str) -> IPv4Network | IPv6Network:
    network = ip_network(value)
    if isinstance(network, IPv6Network) and network.prefixlen >= 96:
        mapped = network.network_address.ipv4_mapped
        if mapped is not None:
            return IPv4Network((mapped, network.prefixlen - 96))
    return network
