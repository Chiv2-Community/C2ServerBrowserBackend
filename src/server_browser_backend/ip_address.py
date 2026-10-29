from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address


@dataclass(frozen=True)
class IPAddress:
    value: IPv4Address | IPv6Address
