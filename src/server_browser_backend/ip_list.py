from typing import Iterable, Iterator, Optional, Set, Sized
from os import path

from server_browser_backend.secured_resource import SecuredResource

class IpList(Sized, Iterable[str]):
    def __init__(self, key: str, ip_list_path: str):
        self.ip_list_path = ip_list_path

        # Load the file line by line in to a set
        initial_ip_list = set()
        self.secured_ip_list = SecuredResource(key, initial_ip_list)

        self.load(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.secured_ip_list.resource)

    def __len__(self) -> int:
        return len(self.secured_ip_list.resource)

    def _process_result(self, result: Optional[SecuredResource[Set[str]]]) -> bool:
        if result is None:
            return False

        self.secured_ip_list = result
        self.save()

        return True

    def load(self, key: str) -> bool:
        try:
            with open(self.ip_list_path, "r") as f:
                entries = set(map(lambda ip: ip.strip(), f.readlines()))
                result = self.secured_ip_list.with_resource(
                    key, self.secured_ip_list.resource.union(entries)
                )
                return self._process_result(result)
        except IOError:
            return True

    def save(self) -> None:
        with open(self.ip_list_path, "w") as f:
            ips = "\n".join(list(self.get_all()))
            f.write(ips)

    def add(self, key: str, ip: str) -> bool:
        return self.add_all(key, [ip])

    def add_all(self, key: str, ips: Iterable[str]) -> bool:
        result = self.secured_ip_list.with_resource(
            key, self.secured_ip_list.resource.union(ips)
        )
        return self._process_result(result)

    def remove(self, key: str, ip: str) -> bool:
        return self.remove_all(key, [ip])
    
    def remove_all(self, key: str, ips: Iterable[str]) -> bool:
        result = self.secured_ip_list.with_resource(
            key, self.secured_ip_list.resource.difference(set(ips))
        )
        return self._process_result(result)

    def clear(self, key: str) -> bool:
        result = self.secured_ip_list.with_resource(key, set())
        return self._process_result(result)

    def get_all(self) -> Set[str]:
        return self.secured_ip_list.resource
