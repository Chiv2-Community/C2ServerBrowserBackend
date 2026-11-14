import os
import tempfile
from ipaddress import IPv4Network, IPv6Network
from pathlib import Path
from threading import RLock
from typing import FrozenSet, Iterable, Iterator, Optional, Set, Sized

from server_browser_backend.ip_address import canonical_network
from server_browser_backend.secured_resource import SecuredResource


class IpList(Sized, Iterable[IPv4Network | IPv6Network]):
    secured_ip_list: SecuredResource[FrozenSet[IPv4Network | IPv6Network]]

    def __init__(self, key: str, ip_list_path: str):
        self.ip_list_path = ip_list_path
        self._mutation_lock = RLock()
        initial_ip_list: FrozenSet[IPv4Network | IPv6Network] = frozenset()
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

    def _commit(
        self, result: Optional[SecuredResource[FrozenSet[IPv4Network | IPv6Network]]]
    ) -> bool:
        """Writer lock required; publish only after replacing the complete file."""
        if result is None:
            return False
        path = Path(self.ip_list_path)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}-", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write("\n".join(sorted(str(ip) for ip in result.resource)))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            self.secured_ip_list = result
            # Once replaced, memory must agree even if directory fsync fails.
            if os.name == "posix":
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return True

    def load(self, key: str) -> Optional[bool]:
        if not self.validate(key):
            return None
        with self._mutation_lock:
            try:
                if not os.path.exists(self.ip_list_path):
                    return True
                # Close before replacement, including on Windows.
                with open(self.ip_list_path, "r", encoding="utf-8") as stream:
                    lines = stream.readlines()
                return self.add_all(key, (line.strip() for line in lines))
            except IOError:
                return False

    def validate(self, key: str) -> bool:
        return self.secured_ip_list.validate(key)

    def save(self, key: str) -> None:
        if not self.validate(key):
            raise ValueError("Invalid secret key.")
        with self._mutation_lock:
            self._commit(self.secured_ip_list)

    def add(self, key: str, ip: str) -> Optional[bool]:
        """Returns None if the ip is invalid"""
        return self.add_all(key, [ip])

    def add_all(self, key: str, str_ips: Iterable[str]) -> Optional[bool]:
        """Returns None if any of the ips are invalid"""
        return self._change(key, str_ips, remove=False)

    def remove(self, key: str, ip: str) -> Optional[bool]:
        """Returns None if the ip is invalid"""
        return self.remove_all(key, [ip])

    def remove_all(self, key: str, str_ips: Iterable[str]) -> Optional[bool]:
        """Returns None if any of the ips are invalid"""
        return self._change(key, str_ips, remove=True)

    def _change(
        self, key: str, str_ips: Iterable[str], *, remove: bool
    ) -> Optional[bool]:
        # Reject invalid credentials before consuming the input iterable.
        if not self.validate(key):
            return None

        try:
            ips = {canonical_network(ip) for ip in str_ips}
        except ValueError:
            return None

        with self._mutation_lock:
            current = self.secured_ip_list.resource
            updated = current.difference(ips) if remove else current.union(ips)
            result = self.secured_ip_list.with_resource(key, updated)
            return self._commit(result)

    def clear(self, key: str) -> bool:
        with self._mutation_lock:
            result = self.secured_ip_list.with_resource(key, frozenset())
            return self._commit(result)

    def get_all(self, key: str) -> Set[IPv4Network | IPv6Network]:
        if not self.validate(key):
            raise ValueError("Invalid secret key.")

        return set(self.secured_ip_list.resource)

    def contains(self, ip_str: str) -> bool:
        try:
            ip = canonical_network(ip_str)
        except ValueError:
            return False

        for other_ip in self.secured_ip_list.resource:
            if ip.overlaps(other_ip):
                return True

        return False
