from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass(frozen=True)
class ExternalAccount:
    eat: str
    eaid: str
    pltfm: str
    dty: str

    @staticmethod
    def from_json(json: Dict[str, Any]) -> ExternalAccount:
        return ExternalAccount(
            eat=json["eat"],
            eaid=json["eaid"],
            pltfm=json["pltfm"],
            dty=json["dty"]
        )

@dataclass(frozen=True)
class EosIdTokenPayload:
    sub: str
    pfsid: str
    iss: str
    dn: str
    nonce: str
    pfpid: str
    aud: str
    pfdid: str
    appid: str
    exp: int
    iat: int
    jti: str
    act: Optional[ExternalAccount] = None

    @staticmethod
    def from_json(json: Dict[str, Any]) -> EosIdTokenPayload:
        act_json = json.get("act")
        act = ExternalAccount.from_json(act_json) if act_json else None
        return EosIdTokenPayload(
            sub=json["sub"],
            pfsid=json["pfsid"],
            iss=json["iss"],
            dn=json["dn"],
            nonce=json["nonce"],
            pfpid=json["pfpid"],
            aud=json["aud"],
            pfdid=json["pfdid"],
            appid=json["appid"],
            exp=json["exp"],
            iat=json["iat"],
            jti=json["jti"],
            act=act
        )
