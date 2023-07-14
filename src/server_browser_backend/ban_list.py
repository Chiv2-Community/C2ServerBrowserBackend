from typing import Iterable, Iterator, Optional, Set, Sized

from server_browser_backend.secured_resource import SecuredResource


class BanList(Sized, Iterable[str]):
    def __init__(self, key: str, ban_list_path: str):
        self.ban_list_path = ban_list_path

        initial_ban_list: Set[str] = set()
        self.secured_ban_list = SecuredResource(key, initial_ban_list)

        self.load(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.secured_ban_list.resource)

    def __len__(self) -> int:
        return len(self.secured_ban_list.resource)

    def _process_result(self, result: Optional[SecuredResource[Set[str]]]) -> bool:
        if result is None:
            return False

        self.secured_ban_list = result
        self.save()

        return True

    def load(self, key: str) -> bool:
        try:
            with open(self.ban_list_path, "r") as f:
                entries = set(map(lambda ip: ip.strip(), f.readlines()))
                result = self.secured_ban_list.with_resource(
                    key, self.secured_ban_list.resource.union(entries)
                )
                return self._process_result(result)
        except IOError:
            return True

    def save(self) -> None:
        with open(self.ban_list_path, "w") as f:
            bans = "\n".join(list(self.get_all()))
            f.write(bans)

    def add(self, key: str, ip: str) -> bool:
        result = self.secured_ban_list.with_resource(
            key, self.secured_ban_list.resource.union(set([ip]))
        )
        return self._process_result(result)

    def add_all(self, key: str, ips: Iterable[str]) -> bool:
        result = self.secured_ban_list.with_resource(
            key, self.secured_ban_list.resource.union(ips)
        )
        return self._process_result(result)

    def remove(self, key: str, ip: str) -> bool:
        result = self.secured_ban_list.with_resource(
            key, self.secured_ban_list.resource.difference(set([ip]))
        )
        return self._process_result(result)

    def clear(self, key: str) -> bool:
        result = self.secured_ban_list.with_resource(key, set())
        return self._process_result(result)

    def get_all(self) -> Set[str]:
        return self.secured_ban_list.resource
