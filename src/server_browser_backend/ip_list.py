from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Iterable, Iterator, Optional, Set, Sized
from os import path

from server_browser_backend.secured_resource import SecuredResource

class IpList(Sized, Iterable[IPv4Network | IPv6Network]):
    secured_ip_list: SecuredResource[Set[IPv4Network | IPv6Network]]

    def __init__(self, key: str, ip_list_path: str):
        self.ip_list_path = ip_list_path
        # Load the file line by line in to a set
        initial_ip_list: Set[IPv4Network | IPv6Network] = set()
        self.secured_ip_list = SecuredResource(key, initial_ip_list)

        load_result = self.load(key)

        if load_result is None:
            raise ValueError("Invalid IPs in ip list file.")
        elif not load_result:
            raise ValueError("Failed to load ip list file.")

    def __iter__(self) -> Iterator[IPv4Network | IPv6Network]:
        return iter(self.secured_ip_list.resource)

    def __len__(self) -> int:
        return len(self.secured_ip_list.resource)

    def _process_result(self, result: Optional[SecuredResource[Set[IPv4Network | IPv6Network]]]) -> bool:
        if result is None:
            return False

        self.secured_ip_list = result
        self.save()

        return True

    def load(self, key: str) -> Optional[bool]:
        try:
            if not path.exists(self.ip_list_path):
                return True
            
            with open(self.ip_list_path, "r") as f:
                entries = map(lambda ip: ip.strip(), f.readlines())
                return self.add_all(key, entries)  
        except IOError:
            return False

    def save(self) -> None:
        with open(self.ip_list_path, "w") as f:
            ips = "\n".join(list(map(lambda x: str(x), self.get_all())))
            f.write(ips)

    def add(self, key: str, ip: str) -> Optional[bool]:
        """Returns None if the ip is invalid"""
        return self.add_all(key, [ip])

    def add_all(self, key: str, str_ips: Iterable[str]) -> Optional[bool]:
        """Returns None if any of the ips are invalid"""
        try:
            ips = set(map(lambda ip: ip_network(ip), str_ips))
        except ValueError:
            return None
        
        result = self.secured_ip_list.with_resource(
            key, self.secured_ip_list.resource.union(ips)
        )
        return self._process_result(result)

    def remove(self, key: str, ip: str) -> Optional[bool]:
        """Returns None if the ip is invalid"""
        return self.remove_all(key, [ip])
    
    def remove_all(self, key: str, str_ips: Iterable[str]) -> Optional[bool]:
        """Returns None if any of the ips are invalid"""
        try:
            ips = set(map(lambda ip: ip_network(ip), str_ips))
        except ValueError:
            return None

        result = self.secured_ip_list.with_resource(
            key, self.secured_ip_list.resource.difference(set(ips))
        )
        return self._process_result(result)

    def clear(self, key: str) -> bool:
        result = self.secured_ip_list.with_resource(key, set())
        return self._process_result(result)

    def get_all(self) -> Set[IPv4Network | IPv6Network]:
        return self.secured_ip_list.resource
    
    def contains(self, ip_str: str) -> bool:
        try:
            ip = ip_network(ip_str)
        except ValueError:
            return False

        for other_ip in self.secured_ip_list.resource:
            if ip.overlaps(other_ip):
                return True
        
        return False
    
